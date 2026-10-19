from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo("America/Bogota")


def now_bogota() -> datetime:
    return datetime.now(BOGOTA)


def money(value) -> float:
    return float(Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def whole(value) -> int:
    return int(Decimal(value or 0).to_integral_value(rounding=ROUND_HALF_UP))
