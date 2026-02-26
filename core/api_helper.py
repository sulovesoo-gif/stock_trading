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

kis = KISApiHelper()