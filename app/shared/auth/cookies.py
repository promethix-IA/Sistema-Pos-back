import hmac
import secrets

from fastapi import HTTPException, Request, Response, status

from shared.config.settings import settings

ACCESS_COOKIE = "pos_access"
CSRF_COOKIE = "pos_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _secure(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "")
    return settings.is_production or request.url.scheme == "https" or forwarded.split(",")[0].strip() == "https"


def _samesite(request: Request) -> str:
    # En producción el front y el API están en dominios distintos.
    return "none" if _secure(request) else "lax"


def _cookie_base(request: Request) -> dict:
    return {
        "path": "/",
        "secure": _secure(request),
        "samesite": _samesite(request),
    }


def attach_auth_cookies(response: Response, request: Request, token: str) -> str:
    csrf = secrets.token_urlsafe(32)
    base = _cookie_base(request)
    response.set_cookie(ACCESS_COOKIE, token, httponly=True, **base)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **base)
    return csrf


def clear_auth_cookies(response: Response, request: Request) -> None:
    base = _cookie_base(request)
    response.delete_cookie(ACCESS_COOKIE, **base)
    response.delete_cookie(CSRF_COOKIE, **base)


def extract_access_token(request: Request, bearer: str | None) -> str | None:
    if bearer:
        return bearer.strip()
    cookie = request.cookies.get(ACCESS_COOKIE)
    return cookie.strip() if cookie else None


def enforce_csrf(request: Request) -> None:
    if request.method.upper() in SAFE_METHODS:
        return
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return
    if not request.cookies.get(ACCESS_COOKIE):
        return
    cookie_token = request.cookies.get(CSRF_COOKIE, "")
    header_token = request.headers.get(CSRF_HEADER, "")
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solicitud rechazada. Recarga e inicia sesión de nuevo.",
        )
