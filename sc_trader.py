# /projects/stock_trading/sc_trader.py
import asyncio
import json
import websockets
import time
import requests
from fast_engine.ws_client import KISWebsocketClient
from fast_engine.calculator import FastScalpingCalculator
from core.api_helper import kis

async def get_initial_stock_data(stock_map):
    """REST API로 현재가 초기 동기화"""
    initial_stocks = []
    # KISApiHelper의 access_token 확인 및 발급
    token = kis.auth()
    
    for code, name in stock_map.items():
        url = f"{kis.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
            "appKey": kis.app_key, "appSecret": kis.app_secret,
            "tr_id": "FJPST01010100"
        }
        try:
            res = requests.get(url, headers=headers, params=params)
            out = res.json().get('output', {})
            initial_stocks.append({
                "code": code, "name": name,
                "price": int(out.get('stck_prpr', 0)),
                "change": int(out.get('prdy_vrss', 0)),
                "rate": float(out.get('prdy_ctrt', 0.0)),
                "volume": int(out.get('acml_vol', 0))
            })
            time.sleep(0.05)
        except Exception as e:
            print(f"⚠️ [{code}] 초기 데이터 로드 실패: {e}")
            continue
    return initial_stocks

async def main():
    # 1. 관심종목 맵 로드
    stock_map = kis.get_my_interests()
    if not stock_map:
        print("❌ 실행 중단: 종목을 가져오지 못했습니다.")
        return

    # 2. 초기 데이터 및 INIT 패킷 생성
    initial_data = await get_initial_stock_data(stock_map)
    init_packet = {"type": "INIT", "stocks": initial_data}
    
    client = KISWebsocketClient()
    calc = FastScalpingCalculator()
    queue = asyncio.Queue()
    
    # 리액트로 보낼 초기화 데이터 큐에 삽입
    await queue.put(init_packet)
    
    async def on_tick_received(data):
        """웹소켓으로부터 수신된 raw 데이터를 가공하여 큐에 삽입"""
        # 체결 데이터 처리
        # print(f"DEBUG: on_tick_received 시작")
        if "price" in data and "type" not in data:
            summary = calc.update_tick(data)
            if summary:
                summary['name'] = stock_map.get(summary['code'], summary['code'])
                summary['type'] = "TICK"
                await queue.put(summary)
                # 규칙 반영: 데이터 도달 확인용 필수 로그
                # print(f"DEBUG: [TICK] {summary['name']} {summary['price']} ({summary['speed']} t/s)")
        
        # 호가 데이터 처리
        elif data.get("type") == "HOKA":
            data['name'] = stock_map.get(data['code'], data['code'])
            await queue.put(data)
            #print(f"DEBUG: [HOKA] {data['name']} 수신") # 필요시 주석 해제

    async def sender():
        """계산된 데이터를 Broadcaster(FastAPI)로 전송"""
        uri = "ws://localhost:8080/ws/publish"
        while True:
            try:
                async with websockets.connect(uri) as ws:
                    # print("✅ Broadcaster 연결 성공")
                    while True:
                        msg = await queue.get()
                        await ws.send(json.dumps(msg))
                        queue.task_done()
            except Exception as e:
                print(f"⚠️ Sender 연결 오류 (재시도 중...): {e}")
                await asyncio.sleep(3)

    # 3. 실행 레이아웃
    await asyncio.gather(
        client.connect(on_tick_received), # 웹소켓 수신 시작
        sender()                          # 데이터 전송 시작
    )

if __name__ == "__main__":
    asyncio.run(main())