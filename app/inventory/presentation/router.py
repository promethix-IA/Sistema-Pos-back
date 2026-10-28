from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.session import get_db
from inventory.infrastructure.repositories.inventory_repository import InventoryRepository
from shared.exceptions import NotFoundError, ValidationError
from shared.http import handle_domain_error
from shared.tenancy import get_tenant_id

router = APIRouter(prefix="/inventory", tags=["inventario"])


class AdjustmentIn(BaseModel):
    productId: int
    mode: Literal["set", "delta"]
    qty: float
    reason: str = Field(default="", max_length=300)


def get_repository(
    session: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> InventoryRepository:
    return InventoryRepository(session, tenant_id)


@router.get("/movements")
def list_movements(
    repository: InventoryRepository = Depends(get_repository),
    limit: int = Query(default=80, ge=1, le=500),
) -> list[dict]:
    return repository.all(limit=limit)


@router.post("/adjustments", status_code=201)
def create_adjustment(payload: AdjustmentIn, repository: InventoryRepository = Depends(get_repository)) -> dict:
    try:
        return repository.adjust(payload.model_dump())
    except (NotFoundError, ValidationError) as exc:
        handle_domain_error(exc)
