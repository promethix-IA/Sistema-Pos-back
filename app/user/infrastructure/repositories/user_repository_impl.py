from sqlalchemy import func, select
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

    def _to_entity(self, model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, user: User) -> UserModel:
        return UserModel(
            email=user.email,
            password_hash=user.password_hash,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
