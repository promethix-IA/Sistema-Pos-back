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
    jwt_expire_minutes: int = 1440
    jwt_session_minutes: int = 480

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
