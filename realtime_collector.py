import time
import json
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from core.db_client import db
from core.api_helper import kis
from analyzer.indicators import calculate_indicators_from_df

KST = ZoneInfo("Asia/Seoul")

# [메모리 저장소] 불필요한 DB/API 호출을 막기 위함
ohlcv_cache = {}
last_price_cache = {}

def is_market_open():
    """장 운영 시간 및 API 점검 시간 확인"""
    now = datetime.now(KST)
    if now.weekday() >= 5: return False
    
    # 한투 점검 시간 방어 (23:30 ~ 00:30)
    curr_h_m = now.strftime('%H%M')
    if '2330' <= curr_h_m or curr_h_m <= '0130': 
        return False

    start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return start_time <= now <= end_time

def check_strategy_and_save(code, name, price, change_rate, ind, investor=None, profile=None):
    """
    계산된 지표를 바탕으로 전략을 판단하고, 
    live_indicators 업데이트 및 signal_history에 기록합니다.
    """

    # 1. 수급 및 매물대 데이터 가공 (ind와 상관없이 먼저 수행)
    f_net = investor.get('foreign_net_5d') if investor else 0
    i_net = investor.get('institution_net_5d') if investor else 0
    v_profile = json.dumps(profile) if profile else None

    # [DB_TRACE]
    print(f"📝 [DB_TRACE] {name}({code}) 업데이트 시도 -> 등락: {change_rate}, 수급(F:{f_net})")

    # [데이터 추가 A] market_ohlcv 당일 시세 업데이트 (대시보드 히스토리용)
    # 오늘 데이터가 없으면 INSERT, 있으면 최신가로 UPDATE (고가/저가 갱신 포함)
    insert_sql = """
        INSERT INTO market_ohlcv (stock_code, datetime, open, high, low, close, volume)
        VALUES (%s, CURDATE(), %s, %s, %s, %s, 0)
        ON DUPLICATE KEY UPDATE 
            close = VALUES(close),
            high = IF(VALUES(close) > high, VALUES(close), high),
            low = IF(VALUES(close) < low, VALUES(close), low),
            datetime = NOW() -- [수정] 마지막 업데이트 시간 기록
    """
    db.execute_query(insert_sql, (code, price, price, price, price))

    # 3. live_indicators 실시간 지표/수급 업데이트
    # rsi, lrl 등은 ind가 있을 때만 업데이트하고, 없으면 기존값 유지(COALESCE)
    rsi = ind.get('rsi') if ind else None
    lrl = ind.get('lrl') if ind else None
    lrs = ind.get('lrs') if ind else None
    r_sq = ind.get('r_square') if ind else None
    bb_u = ind.get('bb_upper') if ind else None
    bb_l = ind.get('bb_lower') if ind else None
    ma_s = ind.get('ma_short') if ind else None
    ma_l = ind.get('ma_long') if ind else None

    # ★ 지표 계산 여부를 판단하는 핵심 변수
    indicator_time = datetime.now(timezone.utc) if ind else None

    update_sql = """
        UPDATE live_indicators SET 
            last_price=%s, 
            change_rate=%s,
            rsi=%s, lrl=%s, lrs=%s, r_square=%s, 
            bb_upper=%s, bb_lower=%s, ma_short=%s, ma_long=%s,
            foreign_net_5d=%s, institution_net_5d=%s, volume_profile=%s,
            updated_at=NOW(),
            last_indicator_at=%s,
            detected_at = IF(DATE(detected_at) != DATE(NOW()) OR detected_at IS NULL, NOW(), detected_at)
        WHERE stock_code=%s
    """
    db.execute_query(update_sql, (price, change_rate, rsi, lrl, lrs, r_sq, bb_u, bb_l, ma_s, ma_l, f_net, i_net, v_profile, indicator_time, code))
    
    # 4. 전략 시그널 판단 (지표가 없으면 여기서 중단 - 의도된 로직)
    if not ind: return

    # 5. 전략 시그널 판단 (BUY/SELL)
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

    # 📦 [이부분!!] 전략 C: 조용한 세력 매집 포착 (사용자 요청사항)
    # 등락률이 전일비 -1.5% ~ +1.5% 사이로 횡보 중인데 에너지가 응축될 때
    if -1.5 <= change_rate <= 1.5 and 48 < rsi < 55 and r_sq < 0.25:
        signal_type = 'BUY'
        reason = f"📦세력매집: 지표응축(RSI:{rsi:.1f}, R2:{r_sq:.2f})"

    # ✨ [이부분!!] 전략 D: 방패 구간 추세 반전 (사용자 요청사항)
    # 과매도 구간을 지나며 하락 추세(R2)가 꺾이고 머리를 들 때
    elif rsi < 35 and r_sq < 0.3 and change_rate > -1.0:
        signal_type = 'BUY'
        reason = f"✨추세반전: 하락멈춤 포착"

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
        print(f"[{datetime.now(KST).strftime('%H:%M:%S')}] 🔔 {signal_type} 발생: {name}({code}) {price}원 - {reason}")

