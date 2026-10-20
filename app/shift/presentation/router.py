from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.session import get_db
from shared.exceptions import ConflictError, NotFoundError, ValidationError
from shared.http import handle_domain_error
from shift.infrastructure.repositories.shift_repository import ShiftRepository
from user.domain.entities.user import User
from user.presentation.deps import get_current_user

router = APIRouter(prefix="/shifts", tags=["cierre-caja"])


class OpenShiftIn(BaseModel):
    openingCash: float = Field(ge=0)
    notes: str = ""


class CloseShiftIn(BaseModel):
    countedCash: float | None = Field(default=None, ge=0)
    notes: str = ""


def get_repository(session: Session = Depends(get_db)) -> ShiftRepository:
    return ShiftRepository(session)


@router.get("/current")
def current_shift(repository: ShiftRepository = Depends(get_repository)) -> dict | None:
    return repository.current()


@router.get("")
def list_shifts(repository: ShiftRepository = Depends(get_repository)) -> list[dict]:
    return repository.list_shifts()


@router.post("", status_code=201)
def open_shift(
    payload: OpenShiftIn,
    repository: ShiftRepository = Depends(get_repository),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        data = payload.model_dump()
        data["openedBy"] = user.email
        return repository.open_shift(data)
    except (ConflictError, ValidationError) as exc:
        handle_domain_error(exc)


@router.get("/{shift_id}/summary")
def shift_summary(shift_id: int, repository: ShiftRepository = Depends(get_repository)) -> dict:
    try:
        return repository.summary(shift_id)
    except NotFoundError as exc:
        handle_domain_error(exc)


@router.post("/{shift_id}/close")
def close_shift(
    shift_id: int,
    payload: CloseShiftIn,
    repository: ShiftRepository = Depends(get_repository),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        data = payload.model_dump()
        data["closedBy"] = user.email
        return repository.close_shift(shift_id, data)
    except (NotFoundError, ValidationError) as exc:
        handle_domain_error(exc)
