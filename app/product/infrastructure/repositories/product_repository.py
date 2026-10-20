from sqlalchemy import func, select
from sqlalchemy.orm import Session

from category.infrastructure.repositories.category_repository import ensure_category
from inventory.infrastructure.repositories.inventory_repository import record_movement
from product.infrastructure.models.product_model import ProductModel
from shared.clock import money, now_bogota, qty
from shared.exceptions import ConflictError, NotFoundError, ValidationError

VALID_SALE_MODES = {"unidad", "granel"}


def normalize_sale_settings(data: dict, *, existing: ProductModel | None = None) -> tuple[str, bool]:
    raw_mode = data.get("saleMode")
    if raw_mode is None and existing is not None:
        sale_mode = (existing.sale_mode or "unidad").strip().lower()
    else:
        sale_mode = str(raw_mode or "unidad").strip().lower()
    if sale_mode not in VALID_SALE_MODES:
        raise ValidationError("El modo de venta debe ser unidad o granel")

    if "tracksInventory" in data:
        tracks_inventory = bool(data["tracksInventory"])
    elif existing is not None:
        tracks_inventory = bool(existing.tracks_inventory)
    else:
        tracks_inventory = True

    if sale_mode == "unidad":
        tracks_inventory = True
    return sale_mode, tracks_inventory


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
        sale_mode, tracks_inventory = normalize_sale_settings(data)
        stock = qty(data.get("stock") or 0) if tracks_inventory else 0
        current = now_bogota()
        model = ProductModel(
            code=data["code"].strip(),
            name=data["name"].strip(),
            category=(data.get("category") or "Sin categoría").strip() or "Sin categoría",
            buy_price=data["buyPrice"],
            sell_price=data["sellPrice"],
            stock=stock,
            sale_mode=sale_mode,
            tracks_inventory=tracks_inventory,
            created_at=current,
            updated_at=current,
        )
        self.session.add(model)
        self.session.flush()
        ensure_category(self.session, model.category)
        entry_type = data.get("entryType") or "ENTRADA_INICIAL"
        if entry_type not in {"ENTRADA_INICIAL", "IMPORTACION"}:
            entry_type = "ENTRADA_INICIAL"
        if tracks_inventory and stock:
            note = "Importación masiva CSV" if entry_type == "IMPORTACION" else "Stock inicial al crear producto"
            ref = "IMP" if entry_type == "IMPORTACION" else "INI"
            record_movement(self.session, model, entry_type, stock, note, ref)
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
        if "saleMode" in data or "tracksInventory" in data:
            model.sale_mode, model.tracks_inventory = normalize_sale_settings(data, existing=model)
            if not model.tracks_inventory:
                model.stock = 0
        if "stock" in data and model.tracks_inventory:
            model.stock = qty(data["stock"])
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
    sale_mode = (model.sale_mode or "unidad").strip().lower()
    if sale_mode not in VALID_SALE_MODES:
        sale_mode = "unidad"
    tracks_inventory = True if sale_mode == "unidad" else bool(model.tracks_inventory)
    return {
        "id": model.id,
        "code": model.code,
        "name": model.name,
        "category": model.category,
        "buyPrice": money(model.buy_price),
        "sellPrice": money(model.sell_price),
        "stock": qty(model.stock),
        "saleMode": sale_mode,
        "tracksInventory": tracks_inventory,
    }
