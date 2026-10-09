from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Tenant(Base):
    __tablename__ = "tenant"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cnpj: Mapped[str | None] = mapped_column(String(20), nullable=True)
    id_cidade: Mapped[int | None] = mapped_column(
        ForeignKey("utils.cidade.id"), nullable=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    plano: Mapped[str] = mapped_column(String(20), nullable=False, default="basico")
    cor_primaria: Mapped[str | None] = mapped_column(String(7), nullable=True)
    # 0131 — com `cor_primaria`, formam o tema do município (`#RRGGBB`):
    # destaque = acento e painel do login; lateral = fundo da barra lateral.
    cor_destaque: Mapped[str | None] = mapped_column(String(7), nullable=True)
    cor_lateral: Mapped[str | None] = mapped_column(String(7), nullable=True)
    # 0132 — títulos: cor (`#RRGGBB`) e fonte, esta de uma lista fechada
    # (`schemas/tenant.py::FONTES_DE_TITULO`), com CHECK no banco.
    cor_titulos: Mapped[str | None] = mapped_column(String(7), nullable=True)
    fonte_titulos: Mapped[str | None] = mapped_column(String(20), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 0129 — identidade da tela de login: marca (qualquer proporção) e foto do
    # painel esquerdo. Definidas pela plataforma; o runtime municipal não tem
    # UPDATE nelas.
    logo_login_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    imagem_login_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 0130 — atribuição da foto, quando a licença dela exigir.
    imagem_login_credito: Mapped[str | None] = mapped_column(String(200), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Fase P2 — NUP federal (Decreto 8.539/2015). Opt-in por tenant.
    codigo_orgao_nup: Mapped[str | None] = mapped_column(String(5), nullable=True)
    usar_nup_federal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # PR 3a — limites básicos (apenas armazenados; sem enforcement neste PR).
    limite_usuarios: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limite_armazenamento_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # PR 3b — dados institucionais editáveis pelo admin municipal (todos nullable).
    sigla: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email_institucional: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefone_institucional: Mapped[str | None] = mapped_column(String(20), nullable=True)
    endereco: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_oficial: Mapped[str | None] = mapped_column(String(255), nullable=True)
    horario_atendimento: Mapped[str | None] = mapped_column(String(255), nullable=True)
    texto_boas_vindas_portal: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Soft-ref a utils.unidade_trabalho.id (sem FK rígida; validado no serviço).
    id_unidade_padrao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Minuta/Google Docs — opt-in por tenant (soberania de dados). Vazio = integração
    # Google desabilitada; o editor interno segue disponível independentemente.
    google_docs_habilitado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
