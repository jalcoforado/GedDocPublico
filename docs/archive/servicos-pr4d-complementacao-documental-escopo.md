# PR 4d — Escopo técnico: Complementação documental formal

**Autor:** Jorge + assistente · **Status:** PROPOSTA (aguardando autorização — nada implementado)

> Fecha o ciclo dos PRs 4a/4b/4c: o **servidor solicita complementação documental
> formalmente** ao cidadão (com mensagem + lista de docs solicitados), e o
> **cidadão responde pelo portal** anexando docs vinculados (reusa PR 4c) e
> clicando em **"Responder complementação"**. **Sem** workflow avançado,
> notificação externa, OCR, IA, GED, prazo, indeferimento, SLA. Gerar primeiro
> este doc; **não implementar**.

---

## 1. Objetivo

Dar ao servidor um botão "Solicitar complementação" no detalhe do processo e ao
cidadão um botão "Responder complementação" no portal, com histórico próprio,
auditoria minimizada e respeitando tudo que já existe (tenant pelo Host, sigilo,
permissão, RLS, dono do processo para cidadão).

## 2. Achados no código (o que será reusado, não recriado)

| Necessidade | Já existe | Decisão |
|---|---|---|
| Documentos exigidos do serviço (com `key` estável) | `protocolos.servico.documentos_exigidos` JSONB (PR 4a + 4c) | **Fonte** das keys solicitáveis |
| Vínculo anexo↔documento exigido | `protocolos.anexo.documento_exigido_key` (PR 4c) | **Fonte** para mostrar quais foram anexados |
| Checklist calculado | [`services/checklist_documentos.py`](../backend/app/services/checklist_documentos.py) `calcular_checklist` | **Estender** com `complementacao_aberta` |
| Dono do processo (cidadão) | [`routers/cidadao.py`](../backend/app/routers/cidadao.py) `_verificar_dono` | **Reusar** |
| Gate servidor (tenant + sigilo + acesso) | [`routers/processos.py`](../backend/app/routers/processos.py) `require_acesso_processo` | **Reusar** |
| Permissão de mutação no processo | `require_permission("processo", "atualizar")` | **Reusar** em solicitar/cancelar |
| Upload do cidadão com `documento_exigido_key` | [`services/anexos.py`](../backend/app/services/anexos.py) (PR 4c) | **Reusar** — não muda nada no upload |
| Auditoria minimizada | [`services/audit.py`](../backend/app/services/audit.py) `log` | Novos eventos: `complementacao.{solicitada,respondida,cancelada}` |

Última migration commitada = `0026` → **nova = `0027`**. Sem mudanças em
`anexo`/`servico`/`processo` (toda a nova superfície está na tabela nova).

## 3. Decisões a fechar (recomendações)

### D-MODELO — tabela própria (RECOMENDADO)

Criar `protocolos.complementacao_documental` (uma linha por solicitação).

