import time
import requests
from datetime import datetime, timedelta
from core.api_helper import kis
from core.db_client import db

def collect_daily_ohlcv_final():
    print("📅 [고속 모드] 일봉 데이터 수집 및 업데이트 시작...")
    kis.auth()

    # 조회 날짜 설정 (시작일: 100일 전, 종료일: 오늘)
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=150)).strftime("%Y%m%d")

    # target_candidates에서 수집 대상 가져오기
    targets = db.execute_query("SELECT stock_code FROM target_candidates")
    
    if not targets:
        print("⚠️ 수집할 대상 종목이 없습니다.")
        return

    for row in targets:
        code = row['stock_code']
        
        # --- [추가된 고속 스킵 로직] ---
        # 해당 종목의 가장 최근 저장 날짜 확인
        last_stored = db.execute_query(
            "SELECT MAX(datetime) as dt FROM market_ohlcv WHERE stock_code=%s", 
            (code,)
        )
        
        if last_stored and last_stored[0]['dt']:
            last_dt = last_stored[0]['dt']
            # 마지막 데이터가 오늘 또는 어제(휴일 고려)라면 수집 건너뜀
            if last_dt.date() >= (datetime.now() - timedelta(days=1)).date():
                print(f"⏩ {code}: 이미 최신 데이터가 존재합니다. (Pass)")
                continue
        # ----------------------------

        url = f"{kis.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {kis.access_token}",
            "appkey": kis.app_key,
            "appsecret": kis.app_secret,
            "tr_id": "FHKST03010100",
            "custtype": "P" # 개인
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": start_date, # 필수: 시작일
            "FID_INPUT_DATE_2": end_date,   # 필수: 종료일
            "FID_PERIOD_DIV_CODE": "D",     # 일봉
            "FID_ORG_ADJ_PRC": "0"          # 0:수정주가 (지표 계산용)
        }

        try:
            res = requests.get(url, headers=headers, params=params)
            if res.status_code == 200:
                data = res.json().get('output2', [])
                if not data:
                    print(f"⚠️ {code}: 응답은 성공했으나 데이터가 없습니다. (메시지: {res_data.get('msg1')})")
                    continue

                inserted_cnt = 0
                for item in data:
                    if not item['stck_bsop_date']: continue
                    raw_date = item['stck_bsop_date']
                    dt = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" 
                    
                    # 중복 키 발생 시 종가만 업데이트하여 데이터 무결성 유지
                    sql = """
                    INSERT INTO market_ohlcv (stock_code, datetime, open, high, low, close, volume, amount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE close = VALUES(close)
                    """
                    db.execute_query(sql, (
                        code, dt, 
                        item['stck_oprc'], item['stck_hgpr'], item['stck_lwpr'], item['stck_clpr'],
                        item['acml_vol'], item['acml_tr_pbmn']
                    ))
                    inserted_cnt += 1
                
                print(f"✅ {code}: {inserted_cnt}개의 일봉 저장 완료")
            else:
                print(f"❌ {code} 에러: {res.status_code}")
                
            time.sleep(0.2) # API 제한 준수

        except Exception as e:
            print(f"❌ {code} 처리 중 오류: {e}")

    print("\n✨ 모든 종목의 데이터 수집 공정이 완료되었습니다.")

if __name__ == "__main__":
    collect_daily_ohlcv_final()