"""SEC-01A — identidade do operador de plataforma.

Revision ID: 0076
Revises: 0075
Create Date: 2026-08-01

Autoridade: `docs/architecture/adr/ADR-016-platform-operator-identity.md` (Aceito).

Entrega três coisas:

1. `aprimora_py.platform_principal` — o principal administrativo, identificado
   pelo par OIDC `(issuer, subject)` (chave natural, `UNIQUE`) e por um `id`
   interno (chave primária, referenciado pela auditoria). **Sem `tenant_id`,
   sem RLS, sem policies**: é tabela de PLATAFORMA, mesmo precedente de
   `tenant`, `modulo` e `tenant_modulo` (ver docstring da 0073). Uma policy
   sobre `app.tenant_id` barraria justamente o caso de uso cross-tenant.

   O ADR §2.2 proíbe vincular a linha a `utils.usuario.id`, a e-mail municipal
   ou a qualquer cadastro de tenant. Aqui isso é: (a) ausência de FK e de
   coluna de tenant; (b) `CHECK` de que `issuer` é uma URL absoluta — um id de
   usuário ou um e-mail municipal não cabe na coluna; (c) `display_label`
   documentado como rótulo, que nunca participa de decisão. A garantia (a) é
   travada por teste em `tests/test_platform_admin_identity.py`.

2. `aprimora_py.platform_audit_log` — trilha AUTORITATIVA das operações de
   plataforma (decisão D-a do brief de SEC-01A). Existe porque
   `aprimora_py.audit_log` tem RLS FORCE com `WITH CHECK (tenant_id = ...)` e
   `id_usuario` com FK para `utils.usuario.id`: um `platform_principal.id` não
   cabe nessa FK e a sessão dedicada de plataforma não terá `app.tenant_id`
   municipal. A entrada visível ao tenant continua sendo gravada em
   `audit_log` — não é redundância, é a trilha que o município enxerga.

3. O papel `aprimora_platform` — `NOBYPASSRLS`, **jamais** `SUPERUSER`
   (ADR §2.3/D-5), criado em bloco `plpgsql DO ... IF NOT EXISTS` no padrão da
   0006. Sem criá-lo aqui, o CI quebra: o workflow cria só `aprimora_app`, e um
   `GRANT ... TO aprimora_platform` numa migration falharia com
   `role "aprimora_platform" does not exist`.

   **Esta migration cria APENAS este papel.** Os papéis municipal, de worker e
   de DDL pertencem a `SEC-RLS-00B` (ADR §9.1) — duas migrations definindo o
   mesmo papel colidem.

Higiene de grants (ADR §2.3): `aprimora_app`, o papel do runtime municipal,
perde o que tem indevidamente de DML de entitlement e de mutação de trilha de
auditoria. O alcance é deliberadamente CIRÚRGICO e o que ficou de fora está
justificado no bloco `_REVOGACOES` abaixo — revogar além disso quebraria
comportamento que hoje é legítimo, e um PR de segurança que derruba o
provisionamento não é contenção, é incidente.

Senha do papel: a de DEV, já versionada por decisão registrada (mesma escolha
da 0006, que cria `aprimora_app` assim). Em produção,
`ALTER ROLE aprimora_platform PASSWORD '<cofre>'` — ver o runbook
`docs/runbooks/platform-operator-bootstrap.md` §1.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0076"
down_revision: str | Sequence[str] | None = "0075"
branch_labels = None
depends_on = None
S = "aprimora_py"
ROLE = "aprimora_platform"


# Cada tupla é (objeto, privilégios, razão). A razão é obrigatória: sem ela,
# ninguém consegue julgar depois se a revogação continua correta.
_REVOGACOES: list[tuple[str, str, str]] = [
    (
        f"{S}.tenant",
        "DELETE",
        "apagar tenant não é operação de nenhum runtime; nem o painel de "
        "plataforma faz isso (desativar é UPDATE ativo=false).",
    ),
    (
        f"{S}.tenant_modulo",
        "UPDATE, DELETE",
        "contratar/descontratar é entitlement — operação de PLATAFORMA. "
        "Descontratar é soft-delete (UPDATE excluido=true), então tirar UPDATE "
        "e DELETE fecha o caminho de mutação de contratação pelo papel "
        "municipal.",
    ),
    (
        f"{S}.audit_log",
        "UPDATE, DELETE",
        "trilha append-only: o runtime municipal grava e lê a própria "
        "auditoria, nunca altera nem apaga linha já gravada.",
    ),
    (
        f"{S}.modulo",
        "INSERT, UPDATE, DELETE",
        "catálogo GLOBAL do produto. A 0073 concede só SELECT; o "
        "GRANT-cobertor do bootstrap devolvia DML. Aqui o estado fica "
        "determinístico.",
    ),
    (
        f"{S}.modulo_transacao",
        "INSERT, UPDATE, DELETE",
        "mesma razão de `modulo`.",
    ),
]

# O que NÃO é revogado, e por quê — a parte que uma revisão futura precisa ler:
#
# - `INSERT` em `tenant`, `tenant_modulo` e `audit_log`: `provisionar_tenant`
#   grava nas três e HOJE roda no papel municipal. Há teste que trava isso
#   (`test_admin_tenants.py::test_provisiona_sob_rls_producao`, sob
#   `aprimora_app`/NOBYPASSRLS). Movê-lo para `aprimora_platform` exigiria
#   conceder a esse papel DML nas tabelas de NEGÓCIO do tenant
#   (`utils.usuario`, `utils.grupo`, `protocolos.tipo_manifestante`, ...), que
#   é exatamente o que o ADR §2.3 lhe nega. É uma tensão real entre o ADR e o
#   fluxo de provisionamento, e resolvê-la não cabe nesta migration:
#   fica registrada para `SEC-01A` parte 2 / `SEC-RLS-00B`.
# - `UPDATE` em `tenant`: uso municipal legítimo — a configuração institucional
#   do próprio tenant (`services/tenant_config.atualizar_config_institucional`)
#   é editada pelo admin do município, não pela plataforma.


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Papel de plataforma (idempotente, padrão da 0006).
    #    Fora do bloco `DO`, um statement que falha aborta a transação inteira
    #    e leva junto o bump de `alembic_version`.
    # ------------------------------------------------------------------
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
                CREATE ROLE {ROLE}
                    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS
                    PASSWORD 'ged_password_secure_local';
            END IF;
        END $$;
        """
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            EXECUTE format('GRANT CONNECT ON DATABASE %I TO {ROLE}', current_database());
        END $$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA {S} TO {ROLE}")

    # ------------------------------------------------------------------
    # 2. platform_principal
    # ------------------------------------------------------------------
    op.create_table(
        "platform_principal",
        sa.Column("id", sa.Integer(), primary_key=True),
        # Chave natural: par OIDC. NUNCA e-mail, NUNCA utils.usuario.id.
        sa.Column("issuer", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        # Rótulo de exibição (tipicamente o e-mail do IdP). Existe para humano
        # ler em tela e em auditoria; não participa de decisão de autorização.
        sa.Column("display_label", sa.String(255), nullable=False),
        # Estado. Nasce INATIVO de propósito: o principal de break-glass é
        # pré-cadastrado e só é ativado por CLI, com dupla aprovação (ADR §2.8).
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column(
            "break_glass", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        # Vigência — `valid_until` é o prazo do break-glass (60 min, ADR §2.8) e
        # é o que a matriz de claims §3 chama de "vigência".
        sa.Column("valid_from", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        # Concessão: quem, quando, por quê (runbook §2 e §3).
        sa.Column("concedido_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("concedido_por", sa.String(255), nullable=False),
        sa.Column("motivo_concessao", sa.Text(), nullable=False),
        # Revogação: quem, quando, por quê (runbook §4).
        sa.Column("revogado_em", sa.DateTime(), nullable=True),
        sa.Column("revogado_por", sa.String(255), nullable=True),
        sa.Column("motivo_revogacao", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("issuer", "subject", name="uq_platform_principal_iss_sub"),
        # O `issuer` é uma URL absoluta de IdP. O CHECK não é decoração: é o que
        # impede que alguém "reaproveite" a coluna para guardar um id de usuário
        # municipal ou um e-mail, que é o vínculo proibido pelo ADR §2.2.
        sa.CheckConstraint(
            "issuer ~ '^https?://.'", name="ck_platform_principal_issuer_url"
        ),
        sa.CheckConstraint(
            "length(btrim(subject)) > 0", name="ck_platform_principal_subject"
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_platform_principal_vigencia",
        ),
        # Revogação é tudo-ou-nada e implica inativo: revogar sem motivo, ou
        # revogar deixando o principal ativo, é exatamente o erro que o runbook
        # §4 quer evitar.
        sa.CheckConstraint(
            "(revogado_em IS NULL AND revogado_por IS NULL AND motivo_revogacao IS NULL)"
            " OR (revogado_em IS NOT NULL AND revogado_por IS NOT NULL"
            "     AND motivo_revogacao IS NOT NULL AND ativo = false)",
            name="ck_platform_principal_revogacao",
        ),
        schema=S,
    )
    op.execute(
        f"COMMENT ON TABLE {S}.platform_principal IS "
        "'SEC-01A/ADR-016: identidade do operador de plataforma. Chave natural "
        "(issuer, subject) do OIDC. Tabela de PLATAFORMA: sem tenant_id, sem "
        "RLS. PROIBIDO vincular a utils.usuario.id, a e-mail municipal ou a "
        "qualquer cadastro de tenant.'"
    )
    op.execute(
        f"COMMENT ON COLUMN {S}.platform_principal.display_label IS "
        "'Rótulo de exibição (normalmente o e-mail do IdP). NUNCA participa de "
        "decisão de autorização — o achado F-01 foi exatamente autorizar por "
        "e-mail.'"
    )

    # ------------------------------------------------------------------
    # 3. platform_audit_log (decisão D-a)
    # ------------------------------------------------------------------
    op.create_table(
        "platform_audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        # Nulo quando a operação foi NEGADA por não haver principal: o runbook
        # §2 manda colher `(iss, sub)` justamente do registro dessa tentativa.
        sa.Column(
            "platform_principal_id",
            sa.Integer(),
            sa.ForeignKey(f"{S}.platform_principal.id"),
            nullable=True,
        ),
        sa.Column("issuer", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("acao", sa.String(80), nullable=False),
        # Nem toda operação tem alvo único (listar tenants não tem). `SET NULL`
        # porque a trilha precisa sobreviver à remoção do tenant.
        sa.Column(
            "tenant_alvo_id",
            sa.Integer(),
            sa.ForeignKey(f"{S}.tenant.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("detalhe", postgresql.JSONB(), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        schema=S,
    )
    op.create_index(
        "ix_platform_audit_log_criado", "platform_audit_log", ["criado_em"], schema=S
    )
    op.create_index(
        "ix_platform_audit_log_principal",
        "platform_audit_log",
        ["platform_principal_id", "criado_em"],
        schema=S,
    )
    op.create_index(
        "ix_platform_audit_log_tenant_alvo",
        "platform_audit_log",
        ["tenant_alvo_id", "criado_em"],
        schema=S,
    )
    op.execute(
        f"COMMENT ON TABLE {S}.platform_audit_log IS "
        "'SEC-01A/ADR-016 (D-a): trilha autoritativa das operações de "
        "plataforma. Fora da RLS municipal de propósito — a entrada VISÍVEL ao "
        "tenant continua em aprimora_py.audit_log.'"
    )

    # ------------------------------------------------------------------
    # 4. Grants — tabelas novas SÓ para aprimora_platform.
    #    O REVOKE de PUBLIC/aprimora_app é explícito para que o estado não
    #    dependa de default privileges herdadas do dono do schema.
    # ------------------------------------------------------------------
    for tabela in ("platform_principal", "platform_audit_log"):
        op.execute(f"REVOKE ALL ON {S}.{tabela} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON {S}.{tabela} FROM aprimora_app")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.{tabela} TO {ROLE}")
    for seq in ("platform_principal_id_seq", "platform_audit_log_id_seq"):
        op.execute(f"REVOKE ALL ON SEQUENCE {S}.{seq} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON SEQUENCE {S}.{seq} FROM aprimora_app")
        op.execute(f"GRANT USAGE, SELECT ON SEQUENCE {S}.{seq} TO {ROLE}")

    # Grants cross-tenant EXPLÍCITOS e ENUMERADOS do papel de plataforma
    # (ADR §2.3): entitlement, e nada de tabela de negócio de tenant.
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.tenant TO {ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.tenant_modulo TO {ROLE}")
    op.execute(f"GRANT SELECT ON {S}.modulo TO {ROLE}")
    op.execute(f"GRANT SELECT ON {S}.modulo_transacao TO {ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON SEQUENCE {S}.tenant_id_seq TO {ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON SEQUENCE {S}.tenant_modulo_id_seq TO {ROLE}")

    # ------------------------------------------------------------------
    # 5. Higiene: o que aprimora_app tem indevidamente (ADR §2.3).
    # ------------------------------------------------------------------
    for objeto, privilegios, _razao in _REVOGACOES:
        op.execute(f"REVOKE {privilegios} ON {objeto} FROM aprimora_app")


def downgrade() -> None:
    # Ordem inversa do upgrade.

    # 5. Devolve a aprimora_app o que foi revogado.
    for objeto, privilegios, _razao in reversed(_REVOGACOES):
        op.execute(f"GRANT {privilegios} ON {objeto} TO aprimora_app")

    # 4. Grants do papel de plataforma sobre objetos que SOBREVIVEM ao
    #    downgrade (os das tabelas novas somem junto com as tabelas).
    op.execute(f"REVOKE ALL ON {S}.tenant FROM {ROLE}")
    op.execute(f"REVOKE ALL ON {S}.tenant_modulo FROM {ROLE}")
    op.execute(f"REVOKE ALL ON {S}.modulo FROM {ROLE}")
    op.execute(f"REVOKE ALL ON {S}.modulo_transacao FROM {ROLE}")
    op.execute(f"REVOKE ALL ON SEQUENCE {S}.tenant_id_seq FROM {ROLE}")
    op.execute(f"REVOKE ALL ON SEQUENCE {S}.tenant_modulo_id_seq FROM {ROLE}")

    # 3 e 2. Tabelas (a auditoria referencia o principal: cai primeiro).
    op.drop_index("ix_platform_audit_log_tenant_alvo", table_name="platform_audit_log", schema=S)
    op.drop_index("ix_platform_audit_log_principal", table_name="platform_audit_log", schema=S)
    op.drop_index("ix_platform_audit_log_criado", table_name="platform_audit_log", schema=S)
    op.drop_table("platform_audit_log", schema=S)
    op.drop_table("platform_principal", schema=S)

    # 1. Papel. `DROP ROLE` falha se ainda houver objeto ou privilégio
    #    dependente; o bloco contém a falha para não abortar o downgrade
    #    inteiro (mesma técnica da 0006).
    op.execute(
        f"""
        DO $$
        BEGIN
            BEGIN EXECUTE format('REVOKE USAGE ON SCHEMA {S} FROM {ROLE}');
            EXCEPTION WHEN OTHERS THEN NULL; END;
            BEGIN EXECUTE format('REVOKE CONNECT ON DATABASE %I FROM {ROLE}', current_database());
            EXCEPTION WHEN OTHERS THEN NULL; END;
            BEGIN EXECUTE 'DROP ROLE IF EXISTS {ROLE}';
            EXCEPTION WHEN OTHERS THEN NULL; END;
        END $$;
        """
    )
