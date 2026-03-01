import streamlit as st
import urllib.parse

# 정적 리소스 로딩 최적화 (가장 위에서 실행)
st.markdown("""
    <style>
        /* 폰트 로딩 대기 방지 */
        * { font-family: 'sans-serif' !important; }
        div[data-testid="stToolbar"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# 1. 페이지 설정 및 사이드바 제거 (팝업용 유지)
st.set_page_config(page_title="전략 분석", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
        /* 사이드바 및 헤더 제거 */
        [data-testid="stSidebar"], [data-testid="stSidebarNav"] { display: none !important; }
        section[data-testid="stSidebar"] + section { margin-left: 0 !important; }
        header { visibility: hidden; height: 0px; }
        footer { visibility: hidden; }

        /* 상/하단 여백(Padding) 강제 제거 */
        .main .block-container {
            padding-top: 1rem !important;    /* 상단 여백 최소화 */
            padding-bottom: 0px !important;   /* [이부분 추가!!] 하단 여백 완전 제거 */
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
            max-width: 100% !important;
        }

        [data-testid="stHeader"] {
            display: none !important;
        }
        
        /* 팝업 전용: 컨텐츠 최상단 밀착 */
        div.block-container {
            padding-top: 1.5rem !important; 
        }
    </style>
""", unsafe_allow_html=True)

# 2. 파라미터 수신 (캐싱 및 불필요한 객체 생성 방지)
p = st.query_params.to_dict()

stock_name = p.get("name", "N/A")
stock_code = p.get("code", "")
# 데이터가 없을 경우를 대비해 기본값 처리
try:
    rsi = int(p.get("rsi", 0))
    r2 = float(p.get("r2", 0))
    lrl = int(p.get("lrl", 0))
    bb_up = int(p.get("bb", 0))
    cur_p = int(p.get("cur", 0))
    ma_short = int(p.get("ma", 0))
    f_net = int(p.get("f_net", 0))
    i_net = int(p.get("i_net", 0))
    vp_raw = p.get("vp", "")
    bb_low = int(p.get("bb_low", 0)) # 파라미터 누락 대비
except:
    st.write("Loading...")
    st.stop()

sig_display = urllib.parse.unquote(p.get("sig", ""))
theme = urllib.parse.unquote(p.get("theme", ""))

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
expander_title = f"📊 {stock_name}({stock_code}) 전략분석  |  {total_sig}"

# --- [상단 타이틀: 원본 expander_title 형식 복제] ---
# 📊 종목명(코드) 전략분석 | 🚀 시그널명
st.markdown(f"""
    <div style='font-size: 19px; font-weight: bold; padding-bottom: 12px; border-bottom: 1px solid #eee; margin-bottom: 20px;'>
        {expander_title}
    </div>
""", unsafe_allow_html=True)

# 원본과 동일한 컬럼 비율 [0.8, 1.2, 2.0]
ex_col1, ex_col2, ex_col3 = st.columns([0.8, 1.2, 2.0])

# --- [1. 실시간 수급: 원본 소스 로직 100% 복제] ---
with ex_col1:
    st.markdown("<p style='font-size:0.85em; font-weight:bold; border-bottom:1px solid #4DB6AC; margin-bottom:5px;'>👥 수급 현황</p>", unsafe_allow_html=True)
    f_color = "#FF5252" if f_net > 0 else "#448AFF"
    i_color = "#FF5252" if i_net > 0 else "#448AFF"
    f_badge = "<span style='background:#FF5252; color:white; padding:1px 4px; border-radius:3px; font-size:0.7em; font-weight:bold; margin-left:3px;'>👽 외인매집</span>" if f_net > 0 else ""
    
    st.markdown(f"""<div style='font-size:0.82em; line-height:1.8;'>
            외인: <span style='color:{f_color}; font-weight:bold;'>{f_net:,}</span> {f_badge}<br>
            기관: <span style='color:{i_color}; font-weight:bold;'>{i_net:,}</span></div>
    """, unsafe_allow_html=True)

