import asyncio
import io
import sys

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from brow.config import DEFAULT_TIMEOUT
from brow.deps import get_session

router = APIRouter(prefix="/eval/{sid}", tags=["eval"])


class EvalReq(BaseModel):
    code: str
    timeout: int = DEFAULT_TIMEOUT


@router.post("")
async def eval_code(body: EvalReq, session=Depends(get_session)):
    page = session.page
    context = session.context

    async def text(selector):
        el = await page.query_selector(selector)
        return (await el.inner_text()).strip() if el else None

    async def texts(selector):
        return [(await el.inner_text()).strip() for el in await page.query_selector_all(selector)]

    sandbox = {
        "page": page,
        "context": context,
        "browser": session.browser,
        "state": session.state,
        "pages": session.pages,
        "asyncio": asyncio,
        "text": text,
        "texts": texts,
    }

    stdout_capture = io.StringIO()
    code = "async def __eval__():\n"
    code += "    global result\n"
    for line in body.code.split("\n"):
        code += f"    {line}\n"

    try:
        exec(compile(code, "<eval>", "exec"), sandbox)
        old_stdout = sys.stdout
        sys.stdout = stdout_capture
        try:
            await asyncio.wait_for(sandbox["__eval__"](), timeout=body.timeout / 1000)
        finally:
            sys.stdout = old_stdout
    except asyncio.TimeoutError:
        # Name the knob and return partial stdout: a bare timeout reads as a hard ceiling and hides progress.
        partial = stdout_capture.getvalue()
        msg = (
            f"Eval timed out after {body.timeout}ms. "
            f"Raise it with --timeout <ms> (e.g. --timeout {max(body.timeout * 4, 120000)}) "
            f"for long jobs, or split the work across calls."
        )
        if partial:
            msg += f"\nPartial stdout before the timeout:\n{partial}"
        raise HTTPException(408, msg)
    except Exception as e:
        msg = str(e)
        if "'coroutine' object" in msg:
            msg += " — page methods are async; did you forget 'await'? (or use the text()/texts() helpers)"
        raise HTTPException(400, msg)

    return {
        "result": sandbox.get("result"),
        "stdout": stdout_capture.getvalue(),
    }
