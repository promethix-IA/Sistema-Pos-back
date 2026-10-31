from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from db.session import get_db
from integration.infrastructure.repositories.integration_repository import IntegrationRepository
from shared.auth import attach_auth_cookies, clear_auth_cookies, create_access_token, ensure_csrf_cookie
from shared.auth.cookies import ACCESS_COOKIE, CSRF_COOKIE
from shared.exceptions import ConflictError, ForbiddenError, MailError, NotFoundError, RateLimitError, UnauthorizedError, ValidationError
from shared.http import handle_domain_error
from shared.mail import mail_configured
from shared.security.rate_limit import client_ip, ip_limiter, login_limiter, reset_ip_limiter, reset_limiter
from desktop.installer import normalize_channel
from license.signing import normalizar_hasta
from shared.subscription import PLAN_MONTHLY, PLAN_TRIAL, billing_owner, desktop_profile, expires_for_plan, next_monthly_expiry
from shared.tenancy import (
    ROLE_OWNER,
    can_edit_business_settings,
    can_manage_users,
    is_platform_admin,
    normalize_business_role,
    tenant_id_of,
)
from user.application.create_user import CreateUser
from user.application.login_user import LoginUser
from user.application.password_reset import RequestPasswordReset, ResetPassword, VerifyPasswordReset
from user.domain.entities.user import User
from user.domain.ports.password_reset_repository import PasswordResetRepository
from user.domain.ports.user_repository import UserRepository
from user.infrastructure.repositories.password_reset_repository_impl import PasswordResetRepositoryImpl
from user.infrastructure.repositories.user_repository_impl import UserRepositoryImpl
from user.presentation.deps import get_current_user
from user.presentation.schemas.user_schema import (
    LoginResponseSchema,
    MeResponseSchema,
    PasswordCodeSchema,
    PasswordEmailSchema,
    PasswordResetSchema,
    UserCreateSchema,
    UserDesktopPatch,
    UserLoginSchema,
    UserResponseSchema,
    UserRolePatch,
    UserSubscriptionPatch,
)


def user_payload(user: User, repository: UserRepository) -> UserResponseSchema:
    payload = UserResponseSchema.from_entity(user)
    if user.role == "owner":
        return payload
    return payload.model_copy(update=desktop_profile(user, repository))

router = APIRouter(prefix="/users", tags=["usuarios"])


def get_user_repository(session: Session = Depends(get_db)) -> UserRepository:
    return UserRepositoryImpl(session)


def get_password_reset_repository(session: Session = Depends(get_db)) -> PasswordResetRepository:
    return PasswordResetRepositoryImpl(session)


@router.get("/me", response_model=MeResponseSchema)
def get_me(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    repository: UserRepository = Depends(get_user_repository),
) -> MeResponseSchema:
    payload = user_payload(current_user, repository)
    return MeResponseSchema(
        **payload.model_dump(),
        csrf_token=ensure_csrf_cookie(response, request),
    )


@router.patch("/me/desktop", response_model=UserResponseSchema)
def set_own_desktop_profile(
    payload: UserDesktopPatch,
    current_user: User = Depends(get_current_user),
    repository: UserRepository = Depends(get_user_repository),
) -> UserResponseSchema:
    try:
        if is_platform_admin(current_user) or not can_edit_business_settings(current_user):
            raise ForbiddenError("No tienes permiso para cambiar el perfil del POS.")
        if not payload.channel:
            raise ValidationError("Elige Windows 10/11 o Windows 7/8.")
        owner = billing_owner(current_user, repository)
        if owner.id is None:
            raise ForbiddenError("No encontramos el negocio de esta cuenta.")
        updated = repository.update_desktop_profile(int(owner.id), channel=normalize_channel(payload.channel))
        return user_payload(updated if current_user.role == "owner" else current_user, repository)
    except (ForbiddenError, ValidationError) as exc:
        handle_domain_error(exc)
        raise


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
    session: Session = Depends(get_db),
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
    if user.role == ROLE_OWNER and user.id is not None:
        IntegrationRepository(session, int(user.id)).ensure_defaults()
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


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    repository: UserRepository = Depends(get_user_repository),
    _current_user: User = Depends(get_current_user),
) -> None:
    try:
        if user_id == _current_user.id:
            raise ForbiddenError("No puedes eliminar tu propia cuenta.")
        target = repository.get_by_id(user_id)
        if target is None:
            raise NotFoundError("Usuario no encontrado")
        if target.role == "admin":
            raise ForbiddenError("No se puede eliminar al admin de plataforma.")
        if is_platform_admin(_current_user):
            if target.role != ROLE_OWNER:
                raise ForbiddenError("Solo puedes eliminar negocios (usuarios padre).")
        elif can_manage_users(_current_user):
            if tenant_id_of(target) != tenant_id_of(_current_user):
                raise NotFoundError("Usuario no encontrado")
            if target.role in {"admin", "owner"}:
                raise ForbiddenError("No se puede eliminar esta cuenta.")
        else:
            raise ForbiddenError("No tienes permiso para eliminar usuarios.")
        repository.delete(user_id)
    except (ConflictError, ForbiddenError, NotFoundError) as exc:
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


