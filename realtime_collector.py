import time
from datetime import datetime
from core.db_client import db
from core.api_helper import kis
import requests

def is_market_open():
    """장 운영 시간 확인 (09:00 ~ 15:30, 주말 제외)"""
    now = datetime.now()
    if now.weekday() >= 5:  # 토, 일
        return False
    start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return start_time <= now <= end_time

def get_current_price(code):
    """한투 API를 이용한 현재가 조회 (실제 시세 데이터)"""
    url = f"{kis.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {kis.access_token}",
        "appkey": kis.app_key,
        "appsecret": kis.app_secret,
        "tr_id": "FHKST01010100"
    }
    params = {
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": code
    }
    res = requests.get(url, headers=headers, params=params)
    if res.status_code == 200:
        return res.json().get('output', {})
    return None

def collect_realtime_data():
    print("🚀 실시간 데이터 수집 엔진 가동 준비... (출근 모드)")
    kis.auth()
    
    while True:
        conn = None
        try:
            # 장 운영 시간 확인
            if not is_market_open():
                now_str = datetime.now().strftime('%H:%M:%S')
                print(f"💤 [{now_str}] 장외 시간입니다. 대기 중...")
                time.sleep(60)
                continue

            # 매 루프마다 DB 조회를 하지 않도록 최적화 가능하나, 타겟 변경 반영을 위해 유지하되
            # 커넥션 관리를 위해 execute_query 대신 직접 커서 사용
            conn = db.get_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT stock_code FROM target_candidates")
                targets = cursor.fetchall()

            if not targets:
                print("⚠️ 감시 대상이 없습니다. target_selector를 확인하세요.")
                time.sleep(30)
                continue

            print(f"📊 {len(targets)}개 종목 수집 시작!")

            for t in targets:
                code = t['stock_code']
                kis.auth() # 토큰 만료 체크 및 갱신
                price_info = get_current_price(code)
                
                if price_info and 'stck_prpr' in price_info:
                    last_price = int(price_info.get('stck_prpr', 0))
                    change_rate = float(price_info.get('prdy_ctrt', 0))
                    
                    sql = """
                    INSERT INTO live_indicators (stock_code, last_price, change_rate, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE 
                    last_price = VALUES(last_price),
                    change_rate = VALUES(change_rate),
                    updated_at = NOW();
                    """
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute(sql, (code, last_price, change_rate))
                            conn.commit()
                        print(f"📡 {code}: {last_price}원 ({change_rate}%)")
                    except Exception as db_e:
                        print(f"⚠️ DB 저장 오류 ({code}): {db_e}")
                
                time.sleep(0.2) # 초당 5건 제한 준수

        except Exception as e:
            print(f"❌ 오류 발생(자동 재시도): {e}")
            time.sleep(10) # 에러 시 잠시 대기 후 부활
        finally:
            if conn: conn.close()

if __name__ == "__main__":
    collect_realtime_data()