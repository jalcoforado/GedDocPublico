"""SEC-RLS-00B — papéis mínimos de runtime, sujeitos a RLS.

Revision ID: 0078
Revises: 0077
Create Date: 2026-08-02

Autoridade: `docs/architecture/adr/ADR-016-platform-operator-identity.md` §2.3 e
§9.1; medição em `docs/architecture/security/rls-bypass-inventory.md`
(achado **F-12**).

Esta migration não troca a credencial de ninguém. Ela deixa o banco em estado
tal que a troca — `SEC-RLS-ROLLOUT` — seja possível sem que nada quebre. São
quatro blocos:

1. **`transporte_regulado`** — o maior item do inventário (§8.5). Sete tabelas
   ficam inacessíveis para qualquer papel sem `BYPASSRLS`, por três defeitos
   independentes que se somam:

   a. **20 policies referenciam `current_setting('app.current_tenant_id')`**,
      GUC que a aplicação NUNCA seta — ela seta `app.tenant_id`
      (`app/database.py`, listener `after_begin`). Pior: **sem** o segundo
      argumento `true`, `current_setting` de GUC inexistente **levanta erro**
      em vez de devolver `NULL`. A policy não nega; ela derruba a consulta com
      `unrecognized configuration parameter`. Origem: migrations 0050, 0051,
      0053, 0056 e 0057; a 0061 corrigiu apenas `alvara`.
   b. **8 tabelas com `ENABLE` e sem `FORCE`.** Hoje isso não aparece porque o
      dono (`ged_user`) é também o runtime. No instante em que o runtime deixar
      de ser o dono, elas passam a ser filtradas — e é aí que (a) estoura.
   c. **4 tabelas e 6 sequences sem grant** para `aprimora_app`. O
      `scripts/bootstrap-db.sh` concede em `protocolos, utils, aprimora_py,
      public` e não em `transporte_regulado`; as migrations do módulo não
      trouxeram o `GRANT` do boilerplate.

   `alvara_auditoria` ganha, além disso, uma policy de modificação: hoje ela só
   tem `tenant_isolation_select`, e aplicar `FORCE` sem isso tornaria a trilha
   **não-inserível** — o módulo pararia de gravar auditoria de alvará.

2. **`aprimora_worker`** (novo) — papel do Celery, com grants **enumerados por
   task**: `SELECT` amplo (as tasks montam relatório lendo o domínio inteiro) e
   escrita apenas nas seis tabelas em que as tasks de fato gravam.

3. **`aprimora_migrator`** (novo) — papel das operações ADMINISTRATIVAS: DDL do
   Alembic e os CLIs de seed/backup. **Nunca** usado por processo de runtime.
   Recebe `CREATE` nos schemas e DML completo, e é o único papel autorizado a
   APAGAR linha de `aprimora_py.audit_log` — por policy nominal, não por
   bypass.

4. **Verificação de `aprimora_platform`** — criado por `SEC-01A` (0076). Esta
   migration **não o redefine** (ADR §9.1: as duas famílias não podem definir o
   mesmo papel); apenas confirma, em bloco `DO`, que ele existe e continua
   `NOSUPERUSER`/`NOBYPASSRLS`, abortando o upgrade se alguém o tiver afrouxado.

**Nenhum dos papéis criados aqui é `SUPERUSER` e nenhum tem `BYPASSRLS`.**
Restaurar o bypass é proibido (ADR §9.1), inclusive como atalho para uma policy
que falha: policy ou grant que falhar é corrigido.

**Lacuna que esta migration NÃO fecha, e é deliberado:** `aprimora_migrator`
recebe `CREATE` nos schemas, mas **não** é dono das tabelas legadas — o dump de
`scripts/bootstrap-db.sh` é carregado por `ged_user`. Migration que faça
`ALTER TABLE` numa tabela pré-existente (por exemplo
`ENABLE ROW LEVEL SECURITY`) exige ser dono, e portanto continua precisando de
`ged_user` em banco já provisionado. Transferir a posse de 234 tabelas é
mudança de bootstrap, não de migration, e teria blast radius maior que o resto
deste PR somado. Registrado como pendência; o teste
`test_rls_papeis_minimos.py` mede o que o papel HOJE consegue, não o que se
gostaria que conseguisse.

Senha dos papéis: a de DEV, já versionada por decisão registrada (mesma escolha
da 0006 e da 0076). Em produção, `ALTER ROLE ... PASSWORD '<cofre>'`.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0078"
down_revision: str | Sequence[str] | None = "0077"
branch_labels = None
depends_on = None

SENHA_DEV = "ged_password_secure_local"

WORKER = "aprimora_worker"
MIGRATOR = "aprimora_migrator"
APP = "aprimora_app"
PLATFORM = "aprimora_platform"

TR = "transporte_regulado"

SCHEMAS_NEGOCIO = (
    "aprimora_py",
    "frota",
    "pagamentos",
    "protocolos",
    TR,
    "utils",
)

# A forma tolerante e correta, usada pelas outras 162 policies do banco. Os dois
# detalhes que faltavam nas 20 defeituosas estão aqui: o nome certo da GUC
# (`app.tenant_id`) e o segundo argumento `true`, que faz `current_setting`
# devolver NULL — e a policy NEGAR — em vez de abortar a consulta.
QUAL = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int"

# As 5 tabelas cujas 20 policies (SELECT/INSERT/UPDATE/DELETE em cada) apontam
# para a GUC inexistente. Os nomes das policies são preservados: recriar com o
# mesmo nome mantém o `downgrade()` simétrico e não muda o que qualquer consulta
# de catálogo já espera encontrar.
TABELAS_GUC_ERRADA = (
    "alvara_documento",
    "alvara_responsavel",
    "veiculo_avaliacao",
    "veiculo_documento",
    "veiculo_vistoria",
)

# A expressão ERRADA, para o downgrade reconstruir o estado anterior tal como
# era — inclusive com o defeito. Downgrade que "melhora" o estado esconde o que
# o upgrade fez e torna o rollback impossível de verificar.
QUAL_ANTIGA = "tenant_id = current_setting('app.current_tenant_id')::integer"

# As 8 tabelas com `ENABLE` e sem `FORCE` (inventário §2.1). Cada uma sai da
# `ALLOWLIST_SEM_RLS_FORCADA` de `tests/test_rls_bypass_caracterizacao.py` no
# mesmo commit — a guarda reprova allowlist obsoleta, e é assim que a dívida
# encolhe de forma verificável.
TABELAS_SEM_FORCE = (
    "alvara",
    "alvara_auditoria",
    "alvara_documento",
    "alvara_responsavel",
    "alvara_veiculo",
    "veiculo_avaliacao",
    "veiculo_documento",
    "veiculo_vistoria",
)

# Grants que faltam a `aprimora_app` em `transporte_regulado` (inventário §4).
# `alvara_auditoria` fica em SELECT+INSERT: é trilha append-only, mesmo
# tratamento que a 0076 deu a `aprimora_py.audit_log` — o runtime municipal
# grava e lê a própria auditoria, nunca altera nem apaga linha já gravada.
GRANTS_APP_TR: tuple[tuple[str, str], ...] = (
    ("alvara", "SELECT, INSERT, UPDATE, DELETE"),
    ("alvara_documento", "SELECT, INSERT, UPDATE, DELETE"),
    ("alvara_responsavel", "SELECT, INSERT, UPDATE, DELETE"),
    ("alvara_auditoria", "SELECT, INSERT"),
)

SEQUENCES_TR_SEM_GRANT = (
    "alvara_documento_id_seq",
    "alvara_id_seq",
    "alvara_responsavel_id_seq",
    "veiculo_avaliacao_id_seq",
    "veiculo_documento_id_seq",
    "veiculo_vistoria_id_seq",
)

# Escrita do worker, tabela a tabela, com a task que justifica cada uma. Tudo o
# mais o worker só LÊ. A lista é curta de propósito: task que precisar gravar em
# tabela nova tem de vir aqui declarar, e o PR que esquecer disso falha em
# `test_rls_papeis_minimos.py`.
ESCRITA_WORKER: tuple[tuple[str, str, str], ...] = (
    (
        "aprimora_py.job",
        "INSERT, UPDATE, DELETE",
        "todas as tasks de job atualizam status/resultado; "
        "`limpar_jobs_antigos` APAGA job vencido — é o único DELETE do worker",
    ),
    (
        "aprimora_py.audit_log",
        "INSERT",
        "trilha append-only: o worker grava, nunca altera nem apaga",
    ),
    (
        "aprimora_py.notificacao",
        "INSERT, UPDATE",
        "`verificar_sla_workflows` dispara notificação de SLA estourado",
    ),
    (
        "aprimora_py.notificacao_preferencia",
        "INSERT, UPDATE",
        "`services/notificacoes` cria a preferência default do destinatário "
        "na primeira notificação",
    ),
    (
        "aprimora_py.workflow_sla_alerta",
        "INSERT, UPDATE",
        "`verificar_sla_workflows` insere o alerta (upsert) e o resolve",
    ),
    (
        "pagamentos.saldo_historico",
        "INSERT, UPDATE",
        "`snapshot_saldos_pagamentos` grava o snapshot diário (upsert por "
        "`uq_saldohist_conta_data`)",
    ),
    (
        "protocolos.anexo",
        "INSERT, UPDATE",
        "`carimbar_anexos` grava o caminho do PDF carimbado",
    ),
)

# Sequences correspondentes às tabelas em que o worker INSERE.
SEQUENCES_WORKER = (
    "aprimora_py.job_id_seq",
    "aprimora_py.audit_log_id_seq",
    "aprimora_py.notificacao_id_seq",
    "aprimora_py.notificacao_preferencia_id_seq",
    "aprimora_py.workflow_sla_alerta_id_seq",
    "pagamentos.saldo_historico_id_seq",
    "protocolos.anexo_id_seq",
)

# Nome da policy que autoriza o papel administrativo a APAGAR linha da trilha
# municipal. Existe por um motivo concreto e único: `seed_demo reset` limpa os
# `audit_log` dos processos de demonstração que ele mesmo criou. Sem uma policy,
# o DELETE não erraria — devolveria **zero linhas**, e o reset diria que limpou
# tudo deixando a trilha para trás. Falha silenciosa é o modo de falha que este
# PR existe para eliminar.
POLICY_AUDIT_DELETE = "audit_log_migrator_delete"


def _cria_papel(nome: str) -> None:
    """`CREATE ROLE` idempotente, no padrão da 0006 e da 0076.

    Fora de um bloco `DO`, um `CREATE ROLE` que falha aborta a transação
    inteira e leva junto o bump de `alembic_version`.
    """
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{nome}') THEN
                CREATE ROLE {nome}
                    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS
                    PASSWORD '{SENHA_DEV}';
            END IF;
        END $$;
        """
    )
    # Idempotência real: se o papel JÁ existia (banco de dev que passou por
    # rollback, ou CI que o criou no bootstrap), o `CREATE` acima é pulado e os
    # atributos ficariam como estavam. Reafirmá-los aqui é o que torna o
    # invariante "nenhum papel de runtime é SUPERUSER" uma consequência da
    # migration, e não uma esperança sobre o estado anterior.
    op.execute(f"ALTER ROLE {nome} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE")
    op.execute(
        f"""
        DO $$
        BEGIN
            EXECUTE format('GRANT CONNECT ON DATABASE %I TO {nome}', current_database());
        END $$;
        """
    )


