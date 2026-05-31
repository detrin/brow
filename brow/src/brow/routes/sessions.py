import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSession(BaseModel):
    profile: str = "default"
    headless: bool = True
    url: Optional[str] = None


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

    resp = {"id": sid, "profile": body.profile}

    if body.url:
        page = session.page
        if page:
            from brow.routes.browser import _take_snapshot

            try:
                r = await page.goto(body.url, timeout=30000)
                resp["url"] = page.url
                resp["status"] = r.status if r else None
            except Exception as e:
                logging.error(f"Navigate to {body.url} failed: {e}")
                resp["url"] = body.url
                resp["status"] = None
                resp["error"] = f"Navigation failed: {e}"
            formatted, truncated, node_count = await _take_snapshot(page)
            resp["snapshot"] = formatted
            if truncated:
                resp["truncated"] = True

    return resp


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
