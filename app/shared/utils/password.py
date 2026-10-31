import hashlib
import secrets

PBKDF2_ITERATIONS = 210_000
LEGACY_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return f"{salt}${PBKDF2_ITERATIONS}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    parts = password_hash.split("$")
    if len(parts) == 2:
        salt, digest = parts
        iterations = LEGACY_PBKDF2_ITERATIONS
    elif len(parts) == 3:
        salt, raw_iterations, digest = parts
        try:
            iterations = int(raw_iterations)
        except ValueError:
            return False
        if iterations < LEGACY_PBKDF2_ITERATIONS or iterations > 2_000_000:
            return False
    else:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return secrets.compare_digest(candidate, digest)


def hash_needs_upgrade(password_hash: str) -> bool:
    parts = password_hash.split("$")
    if len(parts) != 3:
        return True
    try:
        return int(parts[1]) < PBKDF2_ITERATIONS
    except ValueError:
        return True
