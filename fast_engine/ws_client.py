# /projects/stock_trading/fast_engine/ws_client.py
import json
import websockets
import asyncio
import os
import sys

# 기존 프로젝트 구조의 core 모듈 사용
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from core.api_helper import kis

class KISWebsocketClient:
    def __init__(self):
        # 실전: ws://ops.koreainvestment.com:21000
        # 모의: ws://ops.koreainvestment.com:31000
        self.url = "ws://ops.koreainvestment.com:21000"
        self.approval_key = None

    async def connect(self, callback):
        """관심종목 로드 후 웹소켓 연결"""
        # 1. 한투 API를 통해 사용자님의 관심종목 코드를 가져옴
        interest_codes = kis.get_my_interests()
        if not interest_codes:
            print("⚠️ 관심종목이 없거나 가져오지 못했습니다. 테스트용으로 삼성전자(005930)를 넣습니다.")
            interest_codes = ["005930", "000660"]
        
        self.approval_key = kis.get_approval_key()
        
        async with websockets.connect(self.url) as websocket:
            print(f"🚀 관심종목 {len(interest_codes)}개 실시간 연결 시작...")
            
            for code in interest_codes:
                send_data = {
                    "header": {
                        "approval_key": self.approval_key,
                        "custtype": "P",
                        "tr_type": "1",
                        "content-type": "utf-8"
                    },
                    "body": {
                        "input": {
                            "tr_id": "H0STCNT0", # 실시간 체결가
                            "tr_key": code
                        }
                    }
                }
                await websocket.send(json.dumps(send_data))
                await asyncio.sleep(0.1) # 전송 과부하 방지

            while True:
                raw_msg = await websocket.recv()
                if raw_msg[0] in ['0', '1']: # 실시간 체결 데이터
                    await self.parse_and_relay(raw_msg, callback)

    async def parse_and_relay(self, raw_data, callback):
        """가변 데이터 건수(Paging) 처리 로직"""
        parts = raw_data.split('|')
        data_cnt = int(parts[2])
        content = parts[3].split('^')
        
        for i in range(data_cnt):
            offset = i * 46
            if len(content) < offset + 22: continue
            
            tick = {
                "code": content[offset],
                "price": int(content[offset+2]),
                "volume": int(content[offset+12]),
                "strength": float(content[offset+18]),
                "side": content[offset+21], # 1:매수, 5:매도
                "time": content[offset+1]
            }
            await callback(tick)

    