# [지침 준수] 이부분이라고!! 꼭!!
# backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import json
from core.db_client import db

app = FastAPI(title="Strategy Hit Board API")

# React와의 통신 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- [데이터 모델 정의] ---
class StockSignal(BaseModel):
    stock_code: str
    stock_name: str
    last_price: int
    change_rate: float
    sig_name: str
    sig_color: str
    target_reason: Optional[str]
    point: str
    rsi: float
    r_square: float
    lrl: float
    bb_upper: float
    bb_lower: float
    ma_short: float
    foreign_net_5d: float
    institution_net_5d: float
    volume_profile: Optional[str]
    total_shares: int
    detected_time: str

# --- [핵심 로직: 시그널 판정 함수] ---
def get_signal_info(row):
    rsi, r2 = row.get('rsi', 0), row.get('r_square', 0)
    lrl, bb_up, cur_p = row.get('lrl', 0), row.get('bb_upper', 0), row.get('last_price', 0)
    f_net, i_net = row.get('foreign_net_5d', 0), row.get('institution_net_5d', 0)
    ma_short = row.get('ma_short', 0)

    # 1. 로켓: 추세폭발
    if r2 > 0.7 and cur_p > lrl and cur_p > bb_up and (f_net > 0 or i_net > 0):
        return "🚀 로켓: 추세폭발", "#FF5252"
    # 2. 바닥탈출: 역발상
    if rsi < 35 and r2 < 0.25 and cur_p > ma_short:
        return "✨ 바닥탈출: 역발상", "#4DB6AC"
    # 3. 슈퍼: 세력매집
    if cur_p > lrl and r2 >= 0.8 and (f_net > 0 and i_net > 0):
        return "💎 슈퍼: 세력매집", "#FFD700"
    
    return "🔍 일반", "#888888"

@app.get("/api/signals", response_model=List[StockSignal])
def get_all_signals():
    # 데이터 조회 (app.py 쿼리 유지)
    query = """
        SELECT i.*, 
               COALESCE(t.stock_name, s.stock_name) as stock_name, 
               t.reason as target_reason,
               COALESCE(i.detected_at, i.updated_at) as display_time
        FROM live_indicators i 
        INNER JOIN target_candidates t ON i.stock_code = t.stock_code
        LEFT JOIN stock_info s ON i.stock_code = s.stock_code
    """
    rows = db.execute_select_query(query)
    df = pd.DataFrame(rows)
    
    if df.empty: return []

    # 수치형 변환 방어 로직 (NaN 처리 포함)
    num_cols = ['rsi', 'lrl', 'r_square', 'bb_upper', 'bb_lower', 'ma_short', 'last_price', 'change_rate']
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    results = []
    for _, row in df.iterrows():
        sig_name, sig_color = get_signal_info(row)
        
        # 시간 포맷팅
        d_time = row['display_time'].strftime('%H:%M') if pd.notnull(row['display_time']) else "--:--"
        
        results.append(StockSignal(
            stock_code=row['stock_code'],
            stock_name=row['stock_name'],
            last_price=int(row['last_price']),
            change_rate=round(float(row['change_rate']), 2),
            sig_name=sig_name,
            sig_color=sig_color,
            target_reason=row['target_reason'] if row['target_reason'] else "-",
            point=f"RSI {int(row['rsi'])} / R2 {row['r_square']:.2f}",
            rsi=float(row['rsi']),
            r_square=float(row['r_square']),
            lrl=float(row['lrl']),
            bb_upper=float(row['bb_upper']),
            bb_lower=float(row['bb_lower']),
            ma_short=float(row['ma_short']),
            foreign_net_5d=float(row.get('foreign_net_5d')),
            institution_net_5d=float(row.get('institution_net_5d')),
            volume_profile=row.get('volume_profile'),
            total_shares=int(row['total_shares']),
            detected_time=d_time
        ))
    
    # 등락률 순 정렬하여 반환
    results.sort(key=lambda x: x.change_rate, reverse=True)
    return results