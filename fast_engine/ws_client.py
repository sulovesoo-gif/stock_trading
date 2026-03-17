# /projects/stock_trading/fast_engine/ws_client.py
import json
import websockets
import asyncio
import os
import sys
from datetime import datetime
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

    async def connect(self, callback):
        stock_map = kis.get_my_interests()
        interest_codes = list(stock_map.keys())
        
        if not interest_codes:
            print("⚠️ [WS] 구독할 종목 코드가 없습니다.")
            return

        self.approval_key = kis.get_approval_key()
        print(f"🚀 실시간 연결 시작 (종목수: {len(interest_codes)}개)...")
        
        async with websockets.connect(self.url, ping_interval=60) as websocket:
            # print("✅ [WS] 서버 핸드쉐이크 완료. 1초 대기 후 구독 시작...")
            for code in interest_codes:
                # 체결통합(H0UNASP0), 체결KRX(H0STCNT0) 및 호가통합(H0UNASP0),  호가KRX(H0STASP0) 구독
                # await websocket.send(self._make_sub_msg(code, "H0STCNT0"))
                await websocket.send(self._make_sub_msg(code, "H0UNCNT0"))
                # await websocket.send(self._make_sub_msg(code, "H0STASP0"))
                await websocket.send(self._make_sub_msg(code, "H0UNASP0"))
                
                # print(f"📡 [WS] 구독 전송2: {code} (H0STASP0)")
                await asyncio.sleep(0.1)

            # 2. 실시간 체결통보 구독 (장외 테스트용)
            await websocket.send(self._make_sub_msg(kis.hts_id, "H0STCNI0"))
            # 3. 코스피200 선물(10100) 구독 전송
            # print(f"🔔 실시간 체결통보 구독 요청 완료 (ID: {kis.hts_id})")
            await websocket.send(self._make_sub_msg("10100", "H0IFCNT0"))
            # print(f"🚀 [WS] 선물 구독 완료: {"10100"}")

            while True:
                try:
                    raw_data = await websocket.recv()
                    # 수신 확인을 위해 원본 데이터 바로 출력
                    # print(f"📥 RAW 수신: {raw_data}")

                    # [추가] 원본 데이터 로그 기록 로직
                    with open(self.log_file, "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.now(KST)}] {raw_data}\n")
                    
                    # [추가] 파일이 어디에 써지고 있는지 딱 한 번만 출력 (확인용)
                    if not hasattr(self, '_path_printed'):
                        print(f"📍 현재 로그 기록 중: {os.path.abspath(self.log_file)}")
                        self._path_printed = True
                    
                    # print(f"💓 {raw_data}")

                    if raw_data[0] in ['0', '1']:
                        asyncio.create_task(self.parse_and_relay(raw_data, callback))
                    else:
                        msg_json = json.loads(raw_data)
                        tr_id = msg_json.get("header", {}).get("tr_id")
                        
                        if tr_id == "PINGPONG":
                            await websocket.pong(raw_data)
                            # print("💓 [PINGPONG] 응답 전송 완료")
                        else:
                            body = msg_json.get("body", {})
                            if body.get("rt_cd") == '0':
                                print(f"✅ [구독성공] {msg_json['header'].get('tr_key')} - {body.get('msg1')}")
                                if tr_id in ["H0STCNI0", "H0STCNI9"]:
                                    self.aes_key = body.get("output", {}).get("key")
                                    self.aes_iv = body.get("output", {}).get("iv")
                except Exception as e:
                    print(f"⚠️ WS 루프 에러: {e}")
                    await asyncio.sleep(1)

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