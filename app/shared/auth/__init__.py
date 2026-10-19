from datetime import datetime, timedelta, timezone

import jwt

from shared.config.settings import settings
from shared.exceptions import UnauthorizedError

ALGORITHM = "HS256"


def create_access_token(*, user_id: int, email: str, remember: bool) -> str:
    minutes = settings.jwt_expire_minutes if remember else settings.jwt_session_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "remember": remember,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("El token ha expirado") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Token inválido") from exc
