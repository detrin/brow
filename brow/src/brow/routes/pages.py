from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/pages/{sid}", tags=["pages"])


def _get_session(req, sid):
    try:
        return req.app.state.manager.get(sid)
    except KeyError:
        raise HTTPException(404, f"Session {sid} not found")


class NewPageReq(BaseModel):
    url: Optional[str] = None


class SwitchPageReq(BaseModel):
    index: int


@router.get("")
async def list_pages(req: Request, sid: str):
    session = _get_session(req, sid)
    active = session.page
    # Marking the active tab matters: without it there is no way to tell where
    # the next command will land, which is the whole trap this used to create.
    pages = [{"index": i, "url": p.url, "active": p is active} for i, p in enumerate(session.pages)]
    return {"pages": pages}


@router.post("/new")
async def new_page(req: Request, sid: str, body: NewPageReq):
    session = _get_session(req, sid)
    had_explicit_target = session._active is not None
    page = await session.context.new_page()
    if body.url:
        await page.goto(body.url)
    # Only take over as the target if the caller had not deliberately chosen one.
    # Otherwise an explicit `page switch` would be undone by any tab that opens
    # afterwards.
    if not had_explicit_target:
        session.set_active(page)
    return {"index": session.pages.index(page), "url": page.url, "active": session.pages.index(session.page)}


@router.post("/close")
async def close_page(req: Request, sid: str, index: Optional[int] = None):
    session = _get_session(req, sid)
    pages = session.pages
    idx = index if index is not None else len(pages) - 1
    if idx < 0 or idx >= len(pages):
        raise HTTPException(400, f"Page index {idx} out of range")
    await pages[idx].close()
    return {"closed": idx}


@router.post("/switch")
async def switch_page(req: Request, sid: str, body: SwitchPageReq):
    session = _get_session(req, sid)
    pages = session.pages
    if body.index < 0 or body.index >= len(pages):
        raise HTTPException(400, f"Page index {body.index} out of range")
    target = pages[body.index]
    await target.bring_to_front()
    # bring_to_front only affects what the human sees. Recording the choice is
    # what actually retargets subsequent commands.
    session.set_active(target)
    return {"active": body.index, "url": target.url}
