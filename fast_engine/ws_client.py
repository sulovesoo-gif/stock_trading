# /projects/stock_trading/fast_engine/ws_client.py
import json
import websockets
import asyncio
import os
import sys
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

# 기존 프로젝트 구조의 core 모듈 사용
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from core.api_helper import kis

class KISWebsocketClient:
    def __init__(self):
        # 실전: ws://ops.koreainvestment.com:21000
        # 모의: ws://ops.koreainvestment.com:31000
        self.url = "ws://ops.koreainvestment.com:21000"
        self.approval_key = None
        self.aes_key = None
        self.aes_iv = None

    async def connect(self, callback):
        """웹소켓 연결 및 메인 루프"""
        # 1. 관심종목 및 승인키 준비
        interest_codes = kis.get_my_interests()
        print(f"🚀 실시간 연결 시작 (종목수: {len(interest_codes)}개)... {interest_codes}")
        if not interest_codes:
            print("⚠️ 관심종목 로드 실패. 기본 종목으로 대체합니다.")
            interest_codes = ["005930", "000660"]
        
        self.approval_key = kis.get_approval_key()
        if not self.approval_key:
            print("❌ Approval Key 발급 실패. 연결을 중단합니다.")
            return

        # 2. 웹소켓 접속 (ping_interval로 연결 유지 보조)
        async with websockets.connect(self.url, ping_interval=60) as websocket:
            print(f"🚀 실시간 연결 시작 (종목수: {len(interest_codes)}개)...")
            
            # 3. 모든 종목 구독 요청 전송
            for code in interest_codes:
                # (1) 실시간 체결가 구독
                send_trade = {
                    "header": {
                        "approval_key": self.approval_key,
                        "custtype": "P", "tr_type": "1", "content-type": "utf-8"
                    },
                    "body": {"input": {"tr_id": "H0STCNT0", "tr_key": code}}
                }
                await websocket.send(json.dumps(send_trade))
                
                # (2) 실시간 호가 구독 추가 [이 부분이 추가되어야 합니다]
                send_hoka = {
                    "header": {
                        "approval_key": self.approval_key,
                        "custtype": "P", "tr_type": "1", "content-type": "utf-8"
                    },
                    "body": {"input": {"tr_id": "H0STASP0", "tr_key": code}}
                }
                await websocket.send(json.dumps(send_hoka))
                await asyncio.sleep(0.1)

            # 4. 데이터 수신 무한 루프
            while True:
                try:
                    data = await websocket.recv()
                    
                    # [규칙 1] 실시간 체결 데이터 (0:평문, 1:암호화)
                    if data[0] in ['0', '1']:
                        await self.parse_and_relay(data, callback)

                    # [규칙 2] 시스템 메시지 (JSON)
                    else:
                        msg_json = json.loads(data)
                        tr_id = msg_json.get("header", {}).get("tr_id")
                        
                        # 핑퐁 대응 (세션 유지 핵심)
                        if tr_id == "PINGPONG":
                            await websocket.pong(data)
                            print("💓 [PINGPONG] 응답 전송 완료")
                        
                        # 구독 결과 및 키 확보
                        else:
                            body = msg_json.get("body", {})
                            if body.get("rt_cd") == '0':
                                print(f"✅ [구독성공] {msg_json['header'].get('tr_key')} - {body.get('msg1')}")
                                # 체결통보용 키 저장
                                if tr_id in ["H0STCNI0", "H0STCNI9"]:
                                    self.aes_key = body.get("output", {}).get("key")
                                    self.aes_iv = body.get("output", {}).get("iv")
                            else:
                                print(f"❌ [응답에러] {body.get('msg1')}")

                except Exception as e:
                    print(f"⚠️ 루프 에러 발생: {e}")
                    await asyncio.sleep(1)

    # [핵심] 보내주신 복호화 로직 이식
    def decrypt_data(self, cipher_text):
        try:
            cipher = AES.new(self.aes_key.encode('utf-8'), AES.MODE_CBC, self.aes_iv.encode('utf-8'))
            decrypted = bytes.decode(unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size))
            return decrypted
        except Exception as e:
            print(f"❌ 복호화 실패: {e}")
            return None
    
    async def parse_and_relay(self, raw_data, callback):
        parts = raw_data.split('|')
        encrypt_yn = parts[0]
        tr_id = parts[1]
        data_body = parts[3]

        # 암호화 데이터라면 해독 프로세스 가동
        if encrypt_yn == '1':
            data_body = self.decrypt_data(data_body)
            if not data_body: return

        fields = data_body.split('^')

        # [호가 처리: H0STASP0]
        if tr_id == "H0STASP0":
            hoka_data = {
                "type": "HOKA",
                "code": fields[0],
                "time": fields[1],
                # 매도 1~10호가 및 잔량
                "ask": [{"p": fields[i], "v": fields[i+20]} for i in range(3, 13)],
                # 매수 1~10호가 및 잔량
                "bid": [{"p": fields[i], "v": fields[i+20]} for i in range(13, 23)],
                "total_ask_v": fields[43],
                "total_bid_v": fields[44]
            }
            await callback(hoka_data)

        # [체결 처리: H0STCNT0]
        elif tr_id == "H0STCNT0":
            trade_data = {
                "type": "TRADE",
                "code": fields[0],
                "price": int(fields[2]),
                "side": "BUY" if fields[21] == '1' else "SELL", # 1:매수, 5:매도
                "volume": fields[12],
                "time": fields[1]
            }
            await callback(trade_data)


    async def parse_and_relay_old(self, raw_data, callback):
        """실시간 체결가 파싱 (stockspurchase 명세 반영)"""
        parts = raw_data.split('|')
        if len(parts) < 4: return

        encrypt_yn = parts[0]
        tr_id = parts[1]
        data_cnt = int(parts[2])
        data_body = parts[3]

        # 암호화 데이터라면 해독 프로세스 가동
        if encrypt_yn == '1':
            data_body = self.decrypt_data(data_body)
            if not data_body: return

        # 캐럿(^)으로 필드 분리
        all_fields = data_body.split('^')
        # 한투 주식체결가(H0STCNT0) 표준 필드 개수
        fields_per_row = 46 

        for i in range(data_cnt):
            offset = i * fields_per_row
            if len(all_fields) < offset + fields_per_row: continue
            
            try:
                # 올려주신 menulist 순서에 입각한 정밀 인덱싱
                tick = {
                    "code": all_fields[offset + 0],   # 유가증권단축종목코드
                    "time": all_fields[offset + 1],   # 주식체결시간
                    "price": int(all_fields[offset + 2]), # 주식현재가
                    "change": int(all_fields[offset + 4]), # 전일대비
                    "volume": int(all_fields[offset + 12]), # 체결거래량
                    "accum_vol": int(all_fields[offset + 13]), # 누적거래량
                    "strength": float(all_fields[offset + 19]), # 체결강도
                    "side": all_fields[offset + 21]   # 체결구분 (1:매수, 5:매도)
                }
                
                # 계산 엔진(callback)으로 데이터 전달
                await callback(tick)
                
            except (ValueError, IndexError) as e:
                print(f"❌ 파싱 오류: {e}")