from typing import Dict, Set
from fastapi import WebSocket

class Broadcaster:
    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = {}

    async def join(self, room: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(room, set()).add(ws)

    def leave(self, room: str, ws: WebSocket):
        if room in self.rooms:
            self.rooms[room].discard(ws)
            if not self.rooms[room]:
                self.rooms.pop(room, None)

    async def broadcast(self, room: str, payload: dict):
        conns = list(self.rooms.get(room, []))
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                pass

broadcaster = Broadcaster()
