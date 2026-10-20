from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.session import get_db
from sale.infrastructure.repositories.sale_repository import SaleRepository
from shared.clock import now_bogota
from shared.exceptions import NotFoundError, ValidationError
from shared.http import handle_domain_error

router = APIRouter(tags=["ventas"])


class SaleItemIn(BaseModel):
    productId: int
    qty: float = Field(gt=0)
    weight: float | None = None


class PaymentAmountsIn(BaseModel):
    efectivo: float = Field(default=0, ge=0)
    tarjeta: float = Field(default=0, ge=0)
    transferencia: float = Field(default=0, ge=0)
    credito: float = Field(default=0, ge=0)


class SaleIn(BaseModel):
    clientId: int | None = None
    payment: str
    amounts: PaymentAmountsIn | None = None
    items: list[SaleItemIn] = Field(min_length=1)


class ReturnItemIn(BaseModel):
    itemId: int
    qty: float = Field(gt=0)


class ReturnIn(BaseModel):
    items: list[ReturnItemIn] = Field(min_length=1)
    reason: str = ""


class CancelIn(BaseModel):
    reason: str = ""


def get_repository(session: Session = Depends(get_db)) -> SaleRepository:
    return SaleRepository(session)


@router.post("/sales", status_code=201)
def confirm_sale(payload: SaleIn, repository: SaleRepository = Depends(get_repository)) -> dict:
    try:
        return repository.confirm(payload.model_dump())
    except (NotFoundError, ValidationError) as exc:
        handle_domain_error(exc)


@router.get("/sales")
def list_sales(
    date_value: date | None = Query(default=None, alias="date"),
    repository: SaleRepository = Depends(get_repository),
) -> list[dict]:
    day = date_value or now_bogota().date()
    return repository.list_by_date(day)


@router.post("/sales/{sale_id}/cancel")
def cancel_sale(
    sale_id: int,
    payload: CancelIn = CancelIn(),
    repository: SaleRepository = Depends(get_repository),
) -> dict:
    try:
        return repository.cancel_sale(sale_id, payload.reason)
    except (NotFoundError, ValidationError) as exc:
        handle_domain_error(exc)


@router.post("/sales/{sale_id}/returns")
def return_sale_items(
    sale_id: int,
    payload: ReturnIn,
    repository: SaleRepository = Depends(get_repository),
) -> dict:
    try:
        return repository.return_items(sale_id, payload.model_dump())
    except (NotFoundError, ValidationError) as exc:
        handle_domain_error(exc)


@router.get("/dashboard")
def dashboard(repository: SaleRepository = Depends(get_repository)) -> dict:
    return repository.dashboard()
