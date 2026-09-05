from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from brow.deps import get_session

router = APIRouter(prefix="/pages/{sid}", tags=["pages"])


class NewPageReq(BaseModel):
    url: Optional[str] = None


class SwitchPageReq(BaseModel):
    index: int


def _page_at(session, index):
    pages = session.pages
    if index < 0 or index >= len(pages):
        raise HTTPException(400, f"Page index {index} out of range")
    return pages[index]


@router.get("")
async def list_pages(session=Depends(get_session)):
    active = session.page
    return {"pages": [{"index": i, "url": p.url, "active": p is active} for i, p in enumerate(session.pages)]}


@router.post("/new")
async def new_page(body: NewPageReq, session=Depends(get_session)):
    had_explicit_target = session._active is not None
    page = await session.context.new_page()
    if body.url:
        await page.goto(body.url)
    # An explicit `page switch` must survive any tab that opens afterwards.
    if not had_explicit_target:
        session.set_active(page)
    return {"index": session.pages.index(page), "url": page.url, "active": session.pages.index(session.page)}


@router.post("/close")
async def close_page(index: Optional[int] = None, session=Depends(get_session)):
    idx = index if index is not None else len(session.pages) - 1
    await _page_at(session, idx).close()
    return {"closed": idx}


@router.post("/switch")
async def switch_page(body: SwitchPageReq, session=Depends(get_session)):
    target = _page_at(session, body.index)
    await target.bring_to_front()
    # bring_to_front only changes what the human sees; set_active is what
    # retargets subsequent commands.
    session.set_active(target)
    return {"active": body.index, "url": target.url}
