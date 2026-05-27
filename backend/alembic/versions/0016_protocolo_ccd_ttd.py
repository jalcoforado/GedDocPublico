"""Protocolo P4: CCD (Código de Classificação) + TTD (Tabela de Temporalidade).

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-26

CONARQ define um padrão de classificação documental:
- **CCD** (Código de Classificação de Documentos): taxonomia hierárquica de
  classes (000 Administração geral → 020 Pessoal → 021 Cadastro funcional → …)
- **TTD** (Tabela de Temporalidade Documental): pra cada classe (opcionalmente
  combinada com espécie documental), define quanto tempo o documento fica:
    - fase corrente (no setor que produziu)
    - fase intermediária (no arquivo central)
    - destinação final: ELIMINACAO ou GUARDA_PERMANENTE

Adiciona `id_ccd_classe` em `protocolos.processo` (FK opcional — protocolo
existente pode não ter classe ainda; balcão a partir daqui pede CCD).

Seed: estrutura CONARQ "atividades-meio" simplificada (~18 classes em 2 níveis)
+ ~10 regras TTD comuns. Tenant id=1 (Sobral) só — outros tenants seedam via
CLI ou UI admin.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# CCD seed: (codigo, nome, codigo_pai)
# CONARQ atividades-meio — atalho simplificado, real seria muito mais detalhado.
SEED_CCD = [
    # Nível 1 (raízes)
    ("000", "Administração geral", None),
    ("020", "Pessoal", None),
    ("030", "Material", None),
    ("040", "Patrimônio", None),
    ("050", "Orçamento e finanças", None),
    ("060", "Documentação e informação", None),
    ("070", "Comunicações", None),
    ("900", "Assuntos diversos", None),
    # Nível 2 — 000 Administração
    ("010", "Organização e funcionamento", "000"),
    ("011", "Normatização interna", "010"),
    ("012", "Comunicações administrativas", "010"),
    # Nível 2 — 020 Pessoal
    ("021", "Recrutamento e seleção", "020"),
    ("022", "Cadastro funcional", "020"),
    ("023", "Folha de pagamento", "020"),
    ("024", "Assistência ao servidor", "020"),
    # Nível 2 — 030 Material
    ("031", "Aquisição de materiais/serviços", "030"),
    ("032", "Almoxarifado", "030"),
    # Nível 2 — 040 Patrimônio
    ("041", "Bens móveis", "040"),
    ("042", "Bens imóveis", "040"),
    # Nível 2 — 050 Orçamento e finanças
    ("051", "Programação orçamentária", "050"),
    ("052", "Execução financeira", "050"),
    ("053", "Tributos e arrecadação", "050"),
]


# TTD seed: (codigo_ccd, anos_corrente, anos_intermediario, destino_final, observacao)
# `destino_final` = ELIMINACAO | GUARDA_PERMANENTE
SEED_TTD = [
    ("011", 5, 0, "GUARDA_PERMANENTE", "Normas internas têm valor histórico"),
    ("012", 2, 3, "ELIMINACAO", "Comunicações administrativas rotineiras"),
    ("021", 5, 5, "ELIMINACAO", "Processos seletivos — guardar atas, eliminar habilitação"),
    ("022", 0, 0, "GUARDA_PERMANENTE", "Cadastro funcional — guarda permanente (Lei 8.112)"),
    ("023", 5, 95, "ELIMINACAO", "Folha de pagamento — 100 anos total (previdência)"),
    ("024", 5, 5, "ELIMINACAO", "Benefícios e assistência rotineira"),
    ("031", 5, 5, "ELIMINACAO", "Processos de compra — após prazos contratuais"),
    ("032", 2, 3, "ELIMINACAO", "Movimentação de almoxarifado"),
    ("041", 0, 0, "GUARDA_PERMANENTE", "Tombamento de bens móveis"),
    ("042", 0, 0, "GUARDA_PERMANENTE", "Registros imobiliários e desafetação"),
    ("051", 5, 5, "GUARDA_PERMANENTE", "Peças orçamentárias têm valor histórico"),
    ("052", 5, 5, "ELIMINACAO", "Execução financeira — após quitação"),
    ("053", 5, 5, "ELIMINACAO", "Lançamento de tributos — após prescrição"),
    ("900", 2, 3, "ELIMINACAO", "Assuntos diversos sem regra específica (catch-all)"),
]


def upgrade() -> None:
    # === CCD =================================================================
    op.create_table(
        "ccd_classe",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column("codigo", sa.String(length=20), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("descricao", sa.String(length=1000), nullable=True),
        sa.Column(
            "id_classe_pai", sa.Integer(), sa.ForeignKey("protocolos.ccd_classe.id"), nullable=True
        ),
        # palavras_chave: lista separada por vírgula que ajuda na sugestão automática
        sa.Column("palavras_chave", sa.String(length=500), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.UniqueConstraint("tenant_id", "codigo", name="uq_ccd_classe_tenant_codigo"),
        schema="protocolos",
    )
    op.create_index(
        "ix_ccd_classe_tenant_pai",
        "ccd_classe",
        ["tenant_id", "id_classe_pai"],
        schema="protocolos",
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON protocolos.ccd_classe TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON protocolos.ccd_classe_id_seq TO aprimora_app"
    )
    op.execute("ALTER TABLE protocolos.ccd_classe ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE protocolos.ccd_classe FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON protocolos.ccd_classe
            FOR SELECT USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON protocolos.ccd_classe
            FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )

    # Seed CCD em 2 passos (precisa do id_classe_pai resolvido).
    for codigo, nome, _pai in SEED_CCD:
        op.execute(
            sa.text(
                "INSERT INTO protocolos.ccd_classe "
                "(tenant_id, codigo, nome, ativo, excluido) "
                "VALUES (1, :c, :n, TRUE, FALSE)"
            ).bindparams(c=codigo, n=nome)
        )
    for codigo, _nome, pai in SEED_CCD:
        if pai:
            op.execute(
                sa.text(
                    "UPDATE protocolos.ccd_classe SET id_classe_pai = "
                    "(SELECT id FROM protocolos.ccd_classe WHERE tenant_id=1 AND codigo=:p) "
                    "WHERE tenant_id=1 AND codigo=:c"
                ).bindparams(c=codigo, p=pai)
            )

    # === TTD =================================================================
    op.create_table(
        "ttd_regra",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "id_ccd_classe",
            sa.Integer(),
            sa.ForeignKey("protocolos.ccd_classe.id"),
            nullable=False,
        ),
        # Se nullable=true, regra vale pra qualquer espécie naquela classe.
        sa.Column(
            "id_especie_documental",
            sa.Integer(),
            sa.ForeignKey("protocolos.especie_documental.id"),
            nullable=True,
        ),
        sa.Column("anos_corrente", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "anos_intermediario", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        # Enum como CHECK constraint pra simplicidade — sem ENUM PG.
        sa.Column("destino_final", sa.String(length=30), nullable=False),
        sa.Column("observacao", sa.String(length=1000), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.CheckConstraint(
            "destino_final IN ('ELIMINACAO','GUARDA_PERMANENTE')",
            name="ck_ttd_destino_final",
        ),
        # Uma regra por (classe, especie). Especie NULL = catch-all daquela classe.
        # Em PG, NULL é distinto, então (classe, NULL) só pode haver 1 — garantido por
        # índice parcial único:
        schema="protocolos",
    )
    op.create_index(
        "ix_ttd_regra_tenant_classe",
        "ttd_regra",
        ["tenant_id", "id_ccd_classe"],
        schema="protocolos",
    )
    # 1 regra por (tenant, classe, especie). NULLs em especie podem coexistir, então:
    op.execute(
        """
        CREATE UNIQUE INDEX uq_ttd_regra_classe_especie ON protocolos.ttd_regra
            (tenant_id, id_ccd_classe, id_especie_documental)
            WHERE excluido IS FALSE
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_ttd_regra_classe_sem_especie ON protocolos.ttd_regra
            (tenant_id, id_ccd_classe)
            WHERE id_especie_documental IS NULL AND excluido IS FALSE
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON protocolos.ttd_regra TO aprimora_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON protocolos.ttd_regra_id_seq TO aprimora_app"
    )
    op.execute("ALTER TABLE protocolos.ttd_regra ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE protocolos.ttd_regra FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON protocolos.ttd_regra
            FOR SELECT USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_modify ON protocolos.ttd_regra
            FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
        """
    )

    # Seed TTD (id_especie_documental NULL = catch-all)
    for codigo, ac, ai, df, obs in SEED_TTD:
        op.execute(
            sa.text(
                "INSERT INTO protocolos.ttd_regra "
                "(tenant_id, id_ccd_classe, id_especie_documental, "
                "anos_corrente, anos_intermediario, destino_final, observacao, ativo, excluido) "
                "VALUES (1, "
                "(SELECT id FROM protocolos.ccd_classe WHERE tenant_id=1 AND codigo=:c), "
                "NULL, :ac, :ai, :df, :obs, TRUE, FALSE)"
            ).bindparams(c=codigo, ac=ac, ai=ai, df=df, obs=obs)
        )

    # === Coluna em processo ==================================================
    op.add_column(
        "processo",
        sa.Column(
            "id_ccd_classe",
            sa.Integer(),
            sa.ForeignKey("protocolos.ccd_classe.id"),
            nullable=True,
        ),
        schema="protocolos",
    )
    op.create_index(
        "ix_processo_ccd",
        "processo",
        ["tenant_id", "id_ccd_classe"],
        schema="protocolos",
    )


def downgrade() -> None:
    op.drop_index("ix_processo_ccd", table_name="processo", schema="protocolos")
    op.drop_column("processo", "id_ccd_classe", schema="protocolos")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_modify ON protocolos.ttd_regra")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON protocolos.ttd_regra")
    op.execute("DROP INDEX IF EXISTS protocolos.uq_ttd_regra_classe_sem_especie")
    op.execute("DROP INDEX IF EXISTS protocolos.uq_ttd_regra_classe_especie")
    op.drop_index("ix_ttd_regra_tenant_classe", table_name="ttd_regra", schema="protocolos")
    op.drop_table("ttd_regra", schema="protocolos")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_modify ON protocolos.ccd_classe")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON protocolos.ccd_classe")
    op.drop_index("ix_ccd_classe_tenant_pai", table_name="ccd_classe", schema="protocolos")
    op.drop_table("ccd_classe", schema="protocolos")
