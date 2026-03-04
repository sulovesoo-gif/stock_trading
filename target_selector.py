import requests
import time
from core.db_client import db
from core.api_helper import kis

def select_target_stocks():
    print("🎯 [타격 범위 확장] 등락률/신고가 포함 랭킹 수집 시작...")
    kis.auth()

    url = f"{kis.base_url}/uapi/domestic-stock/v1/quotations/volume-rank"
    all_targets = {} 

    sectors = {"0000": "전체시장"}
    criteria = {
        "0": "평균거래량",
        "3": "거래대금", 
        "4": "등락률상위",
        "5": "신고가" #이건 없는 코드다!!!!!!!!!!!!!!!!!!!!!!
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
                        # 상장주식수 안전하게 정수 변환
                        total_shares = int(item.get('lstn_stcn', 0))
                        
                        if code not in all_targets:
                            all_targets[code] = {'name': name, 'reason': c_name, 'total_shares': total_shares}
                        else:
                            if c_name not in all_targets[code]['reason']:
                                all_targets[code]['reason'] += f", {c_name}"
                time.sleep(0.2)
            except Exception as e:
                print(f"❌ {s_name}-{c_name} 조회 오류: {e}")

    print("📥 내 포트폴리오 데이터를 분석 대상에 병합 중...")
    conn = db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT stock_code, stock_name, reason, total_shares FROM my_portfolio")
            portfolio_rows = cursor.fetchall()
            
            for p_code, p_name, p_reason, p_shares in portfolio_rows:
                if p_code in all_targets:
                    if "[포트폴리오]" not in all_targets[p_code]['reason']:
                        all_targets[p_code]['reason'] = f"{all_targets[p_code]['reason']} [포트폴리오]"
                else:
                    all_targets[p_code] = {'name': p_name, 'reason': f"{p_reason} [포트폴리오]", 'total_shares': p_shares if p_shares else 0 }
    finally:
        # 첫 번째 DB 연결 해제
        conn.close()

    # 데이터가 없으면 여기서 종료
    if not all_targets:
        print("⚠️ 수집된 종목이 없습니다.")
        return

    # 두 번째 DB 연결: 데이터 저장 시작
    conn = db.get_connection()
    try:
        with conn.cursor() as cursor:
            # 기존 후보 삭제
            cursor.execute("DELETE FROM target_candidates")

            # target_candidates 저장용 리스트 생성
            insert_data = [(code, info['name'], info['reason']) for code, info in all_targets.items()]
            sql_cand = "INSERT INTO target_candidates (stock_code, stock_name, reason, selected_at) VALUES (%s, %s, %s, NOW())"
            cursor.executemany(sql_cand, insert_data)

            # live_indicators 업데이트 (t_shares 오타 수정 완료)
            for code, info in all_targets.items():
                t_shares = info.get('total_shares', 0)
                sql_live = """
                INSERT INTO live_indicators (stock_code, total_shares, updated_at) 
                VALUES (%s, %s, NOW())
                ON DUPLICATE KEY UPDATE 
                    total_shares = VALUES(total_shares),
                    updated_at = NOW()
                """
                cursor.execute(sql_live, (code, t_shares))

            conn.commit()
            print(f"✅ 총 {len(insert_data)}개 종목 업데이트 완료.")
    except Exception as e:
        print(f"❌ DB 저장 중 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    select_target_stocks()