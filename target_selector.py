import requests
import time
from core.db_client import db
from core.api_helper import kis

def select_target_stocks():
    print("🎯 [타격 범위 확장] 등락률/신고가 포함 랭킹 수집 시작...")
    kis.auth()

    url = f"{kis.base_url}/uapi/domestic-stock/v1/quotations/volume-rank"
    all_targets = {} 

    # 0001: 코스피, 1001: 코스닥
    sectors = {"0001": "코스피", "1001": "코스닥"}
    
    # 확장된 기준: 3(거래대금), 0(평균거래량), 4(등락률상위), 5(신고가)
    criteria = {
        "3": "거래대금", 
        "0": "평균거래량",
        "4": "등락률상위",
        "5": "신고가"
    }

    for s_code, s_name in sectors.items():
        for c_code, c_name in criteria.items():
            print(f"📡 {s_name} - {c_name} 조회 중...")
            
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_COND_SCR_DIV_CODE": "20171",
                "FID_INPUT_ISCD": s_code,
                "FID_DIV_CLS_CODE": "0",
                "FID_BLNG_CLS_CODE": c_code, 
                "FID_TRGT_CLS_CODE": "111111111",
                "FID_TRGT_EXLS_CLS_CODE": "0000000000",
                "FID_INPUT_PRICE_1": "",
                "FID_INPUT_PRICE_2": "",
                "FID_VOL_CNT": "",
                "FID_INPUT_DATE_1": ""
            }
            
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {kis.access_token}",
                "appkey": kis.app_key,
                "appsecret": kis.app_secret,
                "tr_id": "FHPST01710000",
                "custtype": "P"
            }

            try:
                res = requests.get(url, headers=headers, params=params)
                if res.status_code == 200:
                    rank_list = res.json().get('output', [])
                    for item in rank_list:
                        code = item['mksc_shrn_iscd']
                        name = item['hts_kor_isnm']
                        print(f"✅ {name} 등록되었습니다.")
                        # 사유 생성 (예: 코스피 거래대금)
                        # current_reason = f"{s_name} {c_name}"
                        # if code in all_targets:
                        #     # [수정 부분!!] 이미 존재하는 종목이면 사유만 누적 (중복 체크)
                        #     if current_reason not in all_targets[code]['reason']:
                        #         all_targets[code]['reason'] += f", {current_reason}"
                        # else:
                        #     # [수정 부분!!] 처음 발견된 종목이면 이름과 사유를 딕셔너리로 저장
                        #     all_targets[code] = {
                        #         'name': name,
                        #         'reason': current_reason
                        #     }
                            
                        if code not in all_targets:
                            all_targets[code] = {'name': name, 'reason': c_name}
                        else:
                            if c_name not in all_targets[code]['reason']:
                                all_targets[code]['reason'] += f", {c_name}"
                        # 사유 누적
                        # if code in all_targets:
                        #     if c_name not in all_targets[code]:
                        #         all_targets[code] += f", {c_name}"
                        # else:
                        #     all_targets[code] = f"{s_name} {c_name}"
                time.sleep(0.2)
                    
            except Exception as e:
                print(f"❌ {s_name}-{c_name} 조회 오류: {e}")

    if not all_targets:
        print("⚠️ 수집된 종목이 없습니다.")
        return

    # DB 저장 (selected_at 포함)
    conn = db.get_connection()
    try:
        with conn.cursor() as cursor:
            # 기존 후보 삭제
            cursor.execute("DELETE FROM target_candidates")
            
            # 데이터 준비
            insert_data = [(code, reason) for code, reason in all_targets.items()]
            insert_data = [(code, info['name'], info['reason']) for code, info in all_targets.items()]
            
            # selected_at 컬럼을 포함한 쿼리
            # sql = "INSERT INTO target_candidates (stock_code, reason, selected_at) VALUES (%s, %s, NOW())"
            sql = "INSERT INTO target_candidates (stock_code, stock_name, reason, selected_at) VALUES (%s, %s, %s, NOW())"
            cursor.executemany(sql, insert_data)
            
            # live_indicators 초기 레코드 생성 (중복 무시)
            # for code, _ in insert_data:
            #     cursor.execute("INSERT IGNORE INTO live_indicators (stock_code, updated_at) VALUES (%s, NOW())", (code,))

            for code, info in all_targets.items():
                cursor.execute("INSERT IGNORE INTO live_indicators (stock_code, updated_at) VALUES (%s, NOW())", (code,))
            
            conn.commit()
        print(f"✅ 총 {len(insert_data)}개 종목이 'selected_at'과 함께 등록되었습니다.")
    finally:
        conn.close()

if __name__ == "__main__":
    select_target_stocks()