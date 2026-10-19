from shared.exceptions import UnauthorizedError
from shared.utils.password import verify_password
from user.domain.entities.user import User
from user.domain.ports.user_repository import UserRepository


class LoginUser:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(self, email: str, password: str) -> User:
        user = self.repository.get_by_email(email.lower().strip())
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Correo o contraseña incorrectos")
        if not user.is_active:
            raise UnauthorizedError("Usuario inactivo")
        return user
