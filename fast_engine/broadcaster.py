from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
import json
try:
    from fast_engine.parser_utils import parse_data
except ModuleNotFoundError:
    from parser_utils import parse_data

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[+] 리액트 대시보드 연결됨 (총: {len(self.active_connections)}개)")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections: return
        data = json.dumps(message)
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(data)
            except:
                self.disconnect(connection)

manager = ConnectionManager()

@app.websocket("/ws/scalping")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.websocket("/ws/publish")
async def publish_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🚀 [엔진 연결 성공] 데이터 변환 및 방송 시작")
    try:
        while True:
            raw_data = await websocket.receive_text()
            
            # 1. 한국투자증권 시스템 메시지 (JSON 형태) 처리
            if raw_data.startswith('{'):
                try:
                    data_json = json.loads(raw_data)
                    # PINGPONG 또는 시스템 메시지 로그 처리
                    if "header" in data_json:
                        tr_id = data_json.get("header", {}).get("tr_id")
                        if tr_id == "PINGPONG":
                            continue
                        msg = data_json.get('body', {}).get('msg1', '시스템 메시지')
                        print(f"📢 [한투 알림]: {msg}")
                        continue
                    # 그 외 일반 JSON은 그대로 방송
                    await manager.broadcast(data_json)
                except: continue

            # 2. 실시간 데이터 (통합 파서 사용)
            # 국내/해외 체결(TICK), 호가(ORDERBOOK)를 모두 처리
            else:
                payload = parse_data(raw_data)
                if payload:
                    await manager.broadcast(payload)

    except WebSocketDisconnect:
        print("⚠️ [엔진 연결 해제]")
    except Exception as e:
        print(f"❌ [에러 발생]: {e}")