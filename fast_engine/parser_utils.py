def parse_domestic_tick(raw_str):
    """[국내주식] 실시간 체결가 파싱 (H0STCNT0)"""
    try:
        parts = raw_str.split('|')
        fields = parts[3].split('^')
        return {
            "type": "TICK",
            "code": fields[0],
            "price": int(fields[2]),
            "change": int(fields[4]),
            "rate": float(fields[5]),
            "volume": int(fields[12]),
            "strength": float(fields[15]),
            "market": "KR"
        }
    except: return None

def parse_domestic_orderbook(raw_str):
    """[국내주식] 실시간 호가 파싱 (H0STASP0)"""
    try:
        parts = raw_str.split('|')
        fields = parts[3].split('^')
        return {
            "type": "ORDERBOOK",
            "code": fields[0],
            "bid": fields[3], "ask": fields[23],
            "bid_vol": fields[13], "ask_vol": fields[33],
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

def parse_overseas_orderbook(raw_str):
    """[해외주식] 실시간 호가 파싱 (HDFSASP0)"""
    try:
        parts = raw_str.split('|')
        fields = parts[3].split('^')
        return {
            "type": "ORDERBOOK",
            "code": fields[1],
            "bid": fields[11], "ask": fields[12],
            "market": "US"
        }
    except: return None

def parse_data(message):
    if 'H0STCNT0' in message: return parse_domestic_tick(message)
    if 'H0STASP0' in message: return parse_domestic_orderbook(message)
    if 'HDFSCNT0' in message: return parse_overseas_tick(message)
    if 'HDFSASP0' in message: return parse_overseas_orderbook(message)
    return None