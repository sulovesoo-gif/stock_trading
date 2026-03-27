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
                'prev_strength': 0.0,
                'accum_vol': 0,
                'accum_amt': 0,
                'ticks': deque(maxlen=200),
                'tick_speed': 0,
                'vwap': 0.0,
                'change' : 0.0,
                'rate': 0.0, # <--- 1. 등락율 저장소 추가
                'vi_up': 0,        # [수정] 초기값 설정
                'vi_down': 0,      # [수정] 초기값 설정
                'vi_standard': 0,  # [수정] 초기값 설정
                'hoka': None
            }

        status = self.stock_status[code]
        now = time.time()

        
        if data.get('type') == 'HOKA':
            # 호가 업데이트 로직 동일
            # print(f"⚠️ update_tick hoka: {data}")
            status['hoka'] = {
                'ask': data['ask'], 'bid': data['bid'],
                'ask_vol': data['ask_vol'], 'bid_vol': data['bid_vol'],
                'total_ask_vol': data['total_ask_vol'], 'total_bid_vol': data['total_bid_vol']
            }
        else:
            status['curr_price'] = data['price']
            status['prev_strength'] = status['strength']
            status['strength'] = data.get('strength', status['strength'])
            status['change'] = data.get('change', status['change']) # <--- 2. 체결 데이터에서 rate 추출
            status['rate'] = data.get('rate', status['rate']) # <--- 2. 체결 데이터에서 rate 추출
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

            # 1. 가속도: 현재 들어온 데이터와 직전 저장된 strength 비교
            status['is_hot'] = (data['strength'] - status['strength']) >= 2.0
            # 2. 대형체결: 5,000만원 기준 (기존 데이터 활용)
            status['trade_amount'] = data['price'] * data['volume']
            status['is_big_fish'] = status['trade_amount'] >= 50000000

            # 5. 실시간 VWAP 근사치 계산 (단타 지지/저항선 활용)
            status['accum_vol'] = data['accum_vol']
            status['accum_amt'] = data['accum_amt']
            if status['accum_vol'] > 0:
                status['vwap'] = status['accum_amt'] / status['accum_vol']

        return self.get_summary(code)

    def get_summary(self, code):
        # print(f"⚠️ get_summar: {code}")
        """프론트엔드로 보낼 핵심 요약 데이터 반환"""
        s = self.stock_status.get(code)
        if not s: return None

        # 호가 잔량 비율 계산 (이미지 인덱스 23번, 33번 기반 데이터 활용)
        ask = 0
        bid = 0
        ask_vol = 0
        bid_vol = 0
        total_ask_vol = 0
        total_bid_vol = 0
        hoka_ratio = 0
        is_abnormal_hoka = False
        is_fake_wall = False
        if s.get('hoka'):
            try:
                # parser_utils.py에서 넘어온 실시간 호가 잔량
                ask = int(s['hoka'].get('ask', 0))
                bid = int(s['hoka'].get('bid', 0))
                ask_vol = int(s['hoka'].get('ask_vol', 0))
                bid_vol = int(s['hoka'].get('bid_vol', 0))
                total_ask_vol = int(s['hoka'].get('total_ask_vol', 0))
                total_bid_vol = int(s['hoka'].get('total_bid_vol', 0))
                # 호가 이격도 불균형 (2.5배 법칙)
                # 매도잔량이 매수잔량보다 2.5배 이상 많을 때 (상승 가능성 포착)
                if total_bid_vol > 0 and (total_ask_vol / total_bid_vol) >= 2.5:
                    is_abnormal_hoka = True

                # 잔량 대비 체결 속도 미달 (허수벽 탐지)
                # 특정 호가 잔량 / 최근 1분(여기선 window 기준) 평균 체결량 > 10
                # 현재 tick_speed(초당 체결량)를 활용하여 계산
                avg_volume_per_sec = s.get('tick_speed', 0)
                if avg_volume_per_sec > 0:
                    # 최우선 매도호가 잔량 기준 예시
                    if (ask_vol / (avg_volume_per_sec * 60)) > 10:
                        is_fake_wall = True

                total_sum = float(total_ask_vol + total_bid_vol)
                # print(f"hoka_ratio: {total_bid_vol} : {total_bid_vol} : {float(total_ask_vol + total_bid_vol)} 수신")
                # print(f"hoka_ratio: {round((float(total_bid_vol) / total_sum) * 100, 1)} 수신")
                # if (ask_vol + bid_vol) > 0:
                if total_sum > 0:
                    # 매수잔량이 많을수록(비율이 높을수록) 하단 지지가 강bid_vol을 의미
                    hoka_ratio = round((float(total_bid_vol) / total_sum) * 100, 1)
                    # hoka_ratio = round((bid_vol / (ask_vol + bid_vol)) * 100, 1)
            except Exception as e:
                print(f"Error: {e}") # 여기서 로그가 찍히는지 확인
                pass
        
        return {
            "code": code,
            "price": s.get('curr_price', 0),
            "strength": s.get('strength', 0.0),
            "prev_strength": s.get('prev_strength', 0.0),
            "is_hot": s.get('is_hot'),
            "is_big_fish": s.get('is_big_fish'),
            "is_abnormal_hoka": s.get('is_abnormal_hoka'),
            "is_fake_wall": is_fake_wall,
            "speed": round(s.get('tick_speed', 0), 2),
            "vwap": round(s.get('vwap', 0), 0),
            "rate": s.get('rate', 0.0),
            "ask": ask,
            "bid": bid,
            "ask_vol": ask_vol,
            "bid_vol": bid_vol,
            "total_ask_vol": total_ask_vol,
            "total_bid_vol": total_bid_vol,
            "accum_vol": s.get('accum_vol', 0), 
            "accum_amt": s.get('accum_amt', 0),
            "signal": "HOT" if s.get('tick_speed', 0) > 5 else "NORMAL",
            "vi_up": s.get('vi_up', 0),
            "vi_down": s.get('vi_down', 0),
            "vi_distance": round(((s.get('vi_up', 0) - s['curr_price']) / s['curr_price'] * 100), 2) if s.get('vi_up', 0) and s['curr_price'] > 0 else 0,
            "hoka_ratio": hoka_ratio, # 매수잔량 비중 (%)
            "hoka": s.get('hoka')
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