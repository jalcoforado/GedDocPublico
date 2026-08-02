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

# RELÓGIO ÚNICO: **UTC ingênuo**, tanto no default do servidor quanto no código.
#
# As colunas são `TIMESTAMP WITHOUT TIME ZONE`, e o `NOW()` puro grava a hora
# LOCAL do servidor. Como todo o código Python escreve `datetime.now(UTC)`, um
# host com TZ à frente de UTC produziria relógios misturados na mesma coluna —
# e o efeito não seria um erro, seria pior: uma linha criada por SQL cru
# nasceria com `valid_from` no futuro, `vigente_em()` devolveria `False`, e o
# resultado é **um principal cadastrado que simplesmente não opera**, sem
# mensagem em lugar nenhum. Em dev o Postgres está em UTC e isso jamais
# apareceria. Ver `app/utils/relogio.py`.
_AGORA_UTC = sa.text("(NOW() AT TIME ZONE 'utc')")


# Cada tupla é (objeto, revogar, RESTAURAR_NO_DOWNGRADE, razão).
#
# `revogar` e `restaurar` são campos SEPARADOS, e a distinção é o ponto todo
# desta lista. O que o `upgrade()` revoga é o que o **GRANT-cobertor** do
# bootstrap (`GRANT ... ON ALL TABLES ... TO aprimora_app`) havia concedido por
# ACIDENTE; o que o `downgrade()` pode devolver é apenas o que alguma migration
# concedeu por DECLARAÇÃO. Os dois conjuntos quase nunca coincidem:
#
#   objeto            declarado por migration        revogado aqui
#   audit_log         SELECT, INSERT (0014)          UPDATE, DELETE
#   modulo            SELECT (0073)                  INSERT, UPDATE, DELETE
#   modulo_transacao  SELECT (0073)                  INSERT, UPDATE, DELETE
#   tenant            nada                           DELETE
#   tenant_modulo     S,I,U,D (0073)                 UPDATE, DELETE
#
# Reusar `revogar` no `downgrade()` — como esta migration fazia — devolvia a
# `aprimora_app` privilégios que NENHUMA migration jamais concedeu. Em banco
# limpo, `alembic downgrade -1` terminava com o runtime municipal podendo dar
# `UPDATE`/`DELETE` em `audit_log`: o rollback de um PR de segurança deixava a
# trilha append-only mutável, estado que nunca existiu no repositório. Só
# `tenant_modulo` tem algo legítimo a restaurar.
#
# A razão é obrigatória: sem ela ninguém consegue julgar depois se a revogação
# continua correta.
_REVOGACOES: list[tuple[str, str, str, str]] = [
    (
        f"{S}.tenant",
        "DELETE",
        "",  # nenhuma migration concedeu DELETE em tenant a aprimora_app
        "apagar tenant não é operação de nenhum runtime — nem municipal, nem "
        "de plataforma (desativar é UPDATE ativo=false). Por isso o papel de "
        "plataforma também NÃO recebe DELETE aqui: a razão vale para os dois.",
    ),
    (
        f"{S}.tenant_modulo",
        "UPDATE, DELETE",
        "UPDATE, DELETE",  # a 0073 concedeu os quatro; restaurar é honesto
        "contratar/descontratar é entitlement — operação de PLATAFORMA. "
        "Descontratar é soft-delete (UPDATE excluido=true), então tirar UPDATE "
        "e DELETE fecha o caminho de mutação de contratação pelo papel "
        "municipal.",
    ),
    (
        f"{S}.audit_log",
        "UPDATE, DELETE",
        "",  # a 0014 concedeu SELECT, INSERT — e só
        "trilha append-only: o runtime municipal grava e lê a própria "
        "auditoria, nunca altera nem apaga linha já gravada.",
    ),
    (
        f"{S}.modulo",
        "INSERT, UPDATE, DELETE",
        "",  # a 0073 concedeu SELECT — e só
        "catálogo GLOBAL do produto. A 0073 concede só SELECT; o "
        "GRANT-cobertor do bootstrap devolvia DML. Aqui o estado fica "
        "determinístico.",
    ),
    (
        f"{S}.modulo_transacao",
        "INSERT, UPDATE, DELETE",
        "",
        "mesma razão de `modulo`.",
    ),
]

