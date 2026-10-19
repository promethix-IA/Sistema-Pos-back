from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.session import get_db
from sale.infrastructure.repositories.sale_repository import SaleRepository
from shared.exceptions import NotFoundError, ValidationError
from shared.http import handle_domain_error

router = APIRouter(tags=["ventas"])


class SaleItemIn(BaseModel):
    productId: int
    qty: float = Field(gt=0)
    weight: float | None = None


class SaleIn(BaseModel):
    clientId: int | None = None
    payment: str
    items: list[SaleItemIn] = Field(min_length=1)


def get_repository(session: Session = Depends(get_db)) -> SaleRepository:
    return SaleRepository(session)


@router.post("/sales", status_code=201)
def confirm_sale(payload: SaleIn, repository: SaleRepository = Depends(get_repository)) -> dict:
    try:
        return repository.confirm(payload.model_dump())
    except (NotFoundError, ValidationError) as exc:
        handle_domain_error(exc)


@router.get("/dashboard")
def dashboard(repository: SaleRepository = Depends(get_repository)) -> dict:
    return repository.dashboard()
