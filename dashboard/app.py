import sys
import os
import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# 1. 경로 설정 및 DB 연결
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from collector.naver_crawler import sync_naver_themes
from core.db_client import db

# 2. 페이지 설정
st.set_page_config(page_title="STRATEGY HIT BOARD PRO", layout="wide")

# CSS: 디자인 통합 및 전략 태그 스타일 정의
st.markdown("""
<style>
    .mint-header { background-color: #4DB6AC; color: white; padding: 6px 12px; border-radius: 5px 5px 0 0; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }
    .gauge-container { background-color: #f0f0f0; height: 10px; border-radius: 5px; position: relative; margin: 5px 0; overflow: hidden; width: 100%; border: 1px solid #e0e0e0; }
    .gauge-center-line { position: absolute; left: 50%; width: 1px; height: 100%; background-color: #333; z-index: 5; }
    .signal-card { background-color: #ffffff; border: 1px solid #FF5252; border-left: 8px solid #FF5252; padding: 15px; border-radius: 8px; box-shadow: 2px 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #4DB6AC; font-weight: bold; }
    /* 💡 전략 태그: 창(공격)은 붉은색, 방패(수비)는 파란색 계열 */
    .strategy-tag-창 { background-color: #FFEBEE; color: #FF5252; padding: 2px 8px; border-radius: 10px; font-weight: bold; font-size: 0.75em; border: 1px solid #FF5252; }
    .strategy-tag-방패 { background-color: #E3F2FD; color: #2196F3; padding: 2px 8px; border-radius: 10px; font-weight: bold; font-size: 0.75em; border: 1px solid #2196F3; }
</style>
""", unsafe_allow_html=True)

# 3. 데이터 로드 (기존 컬럼 + 선정 사유 조인)
def load_data():
    # 💡 target_candidates 테이블과 조인하여 '선정사유'를 가져옵니다.
    query = """
        SELECT i.*, s.stock_name, s.theme, t.reason as target_reason
        FROM live_indicators i 
        LEFT JOIN stock_info s ON i.stock_code = s.stock_code
        LEFT JOIN target_candidates t ON i.stock_code = t.stock_code
    """
    rows = db.execute_select_query(query)
    df = pd.DataFrame(rows)
    if not df.empty:
        # 수치형 변환
        num_cols = ['rsi', 'lrl', 'r_square', 'bb_upper', 'bb_lower', 'ma_short', 'ma_long', 'last_price', 'change_rate']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df['종목명(코드)'] = df['stock_name'].fillna('nan') + "(" + df['stock_code'] + ")"
        df['주요테마'] = df['theme'].str.split(',').str[0].fillna('기타')
        
        # 💡 전략 분류 기준
        df['전략분류'] = df.apply(lambda x: '창' if (x['change_rate'] > 3 or x['last_price'] > x['bb_upper']) else '방패', axis=1)

        # 💡 [판별 포인트] 로직 강화 (로그에 찍힌 '바닥탈출' 및 '매집' 포착)
        def get_strat_reason(row):
            reasons = []
            # 1. 공격(창) 시그널
            if row['last_price'] > row['bb_upper']: reasons.append("🚀BB상단돌파")
            if row['change_rate'] > 3: reasons.append(f"🔥수급폭발({row['change_rate']}%↑)")
            
            # 2. 바닥탈출 및 추세반전 (사용자님이 로그에서 보신 로직)
            if row['rsi'] < 25 and row['r_square'] > 0.6: 
                reasons.append("🎯바닥탈출(분석중)")
            elif row['전략분류'] == '방패' and row['r_square'] < 0.3 and row['change_rate'] > 0:
                reasons.append("✨추세반전임박")
                
            # 3. 조용한 세력 매집 (주가는 정체인데 에너지가 응축될 때)
            if -1.5 < row['change_rate'] < 1.5 and 45 < row['rsi'] < 60 and row['r_square'] < 0.2:
                reasons.append("📦조용한매집중")
            
            return " & ".join(reasons) if reasons else "박스권유지"
        
        df['판별포인트'] = df.apply(get_strat_reason, axis=1)
    return df

df = load_data()

# 상단 타이틀 및 버튼 배치
# 8:2 비율로 컬럼을 나눕니다.
col_title, col_btn = st.columns([7, 3]) # 버튼 공간 확보

with col_title:
    st.title("🎯 실시간 전략 타격 보드")
    st.caption(f"최근 업데이트: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")

