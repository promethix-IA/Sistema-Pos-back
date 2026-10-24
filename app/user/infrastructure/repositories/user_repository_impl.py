from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from user.domain.entities.user import User
from user.domain.ports.user_repository import UserRepository
from user.infrastructure.models.user_model import UserModel


class UserRepositoryImpl(UserRepository):
    def __init__(self, session: Session):
        self.session = session

    def create(self, user: User) -> User:
        model = self._to_model(user)
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return self._to_entity(model)

    def get_by_id(self, user_id: int) -> User | None:
        model = self.session.get(UserModel, user_id)
        return self._to_entity(model) if model else None

    def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(func.lower(UserModel.email) == email.lower().strip())
        model = self.session.scalar(stmt)
        return self._to_entity(model) if model else None

    def count(self) -> int:
        stmt = select(func.count()).select_from(UserModel)
        return int(self.session.scalar(stmt) or 0)

    def all(self) -> list[User]:
        stmt = select(UserModel).order_by(UserModel.created_at.desc(), UserModel.id.desc())
        return [self._to_entity(model) for model in self.session.scalars(stmt)]

    def list_for_tenant(self, tenant_id: int) -> list[User]:
        stmt = (
            select(UserModel)
            .where(or_(UserModel.id == tenant_id, UserModel.owner_id == tenant_id))
            .order_by(UserModel.created_at.desc(), UserModel.id.desc())
        )
        return [self._to_entity(model) for model in self.session.scalars(stmt)]

    def update_role(self, user_id: int, role: str) -> User:
        from shared.clock import now_bogota
        from shared.exceptions import NotFoundError

        model = self.session.get(UserModel, user_id)
        if model is None:
            raise NotFoundError("Usuario no encontrado")
        model.role = role
        model.updated_at = now_bogota()
        self.session.commit()
        self.session.refresh(model)
        return self._to_entity(model)

    def update_subscription(self, user_id: int, plan: str, plan_expires_at: datetime) -> User:
        from shared.clock import now_bogota
        from shared.exceptions import NotFoundError

        model = self.session.get(UserModel, user_id)
        if model is None:
            raise NotFoundError("Usuario no encontrado")
        model.plan = plan
        model.plan_expires_at = plan_expires_at
        model.updated_at = now_bogota()
        self.session.commit()
        self.session.refresh(model)
        return self._to_entity(model)

    def delete(self, user_id: int) -> None:
        from sqlalchemy.exc import IntegrityError

        from shared.exceptions import ConflictError, NotFoundError

        model = self.session.get(UserModel, user_id)
        if model is None:
            raise NotFoundError("Usuario no encontrado")
        try:
            self.session.delete(model)
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("No se pudo eliminar porque el negocio aún tiene datos asociados.") from exc

    def list_platform_accounts(self) -> list[User]:
        stmt = (
            select(UserModel)
            .where(UserModel.role.in_(("admin", "owner")))
            .order_by(UserModel.created_at.desc(), UserModel.id.desc())
        )
        return [self._to_entity(model) for model in self.session.scalars(stmt)]

    def _to_entity(self, model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
            owner_id=model.owner_id,
            role=model.role or "owner",
            plan=model.plan or "",
            plan_expires_at=model.plan_expires_at,
        )

    def _to_model(self, user: User) -> UserModel:
        return UserModel(
            email=user.email,
            password_hash=user.password_hash,
            is_active=user.is_active,
            owner_id=user.owner_id,
            role=user.role,
            plan=user.plan or "",
            plan_expires_at=user.plan_expires_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
