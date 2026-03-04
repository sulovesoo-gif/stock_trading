import requests
import json
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

KST = ZoneInfo("Asia/Seoul")
load_dotenv()

class KISApiHelper:
    def __init__(self):
        self.base_url = "https://openapi.koreainvestment.com:9443" # 실전 서버
        self.app_key = os.getenv('KIS_API_KEY')
        self.app_secret = os.getenv('KIS_API_SECRET')
        self.access_token = ""
        self.token_expired_at = datetime.now(KST)

    def auth(self):
        """접근 토큰 발급 (유효기간 확인 후 재발급)"""
        # 토큰이 있고 만료 전(여유시간 1분)이면 기존 토큰 반환
        if self.access_token and datetime.now(KST) < self.token_expired_at - timedelta(minutes=1):
            return self.access_token

        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        res = requests.post(url, headers=headers, json=body)
        res.raise_for_status()
        data = res.json()
        
        self.access_token = data['access_token']
        # 만료 시간 설정 (보통 86400초)
        self.token_expired_at = datetime.now(KST) + timedelta(seconds=int(data.get('expires_in', 0)))
        return self.access_token

    def get_stock_name(self, stock_code):
        """종목코드로 종목명 조회 (단건 API 활용 - 초기화용)"""
        self.auth()
            
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/search-info"
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "CTPF1604R" # 종목정보 조회 TR
        }
        params = {
            "PDNO": stock_code,
            "PRDT_TYPE_CD": "300" # 주식
        }
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            data = res.json()
            return data['output']['prdt_abrv_name'] # 종목 약명
        return None

    def get_multi_prices_30(self, code_list):
        """
        [국내주식-205] 관심종목(멀티종목) 시세조회 명세 기준 최종 교정
        - URL: /uapi/domestic-stock/v1/quotations/intstock-multprice
        - TR ID: FHKST11300006
        - 특징: FID_INPUT_ISCD_1~30 방식으로 30개 종목 일괄 시세 리턴
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/intstock-multprice"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST11300006", # 사용자님이 찾으신 명세 ID
            "custtype": "P"
        }
        
        # Query Parameters 구성 (1~30번 나열)
        params = {}
        for i, code in enumerate(code_list[:30]):
            idx = i + 1
            params[f"FID_COND_MRKT_DIV_CODE_{idx}"] = "J"
            params[f"FID_INPUT_ISCD_{idx}"] = code

        try:
            res = requests.get(url, headers=headers, params=params)
            if res.status_code == 200:
                res_data = res.json()
                # [응답 필드 매핑] 명세서상 현재가는 'inter2_prpr' 등의 이름을 가질 수 있음
                # 일단 전체 데이터를 반환하여 collector에서 처리하게 함
                return res_data
            else:
                print(f"⚠️ [205] API 에러: {res.status_code} ({res.text})")
                return None
        except Exception as e:
            print(f"❌ [205] API 통신 에러: {e}")
            return None
            
    def get_multi_prices(self, code_list):
        """최대 50개 종목의 현재가를 한 번에 조회 (HHKST03010101)"""
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-multi-price"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "HHKST03010101", "custtype": "P"
        }
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ",".join(code_list)}

        try:
            res = requests.get(url, headers=headers, params=params)
            
            # [수정 포인트] 응답 상태 코드가 200(성공)이고 내용이 있을 때만 JSON 변환
            if res.status_code == 200 and res.text:
                return res.json().get('output', [])
            else:
                print(f"⚠️ API 서버 응답 비정상 (상태코드: {res.status_code})")
                return []
                
        except Exception as e:
            print(f"❌ 복수 종목 조회 API 통신 에러: {e}")
            return []

    def get_investor_trade_data(self, code):
        """
        [수정] 종목별 외국인/기관 순매수 수량(5일 누적) 수집
        참고: get_multi_prices의 인증 및 에러 처리 구조 적용
        """
        self.auth() # 토큰 유효성 체크
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily"
        today_str = datetime.now().strftime("%Y%m%d")
        
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHPTJ04160001",
            "custtype": "P"
        }

        # FID_ORG_ADJ_PRC와 FID_ETC_CLS_CODE는 공백보다 '0'과 '00'이 안정적입니다.
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": today_str,
            "FID_ORG_ADJ_PRC": "0",
            "FID_ETC_CLS_CODE": "00"
        }

        try:
            res = requests.get(url, headers=headers, params=params)
            
            if res.status_code == 200 and res.text:
                data = res.json()
                output2 = data.get('output2', [])
                
                if not output2:
                    print(f"⚠️ [수급] {code} 응답 성공했으나 데이터(output2)가 비어있음")
                    return None
                    
                # 1️⃣ 오늘(최신) 데이터 1개만 가져오기
                today_data = output2[0] 
                
                # 2️⃣ 오늘 날짜의 거래량/거래대금만 추출 (단위 케어)
                # ※ 주의: 거래대금은 백만원 단위이므로 필요시 계산
                volume = int(today_data.get('acml_vol', 0))
                amount = int(today_data.get('acml_tr_pbmn', 0))
                
                # 최근 5일치 순매수량 합산
                recent_5 = output2[:5]
                f_net = sum(int(day.get('frgn_ntby_qty', 0)) for day in recent_5)
                i_net = sum(int(day.get('orgn_ntby_qty', 0)) for day in recent_5)
                
                print(f"📡 [API] {code} 수급 수신 완료 (외인:{f_net}/기관:{i_net})")
                return {
                    'foreign_net_5d': f_net,
                    'institution_net_5d': i_net,
                    'volume': volume,
                    'amount': amount
                }
            else:
                print(f"⚠️ [수급] API 서버 응답 비정상 (상태코드: {res.status_code})")
                return None
        except Exception as e:
            print(f"❌ [수급] API 통신 에러 ({code}): {e}")
            return None

    def get_price_volume_profile(self, code):
        """
        [최종 수정] 국내주식 매물대/거래비중 수집 (TR: FHPST01130000)
        명세서의 필수 파라미터(FID_COND_SCR_DIV_CODE, FID_INPUT_HOUR_1) 반영
        """
        self.auth()
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/pbar-tratio"
        
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHPST01130000",
            "custtype": "P"
        }
        
        # 명세서 기준 필수 파라미터 교정
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_COND_SCR_DIV_CODE": "20113", # 명세서 필수: 조건화면분류코드
            "FID_INPUT_HOUR_1": ""             # 명세서 필수: 입력시간1 (공백 전달)
        }

        try:
            res = requests.get(url, headers=headers, params=params)
            
            if res.status_code == 200 and res.text:
                data = res.json()

                # output = data.get('output2') if data.get('output2') else data.get('output', [])
                output = data.get('output2', [])
                
                if not output:
                    print(f"⚠️ [매물대] {code} 응답 성공했으나 데이터가 비어있음 (msg1: {data.get('msg1')})")
                    return None
                
                # 비중 높은 상위 5개 추출 (acml_vol_rlim: 누적거래량비중)
                try:
                    # 1. 먼저 '비중(acml_vol_rlim)'이 높은 순으로 정렬해서 상위 5개를 추출합니다.
                    # (시장에서 가장 의미 있는 5대 매물대 확보)
                    sorted_by_vol = sorted(output, key=lambda x: float(x.get('acml_vol_rlim', 0)), reverse=True)
                    top_5 = sorted_by_vol[:5]
                    
                    # 2. [핵심] 추출된 5개를 다시 '가격(stck_prpr)' 기준으로 내림차순 정렬합니다.
                    # 그래야 대시보드에서 고가가 위로, 저가가 아래로 예쁘게 정렬됩니다.
                    final_profile = sorted(top_5, key=lambda x: float(x.get('stck_prpr', 0)), reverse=True)
                    
                    if final_profile:
                        print(f"🧱 [API] {code} 주요 매물대 5개 가격순 정렬 완료")
                    return final_profile
                except (ValueError, TypeError) as e:
                    print(f"❌ [매물대] 데이터 파싱 에러: {e}")
                    return None
            else:
                print(f"⚠️ [매물대] API 서버 응답 비정상 (상태코드: {res.status_code})")
                return None
        except Exception as e:
            print(f"❌ [매물대] API 통신 에러 ({code}): {e}")
            return None
        
kis = KISApiHelper()