def process_batch(code_list, code_to_name):
    """30개 종목에 대한 API 수집 및 지표 연산"""
    success_count = 0
    raw_res = kis.get_multi_prices_30(code_list)
    
    if not raw_res: return 0
    prices_data = raw_res if isinstance(raw_res, list) else raw_res.get('output', [])
    if not prices_data: return 0

    for p in prices_data:
        try:
            code = p.get('inter_shrn_iscd')
            curr_price_str = p.get('inter2_prpr')
            change_rate = float(p.get('prdy_ctrt', 0))
            if not code or not curr_price_str: continue
            
            # print(f"📡 등락률 체크: {change_rate}")
            
            curr_price = int(curr_price_str)
            name = code_to_name.get(code, "Unknown")
            
            # [최적화] 이미 메인 루프에서 동기화된 ohlcv_cache 사용 (DB 조회 0번)
            if code not in ohlcv_cache: continue

            # 🚀 [이부분!!] last_p가 정의되지 않았던 문제를 last_price_cache.get(code)로 해결
            # 1. 캐시에서 이전 가격 가져오기
            last_p = last_price_cache.get(code)
            
            # 2. 지표 결과 변수 초기화 (이건 유지하되)
            ind_results = None 

            print(f"📡 last_p: {last_p}")
            print(f"📡 curr_price: {curr_price}")
            print(f"📡 last_p != curr_price: {last_p != curr_price}")
            # 3. 가격이 변했거나, 아예 처음 수집하는 경우만 계산 시도
            if last_p != curr_price:
                df_hist = ohlcv_cache.get(code)
                if df_hist is not None:
                    # 현재가를 포함한 임시 DF 생성
                    new_row = pd.DataFrame({'close': [curr_price]})
                    df_combined = pd.concat([df_hist, new_row], ignore_index=True)
                    
                    # 지표 계산
                    ind_results = calculate_indicators_from_df(code, df_combined)
                    
                    # ★ 지표 계산이 성공했을 때만 가격 캐시를 업데이트 (매우 중요)
                    if ind_results:
                        last_price_cache[code] = curr_price
                        print(f"✅ {name} 지표 계산 성공 및 캐시 갱신")
                    else:
                        print(f"⚠️ {name} 지표 계산 실패 (데이터 부족 등)")
                else:
                    print(f"❌ {name} ohlcv_cache 데이터 없음")
            else:
                print(f"😴 {name} 가격 변동 없음 ({curr_price}) - 계산 건너뜀")


            # 가격이 변했거나 처음 수집하는 경우에만 지표 연산을 수행합니다.
            # if last_p != curr_price:
            #     last_price_cache[code] = curr_price
            #     df_hist = ohlcv_cache[code].copy()
            #     new_row = pd.DataFrame({'close': [curr_price]})
            #     df_combined = pd.concat([df_hist, new_row], ignore_index=True)
            #     # 1. 지표 계산
            #     ind_results = calculate_indicators_from_df(code, df_combined)

            # 장외시간 가격변동이 없을때 테스트용 
            # ind_results = calculate_indicators_from_df(code, df_combined)
            print(f"📡 수급 체크")
            # 2. [추가] 수급 및 매물대 데이터 가져오기 (사용자님 제공 API)
            investor_data = kis.get_investor_trade_data(code)
            volume_data = kis.get_price_volume_profile(code)
            # 🚀 [이부분!!] 가격 변동과 상관없이 이 함수를 호출해야 DB의 등락률이 네이버와 실시간 동기화됩니다.
            # check_strategy_and_save(code, name, curr_price, change_rate, ind_results)
            check_strategy_and_save(code, name, curr_price, change_rate, ind_results, investor_data, volume_data)
            print(f"📡 매물대 체크")

            success_count += 1
        except Exception:
            continue
    
    print(f"📡 배치 처리 결과: {success_count}/{len(code_list)} 성공")
    return success_count

def collect_realtime_data():
    print("🚀 [터보 엔진] 가동 시작 (DB 일괄 조회 + API 벌크 최적화)")
    kis.auth()

    while True:
        try:
            if not is_market_open():
                print(f"💤 장외 대기 중... ({datetime.now(KST).strftime('%H:%M:%S')})")
                ime.sleep(60); continue

            start_time = time.time()

            # --- [1단계] DB에서 전체 타겟의 과거 90일치 시세 일괄 동기화 ---
            # 휴일 포함 90일을 가져와서 파이썬에서 60개로 커트 (가장 안전한 방식)
            ohlcv_sql = """
                SELECT stock_code, close 
                FROM market_ohlcv 
                WHERE datetime >= DATE_SUB(NOW(), INTERVAL 90 DAY)
                ORDER BY stock_code, datetime DESC
            """
            all_rows = db.execute_query(ohlcv_sql)
            
            temp_map = {}
            for row in all_rows:
                c = row['stock_code']
                if c not in temp_map: temp_map[c] = []
                if len(temp_map[c]) < 60: # 딱 60개만 확보
                    temp_map[c].append(row['close'])
            
            for c, prices in temp_map.items():
                ohlcv_cache[c] = pd.DataFrame({'close': prices[::-1]}).reset_index(drop=True)

            # --- [2단계] 수집 대상 배치(30개 단위) 및 이름 매핑 구성 ---
            batch_sql = """
                SELECT GROUP_CONCAT(stock_code) as batch_codes
                FROM (
                    SELECT stock_code, 
                           CEIL((ROW_NUMBER() OVER (ORDER BY stock_code)) / 30) as g
                    FROM target_candidates
                ) t GROUP BY g
            """
            batches = db.execute_query(batch_sql)
            
            name_rows = db.execute_query("SELECT stock_code, stock_name FROM stock_info")
            code_to_name = {r['stock_code']: r['stock_name'] for r in name_rows}

            # --- [3단계] 배치 처리 실행 ---
            total_target_count = 0
            for b in batches:
                code_list = b['batch_codes'].split(',')
                total_target_count += len(code_list)
                process_batch(code_list, code_to_name)
                time.sleep(0.05) 

            duration = time.time() - start_time
            print(f"⏱️ 사이클 완료: {total_target_count}종목 / 소요시간: {duration:.1f}초")

        except Exception as e:
            print(f"❌ 루프 에러: {e}")
            time.sleep(10)

if __name__ == "__main__":
    collect_realtime_data()