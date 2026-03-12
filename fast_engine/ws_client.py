# /projects/stock_trading/fast_engine/ws_client.py
import json
import websockets
import asyncio
import os
import sys
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from core.api_helper import kis

class KISWebsocketClient:
    def __init__(self):
        self.url = "ws://ops.koreainvestment.com:21000"
        self.approval_key = None
        self.aes_key = None
        self.aes_iv = None
        # 가이드 반영: 원본 데이터 검증을 위한 로그 파일
        self.log_file = f"ws_raw_{datetime.now().strftime('%Y%m%d')}.log"

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
                # 체결(H0STCNT0) 및 호가(H0STASP0) 구독
                await websocket.send(self._make_sub_msg(code, "H0STCNT0"))
                # print(f"📡 [WS] 구독 전송: {code} (H0STCNT0)")
                await websocket.send(self._make_sub_msg(code, "H0STASP0"))
                # print(f"📡 [WS] 구독 전송2: {code} (H0STASP0)")
                await asyncio.sleep(0.1)

            # 2. [추가] 실시간 체결통보 구독 (장외 테스트용)
            sub_msg_cni = json.dumps({
                "header": {
                    "approval_key": self.approval_key,
                    "custtype": "P", "tr_type": "1", "content-type": "utf-8"
                },
                "body": {"input": {"tr_id": "H0STCNI0", "tr_key": kis.hts_id}}
            })
            await websocket.send(sub_msg_cni)
            # print(f"🔔 실시간 체결통보 구독 요청 완료 (ID: {kis.hts_id})")

            while True:
                try:
                    raw_data = await websocket.recv()
                    # 수신 확인을 위해 원본 데이터 바로 출력
                    # print(f"📥 RAW 수신: {raw_data}")
                    
                    with open(self.log_file, "a", encoding="utf-8") as f:
                        f.write(f"{raw_data}\n")
                    
                    if raw_data[0] in ['0', '1']:
                        asyncio.create_task(self.parse_and_relay(raw_data, callback))
                    else:
                        msg_json = json.loads(raw_data)
                        tr_id = msg_json.get("header", {}).get("tr_id")
                        
                        if tr_id == "PINGPONG":
                            await websocket.pong(raw_data)
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

        if encrypt_yn == '1':
            data_body = self.decrypt_data(data_body)
            if not data_body: return

        all_fields = data_body.split('^')

        if tr_id == "H0STCNT0":
            fields_per_row = 46 
            for i in range(data_cnt):
                offset = i * fields_per_row
                if len(all_fields) < offset + fields_per_row: continue
                tick = {
                    "type": "TICK", # 타입 명시
                    "time": all_fields[offset + 1],
                    "code": all_fields[offset + 0],
                    "price": int(all_fields[offset + 2]),
                    "change": int(all_fields[offset + 4]),
                    "rate": float(all_fields[offset + 5]),
                    "volume": int(all_fields[offset + 12]),
                    "strength": float(all_fields[offset + 19]) if all_fields[offset+19] else 0.0,
                    "side": all_fields[offset + 21]
                }
                await callback(tick)

        elif tr_id == "H0STASP0":
            hoka = {
                "type": "HOKA", "code": all_fields[0], "time": all_fields[1],
                "ask": [{"p": all_fields[i], "v": all_fields[i+20]} for i in range(3, 13)],
                "bid": [{"p": all_fields[i], "v": all_fields[i+20]} for i in range(13, 23)],
                "total_ask_v": all_fields[43], "total_bid_v": all_fields[44]
            }
            await callback(hoka)
