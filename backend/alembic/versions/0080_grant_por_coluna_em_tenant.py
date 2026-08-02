"""SEC-RLS-00D — `UPDATE` em `aprimora_py.tenant` passa a ser por COLUNA.

Revision ID: 0080
Revises: 0079
Create Date: 2026-08-02

Autoridade: `docs/BACKLOG-PENDENCIAS.md`, item **1.0.85**, levantado pela revisão
de segurança do `SEC-RLS-00C` (migration 0079). O ADR-016 §2.3 dá a regra geral
("`aprimora_app` … **Sem** DML de entitlement"); aqui ela é aplicada ao caso em
que o privilégio de tabela concedia bem mais do que o uso legítimo justificava.

## O que estava aberto

`aprimora_py.tenant` **não tem RLS** — é tabela de plataforma, por decisão
registrada na 0073 e no CLAUDE.md. Sem RLS, o `GRANT` é a única coisa entre um
papel e a tabela inteira, e `aprimora_app` tinha `UPDATE` de TABELA: as 24
colunas, inclusive `ativo`, `plano`, `slug`, `limite_usuarios` e
`limite_armazenamento_mb`.

A única barreira contra o abuso era o `WHERE Tenant.id == tenant_id` dentro de
`services/tenant_config.atualizar_config_institucional` — barreira de
APLICAÇÃO, não de banco. Um defeito de service ou uma injeção no runtime
municipal podia elevar o próprio `plano`/`limite_*` (entitlement comercial),
reativar um município suspenso, ou **desativar outro município** — negação de
serviço cross-tenant com um `UPDATE`. É a mesma estrutura de risco que o
`SEC-RLS-00C` fechou no `INSERT` e deixou aberta no `UPDATE`.

## A lista de colunas, e de onde ela veio

Não é a whitelist do service copiada: é o levantamento de **todo** caminho de
escrita em `Tenant` que roda sob o papel municipal. São dois, e a whitelist só
cobre o primeiro:

1. `services/tenant_config.atualizar_config_institucional`, por
   `PUT /api/v2/tenants/me` — os 11 campos de `_CAMPOS_INSTITUCIONAIS`, que por
   sua vez espelham `schemas.tenant.TenantInstitucionalUpdate`.
2. `routers/tenant.py::update_nup_config`, por `PUT /api/v2/tenants/me/nup-config`
   — `codigo_orgao_nup` e `usar_nup_federal`. **Mesmo papel de banco, mesma
   permissão (`configuracao:atualizar`), e fora da whitelist**: o serviço não
   passa por `tenant_config`. Deixá-los de fora do grant faria esse endpoint
   devolver 500 (`permission denied for table tenant`) no dia do
   `SEC-RLS-ROLLOUT`, e o rastro apontaria para o service, não para o grant.

O terceiro caminho encontrado, `cli/tenant.py::_set_active` (`tenant activate` /
`deactivate`), gravava `ativo` e `atualizado_em` por `database.SessionLocal` —
isto é, pelo papel MUNICIPAL. Não foi acomodado no grant: ativar e desativar
município é ato de PLATAFORMA (é o que `POST /admin/tenants/{id}/ativar` já faz,
sob `get_platform_db`). A CLI foi corrigida neste mesmo PR para abrir a sessão
de plataforma, como `create` e `retomar` já fazem desde o `SEC-RLS-00C`.

As 11 colunas que ficam de fora — `id`, `slug`, `cnpj`, `id_cidade`, `ativo`,
`plano`, `criado_em`, `atualizado_em`, `limite_usuarios`,
`limite_armazenamento_mb`, `google_docs_habilitado` — são de plataforma ou não
têm caminho municipal de escrita nenhum. `aprimora_platform` continua com
`UPDATE` de tabela inteira e é por lá que todas elas se editam.

**`atualizado_em` fica de fora de propósito.** O modelo não declara `onupdate`
(`app/models/tenant.py:25`), nenhum caminho municipal a atribui à mão e não há
trigger. Se algum dia um caminho municipal precisar gravá-la, acrescente-a aqui
por migration nova — a guarda de divergência aponta o caminho.

## A guarda, que vale mais do que esta migration

`tests/test_grant_por_coluna_tenant.py` compara, em três pontas, o conjunto
concedido no banco, a constante `COLUNAS_MUNICIPAIS_DE_TENANT` do service e os
campos dos schemas Pydantic dos dois endpoints. Sem ela, acrescentar um campo à
whitelist amanhã produziria `permission denied for table tenant` em produção sem
nenhuma pista de que a causa é um grant — e quem investigasse procuraria o
defeito no service.

## Sobre a mensagem de erro do Postgres

Negativa por privilégio de COLUNA devolve exatamente a mesma frase da negativa
por privilégio de TABELA: `permission denied for table tenant`. Verificado neste
banco antes de escrever o teste. É por isso que cada negativa da guarda tem
controle positivo na MESMA sessão — sem ele, o verde não distingue "o grant por
coluna funcionou" de "o papel perdeu a tabela inteira".
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0080"
down_revision: str | Sequence[str] | None = "0079"
branch_labels = None
depends_on = None

S = "aprimora_py"
APP = "aprimora_app"

# Ordem alfabética, não a ordem física da tabela: a lista é lida por humanos e
# comparada com um `frozenset` do service, e ordenar por `attnum` só criaria
# divergência aparente numa revisão futura.
#
# Cada coluna aqui tem um caminho de escrita municipal REAL, nomeado no
# docstring. Acrescentar coluna "por precaução" é reabrir o que este PR fecha.
_COLUNAS_MUNICIPAIS: tuple[str, ...] = (
    # --- 1. configuração institucional (`PUT /tenants/me`) ------------------
    "cor_primaria",
    "email_institucional",
    "endereco",
    "horario_atendimento",
    "id_unidade_padrao",
    "logo_url",
    "nome",
    "sigla",
    "site_oficial",
    "telefone_institucional",
    "texto_boas_vindas_portal",
    # --- 2. NUP federal (`PUT /tenants/me/nup-config`) ----------------------
    "codigo_orgao_nup",
    "usar_nup_federal",
)


def upgrade() -> None:
    # A ordem importa e o REVOKE não é opcional: em Postgres, privilégio de
    # TABELA e privilégio de COLUNA são entradas de ACL DISTINTAS, e o de tabela
    # é o mais amplo dos dois. Conceder por coluna sem revogar o de tabela
    # deixaria o antigo valendo, o `information_schema.column_privileges`
    # continuaria mostrando 24 colunas e esta migration não faria absolutamente
    # nada — falharia em silêncio, que é o pior modo de falhar num PR de
    # segurança.
    op.execute(f"REVOKE UPDATE ON {S}.tenant FROM {APP}")
    colunas = ", ".join(_COLUNAS_MUNICIPAIS)
    op.execute(f"GRANT UPDATE ({colunas}) ON {S}.tenant TO {APP}")


def downgrade() -> None:
    """Devolve o `UPDATE` de TABELA a `aprimora_app`.

    **Isto reabre o alcance que o `upgrade()` fecha** — depois deste
    `downgrade`, o runtime municipal volta a poder gravar `ativo`, `plano`,
    `slug` e os limites de QUALQUER tenant. Está certo assim, e a razão é a
    mesma que a 0076 e a 0079 registram: rollback de migration devolve o estado
    anterior, não um estado intermediário que nunca existiu no repositório.
    Quem roda `downgrade -1` está voltando para a 0079, onde o grant de tabela
    existia por decisão registrada.

    Por isso reverter esta migration é DECISÃO, não reflexo: `alembic downgrade`
    disparado para destravar outra coisa leva junto a reabertura desta brecha.
    Se o motivo do rollback não for "quero o grant de tabela de volta", prefira
    uma migration nova que ajuste a lista de colunas.

    **Divergência deliberada da disciplina `revogar`/`restaurar` da
    0076/0078/0079.** Lá, `downgrade()` só devolve o que alguma migration
    concedeu por DECLARAÇÃO, e nenhuma jamais declarou `UPDATE` em `tenant` para
    `aprimora_app` — ele veio do `GRANT`-cobertor do bootstrap
    (`GRANT ... ON ALL TABLES IN SCHEMA aprimora_py`). Aqui o `GRANT` é
    obrigatório mesmo assim, e a diferença é de natureza: aquelas migrations
    apenas REVOGAM (o `downgrade` que não devolve nada deixa o papel com MENOS
    privilégio, o que é seguro), enquanto esta SUBSTITUI um privilégio por outro
    mais estreito. Um `downgrade` que só revogasse o grant por coluna deixaria
    `aprimora_app` sem `UPDATE` nenhum em `tenant` — estado que nunca existiu no
    repositório e que derruba `PUT /tenants/me` em produção. O rollback tem de
    desfazer a substituição inteira.
    """
    colunas = ", ".join(_COLUNAS_MUNICIPAIS)
    op.execute(f"REVOKE UPDATE ({colunas}) ON {S}.tenant FROM {APP}")
    op.execute(f"GRANT UPDATE ON {S}.tenant TO {APP}")
