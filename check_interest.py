# /projects/stock_trading/check_interest.py
from core.api_helper import kis

def test_interest():
    print("📡 한투 관심종목 그룹[000] 조회를 시작합니다...")
    codes = kis.get_my_interests()
    
    if codes:
        print(f"✅ 현재 구독 예정 종목 ({len(codes)}개): {codes}")
    else:
        print("❌ 종목을 가져오지 못했습니다. API 설정이나 그룹번호를 확인하세요.")

if __name__ == "__main__":
    test_interest()