def _remove_papel(nome: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            BEGIN EXECUTE format('REVOKE CONNECT ON DATABASE %I FROM {nome}', current_database());
            EXCEPTION WHEN OTHERS THEN NULL; END;
            BEGIN EXECUTE 'DROP ROLE IF EXISTS {nome}';
            EXCEPTION WHEN OTHERS THEN NULL; END;
        END $$;
        """
    )


def _recria_policies_tr(qual: str) -> None:
    """(Re)cria as 20 policies das 5 tabelas de transporte com `qual`.

    Os nomes e os comandos são exatamente os das migrations 0050/0051/0053/
    0056/0057 — o que muda é só a expressão.
    """
    for tabela in TABELAS_GUC_ERRADA:
        for sufixo, comando in (
            ("select", "SELECT"),
            ("insert", "INSERT"),
            ("update", "UPDATE"),
            ("delete", "DELETE"),
        ):
            nome = f"{tabela}_{sufixo}"
            op.execute(f"DROP POLICY IF EXISTS {nome} ON {TR}.{tabela}")
            if comando == "INSERT":
                op.execute(
                    f"CREATE POLICY {nome} ON {TR}.{tabela} "
                    f"FOR INSERT WITH CHECK ({qual})"
                )
            elif comando == "UPDATE":
                op.execute(
                    f"CREATE POLICY {nome} ON {TR}.{tabela} "
                    f"FOR UPDATE USING ({qual}) WITH CHECK ({qual})"
                )
            else:
                op.execute(
                    f"CREATE POLICY {nome} ON {TR}.{tabela} "
                    f"FOR {comando} USING ({qual})"
                )


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 0. `aprimora_platform` — VERIFICAR, não redefinir (ADR §9.1).
    #    Falhar aqui é melhor que seguir: se o papel de plataforma ganhou
    #    SUPERUSER ou BYPASSRLS, todo o raciocínio de isolamento deste PR
    #    está errado, e a migration não deveria fingir que não.
    # ------------------------------------------------------------------
    op.execute(
        f"""
        DO $$
        DECLARE r record;
        BEGIN
            SELECT rolsuper, rolbypassrls INTO r
              FROM pg_roles WHERE rolname = '{PLATFORM}';
            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'papel % nao existe: a migration 0076 (SEC-01A) precisa ter '
                    'sido aplicada antes desta', '{PLATFORM}';
            END IF;
            IF r.rolsuper OR r.rolbypassrls THEN
                RAISE EXCEPTION
                    'papel % esta com rolsuper=% / rolbypassrls=% — ADR-016 §2.3 '
                    'proibe as duas coisas', '{PLATFORM}', r.rolsuper, r.rolbypassrls;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # 1. transporte_regulado — policies, FORCE e grants.
    # ------------------------------------------------------------------
    _recria_policies_tr(QUAL)

    # `alvara_auditoria` só tinha `tenant_isolation_select`. Sem uma policy de
    # modificação, o `FORCE` logo abaixo deixaria a trilha não-inserível.
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {TR}.alvara_auditoria")
    op.execute(
        f"CREATE POLICY tenant_isolation_modify ON {TR}.alvara_auditoria "
        f"FOR ALL USING ({QUAL}) WITH CHECK ({QUAL})"
    )

    for tabela in TABELAS_SEM_FORCE:
        op.execute(f"ALTER TABLE {TR}.{tabela} FORCE ROW LEVEL SECURITY")

    for tabela, privilegios in GRANTS_APP_TR:
        op.execute(f"GRANT {privilegios} ON {TR}.{tabela} TO {APP}")
    for seq in SEQUENCES_TR_SEM_GRANT:
        op.execute(f"GRANT USAGE, SELECT ON SEQUENCE {TR}.{seq} TO {APP}")

    # ------------------------------------------------------------------
    # 2. aprimora_worker — leitura ampla, escrita enumerada.
    # ------------------------------------------------------------------
    _cria_papel(WORKER)
    for schema in SCHEMAS_NEGOCIO:
        op.execute(f"GRANT USAGE ON SCHEMA {schema} TO {WORKER}")
        op.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {WORKER}")
    for objeto, privilegios, _razao in ESCRITA_WORKER:
        op.execute(f"GRANT {privilegios} ON {objeto} TO {WORKER}")
    for seq in SEQUENCES_WORKER:
        op.execute(f"GRANT USAGE, SELECT ON SEQUENCE {seq} TO {WORKER}")

    # ------------------------------------------------------------------
    # 3. aprimora_migrator — DDL e operações administrativas (seeds, backup).
    # ------------------------------------------------------------------
    _cria_papel(MIGRATOR)
    for schema in SCHEMAS_NEGOCIO + ("public",):
        op.execute(f"GRANT USAGE, CREATE ON SCHEMA {schema} TO {MIGRATOR}")
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
            f"IN SCHEMA {schema} TO {MIGRATOR}"
        )
        op.execute(
            f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA {schema} TO {MIGRATOR}"
        )
        # `GRANT ... ON ALL TABLES` é um retrato do momento: não alcança tabela
        # criada depois. Sem as default privileges, TODA migration futura teria
        # de lembrar de conceder ao migrator — e a que esquecesse só quebraria
        # no seed seguinte, longe da causa. Vinculadas a `ged_user` porque é ele
        # quem cria as tabelas hoje; o que o próprio migrator criar já nasce
        # dele.
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE ged_user IN SCHEMA {schema} "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {MIGRATOR}"
        )
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE ged_user IN SCHEMA {schema} "
            f"GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {MIGRATOR}"
        )

    # A trilha municipal é append-only para todo mundo (a 0076 tirou
    # UPDATE/DELETE de `aprimora_app`), e não há policy de DELETE — logo,
    # nem o grant bastaria. Esta policy nominal abre a exceção mínima: só
    # `aprimora_migrator`, só DELETE, e só dentro do tenant que a sessão
    # declarou em `app.tenant_id`.
    op.execute(f"DROP POLICY IF EXISTS {POLICY_AUDIT_DELETE} ON aprimora_py.audit_log")
    op.execute(
        f"CREATE POLICY {POLICY_AUDIT_DELETE} ON aprimora_py.audit_log "
        f"FOR DELETE TO {MIGRATOR} USING ({QUAL})"
    )