**Justificativa:** preserva histórico de múltiplas complementações por processo
(brief item 1: "Evitar salvar complementação apenas em campos soltos do processo,
porque isso perde histórico e dificulta auditoria"); isola o texto da mensagem
do servidor numa tabela com RLS própria; permite auditar abertura/cancelamento/
resposta de forma rastreável; não polui `processo` com máquina de estado nova.

### D-STATUS — status separados (RECOMENDADO)

- `StatusDocumental` (PR 4c) permanece intacto: `sem_documentos_exigidos |
  pendente | parcial | completo`.
- Novo enum próprio da entidade: `StatusComplementacao = aberta | respondida |
  cancelada`.
- **Não** adicionar `complementacao_status` em `processo`. "Processo está em
  complementação" = `EXISTS complementacao WHERE id_processo = ? AND status =
  'aberta'`. O checklist do PR 4c **passa a expor** um bloco paralelo
  `complementacao_aberta: ComplementacaoOut | null` no response, para a UI
  destacar.

**Justificativa:** brief item 2 — "Não poluir excessivamente o status documental
se for mais limpo manter status documental e status de complementação separados."
Status documental é "qualidade do checklist em si"; complementação é "fluxo
formal sobre o checklist". Separar evita acoplamento (ex.: um processo
**completo** pode ter complementação aberta se servidor pediu doc adicional
fora da lista padrão; um processo **pendente** sem complementação não bloqueia
nada). Cada status responde a uma pergunta diferente.

### D-RESPOSTA — botão explícito "Responder complementação" (RECOMENDADO)

- Resposta = **ação explícita do cidadão** via `POST .../responder`, **não
  automática**.
- **Não exige** que todos os documentos solicitados estejam anexados (brief item
  4: "não exigir que todos os documentos estejam anexados para permitir
  responder, salvo se for muito simples e claramente desejado"; "evitar bloquear
  o cidadão por regra complexa neste PR").
- Cidadão é quem decide quando "fechou" a resposta — pode anexar parte hoje e
  responder, ou anexar tudo de uma vez. O servidor reabre nova complementação
  se precisar de mais.
- O endpoint apenas muda o status para `respondida` e seta `respondido_em`.
  Não recebe body de mensagem do cidadão neste PR.

**Justificativa:** maior controle do usuário, menos surpresa, sem regra
escondida de "fechar sozinho". Alinhado com o brief.

### D-CANCELAR — endpoint dedicado

- Servidor pode cancelar complementação `aberta` com motivo **opcional**.
- Não exclui linha; status final `cancelada`, com `cancelado_em` e
  `motivo_cancelamento`.
- `respondida` e `cancelada` são finais (sem reabertura neste PR).

### D-CONCORRENCIA — no máximo 1 aberta por processo (RECOMENDADO)

- Antes de inserir, conferir se já existe `aberta` no mesmo `id_processo`;
  se sim, **409 Conflict**.
- Brief item 3: "não permitir múltiplas complementações abertas simultâneas para
  o mesmo processo, salvo justificativa técnica forte". Não vejo justificativa
  forte — manter restrição simples.
- Index parcial `WHERE status = 'aberta'` ajuda a query e a futuro
  constraint `UNIQUE` se quisermos depois.

### D-PERMISSAO

- **Servidor** solicita/cancela: `require_acesso_processo` (tenant + sigilo +
  permissão de leitura) + `require_permission("processo", "atualizar")`.
- **Servidor** lê histórico: `require_acesso_processo` (mesmo gate do detalhe).
- **Cidadão** lê / responde: `_verificar_dono` (mesmo padrão do PR 4c).

### D-AUDIT — minimizado

| Evento | Quando | Payload permitido |
|---|---|---|
| `complementacao.solicitada` | servidor cria | `{id_processo, id_complementacao, documentos_solicitados_keys: [str], canal: "interno", id_usuario_responsavel}` |
| `complementacao.respondida` | cidadão clica responder | `{id_processo, id_complementacao, canal: "portal"}` |
| `complementacao.cancelada` | servidor cancela | `{id_processo, id_complementacao, canal: "interno", id_usuario_responsavel}` |

Nunca registrar: CPF, nome do cidadão, **conteúdo da mensagem do servidor**,
motivo de cancelamento (texto), nome original de arquivo, conteúdo de
documentos.

**Mensagem do servidor:** persistida na tabela `complementacao_documental.mensagem`
(sob RLS); **não** logada no audit. Se no futuro for necessário registrar a
existência sem expor texto, usar hash SHA-256 do conteúdo (não neste PR).

### D-NOTIF — sem motor de notificação (RECOMENDADO)

- **Sem** e-mail, SMS, WhatsApp, push, nem `in_app`. Alinhado ao brief item 6:
  "A complementação deve aparecer no portal do cidadão e no detalhe do processo."
- Cidadão vê a pendência abrindo o processo no portal.
- Servidor vê resposta abrindo o detalhe ou o histórico de complementações.
- Notificação ao cidadão exigiria modelo paralelo para `UsuarioExterno` (motor
  atual referencia `utils.usuario`); **fora deste PR**. Notificação `in_app`
  para servidor é trivial mas não foi pedida — **fora deste PR**, fica como
  hook futuro.

## 4. Migration `0027_complementacao_documental`

Nova tabela em `protocolos`:

```sql
CREATE TABLE protocolos.complementacao_documental (
    id                     SERIAL PRIMARY KEY,
    tenant_id              INTEGER NOT NULL REFERENCES aprimora_py.tenant(id),
    id_processo            INTEGER NOT NULL REFERENCES protocolos.processo(id),
    id_usuario_solicitante INTEGER NOT NULL REFERENCES utils.usuario(id),
    status                 VARCHAR(20) NOT NULL DEFAULT 'aberta',
    mensagem               TEXT NOT NULL,
    documentos_solicitados JSONB NOT NULL,            -- [{"key": "rg"}, {"key": "cpf"}]
    motivo_cancelamento    TEXT NULL,
    criado_em              TIMESTAMP NOT NULL DEFAULT NOW(),  -- = dt_solicitacao
    atualizado_em          TIMESTAMP NULL,
    respondido_em          TIMESTAMP NULL,            -- = dt_resposta
    cancelado_em           TIMESTAMP NULL,            -- = dt_cancelamento
    excluido               BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX ix_complementacao_processo
    ON protocolos.complementacao_documental(id_processo, criado_em DESC);
CREATE INDEX ix_complementacao_status_aberta
    ON protocolos.complementacao_documental(id_processo)
    WHERE status = 'aberta' AND excluido = FALSE;
```

- `criado_em` cumpre o papel de "data de solicitação" (sem duplicar coluna).
- `atualizado_em` é mantido para coerência com o padrão do projeto (servico,
  processo). Setado nas transições.
- RLS habilitada no padrão das demais tabelas de `protocolos` (filtro por
  `tenant_id = current_setting('app.tenant_id')`); GRANTs para `app_user`.
- `downgrade`: drop policy + drop table (downgrade simétrico).

## 5. Estados e transições

```
                 servidor solicita
                       ↓
                   aberta ───── cidadão clica Responder ────→ respondida
                       │
                       └──── servidor cancela ────→ cancelada
```

Invariantes:

- Apenas **1 `aberta`** por `processo` simultaneamente; 409 ao tentar abrir
  outra.
- `respondida` e `cancelada` são finais.
- `documentos_solicitados` deve ser subconjunto **não-vazio** de
  `servico.documentos_exigidos[*].key`. Validado em runtime; 400 em key
  inválida ou processo sem `id_servico` (não há o que solicitar).
- Resposta **não exige** todos os docs anexados (D-RESPOSTA).

## 6. Backend

### 6.1 Modelos / schemas

- `models/complementacao_documental.py::ComplementacaoDocumental` (Mapped, todos
  os campos da §4).
- `schemas/complementacao_documental.py`:
  - `StatusComplementacao = Literal["aberta", "respondida", "cancelada"]`
  - `ComplementacaoSolicitarRequest`: `{ mensagem: str (1..2000), documentos_solicitados: list[str] (1..N) }` — `documentos_solicitados` recebe **keys**.
  - `ComplementacaoCancelarRequest`: `{ motivo: str | None (0..500) }`
  - `ComplementacaoDocSolicitadoOut`: `{ key: str, nome: str, descricao: str | None, enviado: bool }`
  - `ComplementacaoOut`: `{ id, status, mensagem, documentos_solicitados: list[ComplementacaoDocSolicitadoOut], id_usuario_solicitante, nome_solicitante, criado_em, atualizado_em, respondido_em, cancelado_em, motivo_cancelamento }`
  - `ChecklistDocumentosResponse` (PR 4c) **ganha** `complementacao_aberta: ComplementacaoOut | None`.

### 6.2 Serviço `services/complementacao_documental.py`

- `solicitar(db, *, tenant_id, processo_id, usuario_id, mensagem, keys) -> ComplementacaoDocumental`
  - carrega processo (tenant + não excluído) → 404 se ausente;
  - exige `processo.id_servico` → 400 ("processo sem serviço — não há docs exigidos");
  - valida `keys` ⊆ `servico.documentos_exigidos[*].key` → 400 em key inválida;
  - rejeita se já existe `aberta` para o processo → 409;
  - cria linha `status='aberta'`, `documentos_solicitados=[{"key": k} for k in keys]`;
  - `audit_log("complementacao.solicitada", …)`.

- `responder(db, *, tenant_id, processo_id, complementacao_id, cidadao) -> ComplementacaoDocumental`
  - carrega a complementação (tenant + processo) → 404 se ausente;
  - exige status `aberta` → senão **409** ("complementação já respondida/cancelada");
  - seta `status='respondida'`, `respondido_em=now`, `atualizado_em=now`;
  - **não** valida quantidade de anexos (D-RESPOSTA);
  - `audit_log("complementacao.respondida", …)`.

- `cancelar(db, *, tenant_id, processo_id, complementacao_id, motivo, usuario_id) -> ComplementacaoDocumental`
  - exige status `aberta` → senão **409**;
  - seta `status='cancelada'`, `cancelado_em=now`, `atualizado_em=now`,
    `motivo_cancelamento=motivo`;
  - `audit_log("complementacao.cancelada", …)`.

- `listar(db, *, tenant_id, processo_id) -> list[ComplementacaoDocumental]`
  - ordena por `criado_em DESC` (mais recente primeiro). Usado por servidor e
    cidadão (via gate distinto no router).

- `obter_aberta(db, *, tenant_id, processo_id) -> ComplementacaoDocumental | None`
  - consumido pelo checklist (PR 4c) para preencher `complementacao_aberta`.

Quando o serializador monta `documentos_solicitados` no `Out`, ele cruza com os
anexos do processo (mesma lógica do checklist: `documento_exigido_key` corresponde
+ anexo vivo) para preencher `enviado` por item. Isso dá ao servidor visibilidade
de "quanto já chegou" antes da resposta.

### 6.3 Endpoints

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST   | `/api/v2/processos/{processo_id}/complementacoes` | `require_acesso_processo` + `require_permission("processo","atualizar")` | servidor solicita |
| GET    | `/api/v2/processos/{processo_id}/complementacoes` | `require_acesso_processo` | servidor lista histórico (desc por `criado_em`) |
| POST   | `/api/v2/processos/{processo_id}/complementacoes/{id}/cancelar` | `require_acesso_processo` + `require_permission("processo","atualizar")` | servidor cancela aberta |
| GET    | `/api/v2/cidadao/processos/{processo_id}/complementacoes` | cidadão dono | cidadão lista histórico (mesma fonte; serializador idêntico) |
| POST   | `/api/v2/cidadao/processos/{processo_id}/complementacoes/{id}/responder` | cidadão dono | cidadão marca como respondida |

O endpoint de **upload do cidadão** (PR 4c) **não muda** — anexar segue sendo
operação separada, mesmo durante uma complementação aberta. A complementação
aberta apenas dá destaque/contexto aos itens.

## 7. Frontend

### 7.1 Servidor — `/(app)/processos/[id]` aba **Documentos**

Acima do `ChecklistDocumentosCard` (read-only do PR 4c):

- **Bloco "Complementação documental"**:
  - Sem complementação aberta:
    - Botão **"Solicitar complementação"** → `Dialog`:
      - `Textarea` **Mensagem ao cidadão** (1..2000 chars, obrigatório);
      - **Checkboxes** dos itens de `documentos_exigidos` do serviço — pré-marcam
        os itens **não-enviados** do checklist (sugestão), mas o servidor pode
        ajustar; pelo menos 1 selecionado;
      - Botões Cancelar / Enviar solicitação;
    - Sucesso: toast + invalidate `complementacoes` + `checklist`.
  - Complementação aberta presente:
    - Card destacado: mensagem, lista de docs solicitados com badge
      "Enviado/Pendente" (do serializador), data, nome do solicitante;
    - Botão **"Cancelar complementação"** → `Dialog` com `Textarea` motivo
      (opcional).
- **Lista "Histórico"** (compacta) abaixo: linhas de complementações
  respondidas/canceladas com data + quem fez + status. Brief item 3 e 8 pedem
  isso explicitamente.

### 7.2 Cidadão — `/cidadao/processos/[id]`

Acima do `ChecklistDocumentosCard`:

- Se `checklist.complementacao_aberta != null`:
  - **Card destacado** (intent warning), título "**Complementação solicitada**";
  - Mensagem do servidor + nome do solicitante + data;
  - Lista de docs solicitados (`nome` + badge Enviado/Pendente);
  - Botão **"Anexar"** por item pendente → abre o `Dialog` de upload do PR 4c
    (mesma rota; nenhum fluxo paralelo);
  - Botão **"Responder complementação"** (intent primary, atalho no rodapé do
    card) → confirma e dispara `POST .../responder`. Não exige todos
    anexados. Sucesso: card sai de destaque + toast "Complementação enviada".
- Se `complementacao_aberta == null`: bloco não aparece.
- **Lista "Complementações anteriores"** abaixo do checklist (compacta):
  cada linha mostra data + status + mensagem (truncada com expand). Brief
  item 9 pede explicitamente "listar complementações anteriores".

### 7.3 `lib/api.ts`

- `api.processos.solicitarComplementacao(id, { mensagem, documentos_solicitados })`
- `api.processos.listarComplementacoes(id)`
- `api.processos.cancelarComplementacao(id, complementacaoId, { motivo? })`
- `api.cidadao.listarComplementacoes(id)`
- `api.cidadao.responderComplementacao(id, complementacaoId)`
- Tipo `ComplementacaoOut` + extensão de `ChecklistDocumentosResponse`.

## 8. Segurança e LGPD

- **Tenant pelo Host** (middleware atual). Filtro `tenant_id` em toda query.
- **Cidadão só vê/responde processo próprio** (`_verificar_dono`).
- **Servidor só atua em processo que pode acessar** (`require_acesso_processo`
  cobre tenant + sigilo; `require_permission("processo","atualizar")` cobre
  mutação).
- **Cross-tenant 404** (não 403, alinhado com padrão do projeto).
- **Mensagem do servidor** sob RLS, **não** no audit (evita vazamento de
  conteúdo em log).
- **Motivo de cancelamento** sob RLS, **não** no audit.
- **Sem expor** complementação de outro cidadão (filtro por `processo` cujo
  manifestante CPF == cidadão logado).
- Respeitar imutabilidade de assinado (anexos vinculados via PR 4c já herdam).

## 9. Auditoria

Tabela em §3 D-AUDIT. **Nunca**: CPF, nome do cidadão, texto da mensagem do
servidor, texto do motivo, nome original do arquivo, conteúdo do documento.

## 10. Notificação

**Nenhuma neste PR.** Visibilidade exclusiva pelo portal cidadão (card
destacado quando há `aberta`) e pelo detalhe do processo do servidor. Hooks
para notificação futura (in_app servidor, e-mail/WhatsApp cidadão) ficam
mapeados no relatório de PR 4d como gancho.

## 11. Testes obrigatórios

**Backend (pytest):**

- Servidor com `processo:atualizar` solicita complementação válida → 200 +
  linha `aberta` + audit `solicitada` minimizado.
- Servidor solicita com key **inválida** (fora de `documentos_exigidos`) → 400.
- Servidor solicita em processo **sem `id_servico`** → 400.
- Servidor solicita quando já existe outra `aberta` no processo → 409.
- Servidor **sem permissão** (`processo:atualizar`) → 403.
- Servidor **sem acesso** ao processo (sigilo / outro tenant) → 404.
- **Cross-tenant** bloqueado em solicitar/listar/cancelar/responder (404).
- Servidor cancela `aberta` com motivo → 200; cancelar `respondida` → 409;
  cancelar `cancelada` → 409.
- Servidor lista histórico (ordem desc por `criado_em`).
- Cidadão lê `complementacoes` do **próprio** processo; cidadão de **outro**
  processo → 404.
- Cidadão lê `checklist` e vê `complementacao_aberta` preenchida; cidadão de
  outro processo → 404.
- Cidadão **responde** complementação `aberta` → 200 + status `respondida` +
  `respondido_em` setado + audit `respondida` minimizado.
- Cidadão **responde sem anexar todos** os docs solicitados → 200 (resposta
  parcial permitida — D-RESPOSTA).
- Cidadão responde `respondida` ou `cancelada` → 409.
- Cidadão de outro processo tenta responder → 404 (sem vazar existência).
- Após `respondida`: nova solicitação no mesmo processo passa (1 `aberta` por
  vez).
- Checklist `complementacao_aberta` = null após resposta/cancelamento.
- Processo **sem documentos exigidos**: solicitar → 400, checklist segue
  `sem_documentos_exigidos` (não quebra).
- Auditoria `solicitada/respondida/cancelada` **sem** dados sensíveis
  (CPF/nome/mensagem/motivo/arquivo).
- Migration `0027` aplica em banco limpo; round-trip (downgrade dropa policy +
  tabela); reaplicação idempotente.
- **RLS:** sessão com `app.tenant_id` errado **não** lê linhas do tenant
  correto (espelhar testes RLS existentes).

**Frontend (vitest):**

- Servidor: `Dialog` de solicitar valida `mensagem` obrigatória + ≥ 1 doc
  selecionado; chama API com payload correto; pré-marca não-enviados.
- Servidor: card de "Aberta" mostra mensagem + lista de docs com badge
  Enviado/Pendente; botão Cancelar funciona; `Dialog` de motivo respeita
  cancelamento sem motivo.
- Servidor: histórico lista respondidas/canceladas com data e status.
- Servidor sem permissão de `processo:atualizar` **não vê** botões de
  ação (apenas leitura).
- Cidadão: bloco de complementação aparece quando `complementacao_aberta !=
  null`; botão "Anexar" por item pendente abre `Dialog` de upload do PR 4c;
  botão "Responder complementação" chama API e some o destaque.
- Cidadão: lista de complementações anteriores renderiza.
- Cidadão: quando `complementacao_aberta == null`, o bloco não aparece.

**E2E (Playwright — opcional, baixo custo):**

- Servidor solicita → cidadão anexa parte dos docs → cidadão responde →
  servidor abre detalhe e vê `respondida`.

## 12. Fora de escopo

- E-mail · SMS · WhatsApp · push · **in_app**;
- prazo formal de complementação;
- indeferimento automático;
- OCR · IA · validação automática de documentos;
- GED completo · versionamento;
- assinatura de anexos do cidadão;
- workflow avançado · SLA · dashboard por serviço;
- gov.br;
- pagamento/taxa;
- mensagem do cidadão na resposta (corpo de texto);
- reabertura de complementação `respondida/cancelada`;
- motor de notificação para `UsuarioExterno` (cidadão).

## 13. Critérios de aceite

- Migration `0027` (`protocolos.complementacao_documental`) aplicada/testada
  com RLS + GRANTs; round-trip OK.
- Servidor com permissão **abre** complementação válida; chamadas inválidas
  (key fora do serviço, processo sem serviço, já tem aberta, sem permissão,
  sem acesso) retornam 400/403/404/409 conforme regra.
- Servidor **cancela** complementação aberta com motivo opcional;
  cancelar/cancelada já finalizada → 409.
- Servidor lê **histórico** ordenado desc.
- Cidadão dono vê a complementação aberta no checklist (campo `complementacao_aberta`);
  cidadão **não dono** → 404; cross-tenant → 404.
- Cidadão **responde** via botão dedicado mesmo sem ter anexado todos os
  docs; status muda para `respondida`.
- Cidadão lê histórico das próprias complementações.
- Auditoria minimizada nos 3 eventos (sem CPF/nome/mensagem/motivo/arquivo).
- Telas: card servidor (solicitar + ver aberta + cancelar + histórico) e
  bloco cidadão (destaque aberta + anexar via PR 4c + responder + histórico).
- Testes backend + frontend passando; sem regressão (PRs 4a/4b/4c verdes).
- Itens fora de escopo **não** implementados.
- Relatório final: arquivos, testes, riscos, ganchos para PRs futuros
  (notificação a cidadão, prazo, dashboard, indeferimento).
