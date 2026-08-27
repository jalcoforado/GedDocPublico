# P4 — Transporte Regulado: Alvarás — Complementações (Integração Veicular + Histórico + Relatórios)

**Data:** 2026-07-18  
**Status:** PROPOSTA (aguarda autorização Jorge)  
**Base:** P3.2 MERGED (2026-07-18)  
**Estimativa:** 80–100 testes backend, 3 migrations, 4 endpoints, UI significativa

---

## Contexto

P0–P3.2 entreguem fundação completa: permissionários, empresas, veículos, vistorias, alvarás (CRUD + renovação), documentos exigidos, responsáveis. **113 testes, 18 commits.**

P4 complementa a gestão de alvarás com 3 dimensões críticas:
1. **Integração Veicular:** Um alvará pode estar vinculado a múltiplos veículos (táxi amarelo com 2 táxis, mototáxi com 3 motos, etc.)
2. **Histórico & Auditoria:** Trail completo de quem alterou o quê e quando
3. **Relatórios:** Visão gerencial (dashboards, exports, filtros)

---

## Dimensão 1: Integração Veicular

### Backend

**Migration 0058: `transporte_regulado.alvara_veiculo` (join table)**
```sql
CREATE TABLE transporte_regulado.alvara_veiculo (
  id BIGSERIAL PRIMARY KEY,
  tenant_id INT NOT NULL,
  id_alvara BIGINT NOT NULL REFERENCES transporte_regulado.alvara(id),
  id_veiculo BIGINT NOT NULL REFERENCES transporte_regulado.veiculo(id),
  -- Metadados opcionais (ex: designação, data_inicio_vinculo)
  data_vinculo TIMESTAMP DEFAULT NOW(),
  criado_em TIMESTAMP DEFAULT NOW(),
  atualizado_em TIMESTAMP,
  
  UNIQUE (tenant_id, id_alvara, id_veiculo),
  FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id),
  CHECK (tenant_id IS NOT NULL)
);

-- RLS: tenant_isolation_select + modify (padrão 0043)
-- Índices: (tenant_id, id_alvara), (tenant_id, id_veiculo)
-- GRANTs: aprimora_app SELECT/INSERT/UPDATE/DELETE
```

**Service Layer (`services/transporte_regulado.py`)**
- `vincular_veiculo_alvara(db, tenant_id, id_alvara, id_veiculo)` → HTTPException 409 se já vinculado
- `desvincular_veiculo_alvara(db, tenant_id, id_alvara, id_veiculo)` → soft-delete ou direto?
- `listar_veiculos_alvara(db, tenant_id, id_alvara)` → list[VeiculoInfo]
- `listar_alvaras_veiculo(db, tenant_id, id_veiculo)` → list[AlvaraInfo]

**Endpoints**
```
POST   /alvaras/{alvara_id}/veiculos                # vincular veiculo
DELETE /alvaras/{alvara_id}/veiculos/{veiculo_id}  # desvincular
GET    /alvaras/{alvara_id}/veiculos                # listar veículos do alvará
GET    /veiculos/{veiculo_id}/alvaras               # listar alvarás do veículo
```

**Gate:** `require_permission("alvara", "atualizar")` (admin/servidor)

### Frontend

**Component: `AlvaraVeiculosCard`**
- Lista de veículos vinculados (tabela compacta: placa, tipo, vinculado_em)
- Botão "+ Vincular veículo"
- Modal `VincularVeiculoDialog`: picker de veículos (dropdown com busca por placa)
- Botão "Desvincular" por linha (confirm)

**Placement:** Página de detalhe do alvará, seção "Veículos" (após "Responsáveis")

### Tests

- Unit: vincular duplicado → 409, desvincular não-existente → 404
- Unit: listar veículos do alvará (cross-tenant 404)
- Integration: criar alvará sem veículos, vincular N veículos, listar
- Integration: desvincular todos, alvará continua ativo
- HTTP: gates, payload validation
- **Testes:** ~25

---

## Dimensão 2: Histórico & Auditoria

### Backend

**Migration 0059: `transporte_regulado.alvara_auditoria` (append-only)**
```sql
CREATE TABLE transporte_regulado.alvara_auditoria (
  id BIGSERIAL PRIMARY KEY,
  tenant_id INT NOT NULL,
  id_alvara BIGINT NOT NULL REFERENCES transporte_regulado.alvara(id),
  acao TEXT NOT NULL, -- alvara.criada, alvara.renovada, alvara.documentos_atualizados, etc.
  dados_antigos JSONB,  -- snapshot do estado anterior (opcional, para diff visual)
  dados_novos JSONB,    -- snapshot do estado novo
  id_usuario INT REFERENCES aprimora_py.usuario(id),
  criado_em TIMESTAMP DEFAULT NOW(),
  
  FOREIGN KEY (tenant_id) REFERENCES aprimora_py.tenant(id),
  CHECK (tenant_id IS NOT NULL)
);

-- RLS: tenant_isolation_select (read-only para não vazar audit)
-- Índice: (tenant_id, id_alvara, criado_em DESC)
-- GRANTs: aprimora_app SELECT, trigger-only INSERT
```

