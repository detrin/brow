from functools import partialmethod

import httpx

from brow.config import get_daemon_url


class BrowAPIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _raise_api_error(r: httpx.Response):
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
            base_url=base_url or get_daemon_url(),
            timeout=60.0,
        )

    async def request(self, method, path, **kwargs):
        r = await self._client.request(method, path, **kwargs)
        if r.is_error:
            _raise_api_error(r)
        return r.json()

    get = partialmethod(request, "GET")
    post = partialmethod(request, "POST")
    delete = partialmethod(request, "DELETE")

    async def close(self):
        await self._client.aclose()
