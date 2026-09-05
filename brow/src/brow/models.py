from typing import Optional

from pydantic import BaseModel, Field

from brow.config import DEFAULT_TIMEOUT


class NavigateReq(BaseModel):
    url: str
    timeout: int = DEFAULT_TIMEOUT
    wait: str = "load"


class WaitReq(BaseModel):
    selector: Optional[str] = None
    load: bool = False
    timeout: int = DEFAULT_TIMEOUT


class TargetReq(BaseModel):
    selector: Optional[str] = None
    ref: Optional[int] = None
    timeout: int = DEFAULT_TIMEOUT


class RetryTargetReq(TargetReq):
    retry: int = 0
    wait_for_selector: bool = True


class ClickReq(RetryTargetReq):
    pass


class FillReq(RetryTargetReq):
    value: str


class SelectReq(TargetReq):
    value: str


class TypeReq(BaseModel):
    text: str


class KeyReq(BaseModel):
    key: str


class HoverReq(BaseModel):
    selector: str
    timeout: int = DEFAULT_TIMEOUT


class ScrollReq(BaseModel):
    pixels: int = 0
    selector: Optional[str] = None


class ScrollUntilReq(BaseModel):
    until: str
    pixels: int = 800
    max_attempts: int = 10
    timeout: int = DEFAULT_TIMEOUT


class ClickUntilReq(BaseModel):
    selector: str
    until_gone: Optional[str] = None
    max_iterations: int = 25
    settle_ms: int = 500
    timeout: int = DEFAULT_TIMEOUT


class DragReq(BaseModel):
    source: str
    target: str


class UploadReq(BaseModel):
    selector: str
    filepath: str


class ScreenshotReq(BaseModel):
    full: bool = False
    path: Optional[str] = None
    width: Optional[int] = None
    scale: Optional[float] = None
    quality: Optional[str] = None


class FetchReq(BaseModel):
    url: str
    method: str = "GET"
    headers: Optional[dict] = None
    body: Optional[str] = None
    no_cookies: bool = False


class ReplayReq(BaseModel):
    playbook: dict
    vars: dict = Field(default_factory=dict)
