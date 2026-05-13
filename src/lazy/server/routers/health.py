from fastapi import APIRouter, Request

from ..state import ServerState

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health(request: Request):
    state: ServerState = request.app.state.server_state
    return {
        "status": "ok",
        "user_count": len(state.sessions),
        "uptime": round(state.uptime, 1),
        "version": "0.1.0",
    }
