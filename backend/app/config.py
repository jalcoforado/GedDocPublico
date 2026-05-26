from functools import lru_cache
from pathlib import Path

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

    # Anexos legacy (pre Fase 14, single-tenant Sobral). Fallback de leitura.
    uploads_dir: str = "/app/uploads/anexos"
    # Raiz multi-tenant — uploads novos vão para `{tenants_storage_root}/{slug}/anexos/`,
    # carimbados para `.../carimbados/`, jobs para `.../jobs/{job_id}/`.
    tenants_storage_root: str = "/app/uploads/tenants"
    max_upload_size_mb: int = 20

    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    # Legacy jobs root (pre Fase 14). Novos jobs vão para `tenants_storage_root/{slug}/jobs`.
    jobs_results_dir: str = "/app/uploads/jobs"

    # Multi-tenant (Fase 12) — resolução do tenant pelo subdomínio do Host header.
    # Ex.: `sobral.aprimora.local` → slug `sobral`. Em prod muda para `aprimora.app`.
    base_domain: str = "aprimora.local"
    # Tenant default quando Host não tem subdomínio (dev/localhost) ou subdomínio
    # desconhecido (apenas se strict_tenant_resolution=False).
    default_tenant_slug: str = "sobral"
    # True = host desconhecido retorna 404. False = cai no default_tenant_slug.
    strict_tenant_resolution: bool = False

    # Observabilidade (Fase 33). Vazio = desabilitado.
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    log_level: str = "INFO"

    # SMTP — Fase 17b. Sem host setado → driver fica em stub log.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@aprimora.app"
    smtp_use_tls: bool = True  # STARTTLS

    # WhatsApp — Fase 16. provider="zenvia"|"stub" (default stub mantém dev limpo).
    # zenvia_api_url default aponta pro endpoint v2 da Zenvia.
    whatsapp_provider: str = "stub"
    zenvia_api_key: str = ""
    zenvia_api_url: str = "https://api.zenvia.com/v2/channels/whatsapp/messages"
    zenvia_from: str = ""  # número remetente cadastrado no console Zenvia

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


def tenant_anexos_dir(tenant_slug: str) -> Path:
    """Pasta de anexos do tenant: `{tenants_storage_root}/{slug}/anexos/`."""
    p = Path(get_settings().tenants_storage_root) / tenant_slug / "anexos"
    p.mkdir(parents=True, exist_ok=True)
    return p


def tenant_carimbados_dir(tenant_slug: str) -> Path:
    """Pasta de PDFs carimbados (cache) do tenant."""
    p = Path(get_settings().tenants_storage_root) / tenant_slug / "carimbados"
    p.mkdir(parents=True, exist_ok=True)
    return p


def tenant_jobs_dir(tenant_slug: str) -> Path:
    """Pasta-base de resultados de jobs do tenant."""
    p = Path(get_settings().tenants_storage_root) / tenant_slug / "jobs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def resolve_anexo_path(tenant_slug: str, e_doc: str) -> Path | None:
    """Procura um anexo: novo path (por tenant) primeiro, depois legacy (Sobral).

    Retorna o path se existir, None se não estiver em nenhum lugar.
    """
    novo = tenant_anexos_dir(tenant_slug) / e_doc
    if novo.exists():
        return novo
    legacy = Path(get_settings().uploads_dir) / e_doc
    if legacy.exists():
        return legacy
    return None
