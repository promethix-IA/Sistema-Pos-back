from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from db.session import get_db
from shared.auth import create_access_token
from shared.exceptions import ConflictError, ForbiddenError, NotFoundError, RateLimitError, UnauthorizedError, ValidationError
from shared.http import handle_domain_error
from shared.security.rate_limit import client_ip, ip_limiter, login_limiter
from shared.subscription import PLAN_MONTHLY, PLAN_TRIAL, expires_for_plan, next_monthly_expiry
from shared.tenancy import (
    ROLE_OWNER,
    can_manage_users,
    is_platform_admin,
    normalize_business_role,
    tenant_id_of,
)
from user.application.create_user import CreateUser
from user.application.login_user import LoginUser
from user.domain.entities.user import User
from user.domain.ports.user_repository import UserRepository
from user.infrastructure.repositories.user_repository_impl import UserRepositoryImpl
from user.presentation.deps import get_current_user
from user.presentation.schemas.user_schema import (
    LoginResponseSchema,
    UserCreateSchema,
    UserLoginSchema,
    UserResponseSchema,
    UserRolePatch,
    UserSubscriptionPatch,
)

router = APIRouter(prefix="/users", tags=["usuarios"])


def get_user_repository(session: Session = Depends(get_db)) -> UserRepository:
    return UserRepositoryImpl(session)


@router.get("", response_model=list[UserResponseSchema])
def list_users(
    repository: UserRepository = Depends(get_user_repository),
    _current_user: User = Depends(get_current_user),
) -> list[UserResponseSchema]:
    if is_platform_admin(_current_user):
        users = repository.list_platform_accounts()
    elif can_manage_users(_current_user):
        users = repository.list_for_tenant(tenant_id_of(_current_user))
    else:
        handle_domain_error(ForbiddenError("No tienes permiso para ver el equipo."))
        raise
    return [UserResponseSchema.from_entity(user) for user in users]


@router.post("", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateSchema,
    repository: UserRepository = Depends(get_user_repository),
    _current_user: User = Depends(get_current_user),
) -> UserResponseSchema:
    try:
        if is_platform_admin(_current_user):
            plan = (payload.plan or PLAN_TRIAL).strip().lower()
            if plan not in {PLAN_TRIAL, PLAN_MONTHLY}:
                raise ValidationError("El plan debe ser prueba de 15 días o mensual.")
            user = CreateUser(repository).execute(
                email=payload.email,
                password=payload.password,
                owner_id=None,
                role=ROLE_OWNER,
                plan=plan,
                plan_expires_at=expires_for_plan(plan),
            )
        elif can_manage_users(_current_user) and not is_platform_admin(_current_user):
            try:
                role = normalize_business_role(payload.role)
            except ValueError as exc:
                raise ValidationError("El rol debe ser administrador, cajero o inventario") from exc
            user = CreateUser(repository).execute(
                email=payload.email,
                password=payload.password,
                owner_id=tenant_id_of(_current_user),
                role=role,
            )
        else:
            raise ForbiddenError("No tienes permiso para crear usuarios.")
    except (ConflictError, ForbiddenError, ValidationError) as exc:
        handle_domain_error(exc)
        raise
    return UserResponseSchema.from_entity(user)


@router.patch("/{user_id}", response_model=UserResponseSchema)
def update_user_role(
    user_id: int,
    payload: UserRolePatch,
    repository: UserRepository = Depends(get_user_repository),
    _current_user: User = Depends(get_current_user),
) -> UserResponseSchema:
    try:
        if is_platform_admin(_current_user) or not can_manage_users(_current_user):
            raise ForbiddenError("No tienes permiso para cambiar roles.")
        target = repository.get_by_id(user_id)
        if target is None or tenant_id_of(target) != tenant_id_of(_current_user):
            raise NotFoundError("Usuario no encontrado")
        if target.role in {"admin", "owner"} or target.id == _current_user.id:
            raise ForbiddenError("No se puede cambiar el rol de esta cuenta.")
        try:
            role = normalize_business_role(payload.role)
        except ValueError as exc:
            raise ValidationError("El rol debe ser administrador, cajero o inventario") from exc
        return UserResponseSchema.from_entity(repository.update_role(user_id, role))
    except (ForbiddenError, NotFoundError, ValidationError) as exc:
        handle_domain_error(exc)
        raise


@router.patch("/{user_id}/subscription", response_model=UserResponseSchema)
def renew_subscription(
    user_id: int,
    payload: UserSubscriptionPatch,
    repository: UserRepository = Depends(get_user_repository),
    _current_user: User = Depends(get_current_user),
) -> UserResponseSchema:
    try:
        if not is_platform_admin(_current_user):
            raise ForbiddenError("Solo el admin de plataforma puede renovar planes.")
        target = repository.get_by_id(user_id)
        if target is None or target.role != ROLE_OWNER:
            raise NotFoundError("Negocio no encontrado")
        action = (payload.action or "renew").strip().lower()
        if action not in {"renew", "activate_monthly"}:
            raise ValidationError("La acción debe ser renovar o activar el plan mensual.")
        updated = repository.update_subscription(
            user_id,
            PLAN_MONTHLY,
            next_monthly_expiry(target.plan_expires_at),
        )
        return UserResponseSchema.from_entity(updated)
    except (ForbiddenError, NotFoundError, ValidationError) as exc:
        handle_domain_error(exc)
        raise


@router.post("/login", response_model=LoginResponseSchema)
def login_user(
    payload: UserLoginSchema,
    request: Request,
    repository: UserRepository = Depends(get_user_repository),
) -> LoginResponseSchema:
    email = payload.email.lower().strip()
    try:
        ip_limiter.check(f"ip:{client_ip(request)}")
        login_limiter.check(f"email:{email}")
        user = LoginUser(repository).execute(email=email, password=payload.password)
    except (UnauthorizedError, RateLimitError) as exc:
        handle_domain_error(exc)
        raise
    login_limiter.reset(f"email:{email}")
    token = create_access_token(user_id=int(user.id), email=user.email, remember=payload.remember)
    return LoginResponseSchema(access_token=token, user=UserResponseSchema.from_entity(user))


@router.get("/me", response_model=UserResponseSchema)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponseSchema:
    return UserResponseSchema.from_entity(current_user)
