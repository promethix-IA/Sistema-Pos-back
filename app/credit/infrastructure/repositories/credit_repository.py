from sqlalchemy import select
from sqlalchemy.orm import Session

from client.infrastructure.models.client_model import ClientModel
from credit.infrastructure.models.credit_model import CreditDebtModel, CreditPaymentModel
from shared.clock import money, now_bogota
from shared.exceptions import NotFoundError, ValidationError


class CreditRepository:
    def __init__(self, session: Session, user_id: int):
        self.session = session
        self.user_id = user_id

    def list_debts(self, status: str | None = None) -> list[dict]:
        stmt = (
            select(CreditDebtModel, ClientModel.name)
            .outerjoin(ClientModel, ClientModel.id == CreditDebtModel.client_id)
            .where(CreditDebtModel.user_id == self.user_id)
            .order_by(CreditDebtModel.created_at.desc(), CreditDebtModel.id.desc())
        )
        if status:
            stmt = stmt.where(CreditDebtModel.status == status)
        return [self._to_debt(debt, client_name=name or "") for debt, name in self.session.execute(stmt).all()]

    def get_debt(self, debt_id: int) -> dict:
        debt = self.session.get(CreditDebtModel, debt_id)
        if debt is None or debt.user_id != self.user_id:
            raise NotFoundError("Crédito no encontrado")
        return self._to_debt(debt, include_payments=True)

    def create_from_sale(self, sale_id: int, client_id: int, ticket: str, amount: float) -> CreditDebtModel:
        current = now_bogota()
        debt = CreditDebtModel(
            user_id=self.user_id,
            sale_id=sale_id,
            client_id=client_id,
            ticket=ticket,
            total=money(amount),
            paid=0,
            status="pending",
            created_at=current,
            updated_at=current,
        )
        self.session.add(debt)
        self.session.flush()
        return debt

    def add_payment(self, debt_id: int, data: dict) -> dict:
        debt = self.session.get(CreditDebtModel, debt_id)
        if debt is None or debt.user_id != self.user_id:
            raise NotFoundError("Crédito no encontrado")
        remaining = money(money(debt.total) - money(debt.paid))
        if remaining <= 0 or debt.status == "paid":
            raise ValidationError("Este crédito ya está saldado")
        amount = money(data.get("amount") or 0)
        if amount <= 0:
            raise ValidationError("El abono debe ser mayor a 0")
        if amount > remaining:
            raise ValidationError(f"El abono no puede superar el saldo ({remaining})")
        method = (data.get("method") or "efectivo").strip().lower()
        if method not in {"efectivo", "tarjeta", "transferencia"}:
            raise ValidationError("El abono debe ser efectivo, tarjeta o transferencia")
        current = now_bogota()
        self.session.add(
            CreditPaymentModel(
                debt_id=debt.id,
                amount=amount,
                method=method,
                note=(data.get("note") or "").strip(),
                paid_at=current,
            )
        )
        debt.paid = money(money(debt.paid) + amount)
        debt.updated_at = current
        if money(debt.paid) >= money(debt.total):
            debt.status = "paid"
            debt.paid = money(debt.total)
        else:
            debt.status = "partial"
        self.session.commit()
        self.session.refresh(debt)
        return self._to_debt(debt, include_payments=True)

    def _to_debt(self, debt: CreditDebtModel, include_payments: bool = False, client_name: str | None = None) -> dict:
        if client_name is None:
            client = self.session.get(ClientModel, debt.client_id)
            client_name = client.name if client else ""
        remaining = money(max(0, money(debt.total) - money(debt.paid)))
        payload = {
            "id": debt.id,
            "saleId": debt.sale_id,
            "clientId": debt.client_id,
            "clientName": client_name or "",
            "ticket": debt.ticket,
            "total": money(debt.total),
            "paid": money(debt.paid),
            "remaining": remaining,
            "status": debt.status,
            "createdAt": debt.created_at.isoformat(),
            "updatedAt": debt.updated_at.isoformat(),
        }
        if include_payments:
            payments = list(
                self.session.scalars(
                    select(CreditPaymentModel)
                    .where(CreditPaymentModel.debt_id == debt.id)
                    .order_by(CreditPaymentModel.paid_at.desc(), CreditPaymentModel.id.desc())
                ).all()
            )
            payload["payments"] = [
                {
                    "id": payment.id,
                    "amount": money(payment.amount),
                    "method": payment.method,
                    "note": payment.note or "",
                    "paidAt": payment.paid_at.isoformat(),
                }
                for payment in payments
            ]
        return payload
