import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

class DBClient:
    def __init__(self):
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

    def get_connection(self):
        return pymysql.connect(**self.config)

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