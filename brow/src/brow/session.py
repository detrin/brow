from dataclasses import dataclass, field

from brow.config import MAX_SESSIONS

_MISSING_BROWSER_HINTS = ("Executable doesn't exist", "playwright install", "patchright install", "BrowserType.launch")


def is_browser_missing_error(e):
    msg = str(e)
    return any(h in msg for h in _MISSING_BROWSER_HINTS)


@dataclass
class Session:
    id: str
    profile: str
    headless: bool
    browser: object = None
    context: object = None
    state: dict = field(default_factory=dict)
    # Tracked as an object, not an index: indices shift when other tabs open or close.
    _active: object = None

    @property
    def pages(self):
        return self.context.pages if self.context else []

    @property
    def page(self):
        # Without _active, page switch was a no-op: a background popup silently stole the target.
        pages = self.pages
        if self._active is not None and self._active in pages:
            return self._active
        self._active = None
        return pages[-1] if pages else None

    def set_active(self, page):
        self._active = page

    async def launch(self, playwright, user_data_dir):
        self.browser = None
        self.context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
            ignore_default_args=["--enable-automation"],
        )
        self.state["console_logs"] = []
        self.state["network_requests"] = []
        self.state["websocket_messages"] = []
        self.state["actions"] = []

        _TEXT_TYPES = ("application/json", "text/", "application/xml", "application/javascript")

        async def _on_resp(resp):
            ct = resp.headers.get("content-type", "").split(";")[0]
            entry = {
                "method": resp.request.method,
                "url": resp.url,
                "status": resp.status,
                "type": ct,
            }
            if any(ct.startswith(t) for t in _TEXT_TYPES):
                try:
                    body = await resp.body()
                    entry["response_preview"] = body[:1024].decode("utf-8", errors="replace")
                except Exception:
                    pass
            reqs = self.state["network_requests"]
            reqs.append(entry)
            if len(reqs) > 500:
                reqs.pop(0)

        def _on_ws(ws):
            def _frame(direction, data):
                text = (
                    data
                    if isinstance(data, str)
                    else data.decode("utf-8", errors="replace")
                    if isinstance(data, bytes)
                    else str(data)
                )
                msgs = self.state["websocket_messages"]
                msgs.append({"direction": direction, "url": ws.url, "data": text[:2048]})
                if len(msgs) > 200:
                    msgs.pop(0)

            ws.on("framereceived", lambda data: _frame("recv", data))
            ws.on("framesent", lambda data: _frame("sent", data))

        def _attach(page):
            page.on("console", lambda msg: self.state["console_logs"].append(f"[{msg.type}] {msg.text}"))
            page.on("response", _on_resp)
            page.on("websocket", _on_ws)

        for page in self.context.pages:
            _attach(page)
        self.context.on("page", _attach)

    async def close(self):
        if self.context:
            await self.context.close()
            self.context = None
        self.browser = None


class SessionManager:
    def __init__(self):
        self.sessions: dict[str, Session] = {}
        self._counter = 0

    def find_by_profile(self, profile):
        for s in self.sessions.values():
            if s.profile == profile:
                return s
        return None

    def create(self, profile, headless=True):
        if len(self.sessions) >= MAX_SESSIONS:
            raise RuntimeError(f"Max sessions ({MAX_SESSIONS}) reached")
        existing = self.find_by_profile(profile)
        if existing:
            raise RuntimeError(
                f"Profile '{profile}' already in use by session {existing.id}. "
                f"Retry with reclaim, or run: brow session delete {existing.id}"
            )
        self._counter += 1
        sid = str(self._counter)
        self.sessions[sid] = Session(id=sid, profile=profile, headless=headless)
        return sid

    def get(self, sid):
        if sid not in self.sessions:
            raise KeyError(f"Session {sid} not found")
        return self.sessions[sid]

    def delete(self, sid):
        if sid not in self.sessions:
            raise KeyError(f"Session {sid} not found")
        del self.sessions[sid]

    def list(self):
        return [
            {"id": s.id, "profile": s.profile, "headless": s.headless, "pages": len(s.pages)}
            for s in self.sessions.values()
        ]

    async def close_all(self):
        for s in self.sessions.values():
            await s.close()
        self.sessions.clear()
