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
    
    return start_time <= now <= end_time
    # return True

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

            # 1. 해당 종목의 당일 직전 상태값 딱 1건 조회
            prev_sql = """
                SELECT trend_group_no, trend_status, running_peak, running_trough, stock_price, trade_time
                FROM stock_program_trade_history
                WHERE stock_code = %s AND DATE(collect_time) = DATE(CONVERT_TZ(NOW(), '+00:00', '+09:00'))
                ORDER BY trade_time DESC, collect_time DESC 
                LIMIT 1
            """
            # 현재 틱의 순매수 대금 (whol_smtn_ntby_tr_pbmn)
            current_net_buy_amount = int(item['whol_smtn_ntby_tr_pbmn'])
            # THRESHOLD = 10000000000  # 100억 원 기준선
            
            # db 객체의 조회 메서드 구조에 맞게 연동 (fetchone 형태)
            prev_row = db.execute_select_one_query(prev_sql, (code)) 

            if not prev_row:
                # 당일 첫 데이터 초기화 (최초 기준선은 100억)
                THRESHOLD = 10000000000
                # 당일 첫 데이터 초기화
                trend_group_no = 1
                trend_status = 'START'
                running_peak = current_net_buy_amount
                running_trough = current_net_buy_amount
                prev_confirmed_price = None
            else:
                # 💡 [핵심 추가] 영업 시간이 직전 데이터와 동일하다면 중복 데이터이므로 스킵
                p_trade_time = prev_row.get('trade_time')
                if p_trade_time and str(p_trade_time) == trade_time:
                    if not TEST_MODE:  # 테스트 모드가 아닐 때만 스킵
                        continue

                # 💡 DictCursor 기반이므로 key로 데이터를 추출하며, int 형변환 및 None 방어 처리 추가
                p_group = prev_row.get('trend_group_no')
                p_status = prev_row.get('trend_status')
                
                # 가이드라인 금액들이 str이나 None으로 넘어올 경우를 대비해 int 변환
                p_peak = int(prev_row.get('running_peak')) if prev_row.get('running_peak') is not None else current_net_buy_amount
                p_trough = int(prev_row.get('running_trough')) if prev_row.get('running_trough') is not None else current_net_buy_amount
                
                # 주가는 float나 DECIMAL일 수 있으므로 int 처리
                p_price = int(prev_row.get('stock_price')) if prev_row.get('stock_price') is not None else price

                # 💡 [체급 계산 로직 수정] 
                # START 상태일 때는 누적 금액 체급에 관계없이, 최초 방향성을 잡기 위해 기본 100억 허들을 적용합니다.
                if p_status == 'START':
                    THRESHOLD = 10000000000  # 기본 100억 고정 (또는 필요에 따라 조절)
                else:
                    # 이미 UP/DOWN 방향이 잡힌 후에는 고점/저점의 절대값 체급에 따라 동적으로 변동
                    check_amount = abs(p_peak) if p_status == 'UP' else abs(p_trough)
                    
                    if check_amount >= 100000000000:
                        THRESHOLD = 100000000000
                    elif check_amount >= 50000000000:
                        THRESHOLD = 50000000000
                    else:
                        THRESHOLD = 10000000000

                # 기본값 유지 설정
                trend_group_no = p_group
                trend_status = p_status
                prev_confirmed_price = None
                
                # 💥 [상승 중] 최고점 대비 100억 이상 하락 시 -> 하락 전환
                if p_status == 'UP' and current_net_buy_amount <= p_peak - THRESHOLD:
                    trend_group_no = p_group + 1
                    trend_status = 'DOWN'
                    # [중요] 새로운 하락 추세를 시작하므로, 현재 금액을 기준으로 최고/최저점 가이드라인을 리셋
                    running_peak = current_net_buy_amount
                    running_trough = current_net_buy_amount
                    # 1그룹이 마무리되는 시점의 주가를 보관 (수익률 계산용)
                    prev_confirmed_price = p_price
                    
                # 💥 [하락 중] 최저점 대비 100억 이상 상승 시 -> 상승 전환
                elif p_status == 'DOWN' and current_net_buy_amount >= p_trough + THRESHOLD:
                    trend_group_no = p_group + 1
                    trend_status = 'UP'
                    # [중요] 새로운 상승 추세를 시작하므로, 현재 금액을 기준으로 최고/최저점 가이드라인을 리셋
                    running_peak = current_net_buy_amount
                    running_trough = current_net_buy_amount
                    # 직전 그룹이 마무리되는 시점의 주가를 보관
                    prev_confirmed_price = p_price
                    
                # 💥 [START 상태] 최초 100억 기준 방향성 확정
                elif p_status == 'START':
                    running_peak = max(p_peak, current_net_buy_amount)
                    running_trough = min(p_trough, current_net_buy_amount)
                    if current_net_buy_amount >= p_peak + THRESHOLD:
                        trend_status = 'UP'
                        running_peak = current_net_buy_amount
                        running_trough = current_net_buy_amount
                    elif current_net_buy_amount <= p_trough - THRESHOLD:
                        trend_status = 'DOWN'
                        running_peak = current_net_buy_amount
                        running_trough = current_net_buy_amount
                
                # 💥 [추세 유지] 가이드라인 갱신
                else:
                    running_peak = max(p_peak, current_net_buy_amount)
                    running_trough = min(p_trough, current_net_buy_amount)
            # --------------------------------------------------

            # 기존 INSERT문에 새로 정의한 5개 컬럼 추가
            sql = """
                INSERT INTO stock_program_trade_history 
                (collect_time, trade_time, stock_code, stock_price, price_change, price_change_rate, 
                 accumulated_volume, sell_volume, buy_volume, net_buy_volume, 
                 sell_amount, buy_amount, net_buy_amount, net_buy_volume_change, net_buy_amount_change, change_type,
                 trend_group_no, trend_status, running_peak, running_trough, prev_confirmed_price, target_threshold)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            # 기존 args 배열 뒤에 가공한 변수 5개 그대로 병합
            args = [
                now_str, trade_time, code, price, change, ctrt,
                int(item['acml_vol']), int(item['whol_smtn_seln_vol']), int(item['whol_smtn_shnu_vol']),
                int(item['whol_smtn_ntby_qty']), int(item['whol_smtn_seln_tr_pbmn']), int(item['whol_smtn_shnu_tr_pbmn']),
                current_net_buy_amount, vol_icdc, amt_icdc, change_type,
                trend_group_no, trend_status, running_peak, running_trough, prev_confirmed_price, THRESHOLD
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