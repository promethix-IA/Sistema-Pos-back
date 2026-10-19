from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from client.infrastructure.repositories.client_repository import ClientRepository
from db.session import get_db
from shared.exceptions import NotFoundError
from shared.http import handle_domain_error

router = APIRouter(prefix="/clients", tags=["clientes"])


class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = ""
    email: str = ""
    address: str = ""
    idNumber: str = ""
    birthDate: date | None = None


def get_repository(session: Session = Depends(get_db)) -> ClientRepository:
    return ClientRepository(session)


@router.get("")
def list_clients(
    search: str | None = Query(default=None),
    repository: ClientRepository = Depends(get_repository),
) -> list[dict]:
    return repository.all(search)


@router.get("/{client_id}")
def get_client(client_id: int, repository: ClientRepository = Depends(get_repository)) -> dict:
    try:
        return repository.get(client_id)
    except NotFoundError as exc:
        handle_domain_error(exc)


@router.post("", status_code=201)
def create_client(payload: ClientIn, repository: ClientRepository = Depends(get_repository)) -> dict:
    return repository.create(payload.model_dump())
