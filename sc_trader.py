# /projects/stock_trading/sc_trader.py
import asyncio
import json
import websockets
import time
import requests
from fast_engine.ws_client import KISWebsocketClient
from fast_engine.calculator import FastScalpingCalculator
from fast_engine.parser_utils import parse_data
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
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appKey": kis.app_key, 
            "appSecret": kis.app_secret,
            "tr_id": "FHKST01010100",
            "custtype": "P"
        }
        try:
            res = requests.get(url, headers=headers, params=params)
            res_data = res.json()
            out = res_data.get('output', {})
            
            if not out:
                print(f"⚠️ [{code}] 데이터 응답 없음: {res_data.get('msg1')}")
                continue

            # 이틀간 작업하신 stock_map의 name과 REST API의 시세를 결합
            initial_stocks.append({
                "code": code, 
                "name": name, # api_helper.get_my_interests()에서 가져온 이름
                "price": int(out.get('stck_prpr', 0)),
                "change": int(out.get('prdy_vrss', 0)),
                "rate": float(out.get('prdy_ctrt', 0.0)),
                "volume": int(out.get('acml_vol', 0))
            })
            await asyncio.sleep(0.05) # API 호출 제한 준수
        except Exception as e:
            print(f"⚠️ [{code}] 초기 시세 로드 실패: {e}")
            continue
    return initial_stocks

async def main():
    # 1. 관심종목 맵 로드
    stock_map = kis.get_my_interests()
    if not stock_map:
        print("❌ 실행 중단: 종목을 가져오지 못했습니다.")
        return

    print(f"stock_map: {stock_map}")
    # 2. 초기 데이터 및 INIT 패킷 생성
    initial_data = await get_initial_stock_data(stock_map)
    init_packet = {"type": "INIT", "stocks": initial_data}
    
    print(f"initial_data: {initial_data}")
    client = KISWebsocketClient()
    calc = FastScalpingCalculator()
    queue = asyncio.Queue()
    
    # 리액트로 보낼 초기화 데이터 큐에 삽입
    await queue.put(init_packet)
    
    async def on_tick_received(data):
        """웹소켓으로부터 수신된 raw 데이터를 가공하여 큐에 삽입"""
        # 체결 데이터 처리
        print(f"DEBUG: on_tick_received 시작")
        if data.get("type") == "TICK":
            summary = calc.update_tick(data)
            if summary:
                summary['name'] = stock_map.get(summary['code'], summary['code'])
                summary['type'] = "TICK"
                await queue.put(summary)
                # 규칙 반영: 데이터 도달 확인용 필수 로그
                print(f"DEBUG: [TICK] {summary['name']} {summary['price']} ({summary['speed']} t/s)")
        
        # 호가 데이터 처리
        elif data.get("type") == "HOKA":
            data['name'] = stock_map.get(data['code'], data['code'])
            await queue.put(data)
            print(f"DEBUG: [HOKA] {data['name']} 수신") # 필요시 주석 해제

    async def sender():
        """계산된 데이터를 Broadcaster(FastAPI)로 전송"""
        uri = "ws://localhost:8080/ws/publish"

        # 한투 가이드 실제 샘플 문자열
        # raw_data = "0|H0STCNT0|001|000660^132848^93000^2^500^0.54^92646.96^92700^93300^92400^93100^93000^1^1058687^98084114400^11039^8523^-2516^89.44^547838^489995^5^0.47^40.42^090017^2^300^124625^5^-300^091329^2^600^20220830^20^N^13588^10258^77418^117103^0.15^1785780^59.28^0^^92700"
        # print(f"DEBUG: parse_data -  {parse_data(raw_data)} 수신")
        # await on_tick_received(parse_data(raw_data))

        while True:
            try:
                async with websockets.connect(uri) as ws:
                    print("✅ Broadcaster 연결 성공")

                    await ws.send(json.dumps(init_packet))
                    print(f"📢 [INIT] 전송 완료 (종목: {len(initial_data)}개)")
                    
                    while True:
                        # 큐에서 가공된 데이터(TICK/HOKA)를 가져와 전송
                        msg = await queue.get()
                        try:
                            await ws.send(json.dumps(msg))
                            queue.task_done()
                        except Exception as e:
                            print(f"❌ 데이터 전송 중 에러: {e}")
                            # 재연결을 위해 raise
                            raise e
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