**Service Trigger Integration**
- Disparar evento em `criar_alvara`, `renovar_alvara`, `atualizar_responsavel_alvara`, `vincular_veiculo_alvara`, etc.
- Usar padrão existente de `audit_log` ou novo trigger?

**Service Layer**
- `listar_auditoria_alvara(db, tenant_id, id_alvara, limit=50)` → list[AlvaraAuditoriaItem]
- `obter_diff_auditoria(db, id_evento_ant, id_evento_novo)` → comparação visual (antes/depois)

**Endpoint**
```
GET /alvaras/{alvara_id}/auditoria?limit=50&offset=0
```

**Gate:** `require_permission("alvara", "ler")` (read-only, audit é para transparency)

### Frontend

**Component: `AlvaraHistoricoAuditoria`**
- Timeline visual: evento → ator → timestamp → descrição legível
- Click em evento: modal com "Antes/Depois" em card ao lado
- Filtro por ação (opcional)

**Placement:** Tab "Histórico" na página de detalhe do alvará

### Tests

- Unit: eventos criados corretamente
- Unit: diff de campos alterados (responsáveis, documentos, veículos)
- Integration: histórico preservado após soft-delete de referências
- HTTP: gates, paginação
- **Testes:** ~20

---

## Dimensão 3: Relatórios

### Backend

**Migration:** Nenhuma (usa tabelas existentes)

**Service Layer**
- `gerar_relatorio_alvaras(db, tenant_id, filtros)` → agregado (status, vencimentos, etc.)
  - Filtros: `status`, `data_vencimento_ate`, `permissionario_id`, `servico`, `apenas_ativos`
  - Retorna: `{"ativos": N, "vencidos": N, "a_renovar_30d": N, "por_status": {...}, "proximos_vencimentos": [...]}`

**Endpoints**
```
GET /relatorios/alvaras/resumo?filtros=...        # dashboard KPIs
GET /relatorios/alvaras/export?formato=pdf|csv    # export
```

**Gate:** `require_permission("dashboard")` ou `require_permission("alvara", "ler")`

### Frontend

**Component: `RelatorioAlvarasPage`**
- Cards KPI: Ativos, Vencidos, A Renovar em 30d, etc.
- Tabela: ranking por permissionário (alvará count, status breakdown)
- Filtros: status, data vencimento, permissionário (dropdowns)
- Botão "Export PDF" (estilo DO mesmo que pagamentos)

**Placement:** Menu → Transporte → Relatórios (nova rota `/relatorios/alvaras`)

### Tests

- Unit: agregações corretas (vencimento, status breakdown)
- Unit: filtros aplicados (cross-tenant safety)
- Integration: export PDF/CSV format válido
- HTTP: gates, permission checks
- **Testes:** ~25

---

## Sequência de Implementação

1. **Integração Veicular** (Fase 1)
   - Migration 0058 + service + endpoints
   - Frontend card + vincular dialog
   - Testes (25)

2. **Histórico & Auditoria** (Fase 2)
   - Migration 0059 + service + eventos disparados
   - Frontend timeline + diff modal
   - Testes (20)

3. **Relatórios** (Fase 3)
   - Service agregador
   - Endpoints export + dashboard
   - Frontend page + componentes
   - Testes (25)

**Total: 3 commits, ~80 testes, ~1.5 weeks solo (6-8 weeks solo + review Codex)**

---

## Verificação Pré-Commit (Por Fase)

### Fase 1: Integração Veicular
- [ ] Migration 0058 reversível + RLS/GRANTs corretos
- [ ] Endpoints com gates + validation
- [ ] Frontend card renderiza, vincular/desvincular funcionam
- [ ] Testes 25/25 ✓ (pytest + vitest)
- [ ] tsc ✅

### Fase 2: Histórico & Auditoria
- [ ] Migration 0059 + trigger disparando eventos
- [ ] Diff visual correto (antes/depois)
- [ ] Frontend timeline renderiza eventos com atores
- [ ] Testes 20/20 ✓
- [ ] tsc ✅

### Fase 3: Relatórios
- [ ] Agregações corretas (KPIs, status breakdown)
- [ ] Export PDF/CSV válido + legível
- [ ] Filtros aplicados corretamente
- [ ] Frontend page + tabelas funcionam
- [ ] Testes 25/25 ✓
- [ ] tsc ✅

---

## Ganchos Abertos / Futuros

- **P5 (Recadastramento):** Reúso de veículos vinculados para massivo
- **Notificações:** Alerta quando alvará está a vencer (event-driven)
- **Webhooks:** POST externo quando status alvará muda
- **Integração GIS:** Mapa de alvarás ativos por região (geolocalização de veículos)

---

## Referências

- P3.2 commit: transporte-regulado P3.1-P3.2 MERGED (2026-07-18)
- Models: `backend/app/models/transporte_regulado.py` (Alvara, Veiculo, etc.)
- Routers: `backend/app/routers/transporte_regulado.py`
- Migration pattern: `0043`, `0044`, `0057` (RLS, GRANTs, audit pattern)
- Frontend pattern: card + dialog (ex: `AlvaraResponsaveisCard`, `MinutasProcesso`)