# --- [2. 주요 매물대: 원본 소스 로직 100% 복제] ---
with ex_col2:
    st.markdown("<p style='font-size:0.85em; font-weight:bold; border-bottom:1px solid #FFD54F; margin-bottom:5px;'>🧱 핵심 매물대</p>", unsafe_allow_html=True)
    if vp_raw:
        try:
            vp_html = ""
            for item in vp_raw.split("|"):
                price, ratio = item.split(":")
                r_val = float(ratio)
                bar_color = "#FF5252" if r_val > 15 else "#4DB6AC"
                vp_html += f"""<div style="display:flex; align-items:center; height:22px; margin-bottom:2px;">
                    <div style="width:50px; font-size:10px; color:#aaa; text-align:right; margin-right:5px;">{int(price):,}</div>
                    <div style="flex-grow:1; background:#f0f0f0; height:8px; border-radius:2px;">
                        <div style="width:{r_val}%; background:{bar_color}; height:100%; border-radius:2px;"></div>
                    </div>
                    <div style="width:30px; font-size:9px; color:#888; margin-left:5px;">{r_val:.0f}%</div>
                </div>"""
            st.markdown(vp_html, unsafe_allow_html=True)
        except: pass

# --- [3. 실시간 지표 판독: 원본 소스 로직 100% 복제] ---
with ex_col3:
    st.markdown("<p style='font-size:0.85em; font-weight:bold; border-bottom:1px solid #9575CD; margin-bottom:5px;'>💡 지표 판독 가이드</p>", unsafe_allow_html=True)
    
    def get_guide_row(icon, label, val, status_text, desc, status_color="#FFD54F"):
        # f-string 최적화
        return f"""<div style='display:flex; align-items:center; height:22px; font-size:0.78em; margin-bottom:2px;'>
            <div style='min-width:130px; font-weight:bold;'>{icon} {label}({val})</div>
            <div style='margin-left:10px; white-space:nowrap;'>
                <span style='color:{status_color}; font-weight:bold;'>{status_text}</span>: 
                <span style='color:black;'>{desc}</span>
            </div>
        </div>"""

    # 1. RSI
    rsi_st, rsi_desc, rsi_col = ("과매수", "수익실현 고려", "#FF5252") if rsi > 70 else (("과매도", "반등준비", "#448AFF") if rsi < 33 else ("정상", "안정적 추세 진행", "#4DB6AC"))
    st.markdown(get_guide_row("⚠️", "RSI", f"{int(rsi)}", rsi_st, rsi_desc, rsi_col), unsafe_allow_html=True)

    # 2. R2 + LRL
    if r2 > 0.6:
        r2_st = "강한상승" if is_up_trend else "강한하락"
        r2_desc = "홀딩 유지 권장" if is_up_trend else "반등 시 매도/탈출 권장"
        r2_col = "#FF5252" if is_up_trend else "#448AFF"
    elif r2 < 0.2:
        r2_st, r2_desc, r2_col = ("횡보/응축", "방향성 상실, 조만간 급변동(상/하) 가능성", "#FFD54F")
    else:
        r2_st, r2_desc, r2_col = ("완만한추세", "방향성을 서서히 만들어가는 중", "#888")
    st.markdown(get_guide_row("📈", "R-SQ", f"{r2:.2f}", r2_st, r2_desc, r2_col), unsafe_allow_html=True)

    # 3. BB상단
    if cur_p > bb_up:
        st.markdown(get_guide_row("🚀", "BB상단", f"{bb_up:,}", "상단돌파", "강한 슈팅 구간 진입 (보유자 영역)", "#FF5252"), unsafe_allow_html=True)
    else:
        diff = (cur_p/bb_up - 1)*100
        st.markdown(get_guide_row("🛡️", "BB상단", f"{bb_up:,}", "저항확인", f"상단 돌파 시 로켓 전환 ({abs(diff):.1f}% 남음)", "#888"), unsafe_allow_html=True)

    # 4. LRL
    lrl_diff = (cur_p/lrl - 1)*100
    lrl_st = "상방추세" if is_up_trend else "하방추세"
    lrl_col = "#4DB6AC" if is_up_trend else "#448AFF"
    st.markdown(get_guide_row("🎯", "LRL", f"{lrl:,}", lrl_st, f"중심축 대비 {lrl_diff:+.1f}% 위치", lrl_col), unsafe_allow_html=True)

    # 5. 이평선
    ma_st, ma_desc, ma_col = ("지지", "하방 경직성 확보", "#4DB6AC") if cur_p > ma_short else ("저항", "상방 돌파 저항 예상", "#FF5252")
    st.markdown(get_guide_row("📊", "이평선", f"{ma_short:,}", ma_st, ma_desc, ma_col), unsafe_allow_html=True)