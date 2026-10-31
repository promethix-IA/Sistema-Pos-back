from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from license.signing import (
    LicenseKeyError,
    emitir,
    estado_llave,
    hasta_por_periodo,
    normalizar_cliente,
    normalizar_equipo,
    normalizar_hasta,
)
from shared.exceptions import ForbiddenError, ValidationError
from shared.http import handle_domain_error
from shared.tenancy import is_platform_admin
from user.domain.entities.user import User
from user.presentation.deps import get_current_user

router = APIRouter(prefix="/licenses", tags=["licencias"])


class LicenseIn(BaseModel):
    cliente: str = Field(min_length=1, max_length=200)
    equipo: str = Field(min_length=1, max_length=32)
    periodo: str = "anual"
    actualizaciones_hasta: str = ""


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not is_platform_admin(user):
        handle_domain_error(ForbiddenError("Solo el admin de plataforma puede crear licencias."))
    return user


@router.get("")
def license_status(_admin: User = Depends(require_admin)) -> dict:
    llave_lista, aviso = estado_llave()
    return {"ready": llave_lista, "message": aviso}


@router.post("")
def create_license(payload: LicenseIn, _admin: User = Depends(require_admin)) -> Response:
    try:
        cliente = normalizar_cliente(payload.cliente)
        equipo = normalizar_equipo(payload.equipo)
        if payload.periodo.strip():
            hasta = hasta_por_periodo(payload.periodo)
        elif payload.actualizaciones_hasta.strip():
            hasta = normalizar_hasta(payload.actualizaciones_hasta)
        else:
            hasta = hasta_por_periodo("anual")
        archivo, _emitida, filename = emitir(cliente, equipo, hasta)
    except ValidationError as exc:
        handle_domain_error(exc)
        raise
    except LicenseKeyError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message) from exc
    return Response(
        content=archivo,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-License-Filename": filename,
        },
    )
