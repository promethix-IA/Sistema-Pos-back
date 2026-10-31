from pathlib import Path
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ".env"),
        extra="ignore",
    )

    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str
    supabase_jwks_url: str
    supabase_db_host: str = "aws-0-us-east-2.pooler.supabase.com"
    supabase_db_port: int = 5432
    supabase_db_name: str = "postgres"
    supabase_db_password: str = ""
    jwt_secret: str = "pos-cambia-esta-clave-jwt-por-una-larga"
    jwt_expire_minutes: int = 720
    jwt_session_minutes: int = 120
    jwt_issuer: str = "promethixia-pos"
    jwt_audience: str = "promethixia-pos-web"
    app_env: str = "production"
    cors_origins: str = (
        "https://pos.promethixia.com,"
        "https://promethixiafront.netlify.app,"
        "http://localhost:8443,"
        "http://127.0.0.1:8443"
    )
    cors_origin_regex: str = r"https://([a-z0-9-]+--)?promethixiafront\.netlify\.app"
    login_max_attempts: int = 5
    login_window_seconds: int = 900
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = "promethixia@gmail.com"
    smtp_password: str = ""
    smtp_from: str = "Promethixia <promethixia@gmail.com>"
    password_reset_minutes: int = 10
    desktop_installer_path: str = ""
    license_private_key: str = ""
    license_private_key_path: str = ""

    @field_validator("supabase_db_password")
    @classmethod
    def database_password_is_set(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "Falta SUPABASE_DB_PASSWORD. En el dashboard de Supabase abre Connect, "
                "elige Shared pooler y pega la contraseña de la base tal cual, sin codificarla. "
                "SUPABASE_SECRET_KEY no sirve como contraseña de Postgres."
            )
        return value

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_is_strong(cls, value: str) -> str:
        secret = value.strip()
        weak = {
            "pos-cambia-esta-clave-jwt-por-una-larga",
            "cambia-esta-clave-jwt-por-una-de-32-bytes",
        }
        if len(secret) < 32:
            raise ValueError("JWT_SECRET debe tener al menos 32 caracteres.")
        if secret in weak:
            raise ValueError("Cambia JWT_SECRET. No uses el valor de ejemplo.")
        return secret

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() not in {"development", "dev", "local", "test"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def cors_regex(self) -> str | None:
        pattern = self.cors_origin_regex.strip()
        return pattern or None

    @property
    def project_ref(self) -> str:
        host = self.supabase_url.split("://", 1)[-1].split("/")[0]
        return host.split(".")[0]

    @property
    def supabase_db_user(self) -> str:
        return f"postgres.{self.project_ref}"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{quote_plus(self.supabase_db_user)}:{quote_plus(self.supabase_db_password)}"
            f"@{self.supabase_db_host}:{self.supabase_db_port}/{self.supabase_db_name}"
            "?sslmode=require"
        )


settings = Settings()
