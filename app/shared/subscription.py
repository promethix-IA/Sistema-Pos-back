from datetime import datetime, timedelta

from shared.clock import now_bogota
from shared.exceptions import UnauthorizedError
from user.domain.entities.user import User
from user.domain.ports.user_repository import UserRepository

PLAN_TRIAL = "trial"
PLAN_MONTHLY = "monthly"
PLAN_NONE = ""
TRIAL_DAYS = 15
MONTHLY_DAYS = 30


def expires_for_plan(plan: str, from_when: datetime | None = None) -> datetime:
    start = from_when or now_bogota()
    days = TRIAL_DAYS if plan == PLAN_TRIAL else MONTHLY_DAYS
    return start + timedelta(days=days)


def next_monthly_expiry(current: datetime | None, from_when: datetime | None = None) -> datetime:
    now = from_when or now_bogota()
    base = current if current and current > now else now
    return base + timedelta(days=MONTHLY_DAYS)


def billing_owner(user: User, repository: UserRepository) -> User:
    if user.owner_id:
        owner = repository.get_by_id(int(user.owner_id))
        return owner or user
    return user


def desktop_download_enabled(user: User, repository: UserRepository) -> bool:
    if user.role == "admin":
        return False
    if user.role not in {"owner", "administrador"}:
        return False
    return bool(billing_owner(user, repository).desktop_download)


def desktop_profile(user: User, repository: UserRepository) -> dict:
    from desktop.installer import normalize_channel

    owner = billing_owner(user, repository)
    return {
        "desktop_download": desktop_download_enabled(user, repository),
        "desktop_channel": normalize_channel(owner.desktop_channel),
        "desktop_updates_until": owner.desktop_updates_until or "",
    }


def is_subscription_expired(user: User, now: datetime | None = None) -> bool:
    if user.role == "admin":
        return False
    plan = (user.plan or PLAN_NONE).strip()
    if plan not in {PLAN_TRIAL, PLAN_MONTHLY}:
        return False
    if user.plan_expires_at is None:
        return False
    moment = now or now_bogota()
    expires = user.plan_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=moment.tzinfo)
    return expires <= moment


def ensure_subscription_active(user: User, repository: UserRepository) -> None:
    if user.role == "admin":
        return
    owner = billing_owner(user, repository)
    if not is_subscription_expired(owner):
        return
    if owner.plan == PLAN_TRIAL:
        raise UnauthorizedError(
            "Tu prueba gratis de 15 días terminó. Escríbenos a promethixia@gmail.com o por WhatsApp para activar el plan mensual."
        )
    raise UnauthorizedError(
        "Tu plan mensual venció. Escríbenos a promethixia@gmail.com o por WhatsApp para renovar."
    )


def plan_label(plan: str | None) -> str:
    if plan == PLAN_TRIAL:
        return "Prueba gratis"
    if plan == PLAN_MONTHLY:
        return "Mensual"
    return "Libre"


def subscription_state(user: User, now: datetime | None = None) -> str:
    if user.role == "admin":
        return "plataforma"
    if is_subscription_expired(user, now):
        return "vencido"
    if user.plan == PLAN_TRIAL:
        return "prueba"
    if user.plan == PLAN_MONTHLY:
        return "mensual"
    return "activo"
