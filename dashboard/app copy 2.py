import streamlit as st
import pandas as pd
import time
import sys
from pathlib import Path
from datetime import datetime

# [지침 반영] 모듈 경로 자동 추가
root_path = str(Path(__file__).parent.parent)
if root_path not in sys.path:
    sys.path.append(root_path)

from core.db_client import db

# 1. 페이지 설정 및 디자인
st.set_page_config(layout="wide", page_title="까망이 스톡 모니터")

st.markdown("""
<style>
    .sector-card { background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E0E0E0; margin-bottom: 15px; overflow: hidden; }
    .sector-header { background-color: #4DB6AC; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center; color: white; font-weight: bold; }
    .stock-item { padding: 10px 12px; border-bottom: 1px solid #F5F5F5; }
    .gauge-bg { background-color: #EEEEEE; height: 5px; border-radius: 3px; position: relative; margin-top: 8px; }
    .gauge-center { position: absolute; left: 50%; width: 1.5px; height: 10px; background-color: #333; top: -2.5px; z-index: 2; }
    .gauge-fill { position: absolute; height: 100%; border-radius: 3px; }
    .status-connected { color: #00FF00; font-size: 0.8em; font-weight: bold; text-align: right; }
</style>
""", unsafe_allow_html=True)

# 2. 데이터 호출 함수
def get_live_data():
    query = """
    SELECT s.theme, s.stock_name, l.stock_code, l.last_price, l.change_rate, l.updated_at
    FROM live_indicators l
    JOIN stock_info s ON l.stock_code = s.stock_code
    WHERE l.last_price IS NOT NULL
    ORDER BY l.change_rate DESC
    """
    return db.execute_query(query)

def get_signal_data():
    # 전체 신호 탭을 위한 쿼리 (예시: 최근 20개 신호)
    query = "SELECT * FROM signal_history ORDER BY created_at DESC LIMIT 20"
    try:
        return db.execute_query(query)
    except:
        return []

def render_sector_card(sector_name, stocks):
    rates = [float(s['change_rate']) if s['change_rate'] is not None else 0.0 for s in stocks]
    avg_rate = sum(rates) / len(rates) if rates else 0.0
    
    card_html = f'<div class="sector-card"><div class="sector-header"><span>⭐ {sector_name}</span>'
    card_html += f'<span style="background:rgba(255,255,255,0.2); padding:2px 8px; border-radius:4px;">{avg_rate:+.2f}%</span></div>'
    
    for s in stocks:
        rate = float(s['change_rate']) if s['change_rate'] is not None else 0.0
        val = max(min(rate, 30), -30)
        width = abs(val) / 60 * 100
        color = "#FF5252" if val > 0 else "#448AFF"
        left_pos = 50 if val > 0 else 50 - width
        
        card_html += f"""
        <div class="stock-item">
            <div style="display: flex; justify-content: space-between; font-size: 0.9em; font-weight: 500;">
                <span style="color:#333;">{s['stock_name']}</span>
                <span style="color:{color};">{rate:+.2f}%</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.75em; color: #999; margin-top: 2px;">
                <span>{int(s['last_price'] or 0):,}원</span>
                <span>{s['updated_at'].strftime('%H:%M:%S') if s['updated_at'] else ''}</span>
            </div>
            <div class="gauge-bg"><div class="gauge-center"></div><div class="gauge-fill" style="width:{width}%; left:{left_pos}%; background-color:{color};"></div></div>
        </div>
        """
    card_html += "</div>"
    st.markdown(card_html, unsafe_allow_html=True)

# 3. 메인 화면 구성
col_title, col_stat = st.columns([7, 3])
with col_title:
    st.title("🚀 STOCK MONITOR")
with col_stat:
    st.markdown(f'<p class="status-connected">● STATUS: CONNECTED ({datetime.now().strftime("%H:%M:%S")})</p>', unsafe_allow_html=True)

# 4. 탭 구성
tabs = st.tabs(["🚀 주도주", "🌐 전체신호", "📊 단주거래"])

# 실시간 갱신을 위한 루프
placeholder = st.empty()

while True:
    with placeholder.container():
        # 각 탭의 내용을 매 루프마다 렌더링
        with tabs[0]:
            raw_data = get_live_data()
            if raw_data:
                df = pd.DataFrame(raw_data)
                df['main_theme'] = df['theme'].apply(lambda x: x.split(',')[0].strip() if x else '미분류')
                themes = df['main_theme'].unique()[:12] # 12개 섹터까지 확장 가능
                
                rows = [themes[i:i + 4] for i in range(0, len(themes), 4)]
                for row in rows:
                    cols = st.columns(4)
                    for i, theme in enumerate(row):
                        with cols[i]:
                            theme_stocks = df[df['main_theme'] == theme].to_dict('records')
                            render_sector_card(theme, theme_stocks)
            else:
                st.info("주도주 데이터를 불러오는 중...")

        with tabs[1]:
            st.subheader("🌐 실시간 전체 신호")
            signals = get_signal_data()
            if signals:
                st.table(pd.DataFrame(signals))
            else:
                st.write("감지된 신호가 없습니다.")

        with tabs[2]:
            st.subheader("📊 단주 거래 탐지")
            st.write("실시간 단주 체결 내역을 분석 중입니다...")

    time.sleep(5)