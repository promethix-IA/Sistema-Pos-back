from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from category.infrastructure.repositories.category_repository import CategoryRepository
from db.session import get_db
from shared.exceptions import ConflictError, NotFoundError
from shared.http import handle_domain_error
from shared.tenancy import get_tenant_id

router = APIRouter(prefix="/categories", tags=["categorias"])


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


def get_repository(
    session: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> CategoryRepository:
    return CategoryRepository(session, tenant_id)


@router.get("")
def list_categories(repository: CategoryRepository = Depends(get_repository)) -> list[dict]:
    return repository.all()


@router.post("", status_code=201)
def create_category(payload: CategoryIn, repository: CategoryRepository = Depends(get_repository)) -> dict:
    try:
        return repository.create(payload.name)
    except ConflictError as exc:
        handle_domain_error(exc)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, repository: CategoryRepository = Depends(get_repository)) -> Response:
    try:
        repository.delete(category_id)
    except (NotFoundError, ConflictError) as exc:
        handle_domain_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
