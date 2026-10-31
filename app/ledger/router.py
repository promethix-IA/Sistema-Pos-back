from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.session import get_db
from ledger.model import LedgerEntryModel
from shared.clock import money, now_bogota
from shared.exceptions import ForbiddenError, NotFoundError, ValidationError
from shared.http import handle_domain_error
from shared.tenancy import is_platform_admin
from user.domain.entities.user import User
from user.presentation.deps import get_current_user

router = APIRouter(prefix="/ledger", tags=["caja"])

VENTAS = {
    "mensualidad_web": "Mensualidad web",
    "escritorio": "Aplicación de escritorio",
    "actualizaciones": "Actualizaciones",
    "paquete": "Compra de todo",
    "otro": "Otra venta",
}
GASTOS = {
    "dominio": "Dominio",
    "cursor": "Cursor",
    "hosting": "Hosting / servidor",
    "otro": "Otro gasto",
}


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not is_platform_admin(user):
        handle_domain_error(ForbiddenError("Solo el admin de plataforma puede ver la caja."))
    return user


class LedgerIn(BaseModel):
    kind: str = Field(min_length=4, max_length=10)
    category: str = Field(min_length=2, max_length=40)
    concept: str = Field(default="", max_length=200)
    amount: float
    occurred_on: str = ""
    note: str = Field(default="", max_length=400)


class LedgerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    category: str
    category_label: str
    concept: str
    amount: float
    occurred_on: date
    note: str
    created_at: datetime


def _catalogo(kind: str) -> dict[str, str]:
    return VENTAS if kind == "venta" else GASTOS


def _etiqueta(kind: str, category: str) -> str:
    return _catalogo(kind).get(category, category.replace("_", " ").strip() or "Otro")


def _normalizar_fecha(valor: str) -> date:
    texto = (valor or "").strip() or now_bogota().date().isoformat()
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError("La fecha no es válida. Debe verse así: 2026-10-31") from exc


def _normalizar_monto(valor: float) -> Decimal:
    monto = Decimal(str(valor or 0)).quantize(Decimal("0.01"))
    if monto <= 0:
        raise ValidationError("El valor tiene que ser mayor que cero.")
    if monto > Decimal("9999999999.99"):
        raise ValidationError("El valor es demasiado grande.")
    return monto


def _normalizar_kind(valor: str) -> str:
    kind = (valor or "").strip().lower()
    if kind not in {"venta", "gasto"}:
        raise ValidationError("Elige si es una venta o un gasto.")
    return kind


def _normalizar_categoria(kind: str, valor: str) -> str:
    raw = (valor or "").strip().lower().replace(" ", "_")
    if not raw:
        raise ValidationError("Elige el tipo.")
    if raw in _catalogo(kind):
        return raw
    slug = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in raw).strip("_")[:40]
    return slug or "otro"


def _to_out(row: LedgerEntryModel) -> LedgerOut:
    return LedgerOut(
        id=int(row.id),
        kind=row.kind,
        category=row.category,
        category_label=_etiqueta(row.kind, row.category),
        concept=row.concept or "",
        amount=money(row.amount),
        occurred_on=row.occurred_on,
        note=row.note or "",
        created_at=row.created_at,
    )


def _rango_mes(mes: str) -> tuple[date, date] | None:
    texto = (mes or "").strip()
    if not texto or texto == "all":
        return None
    try:
        anio, numero = texto.split("-")
        inicio = date(int(anio), int(numero), 1)
    except ValueError as exc:
        raise ValidationError("El mes no es válido. Debe verse así: 2026-10") from exc
    ultimo = monthrange(inicio.year, inicio.month)[1]
    return inicio, date(inicio.year, inicio.month, ultimo)


@router.get("")
def list_ledger(
    month: str = Query(""),
    session: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    try:
        rango = _rango_mes(month)
    except ValidationError as exc:
        handle_domain_error(exc)
        raise
    stmt = select(LedgerEntryModel).order_by(LedgerEntryModel.occurred_on.desc(), LedgerEntryModel.id.desc())
    if rango:
        stmt = stmt.where(LedgerEntryModel.occurred_on >= rango[0], LedgerEntryModel.occurred_on <= rango[1])
    filas = list(session.scalars(stmt))
    vendido = 0.0
    gastado = 0.0
    ventas: dict[str, float] = {}
    gastos: dict[str, float] = {}
    items = []
    for fila in filas:
        item = _to_out(fila)
        items.append(item)
        if item.kind == "venta":
            vendido += item.amount
            ventas[item.category] = round(ventas.get(item.category, 0) + item.amount, 2)
        else:
            gastado += item.amount
            gastos[item.category] = round(gastos.get(item.category, 0) + item.amount, 2)
    return {
        "month": month or "all",
        "vendido": round(vendido, 2),
        "gastado": round(gastado, 2),
        "ganancia": round(vendido - gastado, 2),
        "ventas": [{"id": key, "label": _etiqueta("venta", key), "amount": amount} for key, amount in ventas.items()],
        "gastos": [{"id": key, "label": _etiqueta("gasto", key), "amount": amount} for key, amount in gastos.items()],
        "items": items,
        "catalogo": {
            "ventas": [{"id": key, "label": label} for key, label in VENTAS.items()],
            "gastos": [{"id": key, "label": label} for key, label in GASTOS.items()],
        },
    }


@router.post("", status_code=201)
def create_ledger(
    payload: LedgerIn,
    session: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> LedgerOut:
    try:
        kind = _normalizar_kind(payload.kind)
        category = _normalizar_categoria(kind, payload.category)
        concept = " ".join((payload.concept or "").split())[:200]
        if not concept:
            raise ValidationError("Escribe el negocio, el servicio o de qué es el movimiento.")
        row = LedgerEntryModel(
            kind=kind,
            category=category,
            concept=concept,
            amount=_normalizar_monto(payload.amount),
            occurred_on=_normalizar_fecha(payload.occurred_on),
            note=" ".join((payload.note or "").split())[:400],
            created_at=now_bogota(),
        )
    except ValidationError as exc:
        handle_domain_error(exc)
        raise
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_out(row)


@router.delete("/{entry_id}", status_code=204)
def delete_ledger(
    entry_id: int,
    session: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> None:
    row = session.get(LedgerEntryModel, entry_id)
    if row is None:
        handle_domain_error(NotFoundError("No encontramos ese movimiento."))
        raise
    session.delete(row)
    session.commit()
