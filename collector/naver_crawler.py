import requests
from bs4 import BeautifulSoup
import time
from core.db_client import db

# [추가 부분!!] 업종(Sector) 정보를 먼저 수집하는 함수
def get_all_sectors():
    """네이버 금융 업종별 시세 페이지에서 업종명과 해당 종목 리스트 수집"""
    sectors = []
    url = "https://finance.naver.com/sise/sise_group.naver?type=group"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # 업종 링크 추출
    sector_elements = soup.select('td a')
    for el in sector_elements:
        if '/sise/sise_group_detail.naver?type=group' in el['href']:
            sectors.append({
                'name': el.text,
                'link': 'https://finance.naver.com' + el['href']
            })
    return sectors

def get_all_themes():
    """네이버 금융 테마 전체 리스트와 URL 수집"""
    themes = []
    # 테마 목록은 보통 1~7페이지 정도 존재함
    for page in range(1, 8):
        url = f"https://finance.naver.com/sise/theme.naver?&page={page}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 테마명과 상세 링크 추출
        theme_elements = soup.select('.col_type1 a')
        if not theme_elements:
            break
            
        for el in theme_elements:
            themes.append({
                'name': el.text,
                'link': 'https://finance.naver.com' + el['href']
            })
        time.sleep(0.3) # 매너 대기
    return themes

def get_stocks_in_theme(theme_link):
    """특정 테마 페이지에 접속하여 포함된 종목코드 리스트 추출"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(theme_link, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    stocks = []
    # 종목 코드 추출 (보통 /item/main.naver?code=005930 형태)
    stock_elements = soup.select('.name_area a')
    for el in stock_elements:
        code = el['href'].split('=')[-1]
        stocks.append(code)
    return stocks

def sync_naver_themes():
    """최종 실행 함수: 업종(Sector)과 테마(Theme) 정보를 모두 업데이트"""
    print("🚀 네이버 업종/테마 동기화 시작...")
    
    # 1. 업종(Sector) 동기화 먼저 진행
    all_sectors = get_all_sectors()
    for sector in all_sectors:
        print(f"🏢 업종 분석 중: {sector['name']}")
        stock_codes = get_stocks_in_theme(sector['link']) # 종목 추출 로직은 동일하게 재사용
        for code in stock_codes:
            # [수정 부분!!] sector 컬럼 업데이트 (중복 방지 및 누적)
            sql = """
            INSERT INTO stock_info (stock_code, stock_name, sector)
            VALUES (%s, 'Unknown', %s)
            ON DUPLICATE KEY UPDATE 
            sector = VALUES(sector), -- 업종은 보통 하나이므로 덮어쓰기
            updated_at = NOW();
            """
            db.execute_query(sql, (code, sector['name']))
        time.sleep(0.1)
    
    # 2. 테마(Theme) 동기화 (기존 로직 유지)
    all_themes = get_all_themes()
    for theme in all_themes:
        print(f"📂 테마 분석 중: {theme['name']}")
        stock_codes = get_stocks_in_theme(theme['link'])
        
        # stock_info 테이블의 theme 컬럼 업데이트
        # 여러 테마에 속할 경우 콤마(,)로 구분하여 누적
        for code in stock_codes:
            sql = """
            INSERT INTO stock_info (stock_code, stock_name, theme)
            VALUES (%s, 'Unknown', %s)
            ON DUPLICATE KEY UPDATE 
            theme = CASE 
                WHEN theme IS NULL OR theme = '' THEN VALUES(theme)
                WHEN theme LIKE CONCAT('%%', VALUES(theme), '%%') THEN theme
                ELSE CONCAT(theme, ', ', VALUES(theme))
            END,
            updated_at = NOW();
            """
            db.execute_query(sql, (code, theme['name']))
            
    print("✅ 모든 테마 및 종목 매핑 완료!")

if __name__ == "__main__":
    sync_naver_themes()