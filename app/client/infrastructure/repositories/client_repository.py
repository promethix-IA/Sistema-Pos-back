from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from client.infrastructure.models.client_model import ClientModel, ClientPurchaseModel
from shared.clock import money, now_bogota
from shared.exceptions import NotFoundError


class ClientRepository:
    def __init__(self, session: Session):
        self.session = session

    def all(self, search: str | None = None) -> list[dict]:
        stmt = select(ClientModel).order_by(ClientModel.name.asc())
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(or_(ClientModel.name.ilike(term), ClientModel.phone.ilike(term)))
        clients = list(self.session.scalars(stmt).all())
        histories = self._histories([client.id for client in clients])
        return [self._to_dict(client, histories.get(client.id, [])) for client in clients]

    def get(self, client_id: int) -> dict:
        model = self.session.get(ClientModel, client_id)
        if model is None:
            raise NotFoundError("Cliente no encontrado")
        history = self._histories([client_id]).get(client_id, [])
        return self._to_dict(model, history)

    def create(self, data: dict) -> dict:
        current = now_bogota()
        model = ClientModel(
            name=data["name"].strip(),
            phone=(data.get("phone") or "").strip(),
            email=(data.get("email") or "").strip(),
            address=(data.get("address") or "").strip(),
            id_number=(data.get("idNumber") or "").strip(),
            birth_date=data.get("birthDate") or None,
            total_bought=0,
            last_purchase=None,
            created_at=current,
            updated_at=current,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return self._to_dict(model, [])

    def _histories(self, client_ids: list[int]) -> dict[int, list[dict]]:
        if not client_ids:
            return {}
        stmt = (
            select(ClientPurchaseModel)
            .where(ClientPurchaseModel.client_id.in_(client_ids))
            .order_by(ClientPurchaseModel.purchased_on.desc(), ClientPurchaseModel.id.desc())
        )
        grouped: dict[int, list[dict]] = {}
        for purchase in self.session.scalars(stmt).all():
            grouped.setdefault(purchase.client_id, []).append(
                {
                    "date": purchase.purchased_on.isoformat(),
                    "items": purchase.items,
                    "total": money(purchase.total),
                }
            )
        return grouped

    def _to_dict(self, model: ClientModel, history: list[dict]) -> dict:
        return {
            "id": model.id,
            "name": model.name,
            "phone": model.phone,
            "email": model.email,
            "address": model.address,
            "idNumber": model.id_number,
            "birthDate": model.birth_date.isoformat() if isinstance(model.birth_date, date) else "",
            "totalBought": money(model.total_bought),
            "lastPurchase": model.last_purchase.isoformat() if model.last_purchase else "—",
            "history": history,
        }
