from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from desktop.installer import download_name, find_installer, list_installers, normalize_channel, published_version
from shared.exceptions import ForbiddenError, NotFoundError
from shared.http import handle_domain_error
from shared.subscription import billing_owner, desktop_download_enabled, desktop_profile
from shared.tenancy import ROLE_OWNER, is_platform_admin, tenant_id_of
from user.domain.entities.user import User
from user.domain.ports.user_repository import UserRepository
from user.presentation.deps import get_current_user, get_user_repository

router = APIRouter(prefix="/desktop", tags=["escritorio"])


def require_installer(channel: str | None) -> Path:
    path = find_installer(channel)
    if path is None:
        if normalize_channel(channel) == "windows7-8":
            handle_domain_error(
                NotFoundError(
                    "Aún no está el instalador de Windows 7/8. Genéralo con npm run instalador:windows7."
                )
            )
        handle_domain_error(NotFoundError("Aún no hay un instalador .exe. Genera el de Sistema-Pos-Escritorio."))
        raise
    return path


@router.get("")
def installer_status(
    current_user: User = Depends(get_current_user),
    repository: UserRepository = Depends(get_user_repository),
) -> dict:
    items = list_installers()
    allowed = desktop_download_enabled(current_user, repository) or is_platform_admin(current_user)
    ready = any(item["ready"] for item in items)
    principal = next((item for item in items if item["id"] == "windows10-11" and item["ready"]), None) or next(
        (item for item in items if item["ready"]), None
    )
    perfil = {} if is_platform_admin(current_user) else desktop_profile(current_user, repository)
    canal = perfil.get("desktop_channel") or "windows10-11"
    principal = next((item for item in items if item["id"] == canal and item["ready"]), None) or principal
    return {
        "ready": ready,
        "allowed": allowed and ready,
        "filename": principal["filename"] if principal else "",
        "size": principal["size"] if principal else 0,
        "items": items,
        "version": published_version(),
        "channel": canal,
        "updates_until": perfil.get("desktop_updates_until") or "",
    }


@router.get("/installer")
def download_own_installer(
    channel: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    repository: UserRepository = Depends(get_user_repository),
) -> FileResponse:
    if is_platform_admin(current_user):
        handle_domain_error(ForbiddenError("Elige un negocio para descargar el instalador."))
        raise
    if not desktop_download_enabled(current_user, repository):
        handle_domain_error(ForbiddenError("El admin de plataforma no habilitó la descarga para este negocio."))
        raise
    owner = billing_owner(current_user, repository)
    path = require_installer(channel or owner.desktop_channel)
    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=download_name(owner.email, path),
        content_disposition_type="attachment",
    )


@router.get("/{user_id}/installer")
def download_installer(
    user_id: int,
    channel: str = Query("windows10-11"),
    repository: UserRepository = Depends(get_user_repository),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    path = require_installer(channel)
    target = repository.get_by_id(user_id)
    if target is None or target.role != ROLE_OWNER:
        handle_domain_error(NotFoundError("Negocio no encontrado"))
        raise
    if is_platform_admin(current_user):
        pass
    elif tenant_id_of(current_user) == int(target.id) and desktop_download_enabled(current_user, repository):
        pass
    else:
        handle_domain_error(ForbiddenError("El admin de plataforma no habilitó la descarga para este negocio."))
        raise
    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=download_name(target.email, path),
        content_disposition_type="attachment",
    )
