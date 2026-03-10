# /projects/stock_trading/fast_engine/broadcaster.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
import json
import asyncio

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        # 접속 중인 활성 웹소켓 리스트
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[+] New Dashboard Client Connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"[-] Client Disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """접속된 모든 대시보드 클라이언트에게 데이터 전송"""
        if not self.active_connections:
            return
            
        # JSON 직렬화 후 전송
        data = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(data)
            except Exception as e:
                # 연결이 끊긴 경우 리스트에서 제거 (예외 처리)
                print(f"❌ Broadcast Error: {e}")
                self.active_connections.remove(connection)

manager = ConnectionManager()

@app.websocket("/ws/scalping")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 클라이언트로부터 오는 메시지 대기 (보통 단타 모듈에선 수신만 하지만 연결 유지를 위해 필요)
            data = await websocket.receive_text()
            # 필요 시 클라이언트의 명령(종목 변경 등) 처리 가능
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- 외부 엔진(ws_client + calculator)에서 호출할 방송 함수 ---
async def send_to_dashboard(summary_data: dict):
    """
    calculator.py에서 계산된 데이터를 대시보드로 쏘는 진입점
    """
    await manager.broadcast(summary_data)

if __name__ == "__main__":
    import uvicorn
    # 단독 테스트 실행: uvicorn broadcaster:app --host 0.0.0.0 --port 8080
    uvicorn.run(app, host="0.0.0.0", port=8080)