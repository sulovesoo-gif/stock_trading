import time
import pandas as pd
import requests
from datetime import datetime
from core.db_client import db
from core.api_helper import kis
from analyzer.indicators import calculate_indicators_from_df

# [메모리 저장소] 불필요한 DB/API 호출을 막기 위함
ohlcv_cache = {}
last_price_cache = {}

def is_market_open():
    """장 운영 시간 및 API 점검 시간 확인"""
    now = datetime.now()
    if now.weekday() >= 5: return False
    
    # 한투 점검 시간 방어 (23:30 ~ 00:30)
    curr_h_m = now.strftime('%H%M')
    if '2330' <= curr_h_m or curr_h_m <= '0130': 
        return False

    start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return start_time <= now <= end_time

def check_strategy_and_save(code, name, price, ind):
    """
    계산된 지표를 바탕으로 전략을 판단하고, 
    live_indicators 업데이트 및 signal_history에 기록합니다.
    """
    if not ind: return

    # 1. 지표 값 추출
    rsi = ind.get('rsi')
    lrl = ind.get('lrl')
    r_sq = ind.get('r_square')
    bb_u = ind.get('bb_upper')
    bb_l = ind.get('bb_lower')
    ma_s = ind.get('ma_short')
    ma_l = ind.get('ma_long')

    # 2. 실시간 지표 테이블(live_indicators) 업데이트
    update_sql = """
        UPDATE live_indicators SET 
            last_price=%s, rsi=%s, lrl=%s, r_square=%s, 
            bb_upper=%s, bb_lower=%s, ma_short=%s, ma_long=%s, 
            updated_at=NOW()
        WHERE stock_code=%s
    """
    db.execute_query(update_sql, (price, rsi, lrl, r_sq, bb_u, bb_l, ma_s, ma_l, code))

    # 3. 전략 시그널 판단 (BUY/SELL)
    signal_type = None
    reason = ""

    # [전략 A] 바닥권 과매도 회복 (🎯)
    if rsi and r_sq and lrl:
        if (rsi < 38) and (0.4 < r_sq < 0.8) and (price >= float(lrl) * 0.98):
            signal_type = 'BUY'
            reason = f"바닥탈출(🎯): RSI:{rsi:.1f}, R2:{r_sq:.2f}"

    # [전략 B] 주도주 상단 돌파 (🔥)
    if not signal_type and bb_u:
        if price > float(bb_u):
            signal_type = 'BUY'
            reason = f"주도주돌파(🔥): BB상단 돌파"

    # [매도 전략] 추세 붕괴 시 (📉)
    if not signal_type and lrl:
        if price < float(lrl) * 0.96:
            signal_type = 'SELL'
            reason = f"추세붕괴(📉): LRL 하향 이탈"

    # 4. 시그널 발생 시 DB 저장 및 로그 출력
    if signal_type:
        history_sql = """
            INSERT INTO signal_history (stock_code, signal_type, signal_price, reason, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """
        db.execute_query(history_sql, (code, signal_type, price, reason))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔔 {signal_type} 발생: {name}({code}) {price}원 - {reason}")

def process_batch(code_list, code_to_name):
    """50개 묶음단위로 시세 조회 후 지표 계산 및 전략 판단"""
    # 1. API 벌크 조회 (api_helper.py에 추가한 함수 호출)
    prices_data = kis.get_multi_prices_30(code_list)
    # [방어 코드 추가] 데이터가 없거나 형식이 잘못된 경우 즉시 종료
    if not prices_data or not isinstance(prices_data, list):
        return

    for p in prices_data:
        try:
            # API 점검 시 데이터 필드가 누락될 수 있으므로 get() 사용 권장
            code = p.get('stck_shrn_iscd')
            if not code: continue
            
            curr_price_str = p.get('stck_prpr')
            if not curr_price_str: continue
            
            curr_price = int(curr_price_str)
            name = code_to_name.get(code, "Unknown")
            
            # [최적화] 가격 변동 없으면 무거운 계산 스킵
            if last_price_cache.get(code) == curr_price:
                continue
            last_price_cache[code] = curr_price

            # [데이터 로드] 메모리에 과거 데이터가 없으면 DB에서 60일치 로드
            if code not in ohlcv_cache:
                sql = "SELECT close FROM market_ohlcv WHERE stock_code=%s ORDER BY datetime DESC LIMIT 60"
                rows = db.execute_query(sql, (code,))
                if rows:
                    ohlcv_cache[code] = pd.DataFrame(rows).iloc[::-1].reset_index(drop=True)
                else:
                    continue

            # 2. 지표 계산 (Pandas 연산)
            df_hist = ohlcv_cache[code].copy()
            new_row = pd.DataFrame({'close': [curr_price]})
            df_combined = pd.concat([df_hist, new_row], ignore_index=True)
            
            # 순수 지표 계산 함수 호출
            ind_results = calculate_indicators_from_df(code, df_combined)

            # 3. 전략 판단 및 저장
            check_strategy_and_save(code, name, curr_price, ind_results)

        except (KeyError, ValueError, TypeError) as e:
            # 개별 종목 데이터 파싱 에러 시 해당 종목만 스킵
            continue

def collect_realtime_data():
    print("🚀 [터보 엔진] 가동 시작 (벌크 최적화 + 무생략 풀버전)")
    
    # 프로그램 시작 시 1회 인증
    try:
        kis.auth()
    except Exception as e:
        print(f"⚠️ 초기 인증 대기: {e}")

    while True:
        try:
            # 1. 장 상태 확인
            if not is_market_open():
                print(f"💤 장외 대기 중... ({datetime.now().strftime('%H:%M:%S')})")
                time.sleep(60)
                continue

            # 2. [사용자 제안 SQL] 50개씩 종목코드를 묶어서 리스트화
            batch_sql = """
                SELECT GROUP_CONCAT(stock_code) as batch_codes
                FROM (
                    SELECT stock_code, 
                           CEIL((ROW_NUMBER() OVER (ORDER BY stock_code)) / 50) as g
                    FROM target_candidates
                ) t GROUP BY g
            """
            batches = db.execute_query(batch_sql)
            
            # 종목명 매핑 정보 (로그 출력용)
            name_rows = db.execute_query("SELECT stock_code, stock_name FROM stock_info")
            code_to_name = {r['stock_code']: r['stock_name'] for r in name_rows}
            
            start_time = time.time()
            
            # 3. 각 50개 묶음(Batch) 처리
            for b in batches:
                code_list = b['batch_codes'].split(',')
                process_batch(code_list, code_to_name)
                time.sleep(0.05) # API 과부하 방지용 미세 대기

            duration = time.time() - start_time
            print(f"⏱️ 사이클 완료: {len(code_to_name)}종목 / 소요시간: {duration:.1f}초")

        except Exception as e:
            print(f"❌ 루프 에러: {e}")
            time.sleep(10)

if __name__ == "__main__":
    collect_realtime_data()