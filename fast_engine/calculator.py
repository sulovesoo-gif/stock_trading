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
        code = data['code']
        if code not in self.stock_status:
            self.stock_status[code] = {
                'curr_price': 0,
                'strength': 0.0,
                'accum_vol': 0,
                'ticks': deque(maxlen=200),
                'tick_speed': 0,
                'vwap': 0.0,
                'total_amt': 0,
                'rate': 0.0, # <--- 1. 등락율 저장소 추가
                'hoka': None
            }

        status = self.stock_status[code]
        
        if data.get('type') == 'HOKA':
            # 호가 업데이트 로직 동일
            status['hoka'] = {
                'ask': data['ask'], 'bid': data['bid'],
                'total_ask_v': data['total_ask_v'], 'total_bid_v': data['total_bid_v']
            }
        else:
            status['curr_price'] = data['price']
            status['prev_strength'] = status['strength']
            status['strength'] = data.get('strength', status['strength'])
            status['rate'] = data.get('rate', status['rate']) # <--- 2. 체결 데이터에서 rate 추출
            now = time.time()
            status['ticks'].append({'t': now, 'v': data['volume'], 'side': data['side']})
            # [교정] 기준가를 바탕으로 실제 VI 발동 가격 계산
            if data.get('vi_standard'):
                base = data['vi_standard']
                status['vi_up'] = int(base * 1.10)   # 상방 10%
                status['vi_down'] = int(base * 0.90) # 하방 10%
                status['vi_standard'] = base
            
        
        # 4. 초당 체결 속도(Tick Speed) 계산
        # 최근 5초 내에 발생한 틱의 개수를 계산하여 수급 폭발 확인
        recent_ticks = [t for t in status['ticks'] if now - t['t'] < self.window_seconds]
        status['tick_speed'] = len(recent_ticks) / self.window_seconds

        # [추가] 급증 알림 플래그 (초당 5건 이상일 때)
        status['is_speeding'] = status['tick_speed'] >= 5.0

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
            "prev_strength": s['prev_strength'],
            "speed": round(s['tick_speed'], 2),
            "vwap": round(s['vwap'], 0),
            "rate": s['rate'], # <--- 3. 프론트로 보낼 데이터에 포함
            "signal": "HOT" if s['tick_speed'] > 5 else "NORMAL",
            "vi_up": s['vi_up'],      # 실제 상방 발동가
            "vi_down": s['vi_down'],  # 실제 하방 발동가
            "vi_distance": round(((s['vi_up'] - s['curr_price']) / s['curr_price'] * 100), 2) if s['vi_up'] else 0,
            "hoka": s['hoka']
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
    # print(f"Summary: {summary}")