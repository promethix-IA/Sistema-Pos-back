from fastapi import HTTPException, status

from shared.config.settings import settings
from shared.exceptions import (
    ConflictError,
    ForbiddenError,
    MailError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
    ValidationError,
)


def handle_domain_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    if isinstance(exc, UnauthorizedError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc
    if isinstance(exc, RateLimitError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=exc.message,
            headers={"Retry-After": str(settings.login_window_seconds)},
        ) from exc
    if isinstance(exc, ForbiddenError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message) from exc
    if isinstance(exc, MailError):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message) from exc
    raise exc
