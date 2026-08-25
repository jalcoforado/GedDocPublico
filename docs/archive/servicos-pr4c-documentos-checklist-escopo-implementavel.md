# PR 4c — Escopo Implementável: Checklist documental e vínculo anexo↔documento exigido

**Autor:** Jorge + assistente · **Status:** ESCOPO FECHADO (aguardando autorização para implementar)

> Consolida a [proposta](servicos-pr4c-documentos-complementacao-escopo.md) com as
> **4 decisões (D-FASE / D-KEY / D-STATUS / D-AUDIT)** fechadas. Entrega **só** o
> checklist + vínculo + status + cards de leitura. **Complementação formal** (PR 4d)
> fica para depois. **Nada será alterado em código até autorização explícita.**

---

## 1. Objetivo

Tornar `servico.documentos_exigidos` (PR 4a) um **checklist operacional**: o
cidadão vê o que falta enviar (com obrigatórios/opcionais), anexa documentos
**vinculados** ao item exigido, e ambos os lados (cidadão e servidor) leem o
**status documental calculado**. Sem GED, OCR, validação automática,
versionamento ou workflow.

**Decisões fechadas:** D-FASE faseamento (4c = checklist + vínculo; 4d =
complementação formal) · D-KEY `anexo.documento_exigido_key` nullable + `key`
estável em cada item de `documentos_exigidos` · D-STATUS calculado, sem tabela
(`sem_documentos_exigidos | pendente | parcial | completo`) · D-AUDIT evento
minimizado `anexo.enviado_cidadao`.

## 2. Migration `0026_anexo_documento_exigido_key`

**Duas mudanças em um único upgrade transacional (compatível com banco antigo):**

1. **Coluna:** `ALTER TABLE protocolos.anexo ADD COLUMN documento_exigido_key varchar(120) NULL`.
   - `anexo` já tem RLS e GRANTs por schema — a coluna nova herda; sem nova policy.
   - Compatível com anexos antigos: ficam `NULL` (= anexo geral, não vinculado).
2. **Backfill estável** de `protocolos.servico.documentos_exigidos`:
   - Para cada `servico` com `documentos_exigidos IS NOT NULL`, percorrer os itens
     em Python (via `op.get_bind()`) e, **se o item não tiver `key`**, gerar
     `key = slugify(nome)` e gravar o JSONB atualizado. Itens **com** key existente
     são preservados (estabilidade D-KEY).
   - Idempotente: re-rodar não muda nada (toda key vira não-nula no primeiro upgrade).
   - `slugify` (mesma função do backend, §4) — determinístico, ≤120 chars, ASCII.

`downgrade`: `DROP COLUMN documento_exigido_key`. (O backfill não é desfeito —
itens passam a ter `key` para sempre; sem impacto pois fica como dado adicional.)

**CI:** `stamp 0020 → upgrade head` roda a 0026 em banco limpo (sem servicos
existentes, backfill é no-op). Validar round-trip antes do commit.

## 3. Schemas

- **`ServicoDocumento`** (em [`schemas/servico.py`](../backend/app/schemas/servico.py))
  ganha `key: str | None` (input opcional — backend preenche se ausente; **output
  sempre preenchido** depois da 0026/normalização ao salvar):
  ```py
  class ServicoDocumento(BaseModel):
      key: str | None = Field(default=None, max_length=120)
      nome: str = Field(min_length=1, max_length=150)
      obrigatorio: bool = False
      descricao: str | None = Field(default=None, max_length=500)
  ```
- **Novos** schemas em `schemas/checklist_documentos.py`:
  ```py
  ChecklistItem { key, nome, obrigatorio, descricao, enviado: bool,
                  anexos: list[ChecklistAnexo] }
  ChecklistAnexo { id_anexo: int, descricao: str | None }
  ChecklistDocumentosResponse { id_processo, id_servico: int | None,
                                status_documental, itens: list[ChecklistItem],
                                obrigatorios_total, obrigatorios_enviados }
  ```

## 4. Serviço de domínio

### 4.1 `slugify` estável (em `services/text.py` *(novo, util pequeno)* ou inline em servico)
Determinístico: lower → NFD strip diacritics → `[^a-z0-9]+` → `-` → trim → `[:120]`.
Idêntico ao slug de URL: `"Documento de identificação"` → `"documento-de-identificacao"`.

