# Pagamentos C2 — Integrações: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Importador de extrato OFX/CNAB240 idempotente, export contábil neutro com lotes imutáveis e API externa M2M (escrita idempotente + leitura por cursor).

**Architecture:** C2.2 estende o pipeline existente `importar_extrato` (dispatch por `formato`) com dois parsers novos e dedupe por `id_externo`; C2.1 adiciona lotes imutáveis sobre eventos derivados do domínio real (débito/liquidação/ordem/estorno/cancelamento) atrás de um `ContabilAdapter`; C2.3 cria o realm `sistema_integrado` (API key) com `Idempotency-Key` na escrita e cursor na leitura, reusando os services existentes.

**Tech Stack:** FastAPI + SQLAlchemy 2 async, Alembic manual, Next.js 15, vitest/pytest.

**Spec:** `docs/superpowers/specs/2026-08-24-pagamentos-c2-integracoes-design.md`

## Global Constraints

- pt-BR em código, comentários, docs e commits; commits terminam com `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- **As RNs existentes não mudam**: RN-01/02/05/06/11/14/15 continuam onde estão; a API M2M e os parsers são portas novas para os MESMOS services — nunca caminho paralelo de regra. Suítes de pagamentos existentes passam sem edição semântica.
- **Toda task backend re-roda as 3 guardas** (`test_guarda_ordem_rotas`, `test_guarda_modularizacao`, `test_guarda_link_url`) + `test_rls_papeis_minimos.py`, com evidência RED do TDD no report.
- Tabela nova = boilerplate RLS completo (tenant_id NOT NULL, ENABLE+FORCE, 2 policies com `NULLIF(current_setting('app.tenant_id', true), '')::int`, GRANT tabela+sequence a `aprimora_app`). Worker não toca nenhuma tabela nova — sem grant de worker. Migration head atual: **0098**; numeração segue 0099, 0100, …, sempre head único, downgrade reverso.
- `tenant_id` sempre do realm/caller, nunca do payload; 404 cross-tenant; 409 para conflito; 403 permissão; GET novo nasce com `require_permission` (a guarda de leitura reprova isenção).
- Transações novas em `utils.transacao`? NÃO há — os endpoints novos usam os códigos de pagamentos existentes (conferir os vizinhos); se alguma task criar código novo, ele ENTRA em `MODULO_TRANSACOES` (a guarda reprova o contrário).
- pytest SEMPRE via `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest <alvo> -q`, em FOREGROUND, uma suíte por vez; frontend `cd frontend; npx vitest run` e `npx tsc --noEmit` no host. Implementers NÃO despacham subagentes nem deixam processos em background.
- Testes: e-mails `.test`, slugs prefixados + uuid, cleanup no teardown, nunca assumir banco vazio; provas por inversão para unicidade/idempotência.

---

### Task 1: C2.2 — parser OFX + dedupe por `id_externo` (migration 0099)

**Files:**
- Create: `backend/app/services/pagamentos_extrato_parsers.py`
- Create: `backend/alembic/versions/0099_lancamento_extrato_id_externo.py`
- Modify: `backend/app/services/pagamentos_conciliacao.py` (`importar_extrato`), `backend/app/models/pagamentos.py` (LancamentoExtrato), `backend/app/schemas/pagamentos.py` (ImportarExtratoIn.formato; ImportarExtratoOut/relato)
- Test: `backend/tests/test_pagamentos_c2_extrato.py` (novo) + fixtures `backend/tests/fixtures/extrato_exemplo.ofx` (SGML 1.x) e `extrato_exemplo_xml.ofx` (2.x XML)

**Interfaces:**
- Contrato interno do parser (consumido também pela Task 2):

```python
@dataclass
class LancamentoParseado:
    data: date
    historico: str          # truncado a 255
    documento: str | None
    favorecido: str | None
    valor: Decimal          # sempre positivo; sinal vira `tipo`
    tipo: str               # "CREDITO" | "DEBITO"
    id_externo: str | None  # FITID no OFX; None quando o formato não dá id

