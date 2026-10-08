"""모든 에러 응답을 { "error": { "code": ..., "message": ... } } 형식으로 통일한다."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


_DEFAULT_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
}


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


async def _api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return _error_response(exc.status_code, exc.code, exc.message)


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _DEFAULT_CODES.get(exc.status_code, "ERROR")
    return _error_response(exc.status_code, code, str(exc.detail))


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"] if p not in ("query", "path", "body"))
        parts.append(f"{loc}: {err['msg']}" if loc else err["msg"])
    return _error_response(422, "VALIDATION_ERROR", "; ".join(parts))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIError, _api_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
