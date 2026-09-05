import asyncio
import json
import subprocess
from pathlib import Path

from benchmarks.stealth import signals

PROBE = (Path(__file__).parent / "probe.js").read_text()

LAUNCH_ARGS = ["--disable-blink-features=AutomationControlled"]


class Unavailable(Exception):
    pass


TEXT_JS = "() => document.title + '\\n' + (document.body ? document.body.innerText : '')"


class Runner:
    name = ""
    fn_forms = ("{js}",)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc):
        await self.stop()

    async def start(self):
        pass

    async def stop(self):
        pass

    async def _first_usable(self, js, usable):
        last = None
        for form in self.fn_forms:
            try:
                value = await self.evaluate(form.format(js=js))
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
                continue
            if usable(value):
                return value, True
            last = value
        return last, False

    async def probe(self):
        value, _ = await self._first_usable(PROBE, lambda r: signals.unusable(r) is None)
        return value

    async def text_sample(self, limit=4000):
        value, ok = await self._first_usable(TEXT_JS, lambda r: isinstance(r, str))
        return value[:limit] if ok else None


class _PlaywrightLike(Runner):
    module = ""
    stealth_args = True
    channel = None

    def __init__(self, profile_dir):
        self.profile_dir = profile_dir

    async def start(self):
        try:
            mod = __import__(f"{self.module}.async_api", fromlist=["async_playwright"])
        except ImportError as e:
            raise Unavailable(f"{self.module} not installed: {e}")
        self._pw = await mod.async_playwright().start()
        kwargs = {"user_data_dir": str(self.profile_dir), "headless": True}
        if self.channel:
            kwargs["channel"] = self.channel
        if self.stealth_args:
            kwargs["args"] = list(LAUNCH_ARGS)
            kwargs["ignore_default_args"] = ["--enable-automation"]
        try:
            self.context = await self._pw.chromium.launch_persistent_context(**kwargs)
        except Exception as e:
            await self._pw.stop()
            raise Unavailable(f"launch failed: {type(e).__name__}: {str(e)[:200]}")
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

    async def goto(self, url):
        r = await self.page.goto(url, timeout=45000, wait_until="domcontentloaded")
        return r.status if r else None

    async def evaluate(self, js):
        return await self.page.evaluate(js)

    async def stop(self):
        try:
            await self.context.close()
        finally:
            await self._pw.stop()


class Patchright(_PlaywrightLike):
    name = "patchright"
    module = "patchright"


class PatchrightBare(_PlaywrightLike):
    """patchright with no stealth launch args, to show what brow's own configuration is worth."""

    name = "patchright-bare"
    module = "patchright"
    stealth_args = False


class PatchrightNewHeadless(_PlaywrightLike):
    name = "patchright-newheadless"
    module = "patchright"
    channel = "chromium"


class PatchrightChrome(_PlaywrightLike):
    name = "patchright-chrome"
    module = "patchright"
    channel = "chrome"


class Playwright(_PlaywrightLike):
    name = "playwright"
    module = "playwright"


class Brow(Runner):
    name = "brow"

    def __init__(self, profile="stealth-bench"):
        self.profile = profile
        self.sid = None

    async def start(self):
        try:
            from brow.client import BrowClient
        except ImportError as e:
            raise Unavailable(f"brow not importable: {e}")
        self.client = BrowClient()
        try:
            r = await self.client.post(
                "/sessions", json={"profile": self.profile, "headless": True, "reclaim": True}
            )
        except Exception as e:
            raise Unavailable(f"brow daemon unreachable ({e}); start it with: brow daemon start --wait")
        self.sid = r["id"]

    async def goto(self, url):
        r = await self.client.post(f"/browser/{self.sid}/navigate", json={"url": url, "timeout": 45000})
        return r.get("status")

    async def evaluate(self, js):
        r = await self.client.post(
            f"/eval/{self.sid}", json={"code": f"result = await page.evaluate({js!r})", "timeout": 60000}
        )
        return r["result"]

    async def stop(self):
        if self.sid:
            try:
                await self.client.delete(f"/sessions/{self.sid}")
            except Exception:
                pass
        await self.client.close()


class AgentBrowser(Runner):
    name = "agent-browser"
    fn_forms = ("({js})()", "await ({js})()", "{js}")

    async def start(self):
        if not self._which():
            raise Unavailable("agent-browser not on PATH")

    @staticmethod
    def _which():
        from shutil import which

        return which("agent-browser")

    async def _cmd(self, *args, timeout=120):
        proc = await asyncio.create_subprocess_exec(
            "agent-browser",
            "--json",
            *args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        try:
            payload = json.loads(out.decode() or "{}")
        except ValueError:
            raise RuntimeError(f"unparseable output: {out[:200]!r} {err[:200]!r}")
        if not payload.get("success"):
            raise RuntimeError(payload.get("error") or "command failed")
        return payload.get("data") or {}

    async def goto(self, url):
        await self._cmd("open", url)
        return None

    async def evaluate(self, js):
        data = await self._cmd("eval", js)
        return data["result"] if "result" in data else data

    async def stop(self):
        try:
            await self._cmd("close", timeout=30)
        except Exception:
            pass


REGISTRY = {
    r.name: r
    for r in (Brow, Patchright, PatchrightBare, PatchrightNewHeadless, PatchrightChrome, Playwright, AgentBrowser)
}


def build(name, tmp_root):
    cls = REGISTRY[name]
    if issubclass(cls, _PlaywrightLike):
        d = Path(tmp_root) / name
        d.mkdir(parents=True, exist_ok=True)
        return cls(d)
    return cls()
