from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ged_user:ged_password_secure_local@ged-saas-project-db-1:5432/ged_saas_db"
    database_url_sync: str | None = None

    jwt_secret_source: str = "db"
    jwt_secret_static: str | None = None
    jwt_ttl_seconds: int = 3600
    jwt_iss: str = "http://projecttech.com.br"
    jwt_aud: str = "http://projecttech.com.br"
    # Algoritmo de EMISSÃO. Validação aceita HS256 OU RS256 sempre.
    # Default HS256 mantém interop com PHP. Trocar pra RS256 só após cutover.
    jwt_algorithm: str = "HS256"
    jwt_private_key_path: str = "/app/keys/jwt_private.pem"
    jwt_public_key_path: str = "/app/keys/jwt_public.pem"

    app_name: str = "sistemas"
    cidade_conn: str = "ged_saas_db"
    environment: str = "desenvolvimento"

    allowed_origins: str = "http://localhost:8090,http://localhost:3000"

    uploads_dir: str = "/app/uploads/anexos"
    max_upload_size_mb: int = 20

    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    jobs_results_dir: str = "/app/uploads/jobs"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def sync_database_url(self) -> str:
        if self.database_url_sync:
            return self.database_url_sync
        return self.database_url.replace("+asyncpg", "+psycopg2")


@lru_cache
def get_settings() -> Settings:
    return Settings()
