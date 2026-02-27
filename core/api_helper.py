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

kis = KISApiHelper()