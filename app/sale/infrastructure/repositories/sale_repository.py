from collections import defaultdict
from datetime import date, datetime, time, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from client.infrastructure.models.client_model import ClientModel, ClientPurchaseModel
from credit.infrastructure.repositories.credit_repository import CreditRepository
from inventory.infrastructure.repositories.inventory_repository import record_movement
from product.infrastructure.models.product_model import ProductModel
from product.infrastructure.repositories.product_repository import to_product
from sale.infrastructure.models.sale_model import SaleItemModel, SaleModel
from shared.clock import BOGOTA, money, now_bogota, qty
from shared.exceptions import NotFoundError, ValidationError
from shift.infrastructure.models.shift_model import CashShiftModel

WEEKDAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
PAYMENT_METHODS = {"efectivo", "tarjeta", "transferencia", "credito", "mixto"}


class SaleRepository:
    def __init__(self, session: Session):
        self.session = session

    def confirm(self, data: dict) -> dict:
        payment = (data.get("payment") or "").strip().lower()
        if payment not in PAYMENT_METHODS:
            raise ValidationError("Método de pago inválido")
        if not data["items"]:
            raise ValidationError("El carrito está vacío")

        shift = self.session.scalars(
            select(CashShiftModel).where(CashShiftModel.status == "open").order_by(CashShiftModel.id.desc())
        ).first()
        if shift is None:
            raise ValidationError("Debes abrir un turno en Cierre de caja antes de vender")

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
            amount = qty(item["qty"])
            tracks = bool(getattr(product, "tracks_inventory", True))
            sale_mode = (getattr(product, "sale_mode", None) or "unidad").strip().lower()
            if sale_mode == "unidad":
                tracks = True
            if tracks and qty(product.stock) < amount:
                raise ValidationError(f"Sin stock suficiente de {product.name}")
            weight = item.get("weight")
            if sale_mode == "granel" and weight is None:
                weight = amount
            line_totals.append((product, amount, weight, tracks, money(product.sell_price) * amount))

        total = round(sum(line[4] for line in line_totals), 2)
        amounts = _payment_breakdown(payment, total, data)
        client_id = data.get("clientId")
        if amounts["credito"] > 0 and not client_id:
            raise ValidationError("Las ventas a crédito requieren un cliente")
        if client_id is not None and self.session.get(ClientModel, client_id) is None:
            raise NotFoundError("Cliente no encontrado")

        sale = SaleModel(
            ticket=f"TMP-{uuid4().hex[:12]}",
            client_id=client_id,
            shift_id=shift.id,
            payment=payment,
            total=total,
            amount_efectivo=amounts["efectivo"],
            amount_tarjeta=amounts["tarjeta"],
            amount_transferencia=amounts["transferencia"],
            amount_credito=amounts["credito"],
            status="completed",
            sold_at=current,
        )
        self.session.add(sale)
        self.session.flush()
        sale.ticket = f"VTA-{sale.id:06d}"

        names = []
        for product, amount, weight, tracks, line_total in line_totals:
            if tracks:
                product.stock = max(0, qty(product.stock) - amount)
                product.updated_at = current
                record_movement(
                    self.session,
                    product,
                    "SALIDA_VENTA",
                    -amount,
                    f"Venta {sale.ticket}",
                    sale.ticket,
                    current,
                )
            self.session.add(
                SaleItemModel(
                    sale_id=sale.id,
                    product_id=product.id,
                    product_name=product.name,
                    qty=amount,
                    cancelled_qty=0,
                    weight=weight,
                    unit_price=product.sell_price,
                    line_total=line_total,
                )
            )
            names.append(f"{product.name} ×{amount:g}")

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

        if amounts["credito"] > 0:
            CreditRepository(self.session).create_from_sale(
                sale.id, int(sale.client_id), sale.ticket, amounts["credito"]
            )

        self.session.commit()
        self.session.refresh(sale)
        return {
            "id": sale.id,
            "ticket": sale.ticket,
            "total": money(sale.total),
            "payment": sale.payment,
            "amounts": {
                "efectivo": money(sale.amount_efectivo),
                "tarjeta": money(sale.amount_tarjeta),
                "transferencia": money(sale.amount_transferencia),
                "credito": money(sale.amount_credito),
            },
            "soldAt": sale.sold_at.isoformat(),
            "store": "Tienda Central",
        }

    def list_by_date(self, day: date) -> list[dict]:
        start = datetime.combine(day, time.min, tzinfo=BOGOTA)
        end = start + timedelta(days=1)
        sales = list(
            self.session.scalars(
                select(SaleModel)
                .where(SaleModel.sold_at >= start, SaleModel.sold_at < end)
                .order_by(SaleModel.sold_at.desc(), SaleModel.id.desc())
            ).all()
        )
        return [self._to_sale_detail(sale) for sale in sales]

    def cancel_sale(self, sale_id: int, reason: str = "") -> dict:
        sale = self._get_sale(sale_id)
        items = self._items_for(sale_id)
        returns = []
        for item in items:
            remaining = qty(item.qty) - qty(item.cancelled_qty)
            if remaining > 0:
                returns.append({"itemId": item.id, "qty": remaining})
        if not returns:
            raise ValidationError("La venta ya está completamente cancelada")
        return self._apply_returns(sale, items, returns, reason or "Cancelación total de la venta")

    def return_items(self, sale_id: int, data: dict) -> dict:
        sale = self._get_sale(sale_id)
        items = self._items_for(sale_id)
        returns = data.get("items") or []
        if not returns:
            raise ValidationError("Indica al menos un producto a devolver")
        reason = (data.get("reason") or "").strip() or "Devolución parcial"
        return self._apply_returns(sale, items, returns, reason)

    def _apply_returns(
        self,
        sale: SaleModel,
        items: list[SaleItemModel],
        returns: list[dict],
        reason: str,
    ) -> dict:
        if (sale.status or "completed") == "cancelled":
            raise ValidationError("La venta ya está cancelada")

        by_id = {item.id: item for item in items}
        current = now_bogota()
        refunded = 0.0
        product_ids = [item.product_id for item in items if item.product_id]
        products = {
            product.id: product
            for product in self.session.scalars(select(ProductModel).where(ProductModel.id.in_(product_ids))).all()
        } if product_ids else {}

        for entry in returns:
            item = by_id.get(int(entry["itemId"]))
            if item is None:
                raise NotFoundError("Producto de la venta no encontrado")
            amount = qty(entry["qty"])
            if amount <= 0:
                raise ValidationError("La cantidad a devolver debe ser mayor a 0")
            remaining = qty(qty(item.qty) - qty(item.cancelled_qty))
            if amount > remaining:
                raise ValidationError(f"Solo puedes devolver hasta {remaining:g} de {item.product_name}")

            item.cancelled_qty = qty(qty(item.cancelled_qty) + amount)
            unit = money(item.unit_price)
            refunded = round(refunded + unit * amount, 2)
            item.line_total = money(unit * (qty(item.qty) - qty(item.cancelled_qty)))

            product = products.get(item.product_id) if item.product_id else None
            if product is not None:
                tracks = bool(getattr(product, "tracks_inventory", True))
                sale_mode = (getattr(product, "sale_mode", None) or "unidad").strip().lower()
                if sale_mode == "unidad":
                    tracks = True
                if tracks:
                    product.stock = qty(product.stock) + amount
                    product.updated_at = current
                    record_movement(
                        self.session,
                        product,
                        "ENTRADA_DEVOLUCION",
                        amount,
                        f"{reason} · {sale.ticket}",
                        sale.ticket,
                        current,
                    )

        sale.total = money(max(0, money(sale.total) - refunded))
        sale.status = self._status_from_items(items)

        if sale.client_id is not None and refunded:
            client = self.session.get(ClientModel, sale.client_id)
            if client is not None:
                client.total_bought = max(0, money(client.total_bought) - refunded)
                client.updated_at = current

        self.session.commit()
        self.session.refresh(sale)
        detail = self._to_sale_detail(sale)
        detail["refunded"] = refunded
        return detail

    def _get_sale(self, sale_id: int) -> SaleModel:
        sale = self.session.get(SaleModel, sale_id)
        if sale is None:
            raise NotFoundError("Venta no encontrada")
        return sale

    def _items_for(self, sale_id: int) -> list[SaleItemModel]:
        return list(
            self.session.scalars(
                select(SaleItemModel).where(SaleItemModel.sale_id == sale_id).order_by(SaleItemModel.id.asc())
            ).all()
        )

    def _status_from_items(self, items: list[SaleItemModel]) -> str:
        if not items:
            return "cancelled"
        all_cancelled = all(qty(item.cancelled_qty) >= qty(item.qty) for item in items)
        if all_cancelled:
            return "cancelled"
        any_cancelled = any(qty(item.cancelled_qty) > 0 for item in items)
        return "partially_cancelled" if any_cancelled else "completed"

    def _to_sale_detail(self, sale: SaleModel) -> dict:
        items = self._items_for(sale.id)
        client_name = None
        if sale.client_id is not None:
            client = self.session.get(ClientModel, sale.client_id)
            client_name = client.name if client is not None else None
        mapped = []
        for item in items:
            sold = qty(item.qty)
            cancelled = qty(item.cancelled_qty)
            active = qty(sold - cancelled)
            unit = money(item.unit_price)
            mapped.append(
                {
                    "id": item.id,
                    "productId": item.product_id,
                    "productName": item.product_name,
                    "qty": sold,
                    "cancelledQty": cancelled,
                    "activeQty": active,
                    "weight": qty(item.weight) if item.weight is not None else None,
                    "unitPrice": unit,
                    "lineTotal": money(unit * active),
                }
            )
        return {
            "id": sale.id,
            "ticket": sale.ticket,
            "clientId": sale.client_id,
            "clientName": client_name,
            "shiftId": getattr(sale, "shift_id", None),
            "payment": sale.payment,
            "total": money(sale.total),
            "amounts": {
                "efectivo": money(getattr(sale, "amount_efectivo", 0) or 0),
                "tarjeta": money(getattr(sale, "amount_tarjeta", 0) or 0),
                "transferencia": money(getattr(sale, "amount_transferencia", 0) or 0),
                "credito": money(getattr(sale, "amount_credito", 0) or 0),
            },
            "status": sale.status or "completed",
            "soldAt": sale.sold_at.isoformat(),
            "items": mapped,
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
                active = qty(item.qty) - qty(getattr(item, "cancelled_qty", 0) or 0)
                if active > 0:
                    qty_by_product[item.product_id] += active
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
            "lowStock": [
                to_product(product)
                for product in products
                if bool(getattr(product, "tracks_inventory", True)) and qty(product.stock) < 5
            ],
        }


