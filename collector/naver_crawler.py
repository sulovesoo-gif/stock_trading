import requests
from bs4 import BeautifulSoup
import time
from core.db_client import db

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
    """최종 실행 함수: 테마 정보를 긁어서 stock_info에 업데이트"""
    print("🚀 네이버 테마 동기화 시작...")
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