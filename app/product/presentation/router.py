from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.session import get_db
from product.infrastructure.repositories.product_repository import ProductRepository, to_product
from shared.exceptions import ConflictError, NotFoundError, ValidationError
from shared.http import handle_domain_error
from shared.tenancy import get_tenant_id

router = APIRouter(prefix="/products", tags=["productos"])

SaleMode = Literal["unidad", "granel"]


class ProductIn(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    category: str = ""
    buyPrice: float = Field(ge=0)
    sellPrice: float = Field(ge=0)
    stock: float = Field(default=0, ge=0)
    saleMode: SaleMode = "unidad"
    tracksInventory: bool = True
    entryType: str = "ENTRADA_INICIAL"


class ProductPatch(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = None
    buyPrice: float | None = Field(default=None, ge=0)
    sellPrice: float | None = Field(default=None, ge=0)
    stock: float | None = Field(default=None, ge=0)
    saleMode: SaleMode | None = None
    tracksInventory: bool | None = None


def get_repository(
    session: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ProductRepository:
    return ProductRepository(session, tenant_id)


@router.get("")
def list_products(repository: ProductRepository = Depends(get_repository)) -> list[dict]:
    return [to_product(item) for item in repository.all()]


@router.post("", status_code=201)
def create_product(payload: ProductIn, repository: ProductRepository = Depends(get_repository)) -> dict:
    try:
        model = repository.create(payload.model_dump())
    except (ConflictError, ValidationError) as exc:
        handle_domain_error(exc)
    return to_product(model)


@router.patch("/{product_id}")
def update_product(
    product_id: int,
    payload: ProductPatch,
    repository: ProductRepository = Depends(get_repository),
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    try:
        model = repository.update(product_id, data)
    except (NotFoundError, ConflictError, ValidationError) as exc:
        handle_domain_error(exc)
    return to_product(model)