def downgrade() -> None:
    # Ordem inversa do upgrade.

    # 3. Papel administrativo.
    op.execute(f"DROP POLICY IF EXISTS {POLICY_AUDIT_DELETE} ON aprimora_py.audit_log")
    for schema in SCHEMAS_NEGOCIO + ("public",):
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE ged_user IN SCHEMA {schema} "
            f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {MIGRATOR}"
        )
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE ged_user IN SCHEMA {schema} "
            f"REVOKE USAGE, SELECT, UPDATE ON SEQUENCES FROM {MIGRATOR}"
        )
        op.execute(
            f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {schema} FROM {MIGRATOR}"
        )
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {MIGRATOR}")
        op.execute(f"REVOKE ALL ON SCHEMA {schema} FROM {MIGRATOR}")
    _remove_papel(MIGRATOR)

    # 2. Worker.
    for seq in SEQUENCES_WORKER:
        op.execute(f"REVOKE ALL ON SEQUENCE {seq} FROM {WORKER}")
    for objeto, _privilegios, _razao in ESCRITA_WORKER:
        op.execute(f"REVOKE ALL ON {objeto} FROM {WORKER}")
    for schema in SCHEMAS_NEGOCIO:
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {WORKER}")
        op.execute(f"REVOKE ALL ON SCHEMA {schema} FROM {WORKER}")
    _remove_papel(WORKER)

    # 1. transporte_regulado — devolve o estado ANTERIOR, defeitos inclusive.
    #    Um downgrade que mantivesse a correção mentiria sobre o que o upgrade
    #    fez, e o `alembic downgrade -1` deixaria de ser rollback verificável.
    for seq in SEQUENCES_TR_SEM_GRANT:
        op.execute(f"REVOKE ALL ON SEQUENCE {TR}.{seq} FROM {APP}")
    # `alvara_auditoria` tinha SELECT antes (concedido fora de migration, pelo
    # GRANT-cobertor do bootstrap): revogamos só o INSERT que ESTA migration
    # concedeu. As outras três não tinham privilégio nenhum.
    op.execute(f"REVOKE INSERT ON {TR}.alvara_auditoria FROM {APP}")
    for tabela in ("alvara", "alvara_documento", "alvara_responsavel"):
        op.execute(f"REVOKE ALL ON {TR}.{tabela} FROM {APP}")

    for tabela in TABELAS_SEM_FORCE:
        op.execute(f"ALTER TABLE {TR}.{tabela} NO FORCE ROW LEVEL SECURITY")

    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {TR}.alvara_auditoria")
    _recria_policies_tr(QUAL_ANTIGA)

    # 0. Nada a desfazer — a verificação de `aprimora_platform` não muda estado.
