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

    # Valor do `app` em utils.sistema/utils.usuario e do claim `app` no JWT.
    # `load_permissions` filtra grupos por Sistema.app == app_name; provisionar
    # tenant grava 'sistemas'. Divergir aqui faz o SU do tenant não ser
    # reconhecido (403 em tudo).
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

    # Validação pública de assinatura (PR2e). Base da URL impressa no comprovante
    # / QR Code. Vazio = deriva do subdomínio do tenant:
    #   https://{slug}.{base_domain}/validar/{codigo}
    # Em prod (HTTPS público) defina explicitamente, ex.: https://sobral.aprimora.app
    public_base_url: str = ""

    # ------------------------------------------------------------------
    # Fronteira de plataforma (SEC-01A / ADR-016).
    #
    # `PLATFORM_ADMIN_EMAILS` FOI REMOVIDA. Era o achado F-01: a autorização
    # cross-tenant era uma comparação de string sobre um e-mail, e o e-mail é
    # único apenas POR TENANT (`UNIQUE (tenant_id, email)`), de modo que
    # qualquer tenant capaz de criar um usuário com o e-mail certo produzia um
    # administrador de plataforma. Não reintroduzir — nem "temporariamente".
    #
    # NENHUM destes campos tem default útil, e isso é deliberado (ADR §2.6,
    # D-2): configuração ausente tem de NEGAR, nunca liberar. Um default
    # embutido converteria esquecimento de configuração em porta aberta, que é
    # exatamente o modo de falha que estamos fechando.
    # ------------------------------------------------------------------
    # Issuer do IdP administrativo. Em produção, `https://accounts.google.com`.
    platform_oidc_issuer: str = ""
    # Client ID do OAuth client DEDICADO ao console, um por ambiente — é o que
    # distingue um token de homologação de um de produção (cenário 24).
    platform_oidc_audience: str = ""
    # JWKS do IdP. Em produção, `https://www.googleapis.com/oauth2/v3/certs`.
    platform_oidc_jwks_url: str = ""
    # Domínio corporativo aceito no claim `hd`. SEM DEFAULT (D-2).
    platform_oidc_hosted_domain: str = ""
    # Conexão da fronteira de plataforma: papel `aprimora_platform`
    # (NOBYPASSRLS, grants cross-tenant enumerados). NUNCA o pool municipal.
    platform_db_url: str = ""

    @property
    def plataforma_configurada(self) -> bool:
        """True só quando os quatro identificadores de ambiente existem.

        Não inclui `platform_db_url` de propósito: a falta dele é erro de
        infraestrutura (matriz §3, "Papel de banco" ⇒ 500), enquanto a falta
        dos identificadores de realm é erro de configuração do IdP (cenários
        23 e 24 ⇒ deny).
        """
        return all(
            (
                self.platform_oidc_issuer.strip(),
                self.platform_oidc_audience.strip(),
                self.platform_oidc_jwks_url.strip(),
                self.platform_oidc_hosted_domain.strip(),
            )
        )

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

    # Cifragem de dados sensíveis (dados bancários de fornecedor, tokens Google).
    # Fernet key (base64 urlsafe de 32 bytes). Vazio em dev → operações de cifra falham
    # explicitamente. Gerar com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    dados_sensiveis_encryption_key: str = ""

    # Google OAuth (PR-F) — Google Docs integration.
    # Obtenha em https://console.cloud.google.com/apis/credentials (OAuth 2.0 Web Application)
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v2/auth/google/callback"
    google_credentials_file: str = "/app/keys/google-credentials.json"

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


# `is_platform_admin(email)` FOI REMOVIDA em SEC-01A. Era o caminho de decisão
# do achado F-01. Quem autoriza a fronteira de plataforma hoje é
# `app.auth.plataforma.require_platform_admin`, que exige token administrativo
# RS256 do IdP dedicado + principal ativo em `aprimora_py.platform_principal`.
# O e-mail sobrevive apenas como `display_label` do principal, e não decide
# nada (ADR-016 §2.1).


# PR3a — módulos derivados do plano (apenas exibição; sem enforcement neste PR).
# Mapa de partida; refinar conforme catálogo real de módulos.
PLANO_MODULOS: dict[str, list[str]] = {
    "basico": ["protocolo", "processos", "assinatura"],
    "profissional": [
        "protocolo", "processos", "assinatura", "workflow", "relatorios", "organograma",
    ],
    "enterprise": [
        "protocolo", "processos", "assinatura", "workflow", "relatorios",
        "organograma", "auditoria", "dashboard",
    ],
}


def modulos_do_plano(plano: str | None) -> list[str]:
    """Módulos ativos derivados do plano. Plano desconhecido → conjunto básico."""
    return PLANO_MODULOS.get((plano or "basico").lower(), PLANO_MODULOS["basico"])


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


def validacao_publica_url(tenant_slug: str, codigo: str) -> str:
    """URL pública de validação (impressa no comprovante / QR). Usa
    `public_base_url` quando definido; senão deriva do subdomínio do tenant."""
    s = get_settings()
    base = s.public_base_url.strip().rstrip("/")
    if not base:
        base = f"https://{tenant_slug}.{s.base_domain}"
    return f"{base}/validar/{codigo}"


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
