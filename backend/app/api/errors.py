from uuid import uuid4

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def error_response(
    *,
    code: str,
    message: str,
    status_code: int,
    fields: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "fields": fields,
                "request_id": f"req_{uuid4().hex}",
            }
        },
    )


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    code_by_status = {
        status.HTTP_400_BAD_REQUEST: "bad_request",
        status.HTTP_401_UNAUTHORIZED: "unauthorized",
        status.HTTP_403_FORBIDDEN: "forbidden",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_409_CONFLICT: "conflict",
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
        status.HTTP_503_SERVICE_UNAVAILABLE: "provider_not_configured",
    }
    message = exc.detail if isinstance(exc.detail, str) else "请求失败"
    return error_response(
        code=code_by_status.get(exc.status_code, "request_failed"),
        message=message,
        status_code=exc.status_code,
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    fields: dict[str, str] = {}
    for error in exc.errors():
        key = ".".join(str(part) for part in error.get("loc", []) if part != "body")
        fields[key or "body"] = str(error.get("msg", "字段不合法"))

    return error_response(
        code="validation_failed",
        message="部分字段需要修正。",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        fields=fields,
    )
