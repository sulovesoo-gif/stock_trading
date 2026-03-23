def parse_domestic_tick(raw_str):
    """[국내주식] 실시간 체결가 파싱 (H0UNCNT0[KRX/NXT 통합], H0STCNT0[KRX])"""
    try:
        parts = raw_str.split('|')
        fields = parts[3].split('^')
        return {
            "type": "TICK",
            "code": fields[0],
            "price": int(fields[2]),
            "change": int(fields[4]),
            "rate": float(fields[5]),
            "volume": int(fields[12]),       # 실시간 체결량(CNTG_VOL)
            "accum_volume": int(fields[13]), # 누적 거래량
            "strength": float(fields[18]),   # 체결강도
            "side": fields[21],              # 매도매수구분
            "vi_standard": int(fields[45]) if fields[45] else 0, # [추가] 정적VI발동기준가
            "market": "KR"
        }
    except Exception as e:
        print(f"❌ 파싱 에러 ({fields[0] if 'fields' in locals() else 'unknown'}): {e}")
        return None

def parse_domestic_hoka(raw_str):
    """[국내주식] 실시간 호가 파싱 (H0UNASP0)"""
    try:
        parts = raw_str.split('|')
        fields = parts[3].split('^')
        return {
            "type": "HOKA",
            "code": fields[0],
            "ask": fields[3],           # 매도호가1
            "ask_vol": fields[23],      # 매도호가 잔량1
            "bid": fields[13],          # 매수호가1
            "bid_vol": fields[33],      # 매수호가 잔량1
            "total_ask_vol": fields[43],  # 총 매도호가 잔량
            "total_bid_vol": fields[44],  # 총 매수호가 잔량,
            "market": "KR"
        }
    except: return None

def parse_overseas_tick(raw_str):
    """[해외주식] 실시간 체결가 파싱 (HDFSCNT0)"""
    try:
        parts = raw_str.split('|')
        fields = parts[3].split('^')
        return {
            "type": "TICK",
            "code": fields[1],
            "price": float(fields[11]),
            "change": float(fields[14]),
            "rate": float(fields[15]),
            "volume": int(fields[18]),
            "market": "US"
        }
    except: return None

def parse_overseas_hoka(raw_str):
    """[해외주식] 실시간 호가 파싱 (HDFSASP0)"""
    try:
        parts = raw_str.split('|')
        fields = parts[3].split('^')
        return {
            "type": "HOKA",
            "code": fields[1],
            "bid": fields[11], "ask": fields[12],
            "market": "US"
        }
    except: return None

def parse_futures_tick(raw_str):
    """[지수선물] 실시간 체결가 파싱 (H0IFCNT0)"""
    try:
        parts = raw_str.split('|')
        fields = parts[3].split('^')
        return {
            "type": "FUTURES_TICK",
            "code": fields[0],           # 0: 종목코드
            "price": float(fields[5]),   # 5: 현재가 (FTRS_PRPR)
            "change": float(fields[2]),  # 2: 전일대비 (PRDY_VRSS)
            "rate": float(fields[4]),    # 4: 대비율 (FTRS_PRDY_CTRT)
            "volume": int(fields[9]),    # 9: 최종 체결량 (LAST_CNQN)
            "market": "KR_FUT"
        }
    except: return None
    
def parse_data(message):
    if 'H0UNCNT0' in message or 'H0STCNT0' in message or 'H0NXCNT0' in message or 'H0STOUP0' in message: return parse_domestic_tick(message)
    if 'H0UNASP0' in message or 'H0STASP0' in message or 'H0NXASP0' in message or 'H0STOAA0' in message: return parse_domestic_hoka(message)
    if 'HDFSCNT0' in message: return parse_overseas_tick(message)
    if 'HDFSASP0' in message: return parse_overseas_hoka(message)
    if "H0IFCNT0" in message: return parse_futures_tick(message)
    return None