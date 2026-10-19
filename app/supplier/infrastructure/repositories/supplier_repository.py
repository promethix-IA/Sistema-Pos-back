from sqlalchemy import select
from sqlalchemy.orm import Session

from product.infrastructure.models.product_model import ProductModel
from shared.clock import money, now_bogota, whole
from shared.exceptions import NotFoundError
from supplier.infrastructure.models.supplier_model import SupplierModel, SupplierOrderModel


class SupplierRepository:
    def __init__(self, session: Session):
        self.session = session

    def all(self) -> list[dict]:
        suppliers = list(self.session.scalars(select(SupplierModel).order_by(SupplierModel.name.asc())).all())
        orders = self._orders([item.id for item in suppliers])
        return [self._to_dict(item, orders.get(item.id, [])) for item in suppliers]

    def create(self, data: dict) -> dict:
        current = now_bogota()
        model = SupplierModel(
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
        if supplier is None:
            raise NotFoundError("Proveedor no encontrado")
        qty = data["qty"]
        unit_price = data["unitPrice"]
        order = SupplierOrderModel(
            supplier_id=supplier.id,
            ordered_on=now_bogota().date(),
            product=data["product"].strip(),
            qty=qty,
            unit_price=unit_price,
            price=qty * unit_price,
        )
        self.session.add(order)
        fragment = data["product"].strip().lower()
        products = self.session.scalars(select(ProductModel)).all()
        added = whole(qty)
        for product in products:
            if fragment and fragment in product.name.lower():
                product.stock += added
                product.updated_at = now_bogota()
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