### 4.2 Normalização ao salvar — `services/servico.py`
Em `criar_servico` e `atualizar_servico`, antes de persistir `documentos_exigidos`:
- Para cada item: se `item["key"]` ausente/vazio → `item["key"] = slugify(item["nome"])`.
- Conflito (dois itens com mesma `key` derivada) → sufixar `-2`, `-3`… para garantir unicidade dentro do mesmo serviço.
- Itens com `key` informada pelo cliente: preservar (admin pode renomear o `nome`
  sem mudar a `key` — estabilidade D-KEY).

### 4.3 `services/checklist_documentos.py` *(novo)*
- `calcular_checklist(db, processo, *, tenant_id) -> ChecklistDocumentosResponse`:
  - Se `processo.id_servico` é nulo → status `sem_documentos_exigidos`, `itens=[]`.
  - Carrega `Servico` (same-tenant + não excluído); se sem `documentos_exigidos` →
    `sem_documentos_exigidos`.
  - Carrega anexos do processo (`Anexo` join `AnexoProcesso`, ambos não excluídos,
    `anexo.ativo`); agrupa por `documento_exigido_key`.
  - Para cada item: `enviado = len(anexos[item.key]) > 0`; `anexos[]` mapeado.
  - **Status** (D-STATUS):
    - `obrigatorios = [i for i in itens if i.obrigatorio]`
    - sem obrigatórios + sem itens → `sem_documentos_exigidos`
    - sem obrigatórios + itens opcionais → `completo` (não há o que falhar)
    - `pendente` se nenhum obrigatório enviado; `parcial` se parte; `completo` se todos.

