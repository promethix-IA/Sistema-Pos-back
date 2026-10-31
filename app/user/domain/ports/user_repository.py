from abc import ABC, abstractmethod
from datetime import datetime

from user.domain.entities.user import User


class UserRepository(ABC):
    @abstractmethod
    def create(self, user: User) -> User:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def count(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def all(self) -> list[User]:
        raise NotImplementedError

    @abstractmethod
    def list_for_tenant(self, tenant_id: int) -> list[User]:
        raise NotImplementedError

    @abstractmethod
    def list_platform_accounts(self) -> list[User]:
        raise NotImplementedError

    @abstractmethod
    def update_role(self, user_id: int, role: str) -> User:
        raise NotImplementedError

    @abstractmethod
    def update_subscription(self, user_id: int, plan: str, plan_expires_at: datetime) -> User:
        raise NotImplementedError

    @abstractmethod
    def update_desktop_download(self, user_id: int, enabled: bool) -> User:
        raise NotImplementedError

    @abstractmethod
    def update_desktop_profile(
        self,
        user_id: int,
        *,
        enabled: bool | None = None,
        channel: str | None = None,
        updates_until: str | None = None,
    ) -> User:
        raise NotImplementedError

    @abstractmethod
    def delete(self, user_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_password(self, user_id: int, password_hash: str) -> User:
        raise NotImplementedError
