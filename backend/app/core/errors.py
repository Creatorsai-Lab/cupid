"""Typed application errors. Services raise them; one handler in main.py turns
them into HTTP responses, so routers need no try/except.
"""


class AppError(Exception):
    status: int = 500
    code: str = "internal_error"


class NotFoundError(AppError):
    status, code = 404, "not_found"


class ForbiddenError(AppError):
    status, code = 403, "forbidden"


class ConflictError(AppError):
    status, code = 409, "conflict"


class ServiceUnavailableError(AppError):
    status, code = 503, "service_unavailable"
