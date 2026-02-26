import time
from core.api_helper import kis
from collector.naver_crawler import sync_naver_themes
from core.db_client import db

def initialize_market_data():
    """
    [전체 초기화 로직]
    1. 네이버 테마/종목 맵핑 수집 (Unknown 이름으로 저장)
    2. 한투 API 마스터 정보를 가져와 실제 종목명 업데이트
    """
    print("=== 🚀 주식 시스템 데이터 초기화 시작 ===")
    
    # Step 1: 네이버 테마 동기화 (다중 테마 지원 로직 포함)
    sync_naver_themes()
    
    # Step 2: 한투 API 인증 및 종목명 동기화
    print("\n🔐 한투 API 인증 및 종목명 업데이트 중...")
    kis.auth()
    master_list = kis.get_stock_master() # 전 종목 리스트 확보
    
    for stock in master_list:
        sql = """
        UPDATE stock_info 
        SET stock_name = %s 
        WHERE stock_code = %s;
        """
        db.execute_query(sql, (stock['name'], stock['code']))
    
    print("\n✅ 모든 기초 데이터(Group A) 수집이 완료되었습니다!")

if __name__ == "__main__":
    initialize_market_data()