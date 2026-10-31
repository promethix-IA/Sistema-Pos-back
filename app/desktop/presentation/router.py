from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from desktop.installer import installer_filename, installer_source, list_installers, normalize_channel, published_version
from shared.exceptions import ForbiddenError, NotFoundError
from shared.http import handle_domain_error
from shared.subscription import billing_owner, desktop_download_enabled, desktop_profile
from shared.tenancy import ROLE_OWNER, is_platform_admin, tenant_id_of
from user.domain.entities.user import User
from user.domain.ports.user_repository import UserRepository
from user.presentation.deps import get_current_user, get_user_repository

router = APIRouter(prefix="/desktop", tags=["escritorio"])


def require_download(current_user: User, repository: UserRepository, user_id: int | None = None) -> User:
    if user_id is None:
        if is_platform_admin(current_user):
            handle_domain_error(ForbiddenError("Elige un negocio para descargar el instalador."))
            raise
        if not desktop_download_enabled(current_user, repository):
            handle_domain_error(ForbiddenError("El admin de plataforma no habilitó la descarga para este negocio."))
            raise
        return billing_owner(current_user, repository)

    target = repository.get_by_id(user_id)
    if target is None or target.role != ROLE_OWNER:
        handle_domain_error(NotFoundError("Negocio no encontrado"))
        raise
    if is_platform_admin(current_user):
        return target
    if tenant_id_of(current_user) == int(target.id) and desktop_download_enabled(current_user, repository):
        return target
    handle_domain_error(ForbiddenError("El admin de plataforma no habilitó la descarga para este negocio."))
    raise


def describe_installer(email: str, channel: str | None) -> dict:
    wanted = normalize_channel(channel)
    path, url = installer_source(wanted)
    filename = installer_filename(email, wanted, path)
    if path is None and not url:
        handle_domain_error(NotFoundError("Aún no está el instalador en el servidor."))
        raise
    return {
        "local": path is not None and not url,
        "url": url,
        "filename": filename,
        "path": path,
        "channel": wanted,
    }


def send_local_installer(path: Path, filename: str) -> FileResponse:
    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=filename,
        content_disposition_type="attachment",
    )


@router.get("")
def installer_status(
    current_user: User = Depends(get_current_user),
    repository: UserRepository = Depends(get_user_repository),
) -> dict:
    items = list_installers()
    allowed = desktop_download_enabled(current_user, repository) or is_platform_admin(current_user)
    ready = any(item["ready"] for item in items)
    perfil = {} if is_platform_admin(current_user) else desktop_profile(current_user, repository)
    canal = perfil.get("desktop_channel") or "windows10-11"
    principal = next((item for item in items if item["id"] == canal and item["ready"]), None) or next(
        (item for item in items if item["ready"]), None
    )
    return {
        "ready": ready,
        "allowed": allowed,
        "filename": principal["filename"] if principal else "",
        "size": principal["size"] if principal else 0,
        "items": items,
        "version": published_version(),
        "channel": canal,
        "updates_until": perfil.get("desktop_updates_until") or "",
    }


@router.get("/link")
def own_installer_link(
    channel: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    repository: UserRepository = Depends(get_user_repository),
) -> dict:
    owner = require_download(current_user, repository)
    info = describe_installer(owner.email, channel or owner.desktop_channel)
    return {"local": info["local"], "url": info["url"], "filename": info["filename"]}


@router.get("/installer")
def download_own_installer(
    channel: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    repository: UserRepository = Depends(get_user_repository),
) -> FileResponse:
    owner = require_download(current_user, repository)
    info = describe_installer(owner.email, channel or owner.desktop_channel)
    if info["path"] is None:
        handle_domain_error(NotFoundError("Usa el enlace publicado del instalador. No está copiado en este servidor."))
        raise
    return send_local_installer(info["path"], info["filename"])


@router.get("/{user_id}/link")
def installer_link(
    user_id: int,
    channel: str = Query("windows10-11"),
    repository: UserRepository = Depends(get_user_repository),
    current_user: User = Depends(get_current_user),
) -> dict:
    target = require_download(current_user, repository, user_id)
    info = describe_installer(target.email, channel)
    return {"local": info["local"], "url": info["url"], "filename": info["filename"]}


@router.get("/{user_id}/installer")
def download_installer(
    user_id: int,
    channel: str = Query("windows10-11"),
    repository: UserRepository = Depends(get_user_repository),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    target = require_download(current_user, repository, user_id)
    info = describe_installer(target.email, channel)
    if info["path"] is None:
        handle_domain_error(NotFoundError("Usa el enlace publicado del instalador. No está copiado en este servidor."))
        raise
    return send_local_installer(info["path"], info["filename"])
