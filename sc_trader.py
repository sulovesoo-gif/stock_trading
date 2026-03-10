# /projects/stock_trading/sc_trader.py
import asyncio
import json
import websockets
from fast_engine.ws_client import KISWebsocketClient
from fast_engine.calculator import FastScalpingCalculator

async def main():
    # 1. 엔진 초기화
    client = KISWebsocketClient()
    calc = FastScalpingCalculator()

    # 내부 큐를 활용해 Broadcaster 연결 유지
    queue = asyncio.Queue()

    async def on_tick_received(tick_data):
        summary = calc.update_tick(tick_data)
        if summary:
            await queue.put(summary)
            # 터미널에 데이터 수신 로그가 찍히는지 확인용
            print(f"DEBUG: [{summary['code']}] {summary['price']} - Speed: {summary['speed']}")

    # Broadcaster로 데이터를 계속 쏴주는 별도 태스크
    async def sender():
        uri = "ws://localhost:8080/ws/publish"
        while True:
            try:
                async with websockets.connect(uri) as ws:
                    print("✅ Broadcaster 서버에 연결되었습니다.")
                    while True:
                        msg = await queue.get()
                        await ws.send(json.dumps(msg))
            except Exception as e:
                print(f"⚠️ Broadcaster 연결 재시도 중... ({e})")
                await asyncio.sleep(2)

    # 두 가지 작업을 동시에 실행
    await asyncio.gather(
        client.connect(on_tick_received),
        sender()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 프로그램을 종료합니다.")