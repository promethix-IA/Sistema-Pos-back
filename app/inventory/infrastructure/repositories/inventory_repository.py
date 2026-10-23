from collections import defaultdict
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from inventory.infrastructure.models.movement_model import InventoryMovementModel
from product.infrastructure.models.product_model import ProductModel
from sale.infrastructure.models.sale_model import SaleItemModel, SaleModel
from shared.clock import now_bogota, qty as as_qty
from shared.exceptions import NotFoundError, ValidationError
from supplier.infrastructure.models.supplier_model import SupplierOrderModel


def record_movement(
    session: Session,
    product: ProductModel,
    movement_type: str,
    qty: float,
    note: str,
    ref: str = "",
    when: datetime | date | None = None,
) -> None:
    if qty == 0:
        return
    current = when or now_bogota()
    moved_on = current.date() if isinstance(current, datetime) else current
    session.add(
        InventoryMovementModel(
            user_id=product.user_id,
            product_id=product.id,
            product_name=product.name,
            product_code=product.code,
            movement_type=movement_type,
            qty=qty,
            balance_after=as_qty(product.stock),
            note=note,
            ref=ref or "",
            moved_on=moved_on,
            created_at=now_bogota(),
        )
    )


def to_movement(model: InventoryMovementModel) -> dict:
    return {
        "id": model.id,
        "date": model.moved_on.isoformat(),
        "productId": model.product_id,
        "productName": model.product_name,
        "productCode": model.product_code,
        "type": model.movement_type,
        "qty": as_qty(model.qty),
        "balanceAfter": as_qty(model.balance_after),
        "note": model.note,
        "ref": model.ref or "",
    }


class InventoryRepository:
    def __init__(self, session: Session, user_id: int):
        self.session = session
        self.user_id = user_id

    def all(self) -> list[dict]:
        stmt = (
            select(InventoryMovementModel)
            .where(InventoryMovementModel.user_id == self.user_id)
            .order_by(
                InventoryMovementModel.moved_on.desc(),
                InventoryMovementModel.id.desc(),
            )
        )
        return [to_movement(item) for item in self.session.scalars(stmt).all()]

    def adjust(self, data: dict) -> dict:
        product = self.session.get(ProductModel, data["productId"])
        if product is None or product.user_id != self.user_id:
            raise NotFoundError("Producto no encontrado")
        if not bool(getattr(product, "tracks_inventory", True)):
            raise ValidationError("Este producto no lleva inventario")
        value = as_qty(data["qty"])
        current_stock = as_qty(product.stock)
        delta = as_qty(value - current_stock) if data["mode"] == "set" else value
        if delta == 0:
            raise ValidationError("El ajuste no cambia el stock")
        new_stock = as_qty(current_stock + delta)
        if new_stock < 0:
            raise ValidationError("El stock no puede quedar negativo")
        product.stock = new_stock
        product.updated_at = now_bogota()
        reason = (data.get("reason") or "").strip()
        if not reason:
            reason = f"Ajuste a cantidad {value:g}" if data["mode"] == "set" else f"Ajuste relativo {delta:+g}"
        record_movement(self.session, product, "AJUSTE", delta, reason, "AJUSTE")
        self.session.commit()
        movement = self.session.scalars(
            select(InventoryMovementModel)
            .where(InventoryMovementModel.user_id == self.user_id)
            .order_by(InventoryMovementModel.id.desc())
        ).first()
        return to_movement(movement)


def seed_movements(session: Session) -> None:
    existing = int(session.scalar(select(func.count()).select_from(InventoryMovementModel)) or 0)
    if existing:
        return
    products = list(session.scalars(select(ProductModel)).all())
    if not products:
        return
    by_id = {product.id: product for product in products}
    events: list[tuple] = []

    sale_rows = session.execute(
        select(SaleItemModel, SaleModel).join(SaleModel, SaleItemModel.sale_id == SaleModel.id)
    ).all()
    for item, sale in sale_rows:
        product = by_id.get(item.product_id)
        if product is None:
            continue
        sold_on = sale.sold_at.date() if isinstance(sale.sold_at, datetime) else sale.sold_at
        events.append(
            (sold_on, 1, product, "SALIDA_VENTA", -as_qty(item.qty), f"Venta {sale.ticket}", sale.ticket)
        )

    for order in session.scalars(select(SupplierOrderModel)).all():
        added = as_qty(order.qty)
        if order.product_id and order.product_id in by_id:
            targets = [by_id[order.product_id]]
        else:
            fragment = (order.product or "").strip().lower()
            targets = [product for product in products if fragment and fragment in product.name.lower()]
        invoice = order.invoice or ""
        for product in targets:
            events.append(
                (order.ordered_on, 0, product, "ENTRADA_COMPRA", added, f"Compra {order.product}", invoice)
            )

    net: dict[int, float] = defaultdict(float)
    for _moved_on, _sort, product, _movement_type, movement_qty, _note, _ref in events:
        net[product.id] += as_qty(movement_qty)

    combined = list(events)
    for product in products:
        opening = as_qty(as_qty(product.stock) - net[product.id])
        if opening:
            combined.append(
                (date(2000, 1, 1), 0, product, "ENTRADA_INICIAL", opening, "Stock inicial del sistema", "INI")
            )

    balances: dict[int, float] = defaultdict(float)
    for moved_on, _sort, product, movement_type, movement_qty, note, ref in sorted(
        combined, key=lambda row: (row[0], row[1], row[2].id)
    ):
        balances[product.id] = as_qty(balances[product.id] + as_qty(movement_qty))
        session.add(
            InventoryMovementModel(
                user_id=product.user_id,
                product_id=product.id,
                product_name=product.name,
                product_code=product.code,
                movement_type=movement_type,
                qty=movement_qty,
                balance_after=balances[product.id],
                note=note,
                ref=ref or "",
                moved_on=moved_on,
                created_at=now_bogota(),
            )
        )
    session.commit()
