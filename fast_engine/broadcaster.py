# /projects/stock_trading/fast_engine/broadcaster.py
# 이 파일 하나만 8080 포트로 띄우면 됩니다.

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
import json

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
        for connection in self.active_connections:
            try:
                await connection.send_text(data)
            except:
                self.active_connections.remove(connection)

manager = ConnectionManager()

# 1. 리액트 웹 화면이 붙는 곳 (출구)
@app.websocket("/ws/scalping")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # 연결 유지용
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# 2. sc_trader.py 엔진이 데이터를 던지는 곳 (입구)
@app.websocket("/ws/publish")
async def publish_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🚀 [엔진 연결 성공] 데이터 수신 중...")
    try:
        while True:
            data = await websocket.receive_text()
            # 받은 데이터를 리액트로 즉시 방송
            await manager.broadcast(json.loads(data))
    except WebSocketDisconnect:
        print("⚠️ [엔진 연결 해제]")
    except Exception as e:
        print(f"❌ [엔진 수신 에러]: {e}")