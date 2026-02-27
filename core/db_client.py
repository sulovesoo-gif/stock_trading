import pymysql
import os
from dotenv import load_dotenv
from datetime import datetime
# 🚀 [이부분!!] 타임존 판단 및 변환을 위해 추가
from zoneinfo import ZoneInfo

load_dotenv()

class DBClient:
    def __init__(self):
        self.KST = ZoneInfo("Asia/Seoul")
        self.UTC = ZoneInfo("UTC")
        self.config = {
            'host': os.getenv('TIDB_HOST'),
            'port': int(os.getenv('TIDB_PORT')),
            'user': os.getenv('TIDB_USER'),
            'password': os.getenv('TIDB_PASS'),
            'database': os.getenv('TIDB_DB'),
            'cursorclass': pymysql.cursors.DictCursor,
            'ssl_verify_cert': True,
            'ssl_verify_identity': True
        }

    # 🚀 [이부분!!] 데이터 내의 시간을 찾아 KST로 변환하는 지능형 헬퍼 함수
    def _handle_timezone(self, rows):
        if not rows: return rows
        for row in rows:
            for key, value in row.items():
                if isinstance(value, datetime):
                    # 타임존 정보가 없으면(Naive) UTC로 간주 후 KST 변환
                    if value.tzinfo is None:
                        value = value.replace(tzinfo=self.UTC)
                    row[key] = value.astimezone(self.KST)
        return rows

    def get_connection(self):
        return pymysql.connect(**self.config)

    # 🚀 [트랙 1] 화면 표시용: 자동으로 KST 변환 수행 (app.py에서 사용)
    def execute_select_query(self, sql, params=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                conn.commit()
                result = cursor.fetchall()
                return self._handle_timezone(result)
        finally:
            conn.close()

    # 🚀 [트랙 2] 내부 로직용: 원본 데이터(UTC) 유지 (수집기, 분석기에서 사용)
    def execute_query(self, sql, params=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                conn.commit()
                return cursor.fetchall()
        finally:
            conn.close()

db = DBClient()