@router.patch("/{user_id}/desktop", response_model=UserResponseSchema)
def set_desktop_download(
    user_id: int,
    payload: UserDesktopPatch,
    repository: UserRepository = Depends(get_user_repository),
    _current_user: User = Depends(get_current_user),
) -> UserResponseSchema:
    try:
        if not is_platform_admin(_current_user):
            raise ForbiddenError("Solo el admin de plataforma puede habilitar la descarga del POS.")
        target = repository.get_by_id(user_id)
        if target is None or target.role != ROLE_OWNER:
            raise NotFoundError("Negocio no encontrado")
        hasta = None
        if payload.updates_until is not None:
            hasta = normalizar_hasta(payload.updates_until) if payload.updates_until.strip() else ""
        return UserResponseSchema.from_entity(
            repository.update_desktop_profile(
                user_id,
                enabled=payload.enabled,
                channel=normalize_channel(payload.channel) if payload.channel else None,
                updates_until=hasta,
            )
        )
    except (ForbiddenError, NotFoundError, ValidationError) as exc:
        handle_domain_error(exc)
        raise


@router.post("/password/forgot")
def request_password_reset(
    payload: PasswordEmailSchema,
    request: Request,
    users: UserRepository = Depends(get_user_repository),
    resets: PasswordResetRepository = Depends(get_password_reset_repository),
) -> dict:
    email = payload.email.lower().strip()
    try:
        if not mail_configured():
            raise MailError("No pudimos enviar el código. Intenta más tarde.")
        reset_ip_limiter.check(f"ip:{client_ip(request)}")
        reset_limiter.check(f"email:{email}")
        RequestPasswordReset(users, resets).execute(email)
    except (RateLimitError, ValidationError, MailError) as exc:
        handle_domain_error(exc)
        raise
    return {"message": "Si el correo está registrado, te enviamos un código de verificación."}


@router.post("/password/verify")
def verify_password_reset(
    payload: PasswordCodeSchema,
    request: Request,
    resets: PasswordResetRepository = Depends(get_password_reset_repository),
) -> dict:
    email = payload.email.lower().strip()
    try:
        ip_limiter.check(f"reset-verify:{client_ip(request)}")
        VerifyPasswordReset(resets).execute(email, payload.code)
    except (RateLimitError, ValidationError) as exc:
        handle_domain_error(exc)
        raise
    return {"ok": True}


@router.post("/password/reset")
def reset_password(
    payload: PasswordResetSchema,
    request: Request,
    users: UserRepository = Depends(get_user_repository),
    resets: PasswordResetRepository = Depends(get_password_reset_repository),
) -> dict:
    email = payload.email.lower().strip()
    try:
        ip_limiter.check(f"reset:{client_ip(request)}")
        ResetPassword(users, resets).execute(email, payload.code, payload.password)
    except (RateLimitError, ValidationError) as exc:
        handle_domain_error(exc)
        raise
    return {"message": "La contraseña se actualizó. Ya puedes iniciar sesión."}


@router.post("/login", response_model=LoginResponseSchema)
def login_user(
    payload: UserLoginSchema,
    request: Request,
    response: Response,
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
    csrf = attach_auth_cookies(response, request, token, remember=payload.remember)
    return LoginResponseSchema(
        access_token="",
        token_type="cookie",
        csrf_token=csrf,
        user=user_payload(user, repository),
    )


@router.post("/logout")
def logout_user(request: Request, response: Response) -> dict:
    clear_auth_cookies(response, request)
    return {"ok": True}
