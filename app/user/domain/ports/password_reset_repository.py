from abc import ABC, abstractmethod
from datetime import datetime


class PasswordReset:
    def __init__(
        self,
        id: int,
        user_id: int,
        email: str,
        code_hash: str,
        expires_at: datetime,
        attempts: int,
        used_at: datetime | None,
    ):
        self.id = id
        self.user_id = user_id
        self.email = email
        self.code_hash = code_hash
        self.expires_at = expires_at
        self.attempts = attempts
        self.used_at = used_at


class PasswordResetRepository(ABC):
    @abstractmethod
    def create(
        self,
        *,
        user_id: int,
        email: str,
        code_hash: str,
        expires_at: datetime,
        created_at: datetime,
    ) -> PasswordReset:
        raise NotImplementedError

    @abstractmethod
    def invalidate_open(self, user_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_open(self, email: str) -> PasswordReset | None:
        raise NotImplementedError

    @abstractmethod
    def increment_attempts(self, reset_id: int) -> int:
        raise NotImplementedError

    @abstractmethod
    def mark_used(self, reset_id: int, used_at: datetime) -> None:
        raise NotImplementedError
