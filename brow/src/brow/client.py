import httpx
from brow.config import DAEMON_URL


class BrowAPIError(Exception):
    """Raised when the brow daemon returns an error response."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _raise_api_error(r: httpx.Response):
    """Extract detail from JSON error response and raise BrowAPIError."""
    try:
        body = r.json()
        if isinstance(body, dict):
            detail = body.get("detail", r.text)
        else:
            detail = str(body)
    except Exception:
        detail = r.text
    raise BrowAPIError(r.status_code, str(detail))


class BrowClient:
    def __init__(self, base_url=None):
        self._client = httpx.AsyncClient(
            base_url=base_url or DAEMON_URL,
            timeout=60.0,
        )

    async def get(self, path, **kwargs):
        r = await self._client.get(path, **kwargs)
        if r.is_error:
            _raise_api_error(r)
        return r.json()

    async def post(self, path, **kwargs):
        r = await self._client.post(path, **kwargs)
        if r.is_error:
            _raise_api_error(r)
        return r.json()

    async def delete(self, path, **kwargs):
        r = await self._client.delete(path, **kwargs)
        if r.is_error:
            _raise_api_error(r)
        return r.json()

    async def close(self):
        await self._client.aclose()
