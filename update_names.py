import time
from core.api_helper import kis
from core.db_client import db

def update_unknown_stock_names():
    """
    stock_info 테이블에서 stock_name이 'Unknown'인 종목들을 찾아
    한투 API를 통해 실제 종목명으로 업데이트합니다.
    """
    print("🔍 이름이 'Unknown'인 종목 조회 중...")
    
    # 1. 이름이 Unknown인 종목 코드 리스트 가져오기
    select_sql = "SELECT stock_code FROM stock_info WHERE stock_name = 'Unknown';"
    unknown_stocks = db.execute_query(select_sql)
    
    if not unknown_stocks:
        print("✅ 업데이트할 'Unknown' 종목이 없습니다.")
        return

    print(f"📦 총 {len(unknown_stocks)}개의 종목을 업데이트합니다.")
    
    # 2. 한투 API 인증 (토큰 발급)
    kis.auth()
    
    success_count = 0
    for stock in unknown_stocks:
        code = stock['stock_code']
        
        try:
            # 한투 API로 종목명 조회
            real_name = kis.get_stock_name(code)
            
            if real_name:
                # DB 업데이트
                update_sql = "UPDATE stock_info SET stock_name = %s WHERE stock_code = %s;"
                db.execute_query(update_sql, (real_name, code))
                print(f"✅ 업데이트 완료: {code} -> {real_name}")
                success_count += 1
            else:
                print(f"⚠️ {code}: API에서 이름을 찾을 수 없습니다.")
            
            # API 과부하 방지를 위한 미세 대기 (초당 5건 제한 등 대비)
            time.sleep(0.1)
            
        except Exception as e:
            print(f"❌ {code} 처리 중 오류 발생: {e}")

    print(f"\n✨ 작업 완료! (성공: {success_count}/{len(unknown_stocks)})")

if __name__ == "__main__":
    update_unknown_stock_names()