def _payment_breakdown(payment: str, total: float, data: dict) -> dict[str, float]:
    raw = data.get("amounts") or {}
    if payment == "mixto":
        amounts = {
            "efectivo": money(raw.get("efectivo") or 0),
            "tarjeta": money(raw.get("tarjeta") or 0),
            "transferencia": money(raw.get("transferencia") or 0),
            "credito": money(raw.get("credito") or 0),
        }
        if any(value < 0 for value in amounts.values()):
            raise ValidationError("Los montos de pago no pueden ser negativos")
        paid = round(sum(amounts.values()), 2)
        if abs(paid - total) > 0.01:
            raise ValidationError(f"La suma de pagos ({paid}) debe igualar el total ({total})")
        if paid <= 0:
            raise ValidationError("Indica cómo se paga la venta mixta")
        return amounts

    amounts = {"efectivo": 0.0, "tarjeta": 0.0, "transferencia": 0.0, "credito": 0.0}
    amounts[payment] = money(total)
    return amounts


def _change(current: float, previous: float, label: str) -> str:
    if previous == 0:
        return "Sin comparación" if current == 0 else f"+100% vs {label}"
    percent = round((current - previous) / previous * 100)
    sign = "+" if percent >= 0 else ""
    return f"{sign}{percent}% vs {label}"
