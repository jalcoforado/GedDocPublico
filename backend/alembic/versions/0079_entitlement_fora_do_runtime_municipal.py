"""SEC-RLS-00C — entitlement sai do alcance do runtime municipal.

Revision ID: 0079
Revises: 0078
Create Date: 2026-08-02

Autoridade: `docs/architecture/adr/ADR-016-platform-operator-identity.md` §2.3
("`aprimora_app` … **Sem** DML de entitlement") e o plano
`docs/superpowers/plans/2026-08-01-arquitetura-modular-monolito.md`, seção
`SEC-RLS-00B`, item 10 — onde esta revogação ficou registrada como **adiada**,
com a razão.

## O que estava aberto

A fronteira de entitlement estava fechada no HTTP (`require_platform_admin`
protege as 8 rotas de `/admin/tenants`) e **aberta no SQL**:

```
aprimora_app -> tenant         : INSERT, SELECT, UPDATE
aprimora_app -> tenant_modulo  : INSERT, SELECT
```

`aprimora_py.tenant_modulo` **não tem RLS** — é tabela de plataforma, por
decisão registrada na 0073 e no CLAUDE.md. Sem RLS, o `GRANT` é a única coisa
entre um papel e a tabela inteira: qualquer injeção ou defeito de service no
runtime municipal inseria uma linha de contratação para **qualquer** tenant,
auto-contratando módulo que ninguém comprou. Alterar e apagar já não dava (a
0076 revogou `UPDATE`/`DELETE`); **criar, dava** — e criar é o que basta para
contratar.

## Por que só agora

A 0076 deixou o `INSERT` de pé por um motivo concreto, escrito no seu bloco "O
que NÃO é revogado, e por quê": `provisionar_tenant` era um bloco monolítico que
gravava nas tabelas de entitlement **e** nas tabelas de negócio do tenant, tudo
sob o papel municipal. Revogar sem partir teria derrubado o onboarding — "um PR
de segurança que derruba o provisionamento não é contenção, é incidente".

O `SEC-RLS-00C` partiu o provisionamento em dois atos
(`app/services/provisioning_tenant.py`): o ato de PLATAFORMA cria o tenant e a
contratação sob `aprimora_platform`; o ato MUNICIPAL povoa o tenant sob o papel
municipal, já no contexto daquele tenant. Feita a partição, o `INSERT` deixou de
ter uso legítimo no papel municipal — e é o que esta migration tira.

## O que NÃO é revogado, e por quê — decidido caso a caso

- **`UPDATE` em `aprimora_py.tenant` FICA, e o alcance real é maior do que o uso
  que o justifica.** O uso legítimo é diário e é cadastro institucional, não
  entitlement: `services/tenant_config.atualizar_config_institucional` deixa o
  admin do MUNICÍPIO editar sigla, endereço, telefone, texto do portal e unidade
  padrão do próprio tenant, filtrando `Tenant.id == tenant_id` em código.

  **Mas o grant é de tabela inteira.** `aprimora_py.tenant` não tem RLS, e
  `information_schema.column_privileges` mostra `UPDATE` para `aprimora_app` nas
  24 colunas — inclusive `ativo`, `plano`, `slug`, `limite_usuarios` e
  `limite_armazenamento_mb`. É a MESMA estrutura de risco que este PR fecha no
  `INSERT`, deixada aberta no `UPDATE`: um defeito de service no runtime
  municipal poderia elevar o próprio plano, reativar-se depois de suspenso ou
  **desativar outro município**. A whitelist de campos do service é barreira de
  aplicação, não de banco.

  Não é regressão — o grant é anterior a este PR e o comportamento não muda —,
  mas a razão registrada tinha de dizer o que o grant concede, e não só o que o
  código faz com ele. Fechar de verdade é `GRANT UPDATE (col, ...)` por coluna;
  está em `docs/BACKLOG-PENDENCIAS.md` como **SEC-RLS-00D — grant por coluna em
  `aprimora_py.tenant`**.
- **`INSERT` em `aprimora_py.audit_log` FICA.** Não é entitlement de forma
  nenhuma: é a trilha que o próprio município grava a cada mutação, por
  `services/audit.py`, chamado de dezenas de rotas. E a tabela **tem** RLS FORCE
  com `WITH CHECK (tenant_id = current_setting('app.tenant_id'))`, então existe
  segunda barreira — o papel municipal só grava dentro do próprio tenant, ao
  contrário de `tenant_modulo`. Revogá-lo não fecharia brecha e derrubaria a
  aplicação inteira. Travado por
  `tests/test_entitlement_fronteira_sql.py::test_aprimora_app_continua_gravando_a_propria_trilha`.
- **`SELECT` nas duas FICA.** O runtime municipal precisa ler a própria
  contratação: é disso que vivem `auth/perms.py` (bloqueio por módulo não
  contratado) e `auth/modulos.py::require_modulo`.
- **`USAGE` nas sequences `tenant_id_seq` e `tenant_modulo_id_seq` FICA.** Sem
  `INSERT` na tabela, `nextval()` só queima id — não grava linha nenhuma.
  Revogar não fecharia nada e alongaria o `downgrade` sem ganho; a barreira que
  importa é a da tabela.

Com isto, `_REVOGACOES` da 0076 não tem mais nenhum item adiado, e o bloco de
comentário de lá foi atualizado para apontar para cá.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0079"
down_revision: str | Sequence[str] | None = "0078"
branch_labels = None
depends_on = None

S = "aprimora_py"
APP = "aprimora_app"

# Mesma forma da lista da 0076, e pelo mesmo motivo: `revogar` e `restaurar` são
# campos SEPARADOS. O `upgrade()` revoga o que EXISTE hoje; o `downgrade()`
# devolve apenas o que alguma migration concedeu por DECLARAÇÃO. Reusar
# `revogar` no rollback devolveria a `aprimora_app` privilégio que nenhuma
# migration jamais deu — foi exatamente o defeito que a 0076 documenta ter
# corrigido.
#
#   objeto          declarado por migration                   revogado aqui
#   tenant          nada (veio do GRANT-cobertor do bootstrap)  INSERT
#   tenant_modulo   SELECT, INSERT, UPDATE, DELETE (0073)       INSERT
#
# Restaurar `INSERT` em `tenant_modulo` no downgrade reabre, sim, exatamente a
# brecha que este PR fecha — e é o comportamento CERTO: rollback de migration
# devolve o estado anterior declarado, não um estado intermediário que nunca
# existiu no repositório. Quem roda `downgrade -1` está voltando para a 0078,
# onde a brecha existia por decisão registrada.
_REVOGACOES: list[tuple[str, str, str, str]] = [
    (
        f"{S}.tenant",
        "INSERT",
        "",  # nenhuma migration concedeu INSERT em tenant a aprimora_app
        "criar município é ato de PLATAFORMA. Depois do SEC-RLS-00C quem insere "
        "é `criar_registro_de_tenant`, sob `aprimora_platform`. O papel "
        "municipal continua com SELECT (resolução de tenant, branding) e UPDATE "
        "(configuração institucional do próprio tenant).",
    ),
    (
        f"{S}.tenant_modulo",
        "INSERT",
        "INSERT",  # a 0073 concedeu os quatro; restaurar INSERT é honesto
        "contratar módulo é entitlement, e `tenant_modulo` NÃO tem RLS — o grant "
        "é a única barreira. Com INSERT, um defeito de service no runtime "
        "municipal auto-contratava módulo para qualquer tenant. Depois do "
        "SEC-RLS-00C quem contrata é o ato de plataforma.",
    ),
]


def upgrade() -> None:
    for objeto, revogar, _restaurar, _razao in _REVOGACOES:
        op.execute(f"REVOKE {revogar} ON {objeto} FROM {APP}")


def downgrade() -> None:
    # Vazio em `restaurar` ⇒ nada a devolver, e o `GRANT` é PULADO: `GRANT  ON x
    # TO y` é erro de sintaxe, e um `GRANT ALL` "por garantia" seria pior ainda.
    for objeto, _revogar, restaurar, _razao in reversed(_REVOGACOES):
        if not restaurar:
            continue
        op.execute(f"GRANT {restaurar} ON {objeto} TO {APP}")
