"""Application error types and HTTP error handling."""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """An expected application error safe to expose to an API client."""

    def __init__(self, message: str, status_code: int = 400, code: str = "app_error") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """Return a stable error shape for expected application failures."""

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
