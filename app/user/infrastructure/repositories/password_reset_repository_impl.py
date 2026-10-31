from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from user.domain.ports.password_reset_repository import PasswordReset, PasswordResetRepository
from user.infrastructure.models.password_reset_model import PasswordResetModel


class PasswordResetRepositoryImpl(PasswordResetRepository):
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        user_id: int,
        email: str,
        code_hash: str,
        expires_at: datetime,
        created_at: datetime,
    ) -> PasswordReset:
        model = PasswordResetModel(
            user_id=user_id,
            email=email,
            code_hash=code_hash,
            expires_at=expires_at,
            attempts=0,
            used_at=None,
            created_at=created_at,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return self._to_entity(model)

    def invalidate_open(self, user_id: int) -> None:
        from shared.clock import now_bogota

        self.session.execute(
            update(PasswordResetModel)
            .where(
                PasswordResetModel.user_id == user_id,
                PasswordResetModel.used_at.is_(None),
            )
            .values(used_at=now_bogota())
        )
        self.session.commit()

    def get_open(self, email: str) -> PasswordReset | None:
        stmt = (
            select(PasswordResetModel)
            .where(
                func.lower(PasswordResetModel.email) == email.lower().strip(),
                PasswordResetModel.used_at.is_(None),
            )
            .order_by(PasswordResetModel.created_at.desc(), PasswordResetModel.id.desc())
            .limit(1)
        )
        model = self.session.scalar(stmt)
        return self._to_entity(model) if model else None

    def increment_attempts(self, reset_id: int) -> int:
        model = self.session.get(PasswordResetModel, reset_id)
        if model is None:
            return 0
        model.attempts = int(model.attempts or 0) + 1
        self.session.commit()
        return int(model.attempts)

    def mark_used(self, reset_id: int, used_at: datetime) -> None:
        model = self.session.get(PasswordResetModel, reset_id)
        if model is None:
            return
        model.used_at = used_at
        self.session.commit()

    def _to_entity(self, model: PasswordResetModel) -> PasswordReset:
        return PasswordReset(
            id=int(model.id),
            user_id=int(model.user_id),
            email=model.email,
            code_hash=model.code_hash,
            expires_at=model.expires_at,
            attempts=int(model.attempts or 0),
            used_at=model.used_at,
        )