def parse_ofx(conteudo: str) -> list[LancamentoParseado]: ...
```

- `parse_ofx` aceita OFX 1.x SGML (tags sem fechamento, cabeçalho `OFXHEADER:100`) E 2.x XML — detecta pelo cabeçalho. Campos de `<STMTTRN>`: `DTPOSTED`→data, `TRNAMT`→valor/tipo (negativo=DEBITO), `MEMO`/`NAME`→historico/favorecido, `CHECKNUM`/`REFNUM`→documento, `FITID`→id_externo. Sem lib externa (SGML do OFX 1.x quebra parsers XML; um scanner de tags próprio de ~80 linhas é mais robusto e sem dependência nova).
- Migration 0099: `ADD COLUMN id_externo varchar(64) NULL` e `ADD COLUMN id_conta integer NULL REFERENCES pagamentos.conta_bancaria(id)` em `pagamentos.lancamento_extrato`; backfill `id_conta` a partir do extrato (`UPDATE ... SET id_conta = e.id_conta FROM pagamentos.extrato e WHERE ...`); `ALTER COLUMN id_conta SET NOT NULL`; índice único parcial `uq_lancamento_extrato_id_externo (tenant_id, id_conta, id_externo) WHERE id_externo IS NOT NULL` (FITID é único POR CONTA — sem `id_conta` na chave, duas contas com o mesmo FITID colidiriam). ADD COLUMN herda RLS/grants — não repetir. Downgrade dropa índice e colunas.
- `importar_extrato`: `formato` passa a aceitar `"CSV" | "OFX"` (CNAB240 na Task 2); dispatch para o parser; o hash de arquivo por `(conta, hash)` → 409 CONTINUA (contrato da C1); **dedupe por lançamento**: linha cujo `(id_conta, id_externo)` já existe é PULADA e contada; linhas sem `id_externo` seguem o comportamento atual (só o hash do arquivo protege — pagamentos iguais no mesmo dia são legítimos, pular por `(data, valor)` esconderia lançamento real; o relato avisa "possíveis duplicatas" quando `(data, valor, tipo)` coincide com lançamento existente da conta, SEM pular).
- Resposta do import ganha o relato: `{total_no_arquivo, importados, ignorados_por_id_externo, possiveis_duplicatas, extrato: ExtratoOut}` — schema `ImportarExtratoResultadoOut`. A rota existente de import (localizar em `routers/pagamentos_conciliacao.py`) passa a devolvê-lo; o front atual só usa campos do extrato → conferir a tela e ajustar o tipo em `api.ts` NO MESMO commit (regra do response_model × api.ts).

- [ ] **Step 1: testes RED** — (a) `parse_ofx` SGML: fixture com 3 lançamentos (crédito, débito, com FITID) → lista correta; (b) `parse_ofx` XML idem; (c) OFX malformado → erro claro 422; (d) importar OFX cria extrato + lançamentos com `id_externo`; (e) importar SEGUNDO arquivo OFX que sobrepõe período (2 FITIDs repetidos + 1 novo) → só o novo entra, relato conta os ignorados; (f) inversão: mesmo FITID em CONTAS diferentes → ambos entram; (g) CSV continua funcionando (regressão, `id_externo=None`); (h) migration: backfill de `id_conta` confere com o extrato.
- [ ] **Step 2: migration 0099 + modelo + parser + dispatch + relato.** upgrade/downgrade provados.
- [ ] **Step 3: verde + regressão** — Step 1 PASSA; `pytest tests/ -k "pagamentos" -q` verde; guardas + RLS.
- [ ] **Step 4: commit** — `feat(pagamentos): importador OFX com dedupe por id_externo (C2.2)`.

---

### Task 2: C2.2 — parser CNAB240 de extrato

**Files:**
- Modify: `backend/app/services/pagamentos_extrato_parsers.py` (`parse_cnab240`), `backend/app/services/pagamentos_conciliacao.py` (aceitar `"CNAB240"`)
- Test: `backend/tests/test_pagamentos_c2_extrato.py` (seção CNAB) + fixture `backend/tests/fixtures/extrato_exemplo.cnab240.txt`

**Interfaces:**
- `parse_cnab240(conteudo: str) -> list[LancamentoParseado]` — layout FEBRABAN de extrato (registro tipo 3, segmento E): posições fixas de 240 chars; data (posições do campo data de lançamento), valor + sinal D/C → tipo, histórico, nº documento → `documento` e `id_externo` (quando vazio, `id_externo=None`). Linhas de header/trailer (tipos 0,1,5,9) são puladas; linha com tamanho ≠ 240 → 422 com o nº da linha.
- Fixture construída à mão no layout FEBRABAN com 3 lançamentos (documentada campo a campo em comentário no teste — é a "spec executável" do layout até chegar arquivo real do banco do piloto; o desvio por banco é adaptação futura registrada na spec).

- [ ] **Step 1: testes RED** — (a) fixture parseia 3 lançamentos com data/valor/tipo/documento certos; (b) linha de 239 chars → 422 citando a linha; (c) import CNAB240 fim-a-fim cria extrato + lançamentos; (d) reimport do mesmo arquivo → 409 do hash (regressão do contrato).
- [ ] **Step 2: implementar parser + dispatch.**
- [ ] **Step 3: verde + guardas.**
- [ ] **Step 4: commit** — `feat(pagamentos): parser CNAB240 de extrato (C2.2)`.

---

### Task 3: C2.2 — upload de arquivo na tela + relato do import

**Files:**
- Modify: `frontend/lib/api.ts` (tipo `ImportarExtratoResultadoOut` + método), tela de conciliação/extrato (localizar em `frontend/app/(app)/m/pagamentos/` — grep por "extrato"/"conciliacao"; o import hoje é textarea/CSV — conferir)
- Test: `frontend/__tests__/` teste do componente de import (padrão dos vizinhos)

**Interfaces:** seletor de formato (CSV/OFX/CNAB240) + upload de arquivo (leitura como texto no browser, `FileReader`; o payload continua `conteudo: string` — sem multipart); após importar, painel de relato: importados / ignorados por id externo / possíveis duplicatas (com aviso explicando) / link para o extrato.

- [ ] **Step 1: teste RED do componente** (mock fetch): seleciona OFX, envia, exibe o relato com os 3 contadores. FALHA → implementar → PASSA.
- [ ] **Step 2: costura + `npx tsc --noEmit` + `npx vitest run` completos.**
- [ ] **Step 3: commit** — `feat(pagamentos): upload OFX/CNAB240 com relato de import na tela (C2.2)`.

---

### Task 4: C2.1 — eventos contábeis + lotes imutáveis (migration 0100)

**Files:**
- Create: `backend/app/services/pagamentos_contabil.py`, `backend/alembic/versions/0100_export_contabil.py`
- Modify: `backend/app/models/pagamentos.py` (2 modelos novos), `backend/app/schemas/pagamentos.py`, `backend/app/routers/pagamentos_caixa.py` OU router novo `pagamentos_contabil.py` (+ `main.py` prefix `/api/v2`)
- Test: `backend/tests/test_pagamentos_c2_contabil.py`

**Interfaces:**
- Migration 0100, duas tabelas com boilerplate RLS completo:
  - `pagamentos.export_contabil_lote` (id, tenant_id, numero int NOT NULL — sequencial POR tenant, unique parcial `(tenant_id, numero)`, periodo_inicio/fim date, formato_versao varchar(20) default 'neutro-csv-v1', qtd_eventos int, hash_conteudo varchar(64), id_usuario FK, gerado_em, excluido bool default false);
  - `pagamentos.export_contabil_evento` (id, tenant_id, id_lote FK, tipo_evento varchar(30) CHECK nos 5 tipos, id_origem int NOT NULL, ocorrido_em timestamp, **unique `(tenant_id, tipo_evento, id_origem)`** — o "evento pertence a exatamente um lote").
- `services/pagamentos_contabil.py`:
  - `coletar_eventos_pendentes(db, *, tenant_id, ate: date) -> list[EventoContabil]` — varre o domínio: `debito_empenhado` (débito não excluído com `numero_empenho` preenchido; `ocorrido_em` = quando o empenho entrou — usar o campo real do débito/histórico, conferir no modelo), `liquidacao` (débitos liquidados — campo/histórico real da RF-VAL-02), `pagamento` (ordens executadas + `excecao_saldo`/justificativa RN-15), `estorno_parcela`, `cancelamento_debito` (via `DebitoHistorico`/status — conferir como `cancelar` registra). Exclui os já presentes em `export_contabil_evento`. `id_evento` público = `f"{tipo_evento}:{id_origem}"` (estável, derivado — nunca sequência própria).
  - `gerar_lote(db, *, tenant_id, ate, usuario_id) -> ExportContabilLote` — coleta, grava lote+eventos, calcula hash do CSV; **sem evento pendente → 409 "nada a exportar"**.
  - `reconstruir_csv(db, *, tenant_id, lote_id) -> bytes` — regera dos dados; assert do hash contra o gravado (divergência → 500 com log, é corrupção).
  - `ContabilAdapter` protocolo + `AdapterNeutroCSV` registrado em `ADAPTERS = {"neutro-csv-v1": ...}`. Colunas do CSV: `id_evento;tipo_evento;id_debito;ocorrido_em;lote;numero_empenho;fonte;credor_doc;credor_nome;valor;vencimento;data_liquidacao;numero_ordem;conta;data_pagamento;valor_pago;excecao_saldo;justificativa;motivo` (vazias quando não se aplicam ao tipo; separador `;`, encoding utf-8-sig — padrão dos exports da C1.3, conferir `pagamentos_export.py` e seguir IGUAL).
- Rotas (mesmo gate dos endpoints de caixa/export vizinhos): `POST /pagamentos/contabil/lotes` (gera; body `{ate}`), `GET /pagamentos/contabil/lotes` (lista), `GET /pagamentos/contabil/lotes/{id}/arquivo` (download CSV; reemissão = mesmo lote).

- [ ] **Step 1: testes RED** — (a) domínio com 1 débito empenhado+liquidado+pago → lote com 3 eventos, CSV com 3 linhas e hash estável; (b) **imutabilidade**: gerar de novo sem evento novo → 409; download do lote 1 devolve o MESMO conteúdo (hash); (c) **complemento**: novo pagamento após o lote 1 → lote 2 só com o evento novo; (d) inversão da unicidade: inserir o mesmo `(tipo_evento, id_origem)` em dois lotes → IntegrityError; (e) estorno e cancelamento aparecem com os tipos certos; (f) RN-15: pagamento com exceção traz justificativa no CSV; (g) HTTP usuário comum com permissão gera e baixa; (h) cross-tenant 404.
- [ ] **Step 2: migration + services + rotas.** upgrade/downgrade provados.
- [ ] **Step 3: verde + `pytest tests/ -k pagamentos -q` + guardas + RLS.**
- [ ] **Step 4: commit** — `feat(pagamentos): export contabil neutro com lotes imutaveis (C2.1)`.

---

### Task 5: C2.1 — botão de lote na tela

**Files:** `frontend/lib/api.ts` + tela de pagamentos onde vivem os exports da C1.3 (localizar o padrão de botão de export; grep por "export" em `frontend/app/(app)/m/pagamentos/`); teste vitest.

- [ ] **Step 1: teste RED** — lista de lotes renderiza; botão "Gerar lote" chama o POST; download aponta para a rota do arquivo. → implementar → PASSA.
- [ ] **Step 2: `tsc` + vitest completos; commit** — `feat(pagamentos): tela de lotes do export contabil (C2.1)`.

---

### Task 6: C2.3 — realm M2M: sistema integrado + API key (migration 0101)

**Files:**
- Create: `backend/app/auth/sistema_integrado.py`, `backend/alembic/versions/0101_sistema_integrado_idempotencia.py`
- Modify: `backend/app/models/pagamentos.py`, `backend/app/schemas/pagamentos.py`, router de cadastros de pagamentos (gestão de chaves), `backend/app/observability/logging.py` (redação de `X-Api-Key` — conferir como Authorization é redigido e fazer IGUAL)
- Test: `backend/tests/test_pagamentos_c2_api.py` (novo)

**Interfaces:**
- Migration 0101, duas tabelas com boilerplate RLS completo:
  - `pagamentos.sistema_integrado` (id, tenant_id, nome varchar(120), prefixo varchar(12) — público, ex. `apy_ab12cd34`, unique global, hash_chave varchar(100) — bcrypt, escopo_leitura bool, escopo_escrita bool, ativo bool default true, criado_em, revogado_em nullable, id_usuario_criador FK);
  - `pagamentos.idempotencia` (id, tenant_id, id_sistema FK, chave varchar(64), hash_payload varchar(64), status_code int, corpo_resposta JSONB, criado_em; **unique `(tenant_id, id_sistema, chave)`**).
- `auth/sistema_integrado.py`: `get_current_sistema_integrado` (header `X-Api-Key` = `<prefixo>.<segredo>`): busca por prefixo, `bcrypt.checkpw` do segredo, exige ativo e não revogado → objeto com tenant_id/escopos; 401 sem/inválida/revogada. Helpers `require_escopo_leitura`/`require_escopo_escrita` (403). Usa o MESMO custo de bcrypt de `auth/password.py`.
- Gestão (realm admin, permissão dos cadastros de pagamentos): `POST /pagamentos/sistemas-integrados` (gera prefixo+segredo, devolve a chave completa UMA vez), `GET` lista (sem segredo), `POST /{id}/revogar`.

- [ ] **Step 1: testes RED** — (a) criar sistema devolve chave `apy_….…` e a lista não expõe segredo; (b) chave válida resolve tenant/escopos; (c) inválida/revogada → 401; (d) chave do tenant A não enxerga dados do tenant B (par de tenants); (e) log de request com `X-Api-Key` não contém o segredo (teste sobre o formatter, molde do que já cobre Authorization — se não houver, criar).
- [ ] **Step 2: migration + realm + gestão.** upgrade/downgrade provados.
- [ ] **Step 3: verde + guardas + RLS.**
- [ ] **Step 4: commit** — `feat(pagamentos): realm de sistema integrado com API key (C2.3)`.

---

### Task 7: C2.3 — escrita idempotente + leitura por cursor

**Files:**
- Create: `backend/app/routers/pagamentos_integracao.py` (+ `main.py`, prefix `/api/v2`)
- Create: `backend/app/services/pagamentos_idempotencia.py`
- Modify: `nginx/default.conf` (rate limit básico no prefixo `/api/v2/integracao/` — `limit_req_zone` + `limit_req`; NÃO mexer na regex de páginas)
- Test: `backend/tests/test_pagamentos_c2_api.py` (seções escrita/leitura)

**Interfaces:**
- `pagamentos_idempotencia.executar_idempotente(db, *, sistema, chave, payload_hash, executor) -> (status_code, corpo)`: busca `(tenant, sistema, chave)`; hit com mesmo hash → resposta gravada; hit com hash diferente → 409; miss → executa `executor()` (que chama o service real), grava resposta, devolve. Corrida da mesma chave: INSERT antecipado da linha (status NULL) protegido pelo unique — o perdedor do INSERT relê e devolve a gravada (ou 409 `em processamento` se ainda NULL; documentar).
- Rotas M2M (todas com `Depends(get_current_sistema_integrado)` + gate de módulo `pagamentos` do tenant; NUNCA `require_permission` de usuário):
  - `POST /integracao/pagamentos/debitos` (escopo escrita; header `Idempotency-Key` obrigatório → 422 sem ele; payload = subconjunto documentado do `DebitoCreate` existente; reusa `pagamentos_debitos` service — RN-01/02/06 intactas);
  - `POST /integracao/pagamentos/debitos/{id}/liquidar` (idem, reusa o service de liquidação);
  - `GET /integracao/pagamentos/debitos|ordens|baixas` (escopo leitura; `?cursor=<id>&limite<=200&alterado_desde=`; resposta `{items, proximo_cursor}`; ordenação id ASC; baixas = `MovimentacaoConta` de pagamento — conferir o modelo; débitos/ordens com `id_evento` correspondente quando exportados).
- **Rota literal antes de paramétrica** no router novo (a guarda pega).

- [ ] **Step 1: testes RED** — (a) POST débito com chave X cria; repetir chave X + mesmo payload → MESMA resposta, sem segundo débito (inversão: contar débitos); (b) chave X + payload diferente → 409; (c) sem `Idempotency-Key` → 422; (d) escopo leitura tentando POST → 403; (e) GET débitos paginado por cursor cobre a lista inteira sem repetir nem pular (criar 5, varrer com limite 2); (f) `alterado_desde` filtra; (g) RN-01 pela porta M2M: liquidar sem empenho → mesmo erro do realm admin (a prova de que não há caminho paralelo); (h) cross-tenant 404 com chave do outro tenant.
- [ ] **Step 2: implementar + nginx.** Conferir nginx com `docker compose exec nginx nginx -t` (ou reload do container local).
- [ ] **Step 3: verde + `pytest tests/ -k pagamentos -q` + guardas.**
- [ ] **Step 4: commit** — `feat(pagamentos): API M2M com escrita idempotente e leitura por cursor (C2.3)`.

---

### Task 8: C2.3 — tela de gestão de chaves + docs de integração

**Files:** `frontend/lib/api.ts` + tela nova de gestão em pagamentos (seção nos cadastros — seguir CrudPage/padrão vizinho; card/entrada de menu se necessário conforme guardas de menu); `docs/INTEGRACAO-PAGAMENTOS.md` (contrato da API M2M: auth, idempotência, cursores, exemplos curl; e o dicionário do CSV `neutro-csv-v1`); teste vitest.

- [ ] **Step 1: teste RED da tela** (criar chave mostra o segredo UMA vez com aviso; lista mostra prefixo/escopos/estado; revogar pede confirmação). → implementar → PASSA. Guardas de menu/página órfã verdes (`npx vitest run` completo).
- [ ] **Step 2: escrever `docs/INTEGRACAO-PAGAMENTOS.md`** (o contrato público — é o artefato que a prefeitura entrega ao sistema integrado).
- [ ] **Step 3: `tsc` + vitest; commit** — `feat(pagamentos): gestao de chaves M2M + contrato de integracao (C2.3)`.

---

### Task 9: Fechamento — backlog + suítes completas

**Files:** `docs/BACKLOG-PENDENCIAS.md` (§2.1: C2 entregue, bloco datado com o que entrou, decisões — formato neutro por falta de spec externa, XLSX continua fora, API bancária/CNAB remessa continuam 3ª etapa — e pendências novas que as tasks registrarem).

- [ ] **Step 1: atualizar backlog.**
- [ ] **Step 2: suíte backend completa SOLO (`pytest -q`) + `npx vitest run` + `npx tsc --noEmit`.**
- [ ] **Step 3: commit** — `docs(pagamentos): fecha C2 no backlog (integracoes)`.
