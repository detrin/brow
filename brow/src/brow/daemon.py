import os
import signal
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from playwright.async_api import async_playwright

from brow.config import DAEMON_HOST, DAEMON_PORT, PID_FILE, ensure_dirs
from brow.session import SessionManager
from brow.profiles import ProfileManager

def create_app():
    manager = SessionManager()
    profiles = ProfileManager()

    @asynccontextmanager
    async def lifespan(app):
        pw = await async_playwright().start()
        app.state.pw = pw
        app.state.manager = manager
        app.state.profiles = profiles
        yield
        await manager.close_all()
        await pw.stop()

    app = FastAPI(lifespan=lifespan)

    from brow.routes.sessions import router as sessions_router
    from brow.routes.browser import router as browser_router
    from brow.routes.pages import router as pages_router
    from brow.routes.profiles import router as profiles_router
    from brow.routes.eval import router as eval_router

    app.include_router(sessions_router)
    app.include_router(browser_router)
    app.include_router(pages_router)
    app.include_router(profiles_router)
    app.include_router(eval_router)

    @app.get("/status")
    async def status():
        return {"sessions": len(manager.sessions), "status": "running"}

    return app

def run_daemon(host=None, port=None):
    ensure_dirs()
    host = host or DAEMON_HOST
    port = port or DAEMON_PORT
    PID_FILE.write_text(str(os.getpid()))
    try:
        uvicorn.run(create_app(), host=host, port=port, log_level="warning")
    finally:
        PID_FILE.unlink(missing_ok=True)

def stop_daemon():
    if not PID_FILE.exists():
        return False
    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    PID_FILE.unlink(missing_ok=True)
    return True

def daemon_running():
    if not PID_FILE.exists():
        return False
    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        return False

if __name__ == "__main__":
    import sys
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else None
    run_daemon(port=port)
