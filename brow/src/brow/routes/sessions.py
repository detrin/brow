import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from brow.session import is_browser_missing_error

router = APIRouter(prefix="/sessions", tags=["sessions"])

_BROWSER_MISSING_MSG = "Chromium is not installed. Run: brow setup  (or: patchright install chromium)"


class CreateSession(BaseModel):
    profile: str = "default"
    headless: bool = True
    url: Optional[str] = None
    reclaim: bool = False


@router.post("")
async def create(req: Request, body: CreateSession):
    mgr = req.app.state.manager
    profiles = req.app.state.profiles
    pw = req.app.state.pw
    if body.reclaim:
        stale = mgr.find_by_profile(body.profile)
        if stale:
            await stale.close()
            mgr.delete(stale.id)
    try:
        sid = mgr.create(body.profile, body.headless)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    session = mgr.get(sid)
    user_data_dir = profiles.get_profile_dir(body.profile)
    try:
        await session.launch(pw, user_data_dir)
    except Exception as e:
        mgr.delete(sid)
        if is_browser_missing_error(e):
            raise HTTPException(503, _BROWSER_MISSING_MSG)
        raise HTTPException(500, f"Failed to launch browser: {e}")

    resp = {"id": sid, "profile": body.profile}

    if body.url:
        page = session.page
        if page:
            from brow.snapshot import take_snapshot, with_snapshot

            try:
                r = await page.goto(body.url, timeout=30000)
                resp["url"] = page.url
                resp["status"] = r.status if r else None
            except Exception as e:
                logging.error(f"Navigate to {body.url} failed: {e}")
                resp["url"] = body.url
                resp["status"] = None
                resp["error"] = f"Navigation failed: {e}"
            formatted, meta = await take_snapshot(page)
            resp["snapshot"] = formatted
            with_snapshot(resp, meta)

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
