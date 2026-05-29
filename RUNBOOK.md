# Runbook operacional — Aprimora SaaS

Procedimentos para operações de produção. Tudo executável como `docker exec aprimora-py-backend ...`.

---

## Painel admin de plataforma (PR3a)

Onboarding e gestão de tenants pela interface, sem mexer no banco.

**`PLATFORM_ADMIN_EMAILS` é obrigatório** para operar o painel. É a allowlist
(separada por vírgula) de e-mails de usuários com acesso à administração da
plataforma. **Vazio = ninguém acessa** (bloqueio seguro por padrão). NÃO é
permissão de tenant: super-usuário de prefeitura **não** entra.

```bash
# .env do backend (produção)
PLATFORM_ADMIN_EMAILS=ops@aprimora.app,gestor@aprimora.app
```

- Painel: `/admin/tenants` (criar/listar/editar/ativar/desativar).
- Criar uma prefeitura gera uma **senha temporária exibida UMA ÚNICA VEZ** na
  resposta; repasse pelo canal acordado (NUNCA email texto-puro) e oriente a
  troca após o 1º acesso. Só o hash bcrypt é persistido.
- API: `POST /api/v2/admin/tenants` (e `GET/PUT/.../ativar/desativar`),
  protegida pela allowlist (`require_platform_admin`).

## Onboarding de um novo tenant (CLI)

A CLI usa o **mesmo serviço** (`services/provisioning_tenant`) do painel:

```bash
docker exec aprimora-py-backend python -m app.cli.tenant create \
  --slug fortaleza \
  --nome "Prefeitura Municipal de Fortaleza" \
  --cnpj 07954605000160 \
  --plano profissional \
  --cor "#0055aa" \
  --admin-email admin@fortaleza.gov.br \
  --admin-cpf 12345678901 \
  --admin-nome "Maria Silva"
```

Saída inclui a senha temporária gerada (exibida uma vez). Em prod, repasse pelo
canal acordado (NUNCA por email texto-puro). Só o hash bcrypt é persistido
(o campo MD5 legado fica vazio).

Pós-criação:
1. Configurar DNS: `fortaleza.aprimora.app` → mesmo IP do produto
2. Compartilhar URL + credenciais com o cliente
3. Acompanhar primeiros logins via `aprimora.access` logs (filtrar `tenant_slug=fortaleza`)

Listar tenants existentes:

```bash
docker exec aprimora-py-backend python -m app.cli.tenant list
```

Desativar (impede login, preserva dados):

```bash
docker exec aprimora-py-backend python -m app.cli.tenant deactivate fortaleza
docker exec aprimora-py-backend python -m app.cli.tenant activate fortaleza
```

---

## Backup por tenant

### Inspecionar o tamanho

```bash
docker exec aprimora-py-backend python -m app.cli.backup stats --tenant sobral
```

Mostra linhas por tabela + total. Útil pra validar que dados foram backfilled
após migração ou pra prever tamanho do export.

### Exportar dados

```bash
docker exec aprimora-py-backend python -m app.cli.backup export --tenant sobral
```

Gera `/app/uploads/tenants/sobral/backups/backup_sobral_<timestamp>Z.sql`
com:

- `BEGIN` + `SET session_replication_role = 'replica'` (pula FKs durante restore)
- `DELETE FROM <tabela> WHERE tenant_id = X` (ordem inversa — idempotente)
- `INSERT INTO <tabela> ... VALUES (...)` (ordem topológica — pais primeiro)
- `SELECT setval(<sequence>, MAX(id))` (alinha sequences pra novos inserts não colidirem)
- `SET session_replication_role = 'origin'` + `COMMIT`

**Tabelas dump-adas** (27 ao total): a linha do tenant em `aprimora_py.tenant`
mais as 26 tabelas tenanted (16 em `protocolos.*`, 9 em `utils.*`, `aprimora_py.job`).

**NÃO** inclui catálogos globais (`utils.estado/cidade/bairro/nivel/sistema/transacao`,
`protocolos.acao/prioridade/tipo_assinatura`, `public.modulos`). Esses são fixos
(IBGE/sistema) — destino precisa tê-los populados de outro jeito (seed do dump base).

**NÃO** inclui arquivos físicos do storage (`/app/uploads/tenants/<slug>/anexos/`).
Para um backup COMPLETO incluir:

```bash
docker exec aprimora-py-backend tar czf /app/uploads/tenants/sobral/backups/files_sobral_$(date -u +%Y%m%dT%H%M%S).tgz -C /app/uploads/tenants/sobral anexos carimbados
```

### DR drill — validar export sem restaurar

```bash
docker exec aprimora-py-backend python -m app.cli.backup dr-drill --tenant sobral
```

