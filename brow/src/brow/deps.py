import re

from fastapi import Depends, HTTPException, Request


def get_session(req: Request, sid: str):
    try:
        return req.app.state.manager.get(sid)
    except KeyError:
        raise HTTPException(404, f"Session {sid} not found")


def get_page(session=Depends(get_session)):
    if not session.page:
        raise HTTPException(400, "No active page")
    return session.page


SessionDep = Depends(get_session)
PageDep = Depends(get_page)

_REF_RE = re.compile(r"^\s*\[?(\d+)\]?\s*$")


def resolve_selector(body):
    ref = getattr(body, "ref", None)
    if ref is not None:
        return f'[data-brow-ref="{ref}"]'
    selector = getattr(body, "selector", None)
    if selector is None:
        raise HTTPException(400, "Either 'ref' or 'selector' must be provided")
    m = _REF_RE.match(selector)
    return f'[data-brow-ref="{m.group(1)}"]' if m else selector


def log_action(session, action, **kwargs):
    actions = session.state.setdefault("actions", [])
    actions.append({"seq": len(actions) + 1, "action": action, **{k: v for k, v in kwargs.items() if v is not None}})
