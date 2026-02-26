import sys
import os
import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 경로 설정 및 DB 연결
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.db_client import db

# 2. 페이지 설정
st.set_page_config(page_title="STOCK MONITOR", layout="wide")

# CSS: 디자인 유지 및 그래프 이탈 방지
st.markdown("""
<style>
    .mint-header { background-color: #4DB6AC; color: white; padding: 5px 10px; border-radius: 5px 5px 0 0; font-weight: bold; display: flex; justify-content: space-between; }
    .gauge-container { background-color: #eee; height: 8px; border-radius: 4px; position: relative; margin: 8px 0 15px 0; overflow: hidden; width: 100%; }
    .gauge-center-line { position: absolute; left: 50%; width: 2px; height: 12px; background-color: #333; top: -2px; z-index: 10; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #4DB6AC; }
</style>
""", unsafe_allow_html=True)

# 3. 데이터 로드
def load_data():
    query = "SELECT i.*, s.stock_name, s.theme FROM live_indicators i LEFT JOIN stock_info s ON i.stock_code = s.stock_code"
    rows = db.execute_query(query)
    df = pd.DataFrame(rows)
    if not df.empty:
        # 숫자 변환
        num_cols = ['rsi', 'lrl', 'r_square', 'last_price', 'change_rate']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 💡 종목명(코드) 형식 생성
        df['종목명(코드)'] = df['stock_name'] + "(" + df['stock_code'] + ")"
        df['주요테마'] = df['theme'].str.split(',').str[0].fillna('기타')
    return df

df = load_data()

# 상단 타이틀
st.title("🚀 실시간 전략 타격 보드")

if not df.empty:
    # --- [요약 지표 섹션] ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("감시 종목", f"{len(df)}개")
    m2.metric("과매도(RSI 30↓)", f"{len(df[df['rsi'] <= 30])}개")
    m3.metric("추세 강화(R2 0.8↑)", f"{len(df[df['r_square'] >= 0.8])}개")
    m4.metric("평균 등락률", f"{df['change_rate'].mean():+.2f}%")

    tab1, tab2 = st.tabs(["📋 스톡 모니터", "🌐 마켓 섹터 뷰"])

    # --- [탭 1: 스톡 모니터] 등락률 내림차순 정렬 ---
    with tab1:
        # 등락률 기준 내림차순 정렬
        st_df = df.sort_values('change_rate', ascending=False)
        
        # 컬럼명 한글화 및 종목명(코드) 적용
        display_df = st_df.rename(columns={
            '종목명(코드)': '종목명(코드)',
            'rsi': 'RSI',
            'r_square': '추세강도(R2)',
            'lrl': 'LRL예측',
            'last_price': '현재가',
            'change_rate': '등락률',
            '주요테마': '테마'
        })

        st.dataframe(
            display_df[['종목명(코드)', '테마', 'RSI', 'LRL예측', '추세강도(R2)', '현재가', '등락률']].style
            .background_gradient(subset=['등락률'], cmap='RdYlGn')
            .format({'현재가': '{:,.0f}', '등락률': '{:+.2f}%', 'RSI': '{:.1f}', '추세강도(R2)': '{:.4f}'}),
            use_container_width=True, hide_index=True
        )

    # --- [탭 2: 마켓 섹터 뷰] 테마 등락률 순 정렬 ---
    with tab2:
        # 테마별 평균 등락률 순 정렬
        theme_perf = df.groupby('주요테마')['change_rate'].mean().sort_values(ascending=False)
        top_themes = theme_perf.head(8).index.tolist()
        
        t_cols = st.columns(4)
        for idx, theme in enumerate(top_themes):
            with t_cols[idx % 4]:
                t_df = df[df['주요테마'] == theme].sort_values('change_rate', ascending=False).head(5)
                avg_rate = theme_perf[theme]
                
                st.markdown(f"<div class='mint-header'><span>⭐ {theme}</span><span>{avg_rate:+.2f}%</span></div>", unsafe_allow_html=True)
                with st.container(border=True):
                    for _, row in t_df.iterrows():
                        rate = float(row['change_rate'])
                        color = "#FF5252" if rate > 0 else "#448AFF"
                        
                        # 그래프 이탈 방지 계산
                        abs_rate = min(abs(rate), 20) 
                        width_pct = (abs_rate / 20) * 50 
                        left_pos = 50 if rate > 0 else 50 - width_pct

                        # 💡 마켓 섹터 뷰에서도 종목명(코드) 형식 사용
                        st.markdown(f"<div style='display:flex; justify-content:space-between; font-size:0.85em;'><b>{row['종목명(코드)']}</b><span style='color:{color}'>{rate:+.2f}%</span></div>", unsafe_allow_html=True)
                        st.markdown(f"""
                        <div class="gauge-container">
                            <div class="gauge-center-line"></div>
                            <div style="position: absolute; background-color: {color}; height: 100%; width: {width_pct}%; left: {left_pos}%; border-radius: 2px;"></div>
                        </div>
                        """, unsafe_allow_html=True)
else:
    st.info("데이터를 불러오는 중입니다...")