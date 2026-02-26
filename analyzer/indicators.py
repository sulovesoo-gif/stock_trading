import pandas as pd
import numpy as np
from core.db_client import db

def calculate_and_update_indicators():
    print("📈 기초 지표 계산 및 live_indicators 업데이트 시작...")
    
    # 1. 대상 종목 리스트 확보
    targets = db.execute_query("SELECT stock_code FROM target_candidates")
    
    success_cnt = 0
    for row in targets:
        code = row['stock_code']
        
        # 2. 적재된 일봉 데이터 로드 (지표 계산을 위해 충분히 60일치)
        sql = """
            SELECT close FROM market_ohlcv 
            WHERE stock_code = %s 
            ORDER BY datetime DESC LIMIT 60
        """
        rows = db.execute_query(sql, (code,))
        if not rows or len(rows) < 30: # LRL(14) + BB(20) 안정성을 위해 최소 30개
            continue
            
        df = pd.DataFrame(rows)
        # 데이터 역순 정렬 (과거 -> 현재 순서로 계산하기 위함)
        df = df.iloc[::-1].reset_index(drop=True)
        df['close'] = df['close'].astype(float)

        # 3. 지표 계산
        # 볼린저 밴드 (20일, 2표준편차)
        ma20 = df['close'].rolling(window=20).mean()
        std20 = df['close'].rolling(window=20).std()
        bb_upper = ma20 + (std20 * 2)
        bb_lower = ma20 - (std20 * 2)
        
        # RSI (14일)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        # 분모 0 방지
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        # 이동평균선 (5일, 20일)
        ma_short = df['close'].rolling(window=5).mean()
        ma_long = ma20

        # --- [효율적 LRL/R-Square 계산 로직 추가] ---
        # 최근 14일 데이터 추출
        y = df['close'].tail(14).values
        x = np.arange(len(y))
        
        # Numpy polyfit을 이용한 고속 선형회귀 (1차식 y = ax + b)
        slope, intercept = np.polyfit(x, y, 1)
        res_lrl = slope * (len(y) - 1) + intercept # 오늘 시점의 예측값
        
        # R-Square 계산 (결정계수)
        y_pred = slope * x + intercept
        r_square = 1 - (np.sum((y - y_pred)**2) / np.sum((y - np.mean(y))**2))
        res_rsq = r_square
        # ------------------------------------------

        # 4. 최신 지표 값 추출 (마지막 행)
        res_rsi = rsi.iloc[-1]
        res_bb_u = bb_upper.iloc[-1]
        res_bb_l = bb_lower.iloc[-1]
        res_ma_s = ma_short.iloc[-1]
        res_ma_l = ma_long.iloc[-1]

        # 5. live_indicators 업데이트
        # LRL, R-Square 수치 반영 (사용자 지정 live_indicators 스키마 기준)
        update_sql = """
            UPDATE live_indicators 
            SET datetime = NOW(),
                lrl = %s, rsi = %s, bb_upper = %s, bb_lower = %s, 
                r_square = %s, ma_short = %s, ma_long = %s
            WHERE stock_code = %s
        """
        db.execute_query(update_sql, (
            float(res_lrl) if not np.isnan(res_lrl) else None,
            float(res_rsi) if not np.isnan(res_rsi) else None,
            float(res_bb_u) if not np.isnan(res_bb_u) else None,
            float(res_bb_l) if not np.isnan(res_bb_l) else None,
            float(res_rsq) if not np.isnan(res_rsq) else None,
            float(res_ma_s) if not np.isnan(res_ma_s) else None,
            float(res_ma_l) if not np.isnan(res_ma_l) else None,
            code
        ))
        success_cnt += 1

    print(f"✨ 총 {success_cnt}개 종목의 지표 업데이트 완료!")

if __name__ == "__main__":
    calculate_and_update_indicators()