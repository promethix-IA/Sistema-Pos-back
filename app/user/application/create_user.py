from datetime import datetime, timezone

from shared.exceptions import ConflictError
from shared.utils.password import hash_password
from user.domain.entities.user import User
from user.domain.ports.user_repository import UserRepository


class CreateUser:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(
        self,
        email: str,
        password: str,
        owner_id: int | None = None,
        role: str = "owner",
    ) -> User:
        normalized_email = email.lower().strip()
        if self.repository.get_by_email(normalized_email) is not None:
            raise ConflictError("Ya existe un usuario con ese correo")

        now = datetime.now(timezone.utc)
        user = User(
            id=None,
            email=normalized_email,
            password_hash=hash_password(password),
            is_active=True,
            created_at=now,
            updated_at=now,
            owner_id=owner_id,
            role=role,
        )
        return self.repository.create(user)
