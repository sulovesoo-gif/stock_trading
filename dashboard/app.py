import sys
import os
import streamlit as st
import pandas as pd
import time
import json, plotly.express as px
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo
# [수정 부분!!] Streamlit 재실행 예외(RerunException)를 제외한 나머지 통신 에러 방어
from streamlit.runtime.scriptrunner import RerunException
KST = ZoneInfo("Asia/Seoul")

# 0. 캐시 설정 (데이터 로딩 중 깜빡임 방지)
if 'last_df' not in st.session_state:
    st.session_state.last_df = pd.DataFrame()
if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now(KST)

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
    /* 1. 스트림릿 요소 간 기본 간격(Gap) 제거 */
    [data-testid="stVerticalBlock"] > div { padding: 0px !important; margin: 0px !important; gap: 0rem !important; }
    
    /* 2. 컬럼 간 간격 미세 조정 */
    [data-testid="column"] { padding: 0 5px !important; }

    .mint-header { color: #4DB6AC; padding: 6px 0; border-bottom: 2px solid #4DB6AC; font-weight: bold; display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }
    .gauge-container { background-color: #f8f9fa; height: 8px; border-radius: 4px; position: relative; margin: 2px 0; overflow: hidden; width: 100%; border: 1px solid #eee; }
    .gauge-center-line { position: absolute; left: 50%; width: 1px; height: 100%; background-color: #333; z-index: 5; }

    /* 1. 왼쪽 사이드바와 내비게이션 메뉴(app, detail)를 완전히 제거 */
    [data-testid="stSidebar"], [data-testid="stSidebarNav"] {
        display: none !important;
    }

    /* 2. 사이드바가 차지하던 왼쪽 공백 제거 및 전체 너비 확보 */
    section[data-testid="stSidebar"] + section {
        margin-left: 0 !important;
    }

    /* 3. 본문 컨테이너 여백 최적화 */
    .main .block-container {
        max-width: 100% !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-top: 1rem !important;
    }
    
    /* 4. 상단 헤더 메뉴 버튼(햄버거 메뉴) 숨기기 */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

def load_data():
    # 💡 target_candidates 테이블과 조인하여 '선정사유'를 가져옵니다.
    query = """
        SELECT i.*, 
               COALESCE(t.stock_name, s.stock_name) as stock_name, 
               s.theme, s.sector, t.reason as target_reason,
               i.foreign_net_5d, i.institution_net_5d, i.volume_profile,
               COALESCE(i.detected_at, i.updated_at) as display_time
        FROM live_indicators i 
        INNER JOIN target_candidates t ON i.stock_code = t.stock_code
        LEFT JOIN stock_info s ON i.stock_code = s.stock_code
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
        df['업종'] = df['sector'].fillna('기타')
        
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

# 데이터 업데이트
new_df = load_data()
if not new_df.empty:
    st.session_state.last_df = new_df
    st.session_state.last_update = datetime.now(KST)

# 상단 타이틀 및 버튼 배치
# 8:2 비율로 컬럼을 나눕니다.
col_title, col_btn = st.columns([7, 3]) # 버튼 공간 확보

with col_title:
    # 상태 표시등 추가
    status_color = "#00FF00" if (datetime.now().second % 2 == 0) else "#00AA00"
    st.markdown(f"## 🎯 실시간 전략 타격 보드 <span style='color:{status_color}; font-size:0.5em;'>● LIVE ({st.session_state.last_update.strftime('%H:%M:%S')})</span>", unsafe_allow_html=True)
    # st.caption(f"최근 업데이트: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")

with col_btn:
    st.write("##") # 높이 맞춤
    if st.button("🔄 네이버 테마 동기화", use_container_width=True):
        with st.spinner("네이버 테마 데이터를 긁어오는 중..."):
            sync_naver_themes() # naver_crawler.py의 함수 실행
        st.success("동기화 완료!")
        st.rerun()

st.markdown("---") # 시각적인 구분선 추가

# [수정 부분!!] 팝업 호출을 위한 HTML/JS 생성 함수 (sig_name 전용)
# def render_sig_popup_link(row):
#     stock_code = row['stock_code']
#     sig_name = row['sig_name']
#     sig_color = row['sig_color']
    
#     # 팝업으로 열릴 상세 페이지 URL (쿼리 파라미터로 종목코드 전달)
#     popup_url = f"/detail?code={stock_code}&sig={sig_name}&col={sig_color}"
    
#     # [이부분!!] 텍스트 클릭 시 window.open으로 팝업창 실행 (크기 지정)
#     return f"""
#     <a href="javascript:void(0);" 
#        onclick="window.open('{popup_url}', 'detail_{stock_code}', 'width=800,height=300,scrollbars=yes,resizable=yes');"
#        style="text-decoration:none; color:{sig_color}; font-weight:bold; font-size:11px; cursor:pointer;">
#        {sig_name}
#     </a>
#     """

def render_sig_popup_link(row):
    try:
        profile_data = json.loads(row['volume_profile'])[:5]
        v_list = [f"{int(float(p['stck_prpr']))}:{int(float(p['acml_vol_rlim']))}" for p in profile_data]
        v_str = "|".join(v_list) # 예: "25400:20|25300:15..."
    except:
        v_str = ""

    # 필요한 데이터를 딕셔너리로 묶어 JSON화 한 뒤 인코딩
    params = {
        "code": row['stock_code'],
        "name": row['stock_name'],
        "theme": row.get('theme', ''),
        "rsi": int(row.get('rsi', 0)),
        "r2": round(row.get('r_square', 0), 2),
        "lrl": int(row.get('lrl', 0)),
        "bb": int(row.get('bb_upper', 0)),
        "cur": int(row.get('last_price', 0)),
        "ma": int(row.get('ma_short', 0)),
        "f_net": int(row.get('foreign_net_5d', 0)),
        "i_net": int(row.get('institution_net_5d', 0)),
        "sig": row['sig_name'],
        "col": row['sig_color'],        
        # "vol_ratio" : int(row.get('vol_ratio', 0)),
        # "price_item" : int(row.get('stck_prpr', 0)),
        "vp": v_str
    }
    # 매물대는 데이터가 크므로 제외하거나 핵심 1~2개만 포함
    
    query_str = urllib.parse.urlencode(params)
    popup_url = f"/detail?{query_str}"
    
    return f"""
    <a href="javascript:void(0);" 
       onclick="window.open('{popup_url}', 'detail_{row['stock_code']}', 'width=800,height=300');" 
       style="text-decoration:none; color:{row['sig_color']}; font-weight:bold; font-size:11px; cursor:pointer;">
       {row['sig_name']}
    </a>
    """

def render_dashboard(df):
    if df.empty:
        st.warning("데이터를 불러오는 중입니다...")
        return

    # --- [섹션 1: 실시간 전략 TOP 픽 (로켓/바닥/슈퍼 전용)] ---
    # 1. 시그널 등급(우선순위) 부여 함수
    def get_signal_grade(row):
        rsi, r2 = row.get('rsi'), row.get('r_square')
        lrl, bb_up, cur_p = row.get('lrl'), row.get('bb_upper'), row.get('last_price')
        f_net, i_net = row.get('foreign_net_5d', 0), row.get('institution_net_5d', 0)
        ma_short = row.get('ma_short')
        
        # 우선순위: 로켓(1) > 바닥탈출(2) > 슈퍼(3) > 나머지(9)
        if r2 > 0.7 and cur_p > lrl and cur_p > bb_up and (f_net > 0 or i_net > 0):
            return 1, "🚀 로켓: 추세폭발", "#FF5252"
        if rsi < 35 and r2 < 0.25 and cur_p > ma_short:
            return 2, "✨ 바닥탈출: 역발상", "#4DB6AC"
        if cur_p > lrl and r2 >= 0.8 and (f_net > 0 and i_net > 0):
            return 3, "💎 슈퍼: 세력매집", "#FFD700"
        return 9, "🔍 일반", "#888888"

    # 2. 데이터 가공 및 정렬
    df[['sig_grade', 'sig_name', 'sig_color']] = df.apply(
        lambda x: pd.Series(get_signal_grade(x)), axis=1
    )

    # 3. TOP 4 추출 (일반 등급 제외, 우선순위 순 -> 그 안에서 등락률 순)
    top_picks = df[df['sig_grade'] < 9].sort_values(['sig_grade', 'change_rate'], ascending=[True, False]).head(10)

    if not top_picks.empty:
        st.markdown("#### 🎯 오늘의 전략 타격 대상 (TOP 픽)")
        # 💡 5개씩 한 줄에 배치하기 위해 5컬럼 설정
        cols_per_row = 5
        for i in range(0, len(top_picks), cols_per_row):
            s_cols = st.columns(cols_per_row)
            batch = top_picks.iloc[i : i + cols_per_row]
            
            for j, (_, row) in enumerate(batch.iterrows()):
                p_url = f"https://finance.naver.com/item/main.naver?code={row['stock_code']}"
                sig_c = row['sig_color']
                p_col = "#FF5252" if row["change_rate"] > 0 else "#448AFF"

                # [이부분!!] 시그널 팝업 링크 생성
                sig_popup_html = render_sig_popup_link(row)
                
                with s_cols[j]:
                    # [최적화] body margin:0 과 height:150px 조합으로 공백 제거
                    full_card_html = f"""
                    <body style="margin:0; padding:0;">
                        <div style="background:white; border:1px solid #eee; border-top:5px solid {sig_c}; 
                                    padding:8px 12px; border-radius:8px; height:140px; box-shadow: 2px 2px 8px rgba(0,0,0,0.05); 
                                    font-family: 'Malgun Gothic', sans-serif; box-sizing: border-box; overflow:hidden;">
                            
                            <div style="margin-bottom:2px;">
                                {sig_popup_html}  </div>

                            <div style="margin:0; min-height:36px; display:flex; align-items:center;">
                                <a href="{p_url}" target="_blank" 
                                   style="font-size:14px; font-weight:bold; color:black; text-decoration:none; 
                                          line-height:1.2; display:block; word-break:break-all;">
                                    {row['종목명(코드)']}
                                </a>
                            </div>

                            <div style="font-size:12px; line-height:1.3; margin-top:2px;">
                                <div style="margin-bottom:3px;">현재가: <span style="color:{p_col}; font-weight:bold;">{int(row['last_price']):,} ({row['change_rate']:+.2f}%)</span></div>
                                <div style="background:#f9f9f9; padding:5px 8px; border-radius:4px; font-size:11px; 
                                            color:#555; height:35px; overflow:hidden; border:1px solid #f0f0f0;">
                                    📌 {row['판별포인트']}
                                </div>
                            </div>
                        </div>
                    </body>
                    """
                    # height를 145로 설정하여 하단 잘림 방지 및 다음 요소와의 간격 최소화
                    st.components.v1.html(full_card_html, height=145)
    else:
        st.info("현재 로켓/바닥탈출 등 특이 시그널이 발생한 종목이 없습니다. 관망이 유리합니다.")

    st.write("") # 미세 간격 조정

    # --- [섹션 2: 요약 지표] ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("감시 종목", f"{len(df)}개")
    m2.metric("공격 타점(창)", f"{len(df[df['전략분류']=='창'])}개")
    m3.metric("수비 관망(방패)", f"{len(df[df['전략분류']=='방패'])}개")
    m4.metric("평균 등락률", f"{df['change_rate'].mean():+.2f}%")

    # --- [섹션 3: 탭 메뉴] ---
    tab1, tab2 = st.tabs(["📋 스톡 모니터 (공수 전환)", "🌐 마켓 섹터 뷰"])

    col_widths = [0.6, 1.8, 0.8, 0.8, 0.8, 2.2, 3.8, 1.2]
    with tab1:
        # 💡 정렬: 전략분류(창 우선) 내림차순, 그 안에서 등락률 내림차순
        st_df = df.sort_values(['전략분류', 'change_rate'], ascending=[False, False])
        
        # 💡 헤더 구성: [판별포인트] 컬럼 추가를 위해 그리드 비율 재조정
        h_cols = st.columns(col_widths)
        # headers = ["구분", "종목명(코드)", "업종", "현재가", "등락률", "RSI", "R2", "LRL", "BB상단", "이평선", "선정사유", "판별포인트", "추세 게이지"]
        headers = ["구분", "종목명(코드)", "업종", "현재가", "등락률", "🎯 선정 사유", "💡 핵심 판별 포인트", "추세 게이지"]
        for col, title in zip(h_cols, headers):
            col.markdown(f"**{title}**")
        st.markdown("<hr style='margin:5px 0; border:1px solid #4DB6AC;'>", unsafe_allow_html=True)

        for _, row in st_df.iterrows():
            r_cols = st.columns(col_widths)
            rate = float(row['change_rate'])
            color = "#FF5252" if rate > 0 else "#448AFF"
            tag_class = f"strategy-tag-{row['전략분류']}"
            
            r_cols[0].markdown(f"<span class='{tag_class}'>{row['전략분류']}</span>", unsafe_allow_html=True)
            r_cols[1].write(f"**{row['종목명(코드)']}**")
            r_cols[2].markdown(f"<div style='font-size:0.75em; color:#888; line-height:1.1;'>{row['업종'][:4]}</div>", unsafe_allow_html=True)
            r_cols[3].write(f"{int(row['last_price']):,}")
            r_cols[4].markdown(f"<span style='color:{color}'>{rate:+.2f}%</span>", unsafe_allow_html=True)
            
            # 선정 사유 (데이터베이스 기반)
            r_cols[5].write(f"{row['target_reason'][:10] if row['target_reason'] else '-'}")
            
            # 6. 판별 포인트: 가장 넓은 공간 할당, 검정색 텍스트로 가독성 강조
            point = row['판별포인트'] if row['판별포인트'] else "-"
            r_cols[6].markdown(f"<div style='font-size:0.85em; line-height:1.3; color:black;'>{point}</div>", unsafe_allow_html=True)

            raw_time = row.get('display_time')
            detected_time = raw_time.strftime('%H:%M') if pd.notnull(raw_time) else "--:--"

            with r_cols[7]:
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
            
            # 🚀 [바로 여기!!] 게이지 바 출력이 끝난 직후, 루프가 끝나기 전입니다.
            # 이 자리에 넣어야 각 종목 행 바로 아래에 '상세분석' 칸이 생깁니다.
            # --- [종합 시그널: AI 전략 타격 엔진] ---
            rsi, r2 = row.get('rsi'), row.get('r_square')
            lrl, bb_up, bb_low, cur_p = row.get('lrl'), row.get('bb_upper'), row.get('bb_lower'), row.get('last_price')
            f_net, i_net = row.get('foreign_net_5d', 0), row.get('institution_net_5d', 0)
            ma_short = row.get('ma_short')
            
            # 방향성 및 수급 상태 미리 정의
            is_up_trend = cur_p > lrl
            is_double_buy = (f_net > 0 and i_net > 0)
            
            # 1순위: ⚠️ 매도 최우선 (위험 1위: 추락하는 칼날)
            if r2 > 0.6 and not is_up_trend and cur_p < bb_low:
                total_sig = "🚨 절대매도: 추락하는 칼날 (하락관성 극대)"
                sig_color = "#D32F2F" # 진한 빨강
            
            # 2순위: ⚠️ 매도 차선 (위험 2위: 에너지 고갈)
            elif rsi > 80 and r2 < 0.4: # R-SQ가 꺾이기 시작할 때
                total_sig = "🛑 탈출준비: 상승동력 고갈 (과열 후 꺾임)"
                sig_color = "#FF5722" # 주황 빨강

            # 3순위: 🚀 매수 최우선 (추세 폭발형 - The Rocket)
            elif r2 > 0.7 and is_up_trend and cur_p > bb_up and (f_net > 0 or i_net > 0):
                total_sig = "🚀 로켓: 추세폭발 (달리는 말에 올라타라)"
                sig_color = "#FF5252" # 공격적 레드

            # 4순위: ✨ 매수 차선 (바닥 탈출형 - Turnaround)
            elif rsi < 35 and r2 < 0.25 and cur_p > ma_short:
                total_sig = "✨ 바닥탈출: 역발상 타점 (공포에 사서 환희에)"
                sig_color = "#4DB6AC" # 민트색

            # 5순위: 💎 슈퍼 시그널 (수급+추세 베스트 합작)
            elif is_up_trend and r2 >= 0.8 and is_double_buy:
                total_sig = "💎 슈퍼: 세력매집 & 강한추세 견고"
                sig_color = "#FFD700" # 골드

            # 6순위: 일반/중립 상태
            elif r2 < 0.2:
                total_sig = "📦 관망: 방향성 탐색 중 (에너지 응축)"
                sig_color = "#757575"
            else:
                total_sig = "🔍 분석: 일반 추세 진행 중"
                sig_color = "#888888"

            # expander 제목에 실시간 반영
            expander_title = f"📊 {row['종목명(코드)']} 전략분석  |  {total_sig}"
            with st.expander(expander_title):
                ex_col1, ex_col2, ex_col3 = st.columns([0.8, 1.2, 2.0])
                
                # --- [1. 실시간 수급] ---
                with ex_col1:
                    st.markdown("<p style='font-size:0.85em; font-weight:bold; border-bottom:1px solid #4DB6AC; margin-bottom:5px;'>👥 수급 현황</p>", unsafe_allow_html=True)
                    f_net = row.get('foreign_net_5d', 0)
                    i_net = row.get('institution_net_5d', 0)
                    f_color = "#FF5252" if f_net > 0 else "#448AFF"
                    f_badge = "<span style='background:#FF5252; color:white; padding:1px 4px; border-radius:3px; font-size:0.7em; font-weight:bold; margin-left:3px;'>👽 외인매집</span>" if f_net > 0 else ""
                    
                    st.markdown(f"<div style='font-size:0.82em; line-height:1.8;'>외인: <span style='color:{f_color}; font-weight:bold;'>{int(f_net):,}</span> {f_badge}<br>기관: <span style='color:{'#FF5252' if i_net > 0 else '#448AFF'}; font-weight:bold;'>{int(i_net):,}</span></div>", unsafe_allow_html=True)

                # --- [2. 주요 매물대 (콤팩트 유지)] ---
                with ex_col2:
                    st.markdown("<p style='font-size:0.85em; font-weight:bold; border-bottom:1px solid #FFD54F; margin-bottom:5px;'>🧱 핵심 매물대</p>", unsafe_allow_html=True)
                    if row.get('volume_profile'):
                        try:
                            profile = json.loads(row['volume_profile'])
                            for p in profile:
                                vol_ratio = float(p.get('acml_vol_rlim', 0))
                                price_item = int(float(p.get('stck_prpr', 0)))
                                bar_color = "#FF5252" if vol_ratio > 15 else "#4DB6AC"
                                st.markdown(f"""
                                    <div style="display:flex; align-items:center; height:22px; margin-bottom:2px;">
                                        <div style="width:50px; font-size:10px; color:#aaa; text-align:right; margin-right:5px;">{price_item:,}</div>
                                        <div style="flex-grow:1; background:#f0f0f0; height:8px; border-radius:2px;">
                                            <div style="width:{vol_ratio}%; background:{bar_color}; height:100%; border-radius:2px;"></div>
                                        </div>
                                        <div style="width:30px; font-size:9px; color:#888; margin-left:5px;">{vol_ratio:.0f}%</div>
                                    </div>
                                """, unsafe_allow_html=True)
                        except: st.caption("파싱 에러")

                # --- [3. 실시간 지표 판독 (간격 여유 증대)] ---
                with ex_col3:
                    st.markdown("<p style='font-size:0.85em; font-weight:bold; border-bottom:1px solid #9575CD; margin-bottom:5px;'>💡 지표 판독 가이드</p>", unsafe_allow_html=True)
                    
                    def get_guide_row(icon, label, val, status_text, desc, status_color="#FFD54F"):
                        return f"""
                        <div style='display:flex; align-items:center; height:22px; font-size:0.78em; margin-bottom:2px;'>
                            <div style='min-width:130px; font-weight:bold;'>{icon} {label}({val})</div>
                            <div style='margin-left:10px; white-space:nowrap;'>
                                <span style='color:{status_color}; font-weight:bold;'>{status_text}</span>: 
                                <span style='color:black;'>{desc}</span>
                            </div>
                        </div>"""

                    # 1. RSI (과매수/과매도)
                    rsi_st, rsi_desc, rsi_col = ("과매수", "수익실현 고려", "#FF5252") if rsi > 70 else (("과매도", "반등준비", "#448AFF") if rsi < 35 else ("정상", "안정적 추세 진행", "#4DB6AC"))
                    st.markdown(get_guide_row("⚠️", "RSI", f"{int(rsi)}", rsi_st, rsi_desc, rsi_col), unsafe_allow_html=True)

                    # 2. R2 + LRL (추세의 힘과 방향을 동시에 고려한 설명)
                    if r2 > 0.6:
                        r2_st = "강한상승" if is_up_trend else "강한하락"
                        r2_desc = "홀딩 유지 권장" if is_up_trend else "반등 시 매도/탈출 권장"
                        r2_col = "#FF5252" if is_up_trend else "#448AFF"
                    elif r2 < 0.2:
                        r2_st, r2_desc, r2_col = ("횡보/응축", "방향성 상실, 조만간 급변동(상/하) 가능성", "#FFD54F")
                    else:
                        r2_st, r2_desc, r2_col = ("완만한추세", "방향성을 서서히 만들어가는 중", "#888")
                    st.markdown(get_guide_row("📈", "R-SQ", f"{r2:.2f}", r2_st, r2_desc, r2_col), unsafe_allow_html=True)

                    # 3. BB상단 (방패/로켓)
                    if cur_p > bb_up:
                        st.markdown(get_guide_row("🚀", "BB상단", f"{int(bb_up):,}", "상단돌파", "강한 슈팅 구간 진입 (보유자 영역)", "#FF5252"), unsafe_allow_html=True)
                    else:
                        diff = (cur_p/bb_up - 1)*100
                        st.markdown(get_guide_row("🛡️", "BB상단", f"{int(bb_up):,}", "저항확인", f"상단 돌파 시 로켓 전환 ({abs(diff):.1f}% 남음)", "#888"), unsafe_allow_html=True)

                    # 4. LRL (방향성)
                    lrl_diff = (cur_p/lrl - 1)*100
                    lrl_st = "상방추세" if is_up_trend else "하방추세"
                    lrl_col = "#4DB6AC" if is_up_trend else "#448AFF"
                    st.markdown(get_guide_row("🎯", "LRL", f"{int(lrl):,}", lrl_st, f"중심축 대비 {lrl_diff:+.1f}% 위치", lrl_col), unsafe_allow_html=True)

                    # 5. 이평선 (지지/저항)
                    ma_st, ma_desc, ma_col = ("지지", "하방 경직성 확보", "#4DB6AC") if cur_p > row['ma_short'] else ("저항", "상방 돌파 저항 예상", "#FF5252")
                    st.markdown(get_guide_row("📊", "이평선", f"{int(ma_short):,}", ma_st, ma_desc, ma_col), unsafe_allow_html=True)

            # 💡 행 간 구분을 위한 여백 (루프의 마지막)
            st.markdown("<div style='margin-bottom: 2px;'></div>", unsafe_allow_html=True)

    with tab2:
        # 테마별 게이지 바 뷰 (기존 로직 유지)
        theme_perf = df.groupby('주요테마')['change_rate'].mean().sort_values(ascending=False)
        top_themes = theme_perf.index.tolist()
        for i in range(0, len(top_themes), 4):
            t_cols = st.columns(4)
            for idx, theme in enumerate(top_themes[i:i+4]):
                with t_cols[idx]:
                    avg_rate = theme_perf[theme]
                    st.markdown(f"<div class='mint-header'><span>{theme}</span><span style='font-size:0.9em;'>{avg_rate:+.2f}%</span></div>", unsafe_allow_html=True)
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
                            
                            detected_time = row['display_time'].strftime('%H:%M') if pd.notnull(row['display_time']) else "--:--"
                            
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

try:
    # 메인 렌더링 (세션 상태의 데이터를 사용하여 깜빡임 제거)
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    render_dashboard(st.session_state.last_df)
    st.markdown('</div>', unsafe_allow_html=True)

    time.sleep(1) # 1초 대기 후 재실행
    st.rerun()

except RerunException:
    # [수정 부분!!] st.rerun()에 의한 정상적인 재실행은 통과시킴
    raise

except Exception as e:
    # [수정 부분!!] WebSocketClosedError 및 StreamClosedError 방어
    error_msg = str(e)
    if "WebSocketClosedError" in error_msg or "StreamClosedError" in error_msg:
        # 사용자가 창을 닫거나 새로고침할 때 발생하는 에러이므로 로그만 남기고 조용히 처리
        print("ℹ️ 사용자의 연결이 종료되어 대시보드 갱신을 중단합니다.")
    else:
        # 그 외의 진짜 에러는 출력하여 디버깅 가능하게 함
        st.error(f"시스템 오류 발생: {e}")
        print(f"❌ 예기치 못한 통신 오류: {e}")