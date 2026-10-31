from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from db.session import get_db
from shared.auth import decode_access_token, enforce_csrf, extract_access_token
from shared.exceptions import UnauthorizedError
from shared.subscription import ensure_subscription_active
from user.domain.entities.user import User
from user.domain.ports.user_repository import UserRepository
from user.infrastructure.repositories.user_repository_impl import UserRepositoryImpl

bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(session: Session = Depends(get_db)) -> UserRepository:
    return UserRepositoryImpl(session)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    repository: UserRepository = Depends(get_user_repository),
) -> User:
    enforce_csrf(request)
    bearer = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else None
    token = extract_access_token(request, bearer)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (UnauthorizedError, TypeError, ValueError, KeyError) as exc:
        message = getattr(exc, "message", "Token inválido")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = repository.get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autorizado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        ensure_subscription_active(user, repository)
    except UnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return user
