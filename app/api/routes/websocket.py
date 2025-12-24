from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.broadcaster import broadcaster

router = APIRouter(prefix="/ws")

@router.websocket("")
async def ws_endpoint(ws: WebSocket, room: str = Query(...)):
    await broadcaster.join(room, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        broadcaster.leave(room, ws)
