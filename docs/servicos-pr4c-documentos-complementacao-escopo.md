# PR 4c — Escopo técnico: Documentos exigidos, anexos e complementação simples

**Autor:** Jorge + assistente · **Status:** PROPOSTA (aguardando autorização — nada implementado)

> Transforma `servico.documentos_exigidos` (PR 4a) num **checklist operacional**:
> o cidadão vê o que falta e anexa documentos vinculados ao item exigido; o
> servidor vê o checklist. **Sem** GED, OCR, validação automática, versionamento
> ou workflow. Gerar primeiro este doc; **não implementar**.

---

## 1. Objetivo

Dar visibilidade de "o que falta enviar" por processo aberto por serviço e permitir
anexar documentos **vinculados** ao item exigido, com um **status documental
calculado**. Recomenda-se **fasear** a complementação formal (ver D-FASE).

## 2. Achados no código (o que será reusado, não recriado)

| Necessidade | Já existe | Decisão |
|---|---|---|
| Documentos exigidos do serviço | `protocolos.servico.documentos_exigidos` JSONB `[{nome, obrigatorio, descricao}]` (PR 4a) | **Fonte do checklist** |
| Vínculo processo↔serviço | `processo.id_servico` (PR 4b) | deriva o checklist |
| Upload do cidadão | `POST /cidadao/processos/{id}/anexos` → [`services/anexos.py`](../backend/app/services/anexos.py) `upload_anexo` (valida tamanho/ext, cria `Anexo`+`AnexoProcesso`) | **Reusar**; estender com `documento_exigido_key` opcional |
| Modelo de anexo | `Anexo` (sem campo de "doc exigido") + `AnexoProcesso` (link); `Anexo` tem RLS | nova coluna `anexo.documento_exigido_key` (D-KEY) |
| Dono do processo (cidadão) | `routers/cidadao.py::_verificar_dono` (CPF do manifestante == cidadão, no tenant) | **Reusar** no checklist |
| Detalhe do cidadão | `ProcessoCidadaoDetail.anexos` (públicos) | **estender** com checklist |
| Detalhe interno (servidor) | `GET /processos/{id}` → `ProcessoDetail.anexos` (gate `processo`) | **card** de checklist |
| Imutabilidade de assinado | `anexos.py::anexo_esta_assinado` / `delete_anexo` bloqueia assinado | **respeitar** |
| Auditoria | `services/audit.log` (payload JSONB, id_usuario nullable) | evento minimizado |

Última migration = `0025` → **nova = `0026`**. Hoje o upload do cidadão **não**
audita — auditar (minimizado) entra no escopo.

## 3. Decisões a fechar (recomendações)

- **D-FASE — faseamento da complementação (RECOMENDADO):**
  - **PR 4c:** checklist + vínculo anexo↔documento exigido + status calculado
    (`sem_documentos_exigidos | pendente | parcial | completo`) + upload com tag +
    card read-only do servidor.
  - **PR 4d:** complementação **formal** (servidor marca "aguardando
    complementação" + mensagem; status `em_complementacao`; cidadão responde;
    servidor vê resposta).
  - *Motivo:* a complementação formal é um mini-fluxo (status no processo +
    mensagem + bidirecional + auditoria dos dois lados) — cabe num PR próprio. O
    brief já admite esse split. Mantém o 4c pequeno e sem mexer na máquina de
    status do processo.
- **D-KEY — vínculo anexo↔documento:** adicionar `anexo.documento_exigido_key`
  `varchar(120)` **nullable**. Valor = `nome` do documento exigido **normalizado**
  (slug estável a partir do nome). *Recomendado* (menor modelo; compatível com
  anexos antigos = `NULL`). Alternativas (índice posicional / adicionar `key` em
  cada `ServicoDocumento` reescrevendo o JSONB do PR 4a) **rejeitadas** por escopo
  e fragilidade.
- **D-STATUS:** status **calculado** (sem tabela): a partir de `documentos_exigidos`
  + anexos com `documento_exigido_key`. `em_complementacao` só existe a partir do
  PR 4d.
- **D-AUDIT:** auditar `anexo.enviado_cidadao` minimizado (`id_processo`,
  `id_anexo`, `documento_exigido_key`, `canal`). **Sem** nome/conteúdo do arquivo.

## 4. Migration `0026_anexo_documento_exigido`

- `ALTER TABLE protocolos.anexo ADD COLUMN documento_exigido_key varchar(120) NULL`.
- `anexo` já tem RLS/GRANTs — coluna herda; sem nova policy/permissão.
- Compatibilidade: anexos antigos ficam `NULL` (= anexo geral, não vinculado).
- `downgrade`: drop column.

## 5. Status documental (calculado)

`status_documental` derivado em runtime:

| Status | Regra |
|---|---|
| `sem_documentos_exigidos` | `processo.id_servico` nulo **ou** serviço sem `documentos_exigidos` |
| `pendente` | há obrigatórios e **nenhum** obrigatório enviado |
| `parcial` | parte (não todos) dos obrigatórios enviados |
| `completo` | **todos** os obrigatórios enviados |

"Enviado" = existe `Anexo` (não excluído/ativo) vinculado ao processo com
`documento_exigido_key == slug(item.nome)`. Itens **opcionais** entram no checklist
mas não afetam `pendente/parcial/completo`.

## 6. Backend

