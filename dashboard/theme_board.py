import sys
import os

# 1. 프로젝트 루트 경로 설정 (기존 소스 유지)
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px
from core.db_client import db

# 페이지 설정 (독립 실행을 위해 상단에 배치)
st.set_page_config(page_title="테마별 대장주 분석", layout="wide")

def get_theme_data():
    # stock_info의 theme 기반 쿼리
    query = """
        SELECT 
            COALESCE(s.theme, '미분류') AS '테마',
            s.stock_name AS '종목명',
            i.stock_code AS '코드',
            i.rsi AS 'RSI',
            i.lrl AS 'LRL예측',
            i.r_square AS '추세신뢰도',
            i.last_price AS '현재가',
            i.change_rate AS '등락률',
            t.reason AS '선정사유'
        FROM live_indicators i
        JOIN target_candidates t ON i.stock_code = t.stock_code
        LEFT JOIN stock_info s ON i.stock_code = s.stock_code
        ORDER BY s.theme ASC, i.change_rate DESC
    """
    rows = db.execute_query(query)
    df = pd.DataFrame(rows)
    
    if not df.empty:
        # 테마 정제: 콤마로 연결된 경우 첫 번째 테마만 사용
        df['주테마'] = df['테마'].str.split(',').str[0].str.strip()
    return df

st.title("🏆 테마별 그룹 분석 및 대장주 포착")
st.markdown("---")

df = get_theme_data()

if not df.empty:
    # 테마별 그룹핑 리스트 생성
    grouped_themes = df.groupby('주테마')

    # 테마별 카드 출력
    for theme_name, group in grouped_themes:
        with st.expander(f"📂 {theme_name} (종목수: {len(group)}개)", expanded=True):
            # 테마 내 1위(대장주) 정보
            leader = group.iloc[0]
            
            # 요약 지표 (컬럼 4개)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("테마 대장주", leader['종목명'])
            m2.metric("대장주 등락률", f"{leader['등락률']}%")
            m3.metric("평균 RSI", f"{group['RSI'].mean():.2f}")
            m4.metric("최고 신뢰도", f"{group['추세신뢰도'].max():.4f}")

            # 테마 내 종목 리스트
            st.table(group[['종목명', '코드', '현재가', '등락률', 'RSI', '추세신뢰도', '선정사유']])
else:
    st.info("표시할 데이터가 없습니다. 시세 및 지표 계산 프로세스를 확인해 주세요.")