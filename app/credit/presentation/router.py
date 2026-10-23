from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from credit.infrastructure.repositories.credit_repository import CreditRepository
from db.session import get_db
from shared.exceptions import NotFoundError, ValidationError
from shared.http import handle_domain_error
from shared.tenancy import get_tenant_id

router = APIRouter(prefix="/credits", tags=["creditos"])


class CreditPaymentIn(BaseModel):
    amount: float = Field(gt=0)
    method: str = "efectivo"
    note: str = ""


def get_repository(
    session: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> CreditRepository:
    return CreditRepository(session, tenant_id)


@router.get("")
def list_credits(
    status: str | None = Query(default=None),
    repository: CreditRepository = Depends(get_repository),
) -> list[dict]:
    return repository.list_debts(status)


@router.get("/{debt_id}")
def get_credit(debt_id: int, repository: CreditRepository = Depends(get_repository)) -> dict:
    try:
        return repository.get_debt(debt_id)
    except NotFoundError as exc:
        handle_domain_error(exc)


@router.post("/{debt_id}/payments", status_code=201)
def add_payment(
    debt_id: int,
    payload: CreditPaymentIn,
    repository: CreditRepository = Depends(get_repository),
) -> dict:
    try:
        return repository.add_payment(debt_id, payload.model_dump())
    except (NotFoundError, ValidationError) as exc:
        handle_domain_error(exc)
