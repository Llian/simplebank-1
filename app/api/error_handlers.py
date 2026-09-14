"""Maps domain/validation/unexpected errors to the {"error", "message"} body
shape from requirements §6. Routers never build error responses themselves.
"""

import logging
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import DomainError

logger = logging.getLogger(__name__)


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    domain_exc = cast(DomainError, exc)
    return JSONResponse(
        status_code=domain_exc.status_code,
        content={"error": domain_exc.error_code, "message": domain_exc.message},
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "validation_error", "message": "Invalid request."},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "An unexpected error occurred."},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
