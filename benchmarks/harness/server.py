import asyncio
import socket
import uvicorn

class FixtureServer:
    def __init__(self, port=0):
        self.port = port or self._find_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._server = None
        self._task = None

    def _find_free_port(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    async def start(self):
        from benchmarks.fixtures.app import create_fixture_app
        app = create_fixture_app()
        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._task = asyncio.create_task(self._server.serve())
        await asyncio.sleep(0.5)

    async def stop(self):
        if self._server:
            self._server.should_exit = True
            if self._task:
                await self._task
