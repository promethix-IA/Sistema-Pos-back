from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

try:
    from zoneinfo import ZoneInfo

    BOGOTA = ZoneInfo("America/Bogota")
except Exception:
    # El programa empaquetado a veces no encuentra la base de zonas horarias.
    # Bogotá no tiene horario de verano: UTC−5 es el mismo reloj.
    BOGOTA = timezone(timedelta(hours=-5))


def now_bogota() -> datetime:
    return datetime.now(BOGOTA)


def money(value) -> float:
    return float(Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def qty(value) -> float:
    return float(Decimal(value or 0).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def whole(value) -> int:
    return int(Decimal(value or 0).to_integral_value(rounding=ROUND_HALF_UP))
