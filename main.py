import sys
import os
from target_selector import select_target_stocks
from collector.price_collector import collect_daily_ohlcv_final
from collector.naver_crawler import sync_naver_themes
from update_names import update_unknown_stock_names

def run_hourly_batch():
    print(f"⏰ 정기 업데이트 시작...")
    
    # 1. 새로운 테마/급등주가 있을 수 있으니 동기화
    sync_naver_themes()
    update_unknown_stock_names()
    
    # 2. 거래량/거래대금 랭킹 기반 감시 대상 재선정 (매 시간 새로운 급등주 포착)
    select_target_stocks()
    
    # 3. 새로 선정된 종목들의 지표 계산용 일봉 데이터 수집
    collect_daily_ohlcv_final()
    
    print("✅ 정기 업데이트 완료")

if __name__ == "__main__":
    run_hourly_batch()