Faz export + parse-check do SQL gerado. Não restaura em nenhum DB. Roda como
smoke periódico (incluir no Celery Beat quando virar produção).

### Restore num banco destino

```bash
# 1. Copia o arquivo para a máquina destino
docker cp aprimora-py-backend:/app/uploads/tenants/sobral/backups/backup_sobral_<ts>.sql ./

# 2. Garante que o destino tem o schema base (Alembic head)
docker exec <destino> alembic upgrade head

# 3. Garante que catálogos globais estão populados (estado, cidade, etc)
#    — em um banco virgem, rodar os seeds equivalentes ao restore-dev-data.sql

# 4. Aplica o backup
docker cp backup_sobral_<ts>.sql <db-destino>:/tmp/
docker exec <db-destino> psql -U ged_user -d ged_saas_db -f /tmp/backup_sobral_<ts>.sql
```

O `DELETE ... WHERE tenant_id = X` no início torna o restore **idempotente**:
rodar duas vezes não duplica linhas. Se quiser restaurar como NOVO tenant_id
(útil pra clonar Sobral pra um novo cliente), editar o arquivo SQL antes —
substituir `tenant_id = 1` por `tenant_id = N`.

---

## Observabilidade

### Logs estruturados

Cada request gera 1 linha JSON em stdout:

```json
{"ts":"2026-05-23T23:33:03","level":"INFO","logger":"aprimora.access",
 "msg":"http_request","request_id":"ab591d5af3a1456a","tenant_id":1,
 "tenant_slug":"sobral","usuario_id":2,"method":"GET","path":"/api/v2/processos",
 "status":200,"duration_ms":61,"client":"127.0.0.1"}
```

Em produção, agregar com Loki/ELK/Cloudwatch via stdout. Para filtrar por tenant:

```bash
docker logs aprimora-py-backend 2>&1 | grep '"tenant_slug":"sobral"'
```

### Sentry (opcional)

Setar `SENTRY_DSN` no env do backend + instalar `sentry-sdk` no Dockerfile.
Cada evento de erro vem automaticamente com tags `tenant_id`, `tenant_slug`,
`request_id`, `user.id` populados pelo `RequestLoggingMiddleware`.

### Healthcheck

```bash
curl -H "Host: sobral.aprimora.local" http://localhost:8090/api/v2/health
# {"status":"ok","version":"0.1.0","db":"ok","db_latency_ms":1,"tenant":"sobral"}
```

Usar no liveness/readiness do orquestrador. `db_latency_ms > 100` é sinal pra
investigar.

---

## Incidentes comuns

### "Tenant não encontrado" no login

Causa: subdomain do Host não bate com nenhum `aprimora_py.tenant.slug` ativo.

Diagnóstico:

```bash
docker exec aprimora-py-backend python -m app.cli.tenant list
docker logs aprimora-py-backend 2>&1 | grep 'http_request.*404' | tail
```

### Cross-tenant 403

Cliente recebe `403 Token de outro tenant`. Causa: JWT do tenant A com Host do
tenant B (provavelmente cache CDN errado, ou usuário trocou subdomain sem
re-login). Mandar usuário fazer logout + login no subdomain correto.

### Worker Celery não processa

```bash
docker logs aprimora-py-worker --tail 50
```

Caveat conhecido (resolvido na Fase 7.1): nunca importar `SessionLocal`
global em tasks. Usar `task_session_scope(tenant_id=...)`.

---

## Dívida técnica (PR3a e correlatos)

Itens conscientemente adiados — revisitar em PRs futuros:

- **Campo `senha` (MD5 legado) em `utils.usuario`:** hoje NOT NULL. O
  provisionamento grava `""` (só bcrypt é credencial). Remover/torná-lo nullable
  quando o fluxo legado MD5 puder ser aposentado.
- **`must_change_password` no 1º acesso:** não implementado (exige flag +
  enforcement no login + UX). A senha temporária é exibida 1x; troca é manual.
- **Domínio neutro da plataforma:** hoje o admin de plataforma autentica no
  subdomínio do seu tenant de origem; avaliar um domínio/admin dedicado para
  operar a plataforma de forma independente de um tenant.
- **Status do tenant:** hoje booleano `ativo`. Evoluir para enum
  (implantação/trial/suspenso/inadimplente/cancelado) só quando houver
  billing/operação que justifique.
- **Enforcement de limites:** `limite_usuarios`/`limite_armazenamento_mb` são
  apenas armazenados; o bloqueio efetivo (quota) fica para PR futuro.
- **Módulos por tenant:** derivados do `plano` (sem tabela `tenant_modulo`);
  customização fina por módulo é PR posterior.
