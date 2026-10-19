from sqlalchemy import func, select
from sqlalchemy.orm import Session

from category.infrastructure.models.category_model import CategoryModel
from product.infrastructure.models.product_model import ProductModel
from shared.clock import now_bogota
from shared.exceptions import ConflictError, NotFoundError


class CategoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def all(self) -> list[dict]:
        self._ensure_from_products()
        rows = self.session.scalars(select(CategoryModel).order_by(CategoryModel.name.asc())).all()
        return [{"id": row.id, "name": row.name} for row in rows]

    def create(self, name: str) -> dict:
        clean = name.strip()
        if self._find(clean) is not None:
            raise ConflictError("Ya existe una categoría con ese nombre")
        model = CategoryModel(name=clean, created_at=now_bogota())
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return {"id": model.id, "name": model.name}

    def delete(self, category_id: int) -> None:
        model = self.session.get(CategoryModel, category_id)
        if model is None:
            raise NotFoundError("Categoría no encontrada")
        in_use = self.session.scalar(
            select(ProductModel.id).where(func.lower(ProductModel.category) == model.name.lower())
        )
        if in_use is not None:
            raise ConflictError("La categoría está en uso por productos")
        self.session.delete(model)
        self.session.commit()

    def _ensure_from_products(self) -> None:
        names = self.session.scalars(select(ProductModel.category)).all()
        existing = {row.lower() for row in self.session.scalars(select(CategoryModel.name)).all()}
        created = False
        for name in names:
            clean = (name or "").strip()
            if not clean or clean.lower() in existing:
                continue
            self.session.add(CategoryModel(name=clean, created_at=now_bogota()))
            existing.add(clean.lower())
            created = True
        if created:
            self.session.commit()

    def _find(self, name: str) -> CategoryModel | None:
        stmt = select(CategoryModel).where(func.lower(CategoryModel.name) == name.lower().strip())
        return self.session.scalar(stmt)


def ensure_category(session: Session, name: str) -> None:
    clean = (name or "").strip() or "Sin categoría"
    stmt = select(CategoryModel).where(func.lower(CategoryModel.name) == clean.lower())
    if session.scalar(stmt) is None:
        session.add(CategoryModel(name=clean, created_at=now_bogota()))