- **Serviço** `services/checklist_documentos.py` → `calcular_checklist(db, processo, *, tenant_id)`:
  resolve `documentos_exigidos` do serviço, casa com anexos por
  `documento_exigido_key`, devolve itens (`nome, obrigatorio, descricao, enviado,
  anexos[]`) + `status_documental`. Processo **sem** `id_servico` → status
  `sem_documentos_exigidos` (não quebra).
- **Estender `upload_anexo`** com `documento_exigido_key: str | None`:
  - se informado: o processo deve ter `id_servico` e a key precisa casar com um
    `slug(nome)` do `documentos_exigidos` do serviço → senão **400** (key inválida);
  - grava em `anexo.documento_exigido_key`; resto do fluxo inalterado.
- **Endpoints:**

  | Método | Rota | Auth | Descrição |
  |---|---|---|---|
  | GET | `/api/v2/cidadao/processos/{id}/checklist-documentos` | cidadão (dono) | checklist do próprio processo |
  | GET | `/api/v2/processos/{id}/checklist-documentos` | `require_permission("processo")` | checklist (servidor, tenant) |
  | POST | `/api/v2/cidadao/processos/{id}/anexos` | cidadão (dono) | **estendido** com `documento_exigido_key` opcional (Form) |

  (PR 4d acrescenta os endpoints de complementação.)

## 7. Frontend cidadão

- **`/cidadao/processos/[id]`** e a tela pós-abertura: **card "Documentos"** com a
  lista (obrigatório/opcional, enviado/pendente, orientação) consumindo o checklist.
- **Anexar vinculado:** no upload, escolher a qual documento exigido o arquivo
  corresponde (select com os itens) → envia `documento_exigido_key`. Upload "geral"
  (sem key) continua possível.
- `lib/api.ts`: `api.cidadao.checklistDocumentos(id)`; `uploadAnexo` ganha
  `documentoExigidoKey?`.

## 8. Frontend servidor

- **`/processos/[id]`**: **card read-only** de checklist documental (itens +
  pendentes), consumindo `GET /processos/{id}/checklist-documentos`. Sem redesenho
  da tela. Botão **"Solicitar complementação"** e mensagem ao cidadão → **PR 4d**.

## 9. Segurança e LGPD

- Cidadão só vê/anexa no **próprio** processo (`_verificar_dono`); servidor via
  `require_permission("processo")` + tenant.
- Tenant pelo Host; **sem cross-tenant** (checklist filtra por `tenant_id`; 404 fora).
- Não expor documentos/dados de **outros** cidadãos.
- Não permitir anexar em **processo de outro cidadão**, nem **sobrescrever anexo
  assinado** (regra `anexo_esta_assinado` já existe; uploads criam anexo novo, não
  sobrescrevem).
- Regras de tamanho/tipo do `upload_anexo` mantidas.
- **Auditoria minimizada** (D-AUDIT) — sem dados pessoais/conteúdo.

## 10. Auditoria

- `anexo.enviado_cidadao` (novo, minimizado): `{id_processo, id_anexo,
  documento_exigido_key, canal: "portal"}`. Sem nome do arquivo/conteúdo/CPF.
- Eventos de complementação (solicitada/respondida) → **PR 4d**.

## 11. Testes obrigatórios

**Backend (pytest):**
- checklist gerado a partir de `documentos_exigidos` do serviço.
- processo **sem `id_servico`** → `sem_documentos_exigidos` (não quebra).
- serviço **sem** `documentos_exigidos` → `sem_documentos_exigidos`.
- cidadão vê só o checklist do **próprio** processo; **outro cidadão → 404**.
- upload com `documento_exigido_key` **válido** → anexo associado (aparece como enviado).
- upload com key **inválida** (não casa com o serviço) → **400**.
- obrigatório pendente → `pendente`; todos obrigatórios enviados → `completo`;
  parte → `parcial`.
- **cross-tenant** bloqueado (checklist e upload).
- não permite anexar em processo de outro cidadão; respeita anexo assinado.
- auditoria `anexo.enviado_cidadao` **sem** dados sensíveis.
- migration 0026 aplica em banco limpo; round-trip; anexos antigos (`key=NULL`) válidos.

**Frontend (vitest):**
- card de checklist mostra obrigatórios/pendentes/enviados.
- upload vinculado envia `documento_exigido_key`.
- servidor vê card read-only com pendentes.

## 12. Fora de escopo

OCR · validação automática de documentos · assinatura de anexos do cidadão · GED
completo · versionamento · workflow avançado · SLA completo · dashboard por serviço
· pagamento/taxa · gov.br · WhatsApp · classificação por IA · exigência condicional
complexa · formulários dinâmicos · **complementação formal (→ PR 4d)**.

## 13. Critérios de aceite

- Migration 0026 (`anexo.documento_exigido_key`) aplicada/testada; round-trip OK;
  anexos antigos intactos.
- Checklist derivado de `documentos_exigidos`; status calculado correto.
- Upload vinculado por key válida; key inválida rejeitada (400).
- Cidadão só no próprio processo; servidor via permissão; cross-tenant 404.
- Auditoria minimizada (sem dados sensíveis).
- Telas: card do cidadão (com upload vinculado) e card read-only do servidor.
- Testes backend + frontend passando; sem regressão.
- Itens fora de escopo **não** implementados.
- Relatório final: arquivos, testes, riscos, gancho para o **PR 4d** (complementação
  formal) e dashboard por serviço.
