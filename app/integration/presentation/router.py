from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.session import get_db
from integration.infrastructure.repositories.integration_repository import IntegrationRepository
from shared.exceptions import NotFoundError
from shared.http import handle_domain_error

router = APIRouter(prefix="/integrations", tags=["integraciones"])


class ConnectionIn(BaseModel):
    connected: bool


class PrinterIn(BaseModel):
    host: str = Field(min_length=1, max_length=120)
    tcpPort: int = Field(ge=1, le=65535)
    paperWidth: str


class DianIn(BaseModel):
    nit: str = Field(min_length=1, max_length=40)
    softwareId: str = Field(min_length=1, max_length=120)
    softwarePin: str = ""
    environment: str


def get_repository(session: Session = Depends(get_db)) -> IntegrationRepository:
    return IntegrationRepository(session)


@router.get("")
def get_integrations(repository: IntegrationRepository = Depends(get_repository)) -> dict:
    return repository.get()


@router.patch("/peripherals/{code}")
def update_peripheral(
    code: str,
    payload: ConnectionIn,
    repository: IntegrationRepository = Depends(get_repository),
) -> dict:
    try:
        return repository.set_connected(code, payload.connected)
    except NotFoundError as exc:
        handle_domain_error(exc)


@router.put("/printer")
def save_printer(payload: PrinterIn, repository: IntegrationRepository = Depends(get_repository)) -> dict:
    return repository.save_printer(payload.model_dump())


@router.put("/dian")
def save_dian(payload: DianIn, repository: IntegrationRepository = Depends(get_repository)) -> dict:
    return repository.save_dian(payload.model_dump())
