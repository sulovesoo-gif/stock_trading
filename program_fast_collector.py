# /projects/stock_trading/program_fast_collector.py
import time
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from core.db_client import db
from core.api_helper import kis

KST = ZoneInfo("Asia/Seoul")

# 수집 대상 종목 (삼성전자, SK하이닉스)
TARGET_STOCKS = ["005930", "000660"]

TEST_MODE = False

initialized_stocks = set()

def is_market_open():
    """장 운영 시간 확인 (평일 09:00 ~ 15:30)"""
    now = datetime.now(KST)
    if now.weekday() >= 5: 
        return False
    # start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
    # end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    start_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=20, minute=0, second=0, microsecond=0)
    # return start_time <= now <= end_time
    return True

async def fetch_and_insert():
    now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')

    for code in TARGET_STOCKS:
        res = kis.fetch_program_trade(code, market_div="UN")
        if not res or res.get('rt_cd') != '0':
            continue
            
        output = res.get('output', [])
        if not output:
            continue
            
        item = output[0]

        try:
            # 1. 변동 유무 판단 데이터 추출
            vol_icdc = int(item.get('whol_ntby_vol_icdc', 0))
            amt_icdc = int(item.get('whol_ntby_tr_pbmn_icdc', 0))

            # 2. 최초 1회 실행 유무 확인
            is_first_run = code not in initialized_stocks
            
            # 3. 최초 1회가 아니고, TEST_MODE도 아니며, 변동이 둘 다 0이면 스킵
            if not is_first_run and not TEST_MODE:
                if vol_icdc == 0 and amt_icdc == 0:
                    continue

            print(f"📢 테스트용: {item}")

            # 4. change_type 상태 분류
            if vol_icdc > 0:
                change_type = "PROGRAM_BUY"
            elif vol_icdc < 0:
                change_type = "PROGRAM_SELL"
            else:
                # 거래량 변동은 0인데 대금 변동만 있는 미세 경우 방어 및 NO_CHANGE 처리
                if amt_icdc > 0:
                    change_type = "PROGRAM_BUY"
                elif amt_icdc < 0:
                    change_type = "PROGRAM_SELL"
                else:
                    change_type = "NO_CHANGE"

            # 4. API 영업시간 포맷팅 (HHMMSS -> HH:MM:SS)
            bsop_hour = item.get('bsop_hour', '000000')
            if len(bsop_hour) == 6:
                trade_time = f"{bsop_hour[:2]}:{bsop_hour[2:4]}:{bsop_hour[4:]}"
            else:
                trade_time = "00:00:00"

            price = int(item['stck_prpr'])
            change = int(item['prdy_vrss'])
            if item.get('prdy_vrss_sign') in ['4', '5']:
                change = -change
                # 1: 상한가 (전일 대비 크게 상승)2: 상승 (전일 대비 가격 오름)3: 보합 (전일 가격과 동일)4: 하한가 (전일 대비 크게 하락)5: 하락 (전일 대비 가격 내림)
                
            # 전일 대비율 float 형변환 안전하게 처리
            try:
                ctrt = float(item.get('prdy_ctrt', 0.0))
            except:
                ctrt = 0.0

            sql = """
                INSERT INTO stock_program_trade_history 
                (collect_time, trade_time, stock_code, stock_price, price_change, price_change_rate, 
                 accumulated_volume, sell_volume, buy_volume, net_buy_volume, 
                 sell_amount, buy_amount, net_buy_amount, net_buy_volume_change, net_buy_amount_change, change_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            args = [
                now_str, trade_time, code, price, change, ctrt,
                int(item['acml_vol']), int(item['whol_smtn_seln_vol']), int(item['whol_smtn_shnu_vol']),
                int(item['whol_smtn_ntby_qty']), int(item['whol_smtn_seln_tr_pbmn']), int(item['whol_smtn_shnu_tr_pbmn']),
                int(item['whol_smtn_ntby_tr_pbmn']), vol_icdc, amt_icdc, change_type
            ]
            
            db.execute_query(sql, args)
            if is_first_run:
                initialized_stocks.add(code)
                print(f"🚀 [{datetime.now(KST).strftime('%H:%M:%S')}] {code} 최초 기준 데이터 적재 완료 | {trade_time}")
            else:
                print(f"💾 [{datetime.now(KST).strftime('%H:%M:%S')}] {code} 변동 적재 완료 | {trade_time} | {change_type}")
            
        except Exception as e:
            print(f"❌ 파싱 및 개별 저장 에러 ({code}): {e}")
            continue
            
        except Exception as e:
            print(f"❌ 파싱 및 개별 저장 에러 ({code}): {e}")
            continue

async def main():
    print("⚡ 프로그램 매매 고속 수집기 가동 (대상: 삼성전자, SK하이닉스)")
    while True:
        try:
            if is_market_open():
                start_time = time.time()
                await fetch_and_insert()
                
                # 1초 주기 맞춤 처리 (실행 시간에 따른 미세 조정)
                elapsed = time.time() - start_time
                sleep_time = max(0.0, 1.0 - elapsed)
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(60)
        except Exception as e:
            print(f"❌ 루프 에러: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())