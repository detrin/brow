from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/sessions", tags=["sessions"])

class CreateSession(BaseModel):
    profile: str = "default"
    headless: bool = True

@router.post("")
async def create(req: Request, body: CreateSession):
    mgr = req.app.state.manager
    profiles = req.app.state.profiles
    pw = req.app.state.pw
    try:
        sid = mgr.create(body.profile, body.headless)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    session = mgr.get(sid)
    user_data_dir = profiles.get_profile_dir(body.profile)
    await session.launch(pw, user_data_dir)
    return {"id": sid, "profile": body.profile}

@router.get("")
async def list_sessions(req: Request):
    return req.app.state.manager.list()

@router.delete("/{sid}")
async def delete(req: Request, sid: str):
    mgr = req.app.state.manager
    try:
        session = mgr.get(sid)
    except KeyError:
        raise HTTPException(404, f"Session {sid} not found")
    await session.close()
    mgr.delete(sid)
    return {"deleted": sid}
