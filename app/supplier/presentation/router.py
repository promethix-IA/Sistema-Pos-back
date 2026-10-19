from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.session import get_db
from shared.exceptions import NotFoundError
from shared.http import handle_domain_error
from supplier.infrastructure.repositories.supplier_repository import SupplierRepository

router = APIRouter(prefix="/suppliers", tags=["proveedores"])


class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = ""
    products: str = ""


class OrderIn(BaseModel):
    product: str = Field(min_length=1, max_length=200)
    qty: float = Field(gt=0)
    unitPrice: float = Field(ge=0)


def get_repository(session: Session = Depends(get_db)) -> SupplierRepository:
    return SupplierRepository(session)


@router.get("")
def list_suppliers(repository: SupplierRepository = Depends(get_repository)) -> list[dict]:
    return repository.all()


@router.post("", status_code=201)
def create_supplier(payload: SupplierIn, repository: SupplierRepository = Depends(get_repository)) -> dict:
    return repository.create(payload.model_dump())


@router.post("/{supplier_id}/orders", status_code=201)
def create_order(
    supplier_id: int,
    payload: OrderIn,
    repository: SupplierRepository = Depends(get_repository),
) -> dict:
    try:
        return repository.add_order(supplier_id, payload.model_dump())
    except NotFoundError as exc:
        handle_domain_error(exc)
