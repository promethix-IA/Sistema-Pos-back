from sqlalchemy import func, select
from sqlalchemy.orm import Session

from category.infrastructure.repositories.category_repository import ensure_category
from inventory.infrastructure.repositories.inventory_repository import record_movement
from product.infrastructure.models.product_model import ProductModel
from shared.clock import money, now_bogota
from shared.exceptions import ConflictError, NotFoundError


class ProductRepository:
    def __init__(self, session: Session):
        self.session = session

    def all(self) -> list[ProductModel]:
        stmt = select(ProductModel).order_by(ProductModel.name.asc())
        return list(self.session.scalars(stmt).all())

    def get(self, product_id: int) -> ProductModel:
        model = self.session.get(ProductModel, product_id)
        if model is None:
            raise NotFoundError("Producto no encontrado")
        return model

    def create(self, data: dict) -> ProductModel:
        self._ensure_code_available(data["code"])
        current = now_bogota()
        model = ProductModel(
            code=data["code"].strip(),
            name=data["name"].strip(),
            category=(data.get("category") or "Sin categoría").strip() or "Sin categoría",
            buy_price=data["buyPrice"],
            sell_price=data["sellPrice"],
            stock=data["stock"],
            created_at=current,
            updated_at=current,
        )
        self.session.add(model)
        self.session.flush()
        ensure_category(self.session, model.category)
        entry_type = data.get("entryType") or "ENTRADA_INICIAL"
        if entry_type not in {"ENTRADA_INICIAL", "IMPORTACION"}:
            entry_type = "ENTRADA_INICIAL"
        if model.stock:
            note = "Importación masiva CSV" if entry_type == "IMPORTACION" else "Stock inicial al crear producto"
            ref = "IMP" if entry_type == "IMPORTACION" else "INI"
            record_movement(self.session, model, entry_type, model.stock, note, ref)
        self.session.commit()
        self.session.refresh(model)
        return model

    def update(self, product_id: int, data: dict) -> ProductModel:
        model = self.get(product_id)
        if "code" in data and data["code"].strip().lower() != model.code.lower():
            self._ensure_code_available(data["code"], ignore_id=product_id)
            model.code = data["code"].strip()
        if "name" in data:
            model.name = data["name"].strip()
        if "category" in data:
            model.category = data["category"].strip() or "Sin categoría"
            ensure_category(self.session, model.category)
        if "buyPrice" in data:
            model.buy_price = data["buyPrice"]
        if "sellPrice" in data:
            model.sell_price = data["sellPrice"]
        if "stock" in data:
            model.stock = data["stock"]
        model.updated_at = now_bogota()
        self.session.commit()
        self.session.refresh(model)
        return model

    def _ensure_code_available(self, code: str, ignore_id: int | None = None) -> None:
        stmt = select(ProductModel).where(func.lower(ProductModel.code) == code.lower().strip())
        if ignore_id is not None:
            stmt = stmt.where(ProductModel.id != ignore_id)
        if self.session.scalar(stmt) is not None:
            raise ConflictError("Ya existe un producto con ese código")


def to_product(model: ProductModel) -> dict:
    return {
        "id": model.id,
        "code": model.code,
        "name": model.name,
        "category": model.category,
        "buyPrice": money(model.buy_price),
        "sellPrice": money(model.sell_price),
        "stock": model.stock,
    }
