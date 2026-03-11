# /projects/stock_trading/fast_engine/calculator.py
import time
from collections import deque

class FastScalpingCalculator:
    def __init__(self):
        # 종목별 실시간 상태 저장소 (In-Memory)
        # 구조: { '005930': { 'price': 0, 'volume_power': 0.0, 'ticks': deque(...) } }
        self.stock_status = {}
        # 틱 속도 계산을 위한 타임윈도우 (초 단위)
        self.window_seconds = 5 

    def update_tick(self, data):
        """
        ws_client로부터 수신한 체결 데이터를 메모리에 업데이트
        data: {'code', 'price', 'volume', 'strength', 'side', 'time', ...}
        """
        code = data['code']
        
        # 1. 해당 종목 데이터 초기화 (최초 수신 시)
        if code not in self.stock_status:
            self.stock_status[code] = {
                'curr_price': 0,
                'strength': 0.0,
                'accum_vol': 0,
                'ticks': deque(maxlen=200), # 최근 200개 체결 내역 저장
                'tick_speed': 0,            # 초당 체결 건수
                'vwap': 0.0,                # 당일 거래량 가중 평균가
                'total_amt': 0,             # 누적 거래대금 (계산용)
            }

        status = self.stock_status[code]
        
        # 데이터 타입에 따른 분기 처리
        if data.get('type') == 'HOKA':
            status['hoka'] = {
                'ask': data['ask'], # 매도호가 리스트
                'bid': data['bid'], # 매수호가 리스트
                'total_ask_v': data['total_ask_v'],
                'total_bid_v': data['total_bid_v']
            }
        else:
            # 기존 체결가 업데이트 로직
            status['curr_price'] = data['price']
            status['strength'] = data.get('strength', status['strength'])
            now = time.time()
            status['ticks'].append({'t': now, 'v': data['volume'], 'side': data['side']})
        
        # 2. 기본 정보 업데이트
        #status['curr_price'] = data['price']
        #status['strength'] = data['strength']
        
        # 3. 틱 데이터 저장 (시간, 수량, 구분)
        # now = time.time()
        # status['ticks'].append({
        #     't': now,
        #     'v': data['volume'],
        #     'side': data['side'] # 1:매수, 5:매도
        # })

        # 4. 초당 체결 속도(Tick Speed) 계산
        # 최근 5초 내에 발생한 틱의 개수를 계산하여 수급 폭발 확인
        recent_ticks = [t for t in status['ticks'] if now - t['t'] < self.window_seconds]
        status['tick_speed'] = len(recent_ticks) / self.window_seconds

        # 5. 실시간 VWAP 근사치 계산 (단타 지지/저항선 활용)
        # 당일 누적 거래량과 대금을 활용 (정확한 계산을 위해선 초기 누적치가 필요하나 실시간 증분으로 유지)
        status['accum_vol'] += data['volume']
        status['total_amt'] += (data['price'] * data['volume'])
        if status['accum_vol'] > 0:
            status['vwap'] = status['total_amt'] / status['accum_vol']

        return self.get_summary(code)

    def get_summary(self, code):
        """프론트엔드로 보낼 핵심 요약 데이터 반환"""
        s = self.stock_status.get(code)
        if not s: return None
        
        return {
            "code": code,
            "price": s['curr_price'],
            "strength": s['strength'],
            "speed": round(s['tick_speed'], 2),
            "vwap": round(s['vwap'], 0),
            "signal": "HOT" if s['tick_speed'] > 5 else "NORMAL", # 초당 5건 이상 체결 시 핫스팟
            "hoka": s['hoka'] # 대시보드로 호가 데이터 전달
        }

# 테스트 코드
if __name__ == "__main__":
    calc = FastScalpingCalculator()
    # 가상의 체결 데이터 입력 테스트
    test_data = {
        'code': '005930', 'price': 73000, 'volume': 100, 
        'strength': 105.2, 'side': '1', 'time': '103001'
    }
    summary = calc.update_tick(test_data)
    print(f"Summary: {summary}")