from datetime import timedelta
from secrets import randbelow

from shared.clock import now_bogota
from shared.config.settings import settings
from shared.exceptions import MailError, ValidationError
from shared.mail import mail_configured, send_password_reset_code
from shared.utils.password import hash_password, verify_password
from user.domain.ports.password_reset_repository import PasswordReset, PasswordResetRepository
from user.domain.ports.user_repository import UserRepository

MAX_CODE_ATTEMPTS = 5
INVALID_CODE = "El código no coincide con el que enviamos al correo."


def _digits(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


class RequestPasswordReset:
    def __init__(self, users: UserRepository, resets: PasswordResetRepository):
        self.users = users
        self.resets = resets

    def execute(self, email: str) -> None:
        if not mail_configured():
            raise MailError("No pudimos enviar el código. Intenta más tarde.")
        normalized = email.lower().strip()
        user = self.users.get_by_email(normalized)
        if user is None or not user.is_active or user.id is None:
            return
        now = now_bogota()
        code = f"{randbelow(1_000_000):06d}"
        self.resets.invalidate_open(int(user.id))
        self.resets.create(
            user_id=int(user.id),
            email=normalized,
            code_hash=hash_password(code),
            expires_at=now + timedelta(minutes=settings.password_reset_minutes),
            created_at=now,
        )
        try:
            send_password_reset_code(normalized, code)
        except Exception as exc:
            self.resets.invalidate_open(int(user.id))
            raise MailError("No pudimos enviar el código. Intenta más tarde.") from exc


class VerifyPasswordReset:
    def __init__(self, resets: PasswordResetRepository):
        self.resets = resets

    def execute(self, email: str, code: str) -> None:
        _match_open_code(self.resets, email, code)


class ResetPassword:
    def __init__(self, users: UserRepository, resets: PasswordResetRepository):
        self.users = users
        self.resets = resets

    def execute(self, email: str, code: str, password: str) -> None:
        reset = _match_open_code(self.resets, email, code)
        self.users.update_password(reset.user_id, hash_password(password))
        self.resets.mark_used(reset.id, now_bogota())


def _match_open_code(
    resets: PasswordResetRepository,
    email: str,
    code: str,
) -> PasswordReset:
    digits = _digits(code)
    reset = resets.get_open(email.lower().strip())
    if reset is None or len(digits) != 6:
        raise ValidationError(INVALID_CODE)
    now = now_bogota()
    if reset.used_at is not None or reset.expires_at <= now:
        raise ValidationError(INVALID_CODE)
    if reset.attempts >= MAX_CODE_ATTEMPTS:
        raise ValidationError("Demasiados intentos con este código. Solicita uno nuevo.")
    if not verify_password(digits, reset.code_hash):
        attempts = resets.increment_attempts(reset.id)
        if attempts >= MAX_CODE_ATTEMPTS:
            resets.mark_used(reset.id, now)
            raise ValidationError("Demasiados intentos con este código. Solicita uno nuevo.")
        raise ValidationError(INVALID_CODE)
    return reset
