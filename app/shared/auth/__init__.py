from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt

from shared.config.settings import settings
from shared.exceptions import UnauthorizedError

ALGORITHM = "HS256"


def create_access_token(*, user_id: int, email: str, remember: bool) -> str:
    minutes = settings.jwt_expire_minutes if remember else settings.jwt_session_minutes
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "remember": remember,
        "typ": "access",
        "jti": uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=minutes),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("El token ha expirado") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Token inválido") from exc

    if payload.get("typ", "access") != "access":
        raise UnauthorizedError("Token inválido")
    if not str(payload.get("sub", "")).isdigit():
        raise UnauthorizedError("Token inválido")
    return payload