with col_btn:
    st.write("##") # 높이 맞춤
    if st.button("🔄 네이버 테마 동기화", use_container_width=True):
        with st.spinner("네이버 테마 데이터를 긁어오는 중..."):
            sync_naver_themes() # naver_crawler.py의 함수 실행
        st.success("동기화 완료!")
        st.rerun()

st.markdown("---") # 시각적인 구분선 추가

if not df.empty:
    # --- [섹션 1: 실시간 전략 포착 카드] ---
    # 💡 정렬: 창(공격) 중에서도 등락률 높은 순
    buy_signals = df[df['전략분류'] == '창'].sort_values('change_rate', ascending=False)

    if not buy_signals.empty:
        st.subheader("🚀 오늘의 '창' (주도주 및 돌파 포착)")
        s_cols = st.columns(4)
        for i, (_, row) in enumerate(buy_signals.head(4).iterrows()):
            with s_cols[i % 4]:
                st.markdown(f"""
                <div class="signal-card">
                    <span class="strategy-tag-창">공격형(창)</span>
                    <h3 style='margin:5px 0 0 0; color:#FF5252; font-size:1.4em;'>BUY 시그널</h3>
                    <div style='margin-top:10px;'>
                        <b>{row['종목명(코드)']}</b><br>
                        현재가: <span style='font-size:1.1em;'>{int(row['last_price']):,}원 ({row['change_rate']:+.2f}%)</span><br>
                        <small style='color:#666;'>포인트: {row['판별포인트']}</small><br>
                        <small style='color:#4DB6AC;'>선정사유: {row['target_reason'] if row['target_reason'] else '지표분석'}</small>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    st.markdown("---")

    # --- [섹션 2: 요약 지표] ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("감시 종목", f"{len(df)}개")
    m2.metric("공격 타점(창)", f"{len(df[df['전략분류']=='창'])}개")
    m3.metric("수비 관망(방패)", f"{len(df[df['전략분류']=='방패'])}개")
    m4.metric("평균 등락률", f"{df['change_rate'].mean():+.2f}%")

    # --- [섹션 3: 탭 메뉴] ---
    tab1, tab2 = st.tabs(["📋 스톡 모니터 (공수 전환)", "🌐 마켓 섹터 뷰"])

    with tab1:
        # 💡 정렬: 전략분류(창 우선) 내림차순, 그 안에서 등락률 내림차순
        st_df = df.sort_values(['전략분류', 'change_rate'], ascending=[False, False])
        
        # 💡 헤더 구성: [판별포인트] 컬럼 추가를 위해 그리드 비율 재조정
        h_cols = st.columns([0.7, 2, 0.9, 0.9, 0.6, 0.6, 0.8, 0.8, 1.0, 1.2, 1.5, 1.8])
        headers = ["구분", "종목명(코드)", "현재가", "등락률", "RSI", "R2", "LRL", "BB상단", "이평선", "선정사유", "판별포인트", "추세 게이지"]
        for col, title in zip(h_cols, headers):
            col.markdown(f"**{title}**")
        st.markdown("<hr style='margin:5px 0; border:1px solid #4DB6AC;'>", unsafe_allow_html=True)

        for _, row in st_df.iterrows():
            r_cols = st.columns([0.7, 2, 0.9, 0.9, 0.6, 0.6, 0.8, 0.8, 1.0, 1.2, 1.5, 1.8])
            rate = float(row['change_rate'])
            color = "#FF5252" if rate > 0 else "#448AFF"
            tag_class = f"strategy-tag-{row['전략분류']}"
            
            r_cols[0].markdown(f"<span class='{tag_class}'>{row['전략분류']}</span>", unsafe_allow_html=True)
            r_cols[1].write(f"**{row['종목명(코드)']}**")
            r_cols[2].write(f"{int(row['last_price']):,}")
            r_cols[3].markdown(f"<span style='color:{color}'>{rate:+.2f}%</span>", unsafe_allow_html=True)
            r_cols[4].write(f"{int(row['rsi'])}")
            r_cols[5].write(f"{row['r_square']:.2f}")
            r_cols[6].write(f"{int(row['lrl']):,}")
            r_cols[7].write(f"{int(row['bb_upper']):,}")
            r_cols[8].write(f"{int(row['ma_short']):,}") # 지면 관계상 단기이평 위주 노출
            
            # 선정 사유 (데이터베이스 기반)
            r_cols[9].write(f"{row['target_reason'][:10] if row['target_reason'] else '-'}")
            
            # 💡 [신규 추가] 판별 포인트 (창/방패 분류 근거)
            r_cols[10].markdown(f"<small>{row['판별포인트']}</small>", unsafe_allow_html=True)
            

            # 🚀 [이부분!!] 데이터 추적을 위한 정밀 로그 (터미널에서 확인 가능)
            raw_detected = row.get('detected_at')
            raw_updated = row.get('updated_at')
            
            # 딱 한 번만 샘플로 로그 출력 (로그 폭주 방지)
            if _ == 0: 
                print(f"\n🔍 [TRACE] 종목: {row['stock_name']}")
                print(f"   - detected_at: {raw_detected} | Type: {type(raw_detected)} | TZ: {getattr(raw_detected, 'tzinfo', 'None')}")
                print(f"   - updated_at: {raw_updated} | Type: {type(raw_updated)} | TZ: {getattr(raw_updated, 'tzinfo', 'None')}")


            # 🚀 [이부분!!] db_client에서 이미 KST로 변환되어 오므로, 
            # 데이터가 없는 경우에만 '--:--'로 표시하여 혼선을 방지합니다.
            raw_time = row.get('detected_at') or row.get('updated_at')
            detected_time = raw_time.strftime('%H:%M') if pd.notnull(raw_time) else "--:--"

            with r_cols[11]:
                # 🚀 [이부분!!] 기준값을 15에서 30으로 수정하여 섹터뷰와 통일
                abs_val = min(abs(rate), 30)
                width_pct = (abs_val / 30) * 50
                left_pos = 50 if rate > 0 else 50 - width_pct
                
                st.markdown(f"""
                <div style='display:flex; justify-content:space-between; font-size:0.7em; margin-bottom:2px;'>
                    <span></span><span style='color:#888;'>{detected_time}</span>
                </div>
                <div class="gauge-container" style="margin-top:0;">
                    <div class="gauge-center-line"></div>
                    <div style="position: absolute; background-color: {color}; height: 100%; width: {width_pct}%; left: {left_pos}%; border-radius: 2px;"></div>
                </div>
                """, unsafe_allow_html=True)

    with tab2:
        # 테마별 게이지 바 뷰 (기존 로직 유지)
        theme_perf = df.groupby('주요테마')['change_rate'].mean().sort_values(ascending=False)
        top_themes = theme_perf.index.tolist()
        for i in range(0, len(top_themes), 4):
            t_cols = st.columns(4)
            for idx, theme in enumerate(top_themes[i:i+4]):
                with t_cols[idx]:
                    avg_rate = theme_perf[theme]
                    st.markdown(f"<div class='mint-header'><span>⭐ {theme}</span><span>{avg_rate:+.2f}%</span></div>", unsafe_allow_html=True)
                    with st.container(border=True):
                        t_stocks = df[df['주요테마'] == theme].sort_values('change_rate', ascending=False).head(5)
                        for _, row in t_stocks.iterrows():
                            r = float(row['change_rate'])
                            c = "#FF5252" if r > 0 else "#448AFF"
                            # 🚀 [이부분!!] 30% 기준을 더 명확하게 시각화 (전체 너비 100% 기준 대응)
                            # 30%일 때 전체 게이지의 절반(50%)을 꽉 채우도록 계산
                            abs_v = min(abs(r), 30)
                            w = (abs_v / 30) * 50  
                            l = 50 if r > 0 else 50 - w
                            
                            # 🚀 [이부분!!] DB에 detected_at 컬럼이 생기기 전까지 안전하게 시간 추출
                            # row에 detected_at이 있으면 쓰고, 없으면 updated_at을 씁니다.
                            raw_time = row.get('detected_at') or row.get('updated_at') or datetime.now(KST)
                            detected_time = raw_time.strftime('%H:%M')
                            
                            st.markdown(f"""
                                <div style='display:flex; justify-content:space-between; font-size:0.85em; margin-top:5px;'>
                                    <b>{row['종목명(코드)']}</b>
                                    <span style='color:{c}'>{r:+.2f}% <small>({detected_time})</small></span>
                                </div>
                                <div class='gauge-container'>
                                    <div class='gauge-center-line'></div>
                                    <div style='position:absolute; left:{l}%; width:{w}%; height:100%; background-color:{c};'></div>
                                </div>
                            """, unsafe_allow_html=True)
else:
    st.info("데이터 로딩 중...")