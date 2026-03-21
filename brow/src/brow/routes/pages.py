from typing import Optional
from fastapi import APIRouter, Request, HTTPException
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
    pages = [{"index": i, "url": p.url} for i, p in enumerate(session.pages)]
    return {"pages": pages}

@router.post("/new")
async def new_page(req: Request, sid: str, body: NewPageReq):
    session = _get_session(req, sid)
    page = await session.context.new_page()
    if body.url:
        await page.goto(body.url)
    return {"index": len(session.pages) - 1, "url": page.url}

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
    await pages[body.index].bring_to_front()
    return {"active": body.index, "url": pages[body.index].url}
