from sqlalchemy import select
from sqlalchemy.orm import Session

from inventory.infrastructure.repositories.inventory_repository import record_movement
from product.infrastructure.models.product_model import ProductModel
from shared.clock import money, now_bogota, qty as as_qty
from shared.exceptions import NotFoundError, ValidationError
from supplier.infrastructure.models.supplier_model import SupplierModel, SupplierOrderModel


class SupplierRepository:
    def __init__(self, session: Session, user_id: int):
        self.session = session
        self.user_id = user_id

    def all(self) -> list[dict]:
        suppliers = list(
            self.session.scalars(
                select(SupplierModel).where(SupplierModel.user_id == self.user_id).order_by(SupplierModel.name.asc())
            ).all()
        )
        orders = self._orders([item.id for item in suppliers])
        return [self._to_dict(item, orders.get(item.id, [])) for item in suppliers]

    def create(self, data: dict) -> dict:
        current = now_bogota()
        model = SupplierModel(
            user_id=self.user_id,
            name=data["name"].strip(),
            phone=(data.get("phone") or "").strip(),
            products=(data.get("products") or "").strip(),
            created_at=current,
            updated_at=current,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return self._to_dict(model, [])

    def add_order(self, supplier_id: int, data: dict) -> dict:
        supplier = self.session.get(SupplierModel, supplier_id)
        if supplier is None or supplier.user_id != self.user_id:
            raise NotFoundError("Proveedor no encontrado")
        qty = data["qty"]
        unit_price = data["unitPrice"]
        current = now_bogota()
        invoice = (data.get("invoice") or "").strip()
        order = SupplierOrderModel(
            supplier_id=supplier.id,
            ordered_on=current.date(),
            product=data["product"].strip(),
            qty=qty,
            unit_price=unit_price,
            price=qty * unit_price,
            invoice=invoice,
            product_id=data.get("productId"),
        )
        self.session.add(order)
        added = as_qty(qty)
        owned_products = select(ProductModel).where(ProductModel.user_id == self.user_id)
        if data.get("productId"):
            chosen = self.session.get(ProductModel, data["productId"])
            if chosen is None or chosen.user_id != self.user_id:
                raise NotFoundError("Producto no encontrado")
            targets = [chosen]
        else:
            fragment = data["product"].strip().lower()
            targets = [
                product
                for product in self.session.scalars(owned_products).all()
                if fragment and fragment in product.name.lower()
            ]
        for product in targets:
            if not bool(getattr(product, "tracks_inventory", True)):
                raise ValidationError(f"{product.name} no lleva inventario")
            product.stock = as_qty(product.stock) + added
            product.buy_price = unit_price
            product.updated_at = current
            record_movement(
                self.session,
                product,
                "ENTRADA_COMPRA",
                added,
                f"Factura {invoice} · {supplier.name}" if invoice else f"Compra {product.name}",
                invoice,
                current,
            )
        supplier.updated_at = now_bogota()
        self.session.commit()
        return self._supplier_dict(supplier.id)

    def _supplier_dict(self, supplier_id: int) -> dict:
        supplier = self.session.get(SupplierModel, supplier_id)
        orders = self._orders([supplier_id]).get(supplier_id, [])
        return self._to_dict(supplier, orders)

    def _orders(self, supplier_ids: list[int]) -> dict[int, list[dict]]:
        if not supplier_ids:
            return {}
        stmt = (
            select(SupplierOrderModel)
            .where(SupplierOrderModel.supplier_id.in_(supplier_ids))
            .order_by(SupplierOrderModel.ordered_on.desc(), SupplierOrderModel.id.desc())
        )
        grouped: dict[int, list[dict]] = {}
        for order in self.session.scalars(stmt).all():
            grouped.setdefault(order.supplier_id, []).append(
                {
                    "date": order.ordered_on.isoformat(),
                    "product": order.product,
                    "qty": money(order.qty),
                    "unitPrice": money(order.unit_price),
                    "price": money(order.price),
                    "productId": order.product_id,
                    "invoice": order.invoice or "",
                }
            )
        return grouped

    def _to_dict(self, model: SupplierModel, orders: list[dict]) -> dict:
        return {
            "id": model.id,
            "name": model.name,
            "phone": model.phone,
            "products": model.products,
            "orders": orders,
        }
