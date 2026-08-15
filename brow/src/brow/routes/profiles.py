from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["profiles"])


@router.get("/profiles")
async def list_profiles(req: Request):
    return {"profiles": req.app.state.profiles.list()}


@router.delete("/profiles/{name}")
async def delete_profile(req: Request, name: str):
    try:
        req.app.state.profiles.delete(name)
    except KeyError:
        raise HTTPException(404, f"Profile '{name}' not found")
    return {"deleted": name}


class SaveStateReq(BaseModel):
    name: str
    session_id: str


class RestoreStateReq(BaseModel):
    name: str
    session_id: str


@router.post("/states/save")
async def save_state(req: Request, body: SaveStateReq):
    mgr = req.app.state.manager
    try:
        session = mgr.get(body.session_id)
    except KeyError:
        raise HTTPException(404, f"Session {body.session_id} not found")
    state = await session.context.storage_state()
    req.app.state.profiles.save_state(body.name, state)
    return {"saved": body.name}


@router.post("/states/restore")
async def restore_state(req: Request, body: RestoreStateReq):
    mgr = req.app.state.manager
    profiles = req.app.state.profiles
    try:
        session = mgr.get(body.session_id)
    except KeyError:
        raise HTTPException(404, f"Session {body.session_id} not found")
    try:
        state = profiles.load_state(body.name)
    except FileNotFoundError:
        raise HTTPException(404, f"State '{body.name}' not found")
    if state.get("cookies"):
        await session.context.add_cookies(state["cookies"])
    for origin in state.get("origins", []):
        local_storage = origin.get("localStorage", [])
        if not local_storage:
            continue
        page = await session.context.new_page()
        try:
            await page.goto(origin["origin"])
            await page.evaluate(
                "(items) => { for (const {name, value} of items) localStorage.setItem(name, value) }",
                local_storage,
            )
        finally:
            await page.close()
    return {"restored": body.name}


@router.get("/states")
async def list_states(req: Request):
    return {"states": req.app.state.profiles.list_states()}
