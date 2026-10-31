import hmac
import re
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


def ensure_csrf_cookie(response: Response, request: Request) -> str:
    existing = (request.cookies.get(CSRF_COOKIE) or "").strip()
    if existing:
        return existing
    csrf = secrets.token_urlsafe(32)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **_cookie_base(request))
    return csrf


def clear_auth_cookies(response: Response, request: Request) -> None:
    # Hay que borrar con las mismas banderas con las que se creó; si no, el
    # navegador deja la cookie y al recargar vuelve a entrar.
    for samesite in ("none", "lax"):
        for secure in (True, False):
            kwargs = {"path": "/", "secure": secure, "samesite": samesite}
            response.delete_cookie(ACCESS_COOKIE, **kwargs)
            response.delete_cookie(CSRF_COOKIE, **kwargs)


def extract_access_token(request: Request, bearer: str | None) -> str | None:
    if bearer:
        return bearer.strip()
    cookie = request.cookies.get(ACCESS_COOKIE)
    return cookie.strip() if cookie else None


def origin_allowed(origin: str) -> bool:
    value = (origin or "").strip()
    if not value:
        return False
    if value in settings.cors_origin_list:
        return True
    pattern = settings.cors_regex
    return bool(pattern and re.fullmatch(pattern, value))


def enforce_csrf(request: Request) -> None:
    if request.method.upper() in SAFE_METHODS:
        return
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return
    if not request.cookies.get(ACCESS_COOKIE):
        return
    # Front (Netlify) y API (Render) son dominios distintos: el JS no puede leer
    # pos_csrf. Si el Origin es el de Promethixia, el navegador ya bloqueó a otros sitios.
    if origin_allowed(request.headers.get("origin", "")):
        return
    cookie_token = request.cookies.get(CSRF_COOKIE, "")
    header_token = request.headers.get(CSRF_HEADER, "")
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solicitud rechazada. Recarga e inicia sesión de nuevo.",
        )
