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

### Regenerar quando o schema legado mudar

```bash
docker exec ged-saas-project-db-1 pg_dump \
  -U ged_user -d ged_saas_db \
  --schema-only --no-owner --no-privileges \
  -n utils -n protocolos \
  > ci/legacy-schema.sql
```

Como o PHP é legacy intocado, o esperado é raramente atualizar.
