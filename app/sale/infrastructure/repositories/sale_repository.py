import math
from collections import defaultdict
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from client.infrastructure.models.client_model import ClientModel, ClientPurchaseModel
from inventory.infrastructure.repositories.inventory_repository import record_movement
from product.infrastructure.models.product_model import ProductModel
from product.infrastructure.repositories.product_repository import to_product
from sale.infrastructure.models.sale_model import SaleItemModel, SaleModel
from shared.clock import money, now_bogota
from shared.exceptions import NotFoundError, ValidationError

WEEKDAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


class SaleRepository:
    def __init__(self, session: Session):
        self.session = session

    def confirm(self, data: dict) -> dict:
        if data["payment"] not in {"efectivo", "tarjeta"}:
            raise ValidationError("El método de pago debe ser efectivo o tarjeta")
        if not data["items"]:
            raise ValidationError("El carrito está vacío")

        current = now_bogota()
        product_ids = [item["productId"] for item in data["items"]]
        products = {
            product.id: product
            for product in self.session.scalars(select(ProductModel).where(ProductModel.id.in_(product_ids))).all()
        }
        line_totals = []
        for item in data["items"]:
            product = products.get(item["productId"])
            if product is None:
                raise NotFoundError("Producto no encontrado")
            qty = float(item["qty"])
            needed = math.ceil(qty)
            if product.stock < needed:
                raise ValidationError(f"Sin stock suficiente de {product.name}")
            line_totals.append((product, qty, item.get("weight"), money(product.sell_price) * qty))

        total = round(sum(line[3] for line in line_totals), 2)
        sale = SaleModel(
            ticket=f"TMP-{uuid4().hex[:12]}",
            client_id=data.get("clientId"),
            payment=data["payment"],
            total=total,
            sold_at=current,
        )
        if sale.client_id is not None and self.session.get(ClientModel, sale.client_id) is None:
            raise NotFoundError("Cliente no encontrado")
        self.session.add(sale)
        self.session.flush()
        sale.ticket = f"VTA-{sale.id:06d}"

        names = []
        for product, qty, weight, line_total in line_totals:
            product.stock = max(0, product.stock - math.ceil(qty))
            product.updated_at = current
            record_movement(
                self.session,
                product,
                "SALIDA_VENTA",
                -math.ceil(qty),
                f"Venta {sale.ticket}",
                sale.ticket,
                current,
            )
            self.session.add(
                SaleItemModel(
                    sale_id=sale.id,
                    product_id=product.id,
                    product_name=product.name,
                    qty=qty,
                    weight=weight,
                    unit_price=product.sell_price,
                    line_total=line_total,
                )
            )
            names.append(f"{product.name} ×{qty:g}")

        if sale.client_id is not None:
            client = self.session.get(ClientModel, sale.client_id)
            client.total_bought = money(client.total_bought) + total
            client.last_purchase = current.date()
            client.updated_at = current
            self.session.add(
                ClientPurchaseModel(
                    client_id=client.id,
                    purchased_on=current.date(),
                    items=", ".join(names),
                    total=total,
                )
            )

        self.session.commit()
        self.session.refresh(sale)
        return {
            "id": sale.id,
            "ticket": sale.ticket,
            "total": money(sale.total),
            "payment": sale.payment,
            "soldAt": sale.sold_at.isoformat(),
            "store": "Tienda Central",
        }

    def dashboard(self) -> dict:
        today = now_bogota().date()
        week_start = today - timedelta(days=today.weekday())
        year_start = today.replace(month=1, day=1)
        sales = list(self.session.scalars(select(SaleModel)).all())

        def on(sale: SaleModel):
            return sale.sold_at.astimezone(now_bogota().tzinfo).date()

        today_total = sum(money(sale.total) for sale in sales if on(sale) == today)
        yesterday = today - timedelta(days=1)
        yesterday_total = sum(money(sale.total) for sale in sales if on(sale) == yesterday)
        week_total = sum(money(sale.total) for sale in sales if week_start <= on(sale) <= today)
        previous_week_start = week_start - timedelta(days=7)
        previous_week_total = sum(
            money(sale.total) for sale in sales if previous_week_start <= on(sale) < week_start
        )
        year_total = sum(money(sale.total) for sale in sales if on(sale) >= year_start)

        week_series = []
        for offset in range(7):
            day = week_start + timedelta(days=offset)
            amount = sum(money(sale.total) for sale in sales if on(sale) == day)
            label = "Hoy" if day == today else WEEKDAYS[offset]
            week_series.append({"label": label, "amount": amount})
            if day == today:
                break

        month_amounts: dict[int, float] = defaultdict(float)
        for sale in sales:
            sold = on(sale)
            if sold.year == today.year:
                month_amounts[sold.month] += money(sale.total)
        year_series = [
            {"label": MONTHS[month - 1], "amount": month_amounts[month]}
            for month in range(1, today.month + 1)
        ]

        qty_by_product: dict[int, float] = defaultdict(float)
        items = self.session.scalars(select(SaleItemModel)).all()
        for item in items:
            if item.product_id:
                qty_by_product[item.product_id] += float(item.qty)
        products = list(self.session.scalars(select(ProductModel)).all())
        if qty_by_product:
            ranked = sorted(products, key=lambda product: qty_by_product.get(product.id, 0), reverse=True)
        else:
            ranked = sorted(products, key=lambda product: money(product.sell_price), reverse=True)

        return {
            "dateLabel": today.strftime("%Y-%m-%d"),
            "today": today_total,
            "week": week_total,
            "year": year_total,
            "todayChange": _change(today_total, yesterday_total, "ayer"),
            "weekChange": _change(week_total, previous_week_total, "semana pasada"),
            "weekSeries": week_series,
            "yearSeries": year_series,
            "topProducts": [to_product(product) for product in ranked[:5]],
            "lowStock": [to_product(product) for product in products if product.stock < 5],
        }


def _change(current: float, previous: float, label: str) -> str:
    if previous == 0:
        return "Sin comparación" if current == 0 else f"+100% vs {label}"
    percent = round((current - previous) / previous * 100)
    sign = "+" if percent >= 0 else ""
    return f"{sign}{percent}% vs {label}"
