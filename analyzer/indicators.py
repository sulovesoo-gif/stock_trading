import pandas as pd
import numpy as np

def calculate_indicators_from_df(code, df):
    """
    전달받은 DataFrame(과거 일봉 + 현재가)을 바탕으로 
    지표(LRL, RSI, BB, R2)를 순수 계산하여 dict로 반환합니다. (DB 작업 없음)
    """
    try:
        # 최소 20일치 데이터가 있어야 볼린저 밴드 계산 가능
        if df is None or len(df) < 20:
            return None

        # 데이터 정형화
        df['close'] = df['close'].astype(float)
        
        # 1. RSI (14일)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        # 분모 0 방어
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        # 2. 볼린저 밴드 (20일, 2표준편차)
        ma20 = df['close'].rolling(window=20).mean()
        std20 = df['close'].rolling(window=20).std()
        bb_upper = ma20 + (std20 * 2)
        bb_lower = ma20 - (std20 * 2)

        # 3. LRL (14일) 및 R-Square
        period = 14
        if len(df) >= period:
            y = df['close'].tail(period).values
            x = np.arange(period)
            
            # 수평선이 아닐 때만 회귀분석 수행
            if np.std(y) != 0:
                slope, intercept = np.polyfit(x, y, 1)
                lrl_val = slope * (period - 1) + intercept
                
                # R-Square 계산
                y_pred = slope * x + intercept
                ss_res = np.sum((y - y_pred)**2)
                ss_tot = np.sum((y - np.mean(y))**2)
                r_sq = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            else:
                lrl_val, r_sq = y[-1], 0
        else:
            lrl_val, r_sq = None, 0

        # 최종 값 정리 및 결측치 처리
        def clean(val):
            return float(val) if val is not None and not np.isnan(val) and not np.isinf(val) else None

        return {
            'rsi': clean(rsi.iloc[-1]),
            'bb_upper': clean(bb_upper.iloc[-1]),
            'bb_lower': clean(bb_lower.iloc[-1]),
            'lrl': clean(lrl_val),
            'r_square': clean(r_sq),
            'ma_short': clean(ma20.iloc[-1]),
            'ma_long': clean(df['close'].rolling(window=60).mean().iloc[-1]) if len(df) >= 60 else None
        }

    except Exception as e:
        print(f"⚠️ [{code}] 지표 계산 중 물리적 오류: {e}")
        return None