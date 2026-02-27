import requests
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class KISApiHelper:
    def __init__(self):
        self.base_url = "https://openapi.koreainvestment.com:9443" # 실전 서버
        self.app_key = os.getenv('KIS_API_KEY')
        self.app_secret = os.getenv('KIS_API_SECRET')
        self.access_token = ""
        self.token_expired_at = datetime.now()

    def auth(self):
        """접근 토큰 발급 (유효기간 확인 후 재발급)"""
        # 토큰이 있고 만료 전(여유시간 1분)이면 기존 토큰 반환
        if self.access_token and datetime.now() < self.token_expired_at - timedelta(minutes=1):
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
        self.token_expired_at = datetime.now() + timedelta(seconds=int(data.get('expires_in', 0)))
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
        사용자 제공 명세 기준: 최대 30개 종목 일괄 시세 조회
        FID_INPUT_ISCD_1 ~ 30 형식을 사용
        """
        # 1. URL 설정 (멀티 종목 조회용 엔드포인트 확인 필요)
        # 일반 시세 API인 inquire-price에서 이 파라미터를 지원하는 형식이니 주소 확인!
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        
        # 2. Header 설정
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010100", # 기본 시세 TR ID 사용
            "custtype": "P"
        }
        
        # 3. Query Parameter 동적 생성 (1~30번까지)
        params = {}
        for i, code in enumerate(code_list[:30]): # 최대 30개까지만
            idx = i + 1
            params[f"FID_COND_MRKT_DIV_CODE_{idx}"] = "J"
            params[f"FID_INPUT_ISCD_{idx}"] = code

        try:
            res = requests.get(url, headers=headers, params=params)
            
            if res.status_code == 200:
                # 이 경우 응답 데이터 구조가 output1, output2... 또는 리스트 형태일 수 있습니다.
                # 한투 응답을 확인하신 후 파싱 로직을 조정해야 합니다.
                return res.json() 
            else:
                print(f"⚠️ 멀티 조회 에러: {res.status_code}")
                return None
        except Exception as e:
            print(f"❌ 멀티 조회 통신 에러: {e}")
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