### 4.4 `services/anexos.py::upload_anexo` — extensão
- Novo kwarg `documento_exigido_key: str | None = None`.
- Se `documento_exigido_key` é fornecido:
  - `processo.id_servico` deve existir → senão **400** ("este processo não foi
    aberto por serviço; envio geral apenas").
  - Carregar `Servico` same-tenant + `documentos_exigidos`; se vazio → **400**
    ("este serviço não exige documentos específicos").
  - `documento_exigido_key` deve ∈ `{item["key"] for item in documentos_exigidos}` →
    senão **400** ("documento exigido inválido para este serviço").
- Grava em `anexo.documento_exigido_key`. Resto do fluxo inalterado.
- Compatível com upload sem key (anexo geral; `documento_exigido_key=None`).

## 5. Endpoints

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/v2/cidadao/processos/{id}/checklist-documentos` | `get_current_cidadao` + dono (via `_verificar_dono`) | Checklist do **próprio** processo (404 cross-cidadão/cross-tenant) |
| GET | `/api/v2/processos/{id}/checklist-documentos` | `require_permission("processo")` + tenant | Checklist (servidor); 404 fora do tenant |
| POST | `/api/v2/cidadao/processos/{id}/anexos` | cidadão (dono) — **estendido** | Form opcional `documento_exigido_key`; validação §4.4 |

(Sem novos endpoints de complementação — fica para o **PR 4d**.)

## 6. Auditoria (D-AUDIT)

No upload do cidadão (após `upload_anexo`), na **mesma transação**:
```py
await audit_log(db, tenant_id=tenant_id, id_usuario=None,
    acao="anexo.enviado_cidadao", entidade="anexo", id_entidade=anexo.id,
    payload={"id_processo": processo_id,
             "documento_exigido_key": documento_exigido_key,  # str | None
             "canal": "portal"})
```
**Nada de** CPF, nome, nome original do arquivo, conteúdo, corpo, dados pessoais.
Hoje o upload do cidadão **não** audita — entra nessa PR.

## 7. Frontend cidadão

- `lib/api.ts`:
  - `api.cidadao.checklistDocumentos(id) → ChecklistDocumentosResponse`.
  - `api.cidadao.uploadAnexo(processoId, file, descricao?, documentoExigidoKey?)`
    (FormData com `documento_exigido_key` opcional).
  - Tipos: `ChecklistItem`, `ChecklistAnexo`, `ChecklistDocumentosResponse`,
    `StatusDocumental`.
- **`/cidadao/processos/[id]/page.tsx`** — adicionar **card "Documentos exigidos"**:
  - badge de status (`pendente`/`parcial`/`completo`/`sem_documentos_exigidos`);
  - lista: nome, obrigatorio? (asterisco vermelho), descricao, indicador
    `enviado/pendente`, anexos enviados por item;
  - botão **"Anexar documento"** abre dialog: file + (se houver itens exigidos)
    select com os itens → envia `documento_exigido_key` selecionado.
  - Upload "geral" (sem key) continua possível como opção "Outro documento".

## 8. Frontend servidor

- `lib/api.ts`: `api.processos.checklistDocumentos(id)`.
- **`/processos/[id]/page.tsx`** (interno) — **card read-only** "Documentos
  exigidos do serviço": badge de status + lista por item (enviado/pendente) +
  links para os anexos correspondentes. **Sem** botão "Solicitar complementação"
  (→ PR 4d). Não redesenha a tela.

## 9. Segurança e LGPD

- Cidadão **só** vê e anexa no próprio processo (`_verificar_dono`); servidor via
  `require_permission("processo")` + tenant.
- Tenant pelo Host; **sem cross-tenant** (checklist filtra por `tenant_id`; 404 fora).
- Não expor documentos/dados de **outros** cidadãos.
- Não permitir anexar em processo **de outro cidadão** (404 do `_verificar_dono`);
  respeitar imutabilidade de anexo assinado (`anexo_esta_assinado` — uploads sempre
  criam anexo novo, nunca sobrescrevem).
- Regras de tamanho/extensão de `upload_anexo` mantidas.
- **Auditoria minimizada** (§6) — sem dados sensíveis.

## 10. Testes obrigatórios

**Backend (pytest):**
- checklist gerado a partir de `documentos_exigidos` do serviço.
- processo **sem `id_servico`** → status `sem_documentos_exigidos` (não quebra).
- serviço sem `documentos_exigidos` → `sem_documentos_exigidos`.
- cidadão só acessa o **próprio** processo; **outro cidadão → 404**.
- servidor sem permissão `processo` → **403**.
- upload com `documento_exigido_key` **válida** → anexo associado, `enviado=true`
  no checklist; key persiste em `anexo.documento_exigido_key`.
- upload com **key inválida** → **400**.
- upload com key num processo **sem `id_servico`** ou **serviço sem documentos** → **400**.
- anexo antigo com `key=NULL` continua funcionando (lista do processo, leitura).
- status: `pendente` (nenhum obrigatório enviado), `parcial` (parte), `completo`
  (todos obrigatórios). Opcionais não afetam `completo`.
- **cross-tenant** bloqueado (checklist e upload, ambos os lados).
- auditoria `anexo.enviado_cidadao` registrada com payload mínimo — **sem** CPF,
  nome, nome de arquivo, conteúdo.
- normalização de `documentos_exigidos` ao salvar serviço: items sem `key` recebem
  slug do `nome`; items com `key` preservam; conflito → sufixo `-2`.
- migration 0026: aplica em banco limpo; backfill idempotente; round-trip.

**Frontend (vitest):**
- cidadão: card mostra obrigatórios/opcionais/pendentes; upload vinculado envia
  `documento_exigido_key`; status reflete o backend; processo sem documentos
  exigidos mostra estado adequado.
- servidor: card **read-only** lista pendentes e enviados; sem botão de
  complementação.

## 11. Fora de escopo (PR 4d ou futuro)

complementação formal · status `em_complementacao` · notificação ao cidadão ·
prazo de complementação · validação automática · OCR · upload obrigatório
bloqueante (não permitir abrir solicitação sem docs) · GED · versionamento ·
assinatura de anexo do cidadão · workflow · SLA · dashboard por serviço · gov.br ·
WhatsApp · IA.

## 12. Critérios de aceite

- Migration 0026 aplicada/testada; backfill estável; anexos antigos intactos.
- `ServicoDocumento.key` estável (não muda quando `nome` muda em update do serviço).
- Endpoints de checklist (cidadão e servidor) corretos; cross-tenant e cross-cidadão bloqueados.
- Upload do cidadão aceita key opcional; validação 400 nos casos previstos; sem
  key continua funcionando.
- Status documental correto nos 4 estados.
- Auditoria minimizada do upload do cidadão registrada.
- Cards (cidadão com upload vinculado; servidor read-only) integrados sem
  redesenho.
- Testes back+front passando; sem regressão.
- Itens fora de escopo **não** implementados.
- Relatório final: arquivos, testes, riscos, gancho para o **PR 4d**
  (complementação formal) e dashboard por serviço.

## 13. Dívida técnica / notas

- Após o backfill 0026, todo `ServicoDocumento` persistido tem `key`. UI do
  catálogo (admin) **não precisa** expor o campo `key` no editor — backend gera.
- `slugify` é simples por design (ASCII, hífen). Se aparecer caso patológico de
  colisão fora do mesmo serviço, ainda assim cada serviço tem seu próprio
  namespace de keys (validamos por serviço).
- "Sobrescrever anexo assinado" segue protegido pela regra existente; o PR 4c
  apenas **vincula** novos uploads — não altera anexos pré-existentes.
- "Solicitar complementação" e status `em_complementacao` ficam para o **PR 4d**.