# O que NÃO é revogado, e por quê — a parte que uma revisão futura precisa ler:
#
# - `INSERT` em `tenant` e `tenant_modulo`: **NÃO É MAIS ADIADO — a `0079`
#   (`SEC-RLS-00C`) revogou os dois.** O que segurava a revogação aqui era que
#   `provisionar_tenant` gravava nas tabelas de entitlement E nas tabelas de
#   NEGÓCIO do tenant no mesmo bloco, sob o papel municipal; movê-lo inteiro
#   para `aprimora_platform` daria a esse papel DML em `utils.*`, que é
#   exatamente o que o ADR §2.3 lhe nega. A saída foi PARTIR o provisionamento
#   em ato de plataforma e ato municipal (`services/provisioning_tenant.py`), e
#   aí a revogação deixou de derrubar o onboarding. Ver a 0079 para as razões
#   caso a caso e `tests/test_entitlement_fronteira_sql.py` para a guarda.
# - `INSERT` em `audit_log`: FICA, e a 0079 confirmou a decisão. Não é
#   entitlement — é a trilha que o próprio município grava a cada mutação, e a
#   tabela tem RLS FORCE, então há segunda barreira.
# - `UPDATE` em `tenant`: FICA. Uso municipal legítimo — a configuração
#   institucional do próprio tenant
#   (`services/tenant_config.atualizar_config_institucional`) é editada pelo
#   admin do município, não pela plataforma.


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
        sa.Column("valid_from", sa.DateTime(), nullable=False, server_default=_AGORA_UTC),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        # Concessão: quem, quando, por quê (runbook §2 e §3).
        sa.Column("concedido_em", sa.DateTime(), nullable=False, server_default=_AGORA_UTC),
        sa.Column("concedido_por", sa.String(255), nullable=False),
        sa.Column("motivo_concessao", sa.Text(), nullable=False),
        # Revogação: quem, quando, por quê (runbook §4).
        sa.Column("revogado_em", sa.DateTime(), nullable=True),
        sa.Column("revogado_por", sa.String(255), nullable=True),
        sa.Column("motivo_revogacao", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=_AGORA_UTC),
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
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=_AGORA_UTC),
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
    for seq in ("platform_principal_id_seq", "platform_audit_log_id_seq"):
        op.execute(f"REVOKE ALL ON SEQUENCE {S}.{seq} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON SEQUENCE {S}.{seq} FROM aprimora_app")
        op.execute(f"GRANT USAGE, SELECT ON SEQUENCE {S}.{seq} TO {ROLE}")

    # `platform_principal` — DML completo: a CLI concede, revoga (UPDATE) e o
    # `DELETE` é a saída para um principal cadastrado por engano antes de
    # qualquer uso. Mutação de identidade é o trabalho deste papel.
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.platform_principal TO {ROLE}")

    # `platform_audit_log` — APPEND-ONLY, e por isso só SELECT e INSERT.
    # Este papel é o único que escreve na trilha AUTORITATIVA das operações de
    # plataforma. Dar-lhe UPDATE/DELETE significaria que a credencial de
    # `PLATFORM_DB_URL` comprometida — ou um bug numa rota futura — apaga
    # exatamente o registro do que fez. E é dessa trilha que dependem a revisão
    # trimestral (runbook §9) e o pós-uso de break-glass (§5.6): sem ela, as
    # duas revisam o vazio. Mesmo princípio que a 0077 aplica à trilha
    # municipal e que o `_REVOGACOES` aplica a `aprimora_app`.
    op.execute(f"GRANT SELECT, INSERT ON {S}.platform_audit_log TO {ROLE}")

    # Grants cross-tenant EXPLÍCITOS e ENUMERADOS do papel de plataforma
    # (ADR §2.3): entitlement, e nada de tabela de negócio de tenant.
    #
    # SEM `DELETE` em `tenant` nem em `tenant_modulo`, e a razão é a mesma que
    # o `_REVOGACOES` dá para tirá-lo de `aprimora_app`: apagar tenant não é
    # operação de runtime nenhum, e descontratar é soft-delete
    # (`UPDATE excluido = true`). Conceder aqui o que se revoga ali seria a
    # justificativa contradizendo o grant, e contrariaria a regra do CLAUDE.md
    # — exclusão é soft-delete, nunca DELETE físico.
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {S}.tenant TO {ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {S}.tenant_modulo TO {ROLE}")
    op.execute(f"GRANT SELECT ON {S}.modulo TO {ROLE}")
    op.execute(f"GRANT SELECT ON {S}.modulo_transacao TO {ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON SEQUENCE {S}.tenant_id_seq TO {ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON SEQUENCE {S}.tenant_modulo_id_seq TO {ROLE}")

    # ------------------------------------------------------------------
    # 5. Higiene: o que aprimora_app tem indevidamente (ADR §2.3).
    # ------------------------------------------------------------------
    for objeto, revogar, _restaurar, _razao in _REVOGACOES:
        op.execute(f"REVOKE {revogar} ON {objeto} FROM aprimora_app")


def downgrade() -> None:
    # Ordem inversa do upgrade.

    # 5. Devolve a aprimora_app apenas o que ALGUMA MIGRATION concedeu —
    #    campo `restaurar`, não `revogar`. Ver a tabela no bloco `_REVOGACOES`:
    #    o que o upgrade revoga veio do GRANT-cobertor do bootstrap, por
    #    acidente, e reconcedê-lo aqui deixaria o rollback de um PR de
    #    segurança MAIS permissivo do que qualquer estado já declarado (o caso
    #    grave era `UPDATE`/`DELETE` em `audit_log`, que a 0014 nunca deu).
    #    Vazio ⇒ nada a restaurar, e o `GRANT` é pulado: `GRANT  ON x TO y` é
    #    erro de sintaxe, e um `GRANT ALL` "por garantia" seria pior ainda.
    for objeto, _revogar, restaurar, _razao in reversed(_REVOGACOES):
        if not restaurar:
            continue
        op.execute(f"GRANT {restaurar} ON {objeto} TO aprimora_app")

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
