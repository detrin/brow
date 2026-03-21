from dataclasses import dataclass, field
from brow.config import MAX_SESSIONS

@dataclass
class Session:
    id: str
    profile: str
    headless: bool
    browser: object = None
    context: object = None
    state: dict = field(default_factory=dict)

    @property
    def pages(self):
        return self.context.pages if self.context else []

    @property
    def page(self):
        pages = self.pages
        return pages[-1] if pages else None

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
        for page in self.context.pages:
            page.on("console", lambda msg: self.state["console_logs"].append(f"[{msg.type}] {msg.text}"))
        self.context.on("page", lambda page: page.on("console", lambda msg: self.state["console_logs"].append(f"[{msg.type}] {msg.text}")))

    async def close(self):
        if self.context:
            await self.context.close()
            self.context = None
        self.browser = None

class SessionManager:
    def __init__(self):
        self.sessions: dict[str, Session] = {}
        self._counter = 0

    def create(self, profile, headless=True):
        if len(self.sessions) >= MAX_SESSIONS:
            raise RuntimeError(f"Max sessions ({MAX_SESSIONS}) reached")
        for s in self.sessions.values():
            if s.profile == profile:
                raise RuntimeError(f"Profile '{profile}' already in use by session {s.id}")
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
        return [{"id": s.id, "profile": s.profile, "headless": s.headless, "pages": len(s.pages)} for s in self.sessions.values()]

    async def close_all(self):
        for s in self.sessions.values():
            await s.close()
        self.sessions.clear()
