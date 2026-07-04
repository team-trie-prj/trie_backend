"""공통 응답 Envelope + 예외 핸들러 (김예담).

- 성공: {"success": true,  "code": "OK",          "message": "...", "data": {...}}
- 실패: {"success": false, "code": "BAD_REQUEST", "message": "...", "data": null}

**스코프**: 김예담 담당 경로(OWNED_PREFIXES)에만 적용한다.
vikira `/api/v1/*` 등 그 외 경로는 FastAPI 기본 `{"detail": ...}` 형식을 그대로 유지한다.
`code` 는 HTTP 상태명(예: 200→OK, 400→BAD_REQUEST, 404→NOT_FOUND).
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any, Generic, Optional, TypeVar

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import PlainTextResponse

T = TypeVar("T")

# envelope 를 적용할 김예담 담당 라우트 prefix
OWNED_PREFIXES = ("/auth", "/documents", "/api-keys", "/public-data", "/sessions")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    code: str = "OK"
    message: str = "요청 성공"
    data: Optional[T] = None


def ok(data: Any = None, message: str = "요청 성공") -> dict:
    """성공 응답 envelope 생성."""
    return {"success": True, "code": "OK", "message": message, "data": data}


def _is_owned(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in OWNED_PREFIXES)


def _code_name(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).name
    except ValueError:
        return f"HTTP_{status_code}"


def _fail(status_code: int, message: str, data: Any = None, headers=None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "code": _code_name(status_code), "message": message, "data": data},
        headers=headers,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTPException → envelope(김예담 경로) / 기본 {detail}(그 외)."""
    if _is_owned(request.url.path):
        if isinstance(exc.detail, str):
            return _fail(exc.status_code, exc.detail, headers=getattr(exc, "headers", None))
        return _fail(exc.status_code, "요청을 처리할 수 없습니다.",
                     data=jsonable_encoder(exc.detail), headers=getattr(exc, "headers", None))
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail},
                        headers=getattr(exc, "headers", None))


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """요청 검증 실패(422) → envelope(김예담) / 기본 {detail}(그 외)."""
    if _is_owned(request.url.path):
        return _fail(422, "입력값이 올바르지 않습니다.", data=jsonable_encoder(exc.errors()))
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})


async def unhandled_exception_handler(request: Request, exc: Exception):
    """미처리 예외(500) → envelope(김예담) / Starlette 기본(그 외)."""
    if _is_owned(request.url.path):
        return _fail(500, "서버 내부 오류가 발생했습니다.")
    return PlainTextResponse("Internal Server Error", status_code=500)
