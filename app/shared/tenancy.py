from fastapi import Depends
from sqlalchemy.orm import Session

from db.session import get_db
from user.domain.entities.user import User
from user.presentation.deps import get_current_user

ROLE_ADMIN = "admin"
ROLE_OWNER = "owner"
ROLE_MANAGER = "administrador"
ROLE_CASHIER = "cajero"
ROLE_INVENTORY = "inventario"

BUSINESS_ROLES = {ROLE_MANAGER, ROLE_CASHIER, ROLE_INVENTORY}


def tenant_id_of(user: User) -> int:
    if user.role == ROLE_ADMIN:
        return int(user.id)
    return int(user.owner_id or user.id)


def is_platform_admin(user: User) -> bool:
    return user.role == ROLE_ADMIN


def can_manage_users(user: User) -> bool:
    return user.role in {ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER}


def can_edit_business_settings(user: User) -> bool:
    return user.role in {ROLE_OWNER, ROLE_MANAGER}


def normalize_business_role(role: str | None) -> str:
    value = (role or ROLE_CASHIER).strip().lower()
    if value == "cashier":
        return ROLE_CASHIER
    if value not in BUSINESS_ROLES:
        raise ValueError("Rol inválido")
    return value


def get_tenant_id(user: User = Depends(get_current_user)) -> int:
    return tenant_id_of(user)


def get_session(session: Session = Depends(get_db)) -> Session:
    return session
