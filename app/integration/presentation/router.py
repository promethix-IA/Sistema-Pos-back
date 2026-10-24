from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.session import get_db
from integration.infrastructure.repositories.integration_repository import IntegrationRepository
from shared.exceptions import ForbiddenError, NotFoundError
from shared.http import handle_domain_error
from shared.tenancy import can_edit_business_settings, is_platform_admin, get_tenant_id
from user.domain.entities.user import User
from user.presentation.deps import get_current_user

router = APIRouter(prefix="/integrations", tags=["integraciones"])


class ConnectionIn(BaseModel):
    connected: bool


class PrinterIn(BaseModel):
    host: str = Field(min_length=1, max_length=120)
    tcpPort: int = Field(ge=1, le=65535)
    paperWidth: str


class TicketIn(BaseModel):
    storeName: str = Field(min_length=1, max_length=120)
    nitLine: str = Field(default="", max_length=200)
    footer: str = Field(default="", max_length=200)
    showDate: bool = True
    showClient: bool = True
    showPayment: bool = True
    showChange: bool = True
    showReprint: bool = True
    extraHeader: str = ""


class DianIn(BaseModel):
    nit: str = Field(min_length=1, max_length=40)
    softwareId: str = Field(min_length=1, max_length=120)
    softwarePin: str = ""
    environment: str


def get_repository(
    session: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> IntegrationRepository:
    return IntegrationRepository(session, tenant_id)


def require_settings_editor(user: User = Depends(get_current_user)) -> User:
    if not can_edit_business_settings(user):
        handle_domain_error(ForbiddenError("Solo el administrador del negocio puede cambiar esta configuración."))
    return user


@router.get("")
def get_integrations(
    repository: IntegrationRepository = Depends(get_repository),
    user: User = Depends(get_current_user),
) -> dict:
    if is_platform_admin(user):
        handle_domain_error(ForbiddenError("La configuración es solo del administrador del negocio."))
    return repository.get()


@router.patch("/peripherals/{code}")
def update_peripheral(
    code: str,
    payload: ConnectionIn,
    repository: IntegrationRepository = Depends(get_repository),
    _editor: User = Depends(require_settings_editor),
) -> dict:
    try:
        return repository.set_connected(code, payload.connected)
    except NotFoundError as exc:
        handle_domain_error(exc)


@router.put("/printer")
def save_printer(
    payload: PrinterIn,
    repository: IntegrationRepository = Depends(get_repository),
    _editor: User = Depends(require_settings_editor),
) -> dict:
    return repository.save_printer(payload.model_dump())


@router.put("/ticket")
def save_ticket(
    payload: TicketIn,
    repository: IntegrationRepository = Depends(get_repository),
    _editor: User = Depends(require_settings_editor),
) -> dict:
    return repository.save_ticket(payload.model_dump())


@router.put("/dian")
def save_dian(
    payload: DianIn,
    repository: IntegrationRepository = Depends(get_repository),
    _editor: User = Depends(require_settings_editor),
) -> dict:
    return repository.save_dian(payload.model_dump())
