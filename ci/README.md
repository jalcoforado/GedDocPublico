# `ci/`

Artefatos consumidos pelo workflow do GitHub Actions
(`.github/workflows/backend-tests.yml`).

## `legacy-schema.sql`

Dump schema-only do banco `ged_saas_db` dev contendo os schemas
`utils` e `protocolos` — herdados do monolito PHP `aprimora/`.

As migrations do Alembic (0004 em diante) assumem que essas tabelas
**já existem** e adicionam colunas `tenant_id`, policies RLS, novas
tabelas, etc. Em desenvolvimento o banco vem de um dump base PHP;
em CI rodamos este SQL antes de `alembic upgrade head`.

### Revision do dump e migrations novas

O dump reflete o schema numa **revision baseline** (hoje `0020`) e tem o
`alembic_version` vazio. Os workflows fazem:

```bash
alembic stamp 0020   # carimba o baseline do dump (não roda 0001..0020)
alembic upgrade head # roda só as migrations NOVAS (ex.: 0021) — em banco limpo
```

Assim o CI **exercita** cada migration nova num banco limpo. Ao regenerar o
dump (abaixo), **atualize o baseline `0020`** nos workflows
(`backend-tests.yml`, `e2e-assinatura.yml`) para a nova revision do dump.

### Regenerar quando o schema legado mudar

```bash
docker exec ged-saas-project-db-1 pg_dump \
  -U ged_user -d ged_saas_db \
  --schema-only --no-owner --no-privileges \
  -n utils -n protocolos \
  > ci/legacy-schema.sql
```

Como o PHP é legacy intocado, o esperado é raramente atualizar.
