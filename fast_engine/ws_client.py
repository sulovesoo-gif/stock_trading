# /projects/stock_trading/fast_engine/ws_client.py
import json
import websockets
import asyncio
import os
import sys
import calendar
from datetime import datetime, date
from zoneinfo import ZoneInfo
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode
try:
    from fast_engine.parser_utils import parse_data
except ModuleNotFoundError:
    from parser_utils import parse_data

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from core.api_helper import kis

KST = ZoneInfo("Asia/Seoul")

class KISWebsocketClient:
    def __init__(self):
        self.url = "ws://ops.koreainvestment.com:21000"
        self.approval_key = None
        self.aes_key = None
        self.aes_iv = None
        # 가이드 반영: 원본 데이터 검증을 위한 로그 파일
        self.log_file = f"ws_raw_{datetime.now(KST).strftime('%Y%m%d')}.log"

    @staticmethod
    def get_year_code(year):
        return chr(ord('A') + (year - 2020))

    @staticmethod
    def get_second_thursday(year, month):
        cal = calendar.monthcalendar(year, month)
        # 해당 월의 목요일들 추출 (0이 아닌 날짜만)
        thursdays = [week[calendar.THURSDAY] for week in cal if week[calendar.THURSDAY] != 0]
        # 첫 번째 주에 목요일이 없으면 index 에러 방지를 위해 안전하게 처리
        return date(year, month, thursdays[1])

    def get_kospi200_future_code(self):
        today = datetime.now(KST).date()
        year, month = today.year, today.month
        quarter_months = [3, 6, 9, 12]

        target_month = next((m for m in quarter_months if month <= m), 3)
        if month > 12: year += 1

        expiry = self.get_second_thursday(year, target_month)
        
        # 만기일 당일 장 마감 이후나 만기일 이후면 다음물로 롤오버
        if today > expiry:
            idx = quarter_months.index(target_month)
            if idx == 3:
                target_month, year = 3, year + 1
            else:
                target_month = quarter_months[idx + 1]

        year_code = self.get_year_code(year)
        month_code = 'C' if target_month == 12 else str(target_month)
        
        return f"101{year_code}{month_code}000"

    async def connect(self, callback):
        stock_map = kis.get_my_interests()
        interest_codes = list(stock_map.keys())
        # 선물 코드 동적 생성
        future_code = self.get_kospi200_future_code()
        print(f"🎯 산출된 선물 근월물 코드: {future_code}")
        # 현재 시간 (KST 기준)
        now = datetime.now(KST)
        current_time = now.strftime("%H%M") # 예: "1345"
        is_regular_market = "0900" <= current_time <= "1530"
        
        if not interest_codes:
            print("⚠️ [WS] 구독할 종목 코드가 없습니다.")
            return

        while True: # 연결 실패 시 재시도를 위한 루프 추가
            try:
                self.approval_key = kis.get_approval_key()
                print(f"🚀 실시간 연결 시작 (종목수: {len(interest_codes)}개)...")
        
                async with websockets.connect(self.url, ping_interval=None) as websocket:
                    # print("✅ [WS] 서버 핸드쉐이크 완료. 1초 대기 후 구독 시작...")
                    for code in interest_codes:
                        if is_regular_market:
                            await websocket.send(self._make_sub_msg(code, "H0STCNT0"))
                            await websocket.send(self._make_sub_msg(code, "H0STASP0"))
                        else:
                            await websocket.send(self._make_sub_msg(code, "H0NXCNT0"))
                            await websocket.send(self._make_sub_msg(code, "H0NXASP0"))

                        # await websocket.send(self._make_sub_msg(code, "H0UNCNT0"))
                        # await websocket.send(self._make_sub_msg(code, "H0STOUP0"))
                        # await websocket.send(self._make_sub_msg(code, "H0UNASP0"))
                        # await websocket.send(self._make_sub_msg(code, "H0STOAA0"))
                        await asyncio.sleep(0.1)

                    # 2. 실시간 체결통보 구독 (장외 테스트용)
                    await websocket.send(self._make_sub_msg(kis.hts_id, "H0STCNI0"))
                    # 3. 코스피200 선물(10100) 구독 전송
                    # print(f"🔔 실시간 체결통보 구독 요청 완료 (ID: {kis.hts_id})")
                    await websocket.send(self._make_sub_msg(future_code, "H0IFCNT0"))
                    # await websocket.send(self._make_sub_msg("101S12", "H0IFCNT0"))
                    
                    # print(f"🚀 [WS] 선물 구독 완료: {"10100"}")

                    while True:
                        raw_data = await websocket.recv()
                        # 수신 확인을 위해 원본 데이터 바로 출력
                        # print(f"📥 RAW 수신: {raw_data}")

                        # [추가] 원본 데이터 로그 기록 로직
                        with open(self.log_file, "a", encoding="utf-8") as f:
                            f.write(f"[{datetime.now(KST)}] {raw_data}\n")
                        
                        # [추가] 파일이 어디에 써지고 있는지 딱 한 번만 출력 (확인용)
                        # if not hasattr(self, '_path_printed'):
                        #     print(f"📍 현재 로그 기록 중: {os.path.abspath(self.log_file)}")
                        #     self._path_printed = True
                        
                        if "H0IFCNT0" in raw_data:
                            print(f"💓 {raw_data}")

                        if raw_data[0] in ['0', '1']:
                            # if "H0IFCNT0" in raw_data:
                            #     print(f"🔥 선물 실시간 데이터 수신: {raw_data[:50]}...") # 너무 길면 잘라서 출력
                            asyncio.create_task(self.parse_and_relay(raw_data, callback))
                        else:
                            jsonObject = json.loads(raw_data)
                            tr_id = jsonObject["header"]["tr_id"]
                            
                            if tr_id == "PINGPONG":
                                await websocket.pong(raw_data)
                                # print("💓 [PINGPONG] 응답 전송 완료")
                            else:
                                rt_cd = jsonObject["body"]["rt_cd"]
                                if rt_cd == '0':
                                    # print(f"✅ [구독성공] {tr_id} - {jsonObject["body"]["msg1"]}")
                                    if tr_id == "H0STCNI0" or tr_id == "H0STCNI9":
                                        self.aes_key = jsonObject["body"]["output"]["key"]
                                        self.aes_iv = jsonObject["body"]["output"]["iv"]
            except Exception as e:
                err_msg = f"⚠️ WS 루프 에러: {e}"
                print(err_msg)
                self.send_telegram(err_msg)
                await asyncio.sleep(5)

    def _make_sub_msg(self, code, tr_id):
        return json.dumps({
            "header": {"approval_key": self.approval_key, "custtype": "P", "tr_type": "1", "content-type": "utf-8"},
            "body": {"input": {"tr_id": tr_id, "tr_key": code}}
        })

    def decrypt_data(self, cipher_text):
        try:
            cipher = AES.new(self.aes_key.encode('utf-8'), AES.MODE_CBC, self.aes_iv.encode('utf-8'))
            return bytes.decode(unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size))
        except: return None
    
    async def parse_and_relay(self, raw_data, callback):
        parts = raw_data.split('|')
        if len(parts) < 4: return

        encrypt_yn, tr_id, data_cnt, data_body = parts[0], parts[1], int(parts[2]), parts[3]

        # 암호화 여부 확인 ('1'이면 암호화됨)
        if encrypt_yn == '1':
            data_body = self.decrypt_data(data_body)
            if not data_body: return

        # [핵심 수정]: 하드코딩된 인덱스 로직을 모두 지우고 reassembled_data를 생성
        reassembled_data = f"0|{tr_id}|{data_cnt}|{data_body}"
        # 공용 파서 호출 (사용자님이 수정한 18번 인덱스 로직이 여기서 적용됨)
        payload = parse_data(reassembled_data)

        if payload:
            await callback(payload)

    def send_telegram(message: str) -> bool:
        TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "8278913301:AAGgous2CAcYKAf7L_hvJOEmXOErNfNPUTw")
        TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8389619558")

        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            print("⚠️ TELEGRAM_TOKEN/CHAT_ID 비어있음")
            return False

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "disable_web_page_preview": True,
        }
        try:
            r = requests.post(url, data=data, timeout=5)
            return r.status_code == 200
        except Exception:
            return False
