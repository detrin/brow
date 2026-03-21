import httpx
from brow.config import DAEMON_URL

class BrowClient:
    def __init__(self, base_url=None):
        self._client = httpx.AsyncClient(
            base_url=base_url or DAEMON_URL,
            timeout=60.0,
        )

    async def get(self, path, **kwargs):
        r = await self._client.get(path, **kwargs)
        r.raise_for_status()
        return r.json()

    async def post(self, path, **kwargs):
        r = await self._client.post(path, **kwargs)
        r.raise_for_status()
        return r.json()

    async def delete(self, path, **kwargs):
        r = await self._client.delete(path, **kwargs)
        r.raise_for_status()
        return r.json()

    async def close(self):
        await self._client.aclose()
