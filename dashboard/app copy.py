import sys
import os
import streamlit as st
import pandas as pd
# 💡 에러 방지: Plotly 설치 여부 확인 및 Import
try:
    import plotly.express as px
except ImportError:
    st.error("명령창에 'pip install plotly'를 입력해 주세요.")

# 1. 경로 설정 및 모듈 로드
# 💡 ImportError: No module named 'core' 방지를 위해 경로를 절대경로로 보정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.db_client import db

# 2. 페이지 기본 설정 (Dark Theme 기반)
st.set_page_config(page_title="STOCK MONITOR", layout="wide")

# 3. 데이터 로드 및 에러 방어 처리
def load_data():
    query = """
        SELECT i.*, s.stock_name, s.theme
        FROM live_indicators i
        LEFT JOIN stock_info s ON i.stock_code = s.stock_code
        JOIN target_candidates t ON i.stock_code = t.stock_code
    """
    rows = db.execute_query(query)
    df = pd.DataFrame(rows)
    
    if not df.empty:
        # 💡 TypeError 방어: 모든 숫자 컬럼의 None값을 0으로 치환
        numeric_cols = ['rsi', 'lrl', 'r_square', 'ma_short', 'ma_long', 'last_price', 'change_rate', 'bb_upper', 'bb_lower']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 추세 상태 계산
        df['추세상태'] = df.apply(lambda r: "🔥강세" if r['r_square'] > 0.7 and r['lrl'] > r['ma_long'] else "☁️횡보", axis=1)
        df['주요테마'] = df['theme'].str.split(',').str[0].fillna('기타')
    return df

# 4. 헤더 UI
st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <h2 style="margin:0;">🚀 STOCK MONITOR</h2>
        <p style="color: #00ff00; font-weight: bold; margin:0;">● STATUS: CONNECTED</p>
    </div>
    <hr style="margin-top: 5px; margin-bottom: 15px;">
""", unsafe_allow_html=True)

df = load_data()

if not df.empty:
    # 💡 요청하신 탭 구조: 기능 추가 시 여기에 리스트만 늘리면 됩니다.
    tab_monitor, tab_market = st.tabs(["🚀 스톡 모니터", "🌐 마켓 섹터 뷰"])

    # --- [탭 1: 스톡 모니터 (기본 현황)] ---
    with tab_monitor:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("감시 종목", f"{len(df)}개")
        m2.metric("과매도(RSI 30↓)", f"{len(df[df['rsi'] < 30])}개")
        m3.metric("추세 강화", f"{len(df[df['추세상태'] == '🔥강세'])}개")
        # 💡 nan 에러 방지용 평균값 계산
        avg_r2 = df['r_square'].mean() if not df['r_square'].empty else 0
        m4.metric("평균 R²", f"{avg_r2:.4f}")

        # 스타일링된 데이터 테이블
        st.dataframe(
            df[['stock_name', 'last_price', 'change_rate', 'rsi', 'r_square', '주요테마', 'datetime']].style
            .background_gradient(subset=['change_rate'], cmap='RdYlGn')
            .format({
                'last_price': '{:,.0f}', 
                'change_rate': '{:+.2f}%', 
                'rsi': '{:.2f}', 
                'r_square': '{:.4f}'
            }),
            use_container_width=True, hide_index=True
        )

    # --- [탭 2: 마켓 섹터 뷰 (UI 지침 반영)] ---
    with tab_market:
        st.subheader("테마별 그룹화 현황")
        theme_list = sorted(df['주요테마'].unique())
        cols = st.columns(4) # 4열 배치
        
        for idx, theme in enumerate(theme_list):
            with cols[idx % 4]:
                t_df = df[df['주요테마'] == theme].sort_values('change_rate', ascending=False).head(5)
                # 카드형 UI 구현
                st.markdown(f"""
                    <div style="border: 1px solid #444; padding: 10px; border-radius: 10px; background: #1a1c24; margin-bottom: 10px;">
                        <b style="color: #00d4ff;">⭐ {theme}</b>
                """, unsafe_allow_html=True)
                
                for _, row in t_df.iterrows():
                    color = "#ff4b4b" if row['change_rate'] > 0 else "#4b4bff"
                    # 💡 TypeError 방어: float 변환 전 다시 한번 체크
                    rate = float(row['change_rate'])
                    bar_val = min(abs(rate) * 5, 100)
                    st.markdown(f"""
                        <div style="font-size: 0.8em; margin-top: 8px;">
                            {row['stock_name']} <span style="color:{color};">{rate:+.2f}%</span>
                            <div style="background:#333; width:100%; height:4px; margin-top:2px;">
                                <div style="background:{color}; width:{bar_val}%; height:100%;"></div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)