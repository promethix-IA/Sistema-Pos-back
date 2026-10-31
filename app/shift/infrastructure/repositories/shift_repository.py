from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from credit.infrastructure.models.credit_model import CreditDebtModel, CreditPaymentModel
from product.infrastructure.models.product_model import ProductModel
from sale.infrastructure.models.sale_model import SaleItemModel, SaleModel
from shared.clock import money, now_bogota
from shared.exceptions import ConflictError, NotFoundError, ValidationError
from shift.infrastructure.models.shift_model import CashShiftModel


class ShiftRepository:
    def __init__(self, session: Session, user_id: int):
        self.session = session
        self.user_id = user_id

    def current(self) -> dict | None:
        shift = self._open_shift()
        if shift is None:
            return None
        return self.summary(shift.id)

    def list_shifts(self, limit: int = 30) -> list[dict]:
        rows = list(
            self.session.scalars(
                select(CashShiftModel)
                .where(CashShiftModel.user_id == self.user_id)
                .order_by(CashShiftModel.opened_at.desc(), CashShiftModel.id.desc())
                .limit(limit)
            ).all()
        )
        return [self._to_shift(row) for row in rows]

    def open_shift(self, data: dict) -> dict:
        if self._open_shift() is not None:
            raise ConflictError("Ya hay un turno abierto. Ciérralo antes de abrir otro.")
        opening = money(data.get("openingCash") or 0)
        if opening < 0:
            raise ValidationError("El efectivo inicial no puede ser negativo")
        current = now_bogota()
        shift = CashShiftModel(
            user_id=self.user_id,
            opened_at=current,
            closed_at=None,
            opening_cash=opening,
            counted_cash=None,
            status="open",
            opened_by=(data.get("openedBy") or "").strip(),
            closed_by="",
            notes=(data.get("notes") or "").strip(),
        )
        self.session.add(shift)
        self.session.commit()
        self.session.refresh(shift)
        return self._to_shift(shift)

    def close_shift(self, shift_id: int, data: dict) -> dict:
        shift = self.session.get(CashShiftModel, shift_id)
        if shift is None or shift.user_id != self.user_id:
            raise NotFoundError("Turno no encontrado")
        if shift.status != "open":
            raise ValidationError("El turno ya está cerrado")
        counted = data.get("countedCash")
        counted_value = money(counted) if counted is not None and counted != "" else None
        if counted_value is not None and counted_value < 0:
            raise ValidationError("El efectivo contado no puede ser negativo")
        shift.counted_cash = counted_value
        shift.closed_at = now_bogota()
        shift.status = "closed"
        shift.closed_by = (data.get("closedBy") or "").strip()
        if data.get("notes"):
            shift.notes = (data.get("notes") or "").strip()
        self.session.commit()
        self.session.refresh(shift)
        return self.summary(shift.id)

    def summary(self, shift_id: int) -> dict:
        shift = self.session.get(CashShiftModel, shift_id)
        if shift is None or shift.user_id != self.user_id:
            raise NotFoundError("Turno no encontrado")
        sales = list(
            self.session.scalars(
                select(SaleModel)
                .where(SaleModel.user_id == self.user_id, SaleModel.shift_id == shift_id)
                .order_by(SaleModel.sold_at.asc())
            ).all()
        )
        active_sales = [sale for sale in sales if (sale.status or "completed") != "cancelled"]

        by_method = {
            "efectivo": 0.0,
            "tarjeta": 0.0,
            "transferencia": 0.0,
            "credito": 0.0,
        }
        for sale in active_sales:
            by_method["efectivo"] += money(getattr(sale, "amount_efectivo", 0) or 0)
            by_method["tarjeta"] += money(getattr(sale, "amount_tarjeta", 0) or 0)
            by_method["transferencia"] += money(getattr(sale, "amount_transferencia", 0) or 0)
            by_method["credito"] += money(getattr(sale, "amount_credito", 0) or 0)

        # Credit collections during this shift (abonados en caja)
        credit_collections = {"efectivo": 0.0, "tarjeta": 0.0, "transferencia": 0.0}
        if shift.opened_at:
            payments = list(
                self.session.scalars(
                    select(CreditPaymentModel)
                    .join(CreditDebtModel, CreditPaymentModel.debt_id == CreditDebtModel.id)
                    .where(
                        CreditDebtModel.user_id == self.user_id,
                        CreditPaymentModel.paid_at >= shift.opened_at,
                        CreditPaymentModel.paid_at <= (shift.closed_at or now_bogota()),
                    )
                ).all()
            )
            for payment in payments:
                method = (payment.method or "").strip().lower()
                if method in credit_collections:
                    credit_collections[method] += money(payment.amount)

        by_category: dict[str, float] = defaultdict(float)
        sale_ids = [sale.id for sale in active_sales]
        if sale_ids:
            items = list(self.session.scalars(select(SaleItemModel).where(SaleItemModel.sale_id.in_(sale_ids))).all())
            product_ids = [item.product_id for item in items if item.product_id]
            products = {
                product.id: product
                for product in self.session.scalars(select(ProductModel).where(ProductModel.id.in_(product_ids))).all()
            } if product_ids else {}
            for item in items:
                from shared.clock import qty

                active_qty = qty(item.qty) - qty(getattr(item, "cancelled_qty", 0) or 0)
                if active_qty <= 0:
                    continue
                product = products.get(item.product_id) if item.product_id else None
                category = (product.category if product is not None else None) or "Sin categoría"
                by_category[category] += money(money(item.unit_price) * active_qty)

        contado = round(
            by_method["efectivo"] + by_method["tarjeta"] + by_method["transferencia"]
            + credit_collections["efectivo"] + credit_collections["tarjeta"] + credit_collections["transferencia"],
            2,
        )
        expected_cash = round(
            money(shift.opening_cash)
            + by_method["efectivo"]
            + credit_collections["efectivo"],
            2,
        )
        counted = money(shift.counted_cash) if shift.counted_cash is not None else None
        difference = round(counted - expected_cash, 2) if counted is not None else None

        return {
            **self._to_shift(shift),
            "salesCount": len(active_sales),
            "salesTotal": round(sum(money(sale.total) for sale in active_sales), 2),
            "byMethod": {key: round(value, 2) for key, value in by_method.items()},
            "creditCollections": {key: round(value, 2) for key, value in credit_collections.items()},
            "byCategory": [
                {"category": name, "total": round(total, 2)}
                for name, total in sorted(by_category.items(), key=lambda row: row[1], reverse=True)
            ],
            "contado": contado,
            "expectedCash": expected_cash,
            "difference": difference,
        }

    def _open_shift(self) -> CashShiftModel | None:
        return self.session.scalars(
            select(CashShiftModel)
            .where(CashShiftModel.user_id == self.user_id, CashShiftModel.status == "open")
            .order_by(CashShiftModel.id.desc())
        ).first()

    def _to_shift(self, shift: CashShiftModel) -> dict:
        return {
            "id": shift.id,
            "openedAt": shift.opened_at.isoformat() if shift.opened_at else None,
            "closedAt": shift.closed_at.isoformat() if shift.closed_at else None,
            "openingCash": money(shift.opening_cash),
            "countedCash": money(shift.counted_cash) if shift.counted_cash is not None else None,
            "status": shift.status,
            "openedBy": shift.opened_by or "",
            "closedBy": shift.closed_by or "",
            "notes": shift.notes or "",
        }
