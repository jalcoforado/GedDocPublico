# Confronto AS-IS × TO-BE — reunião "Aprimora – Sistemas", 2026-08-27

> **Status:** spec de diagnóstico · **Autoridade sobre:** nada ainda executável.
> **Última verificação:** 2026-08-28, contra `main` em `e4a41ee`.
> Índice: [docs/INDEX.md](../../INDEX.md) · precedência: código > `CLAUDE.md` > este doc.

---

## 1. Objetivo

Confrontar o estado real do código (AS-IS) com o que a reunião de 2026-08-27
definiu (TO-BE), e propor **apenas** mudanças cuja necessidade tenha sido
comprovada por leitura do código executável.

O risco dominante aqui não é deixar de implementar algo — é **reimplementar o
que já existe**. Das 30 linhas da matriz da §5, **16 já estão atendidas**, várias
com teste que trava a regra exata que a reunião pediu. Uma spec que as tratasse
como pendentes custaria semanas e destruiria decisões maduras.

Há um segundo risco, específico desta reunião, e ele é menos óbvio: **boa parte
do que foi demonstrado é o sistema do Ramom, não o nosso** — e parte do que ele
mostrou foi apresentado como *defeito*. Copiar a demonstração linha a linha
importaria defeitos junto. A §4.3 trata disso separadamente.

---

## 2. Fontes analisadas

### 2.1 A reunião

`Aprimora - Sistemas — 2026-08-27 17:48 GMT-03:00 — Anotações do Gemini.docx`
(anotações automáticas: resumo, **7 decisões alinhadas**, 12 próximas etapas, 23
blocos de detalhe). Participantes citados: Jorge Alberto, Ramom Carvalho,
Marúsia Dias.

**Correção de método, registrada de propósito.** A primeira versão desta spec
foi escrita sem este arquivo — eu o procurei no repositório, não achei, e derivei
o TO-BE de um resumo em tópicos. O resumo estava correto no essencial e **errado
em três conclusões**, todas invertidas agora:

| Tema | O que a spec dizia sem a ata | O que a ata diz |
|---|---|---|
| A15 "tornar sem efeito" | `DEPENDE DE DEFINIÇÃO` — conceito a modelar | É **crítica** ao sistema demonstrado: gera "acúmulo de páginas inutilizadas em auditorias". **Não implementar** |
| A9 responsável | `DEPENDE DE DEFINIÇÃO` — unidade ou pessoa? | Pessoa. "Sem responsável atribuído" é estado visível, e é o que separa visão individual de visão de setor |
| M sigilo | `DEPENDE DE DEFINIÇÃO` — qual caso não é coberto? | Não é lacuna de sistema. É exigência burocrática do órgão; a próxima etapa é o Jorge falar com o James |

A lição é a que este repositório já registra em outro contexto: **resumo não é
fonte**. Um resumo fiel pode inverter o sinal de um item — "foi discutido X" não
distingue "queremos X" de "X é o problema".

### 2.2 Governança

`CLAUDE.md` (integral), `README.md`, [`docs/INDEX.md`](../../INDEX.md),
[`docs/BACKLOG-PENDENCIAS.md`](../../BACKLOG-PENDENCIAS.md),
[`docs/INTEGRACAO-PAGAMENTOS.md`](../../INTEGRACAO-PAGAMENTOS.md),
[`ADR-016`](../../architecture/adr/ADR-016-platform-operator-identity.md).

### 2.3 Código

41 routers, 84 services, 31 módulos de model, 105 migrations, 139 arquivos de
teste no backend; 89 no frontend. Lidos: os 33 models de `pagamentos`,
`services/pagamentos_*` (25), `services/workflow_*`, `acoes_processo.py`,
`sigilo.py`, `prazos.py`, `placeholders.py`, `services/ia/*`,
`google_docs_service.py`, `frontend/components/AcoesProcesso.tsx`.

Specs históricas tratadas como **intenção, não estado** — ver
[`docs/superpowers/INDEX.md`](../INDEX.md).

---

## 3. Arquitetura AS-IS relevante

### 3.1 O rito de pagamento já é o rito decidido

`services/pagamentos_estados.py` é domínio puro e declara o grafo:

```
RASCUNHO → AGUARDANDO_GESTOR → AGUARDANDO_VALIDACAO → AGUARDANDO_AUTORIDADE → AUTORIZADA → (execução)
              ↓ AJUSTE_GESTOR      ↓ AJUSTE_VALIDACAO     ↓ AJUSTE_AUTORIDADE
              ↓ REJEITADA_GESTOR                          ↓ INDEFERIDA_AUTORIDADE
```

A Decisão 3 da ata ("solicitação, aprovação do gestor, validação financeira e
autorização final") é literalmente este grafo. E a regra mais delicada — a
validação financeira da CFI **não** rejeita em definitivo — está codificada como
propriedade estrutural: `AGUARDANDO_VALIDACAO` tem **duas saídas e nenhuma
terminal**, com teste que reprova quem acrescentar uma
(`tests/test_pagamentos_validacao_sem_rejeicao.py`).

O débito carrega **três dimensões independentes** (`situacao_tramitacao`,
`situacao_fila`, `situacao_pagamento`); `status` sobrevive derivado até a F5.

### 3.2 Workflow BPM é motor único e já existe

`models/workflow.py` + `workflow_engine.py` + `workflow_dsl.py` +
`workflow_integration.py`. `TipoProcessoWorkflow` mapeia
`(tenant, tipo_processo) → slug`; `auto_iniciar_workflow_se_aplicavel` liga a
instância na abertura; estado com `id_unidade_responsavel` faz
auto-encaminhamento.

É exatamente o "motor de tramitação flexível, que suporta fluxos rígidos,
automáticos ou abertos" que o Jorge descreveu na reunião (§43 da ata).
**Não criar um segundo.** A Decisão 1 (regras por assunto/tipo) cabe aqui.

### 3.3 Quatro eixos de acesso, independentes

Módulo (`auth/modulos.py`), permissão (`auth/perms.py`), sigilo
(`services/sigilo.py`, 5 níveis, erro → 404) e tenant (RLS + `tenant_filter` +
disciplina de service). Nenhum substitui outro; nenhum requisito desta spec
introduz um quinto.

### 3.4 O que "global × municipal" significa hoje

Não há herança. **Todo catálogo de negócio é por tenant** (`tenant_id` NOT NULL +
RLS). Global é curto e deliberado: `aprimora_py.modulo`, `modulo_transacao`,
`utils.sistema`, `utils.nivel`, `protocolos.acao`.

O padrão chega ao tenant por **cópia no provisionamento**
(`provisioning_tenant.py::semear_tenant`), não por *fallback* em leitura.
Consequência: **mudar um padrão global não propaga para tenant já criado**. É o
ponto que a Decisão 2 obriga a resolver (§8, Q1).

---

## 4. Requisitos funcionais consolidados

### 4.1 As 7 decisões alinhadas — a parte mais autoritativa da ata

| # | Decisão (texto da ata, condensado) |
|---|---|
| **D1** | Fluxos de tramitação **pré-definidos por assunto ou tipo**, para restringir opções de destino indevidas e automatizar o encaminhamento |
| **D2** | **Configuração híbrida**: padrão geral para todos os municípios + particularizações por localidade |
| **D3** | Pagamentos: solicitação → aprovação do gestor → validação financeira → autorização final |
| **D4** | **Alçada** por usuário, com base na natureza da despesa e em valor máximo |
| **D5** | **Checklist documental obrigatório**, bloqueando o avanço "caso os itens necessários não sejam **anexados**" |
| **D6** | **SLA** para definir e controlar prazos "para **cada etapa** dos processos" |
| **D7** | **Google Docs** para redação, edição e salvamento automático |

Duas palavras dessas decisões carregam peso técnico e são citadas na matriz:

- **D5 diz "anexados", não "marcados".** Isso decide o achado P0 da §7.1: hoje o
  checklist bloqueia por *declaração*, não por documento.
- **D6 diz "cada etapa".** Isso é SLA por nó de workflow (J1), não prazo
  end-to-end (J2). Os dois existem e **não devem ser fundidos**.

### 4.2 Requisitos dos blocos de detalhe

**Tramitação** — A1 regras por assunto/tipo · A2 roteamento automático ·
A3 destinos permitidos · A4 não exibir destino inválido · A5 não errar depois da
escolha, sem perder trabalho · A6 tramitação automática após assinatura da
autoridade · A7 envio em lote / grupos nomeados · A8 visão individual × setor ·
A9 responsável (pessoa) · A10 rascunhos · A11 favoritos · A12 histórico ·
A13 arquivamento com motivo · A14 apensamento · A16 processos externos ·
**A17 numeração de páginas visível** · **A18 troca de lotação**.

**Regra de negócio explicitada na ata (§34):** tramitação passa pelo **protocolo
central**, salvo fluxo automatizado por assunto. É regulamentada, e existe para
evitar sobrecarga indevida nas caixas de setores específicos.

**Financeiro** — C rito · D alçada · E checklist com anexo · F conta compatível
com a fonte · G integração contábil (arquivo **ou** API; exemplo citado: sistema
**Samuel**) · H conciliação bancária · I cadastros (contratos **simples**) ·
**C2 visão Kanban**.

**Documentos** — K Google Docs · L1 tags automáticas · **L2 templates por setor,
com clonagem**.

**Transversais** — J1/J2 SLA · M sigilo · N usabilidade (erro orientativo, não
oferecer inválido, não perder trabalho, contexto visual) · O IA **para auxiliar
no preenchimento de campos** e tirar dúvidas.

### 4.3 O que a ata registra como DEFEITO — e que seria erro portar

Este bloco existe porque a demonstração do Ramom expôs o sistema dele, incluindo
o que nele não funciona. Ler a ata como catálogo de funcionalidades a copiar
importaria estes três problemas:

| Item | O que a ata diz | Nosso AS-IS |
|---|---|---|
| **"Tornar sem efeito"** | O sistema atual "substitui o desentranhamento de documentos por 'tornar sem efeito', **gerando o acúmulo de páginas inutilizadas em auditorias**" (§39) | Temos **desentranhamento** (`services/desentranhamento.py`) com termo. É o comportamento que a ata prefere. **Não implementar "tornar sem efeito"** |
| **Interface oferece o proibido** | "a interface não deveria exibir opções de setores restritos caso o envio direto seja proibido" (§34) | Temos o **mesmo defeito** (§7.2). Aqui a crítica se aplica a nós |
| **Erro 400 genérico** | Jorge "criticou códigos de erro genéricos como o erro 400" (§44) | Parcial — ver N na matriz |

---

## 5. Matriz AS-IS × TO-BE

| # | Requisito | Status | Evidência no código | Gap real | Mudança recomendada | Risco |
|---|---|---|---|---|---|---|
| **D1**/A1 | Regras de tramitação por assunto/tipo | **ATENDIDO** | `models/workflow.py::TipoProcessoWorkflow`; `workflow_integration.py:49-121`; migration `0009` | Nenhum | Nenhuma | — |
| A2 | Roteamento automático | **ATENDIDO** | `workflow_engine.py:382-414`; `workflow_integration.py:94` | Nenhum | Nenhuma | — |
| A3 | Destinos permitidos/proibidos | **PARCIAL** | Existe no workflow: `workflow_engine.py:500-501` (`transicoes_disponiveis` filtra por unidade, bypass de SU). **Não** existe no encaminhamento avulso | A regra do protocolo central (§34) não está modelada | §7.2 + §8 Q2 | Médio |
| A4 | Não exibir destino inválido | **NÃO IMPLEMENTADO** | `frontend/components/AcoesProcesso.tsx:167-168` → `api.unidades.list({page_size: 200})`: **todas** as unidades | Idêntico à crítica do Ramom | §7.2 | Médio |
| A5 | Não errar depois da escolha | **NÃO IMPLEMENTADO** | `services/acoes_processo.py:80-82` valida **após** a submissão | A ata registra o dano: "bloqueio sem mensagens orientativas, **exigindo a exclusão do arquivo e reinício**" | §7.2 | Médio |
| A6 | Tramitação automática pós-assinatura | **NÃO IMPLEMENTADO** | `disparar_evento` só é chamado com `"abertura"`, `"encaminhamento"`, `"recebimento"` (`workflow_integration.py:121`; `acoes_processo.py:185,272`). `services/assinaturas.py` não o importa | Assinar não move o workflow | §7.3 | Baixo |
| A7 | Envio em lote / grupos nomeados | **NÃO IMPLEMENTADO** | `autorizar_lote` existe só em pagamentos. Não há grupo de destinatários | Ata pede grupos nomeados (fundações, adm. direta, autarquias) | §7.6 | Baixo |
| A8 | Visão individual × setor | **NÃO IMPLEMENTADO** | `routers/processos.py:166` filtra `id_unidade`. Não há escopo "meus" | Depende de A9 | §7.4 | Baixo |
| A9 | Responsável (pessoa) | **NÃO IMPLEMENTADO** | Processo tem `id_unidade_responsavel` (**unidade**). `id_usuario_responsavel` só existe em `pagamentos.BloqueioSaldo` | Ata é clara: pessoa, com "sem responsável" como estado visível | §7.4 | Médio |
| A10 | Rascunhos | **PARCIAL** | Existe em minuta (`models/minuta.py:103`) e débito (`pagamentos.py:185`). **Não** em processo | Abertura é atômica | §8 Q3 | — |
| A11 | Favoritos | **NÃO IMPLEMENTADO** | Busca por `favorit` em backend e frontend: zero | Não existe | §7.6 | Baixo |
| A12 | Histórico | **ATENDIDO** | `services/processo_trail.py`; `models/audit.py`; `workflow_transicao_log`; migration `0014` | Nenhum | Nenhuma | — |
| A13 | Arquivamento com motivo | **PARCIAL** | `workflow_integration.py:148` documenta a ação `"arquivar"`, mas **não há** `def arquivar` em `acoes_processo.py`, nem endpoint, nem `ARQUIVAMENTO` em `protocolos.acao` (`seed_bootstrap.py:410-413`). O frontend **já tem** intent de badge para `ARQUIVAMENTO` | Contrato declarado, ação inexistente | §7.5 | **Alto** |
| A14 | Apensamento | **ATENDIDO** | `services/apensamento.py`; `volumes.py`; `desentranhamento.py` | Nenhum | Nenhuma | — |
| A15 | "Tornar sem efeito" | **NÃO FAZER** | `services/desentranhamento.py` (com termo) | Nenhum — a ata o trata como **defeito** do outro sistema (§4.3) | **Nenhuma** | — |
| A16 | Processos externos | **PARCIAL** | `models/processo.py:88,190` — `externo: bool`; `abertura_processo.py:75` | Ata pede número externo, órgão e setor de origem estruturados | §8 Q4 | — |
| A17 | Numeração de páginas na interface | **NÃO IMPLEMENTADO** | Numeração existe na montagem do PDF (`services/pdf_montagem.py`), não na tela | Ata: obriga gerar PDF só para referenciar página em despacho | §7.6 | Baixo |
| A18 | Troca de lotação | **NÃO IMPLEMENTADO** | Usuário tem lotação única | Ata cita troca para comissões | §8 Q5 | — |
| **D2**/B | Configuração híbrida global + local | **PARCIAL** | Tudo por tenant + RLS; global é só catálogo de plataforma; padrão por cópia em `provisioning_tenant.py::semear_tenant` | Padrão global novo **não alcança tenant existente**. Caso concreto da ata: **assuntos** | §8 Q1 | — |
| **D3**/C | Rito de pagamento | **ATENDIDO** | `pagamentos_estados.py`; `pagamentos_debitos.py`; `pagamentos_caixa.py`; `test_pagamentos_fluxo_gestor.py`, `test_pagamentos_fluxo_validacao_autoridade.py` | Nenhum | **Não tocar** | — |
| C′ | Validação financeira não rejeita | **ATENDIDO** | `TRANSICOES_TRAMITACAO[AGUARDANDO_VALIDACAO]` = 2 saídas, 0 terminais; `test_pagamentos_validacao_sem_rejeicao.py` | Nenhum | **Não tocar** | — |
| C2 | Visão Kanban | **NÃO IMPLEMENTADO** | Filas existem (`pagamentos_filas.py`, `f3_fila`), a apresentação é lista | Só apresentação — os estados já existem | §7.6 | Baixo |
| **D4**/D | Alçada | **ATENDIDO** | `models/pagamentos.py:362-377` — `id_usuario`, `id_natureza`, `valor_maximo`, **+ `id_unidade`, `id_fonte`, `tipo_despesa`**; resolução por especificidade em `pagamentos_autorizacao.py:60-84` | Nenhum — é **mais** do que a D4 pede | **Não simplificar** | — |
| **D5**/E | Checklist bloqueia sem anexo | **PARCIAL** | Configuração e bloqueio existem: `models/pagamentos.py:428-459`; `pagamentos_checklist.py::checklist_pendente`; 422 em `pagamentos_debitos.py:635-640` | **`marcar()` grava só booleano + observação; não há vínculo com `AnexoDebito`.** Dá para marcar "NF anexada" sem NF. A D5 diz "**anexados**" | §7.1 — **P0** | **Alto** |
| F | Conta compatível com a fonte | **ATENDIDO** | `pagamentos_autorizacao.py:142-145` (RN-06, 422); `:37` lista só contas da fonte; `pagamentos_debitos.py:51`; `test_pagamentos_saldos_v2.py` | Nenhum. A ata (§50) descreve a UI de agrupar por fonte e mostrar saldo — já apresentada pelo Jorge | **Não recriar** | — |
| **D**/G | Integração contábil | **ATENDIDO COM MELHORIA** | Arquivo: `pagamentos_contabil.py` com `ContabilAdapter` (Protocol, :404) + `AdapterNeutroCSV` (:408), lote imutável por snapshot JSONB. API: `routers/pagamentos_integracao.py` (POST `/debitos`, `/debitos/{id}/liquidar`; GET `/debitos`,`/ordens`,`/baixas`) com idempotência e credencial M2M | Só o adapter neutro. Ata cita o **sistema Samuel** | Adapter quando houver layout do Samuel. **Não** amarrar o `Protocol` a ele | Baixo |
| H | Conciliação bancária | **ATENDIDO** | `pagamentos_conciliacao.py` (CSV/OFX/CNAB240, `sugerir_baixas`, `conciliar`, `baixa_automatica`); `pagamentos_extrato_parsers.py`; `test_pagamentos_conciliacao_v2.py` | Nenhum | **Não mexer** | — |
| I | Cadastros financeiros | **ATENDIDO** | `Fornecedor` (+histórico), `NaturezaDespesa`, `FonteRecursos`, `ContaBancaria`, `Contrato`; `pagamentos_cadastros.py` | Nenhum | **Manter contrato simples** (pedido do Ramom) | — |
| **D6**/J1 | SLA por etapa | **ATENDIDO** | `schemas/workflow.py:55` (`sla_dias` por estado); `WorkflowSlaAlerta`; `tasks/verificar_sla_workflows.py` (dedup por índice parcial); migration `0010` | Nenhum | Nenhuma | — |
| J2 | Prazo end-to-end | **ATENDIDO** | `services/prazos.py`; `PrazoInfo` (`lib/api.ts:326`); `models/servico.py::prazo_estimado_dias`; `test_pr5b_prazos.py` | Nenhum | **Não fundir com J1** | — |
| **D7**/K | Google Docs | **ATENDIDO** | `google_docs_service.py` (criar, sincronizar, exportar PDF, arquivar, renovar token); `google_oauth_flow.py`; `models/google_credencial.py` (Fernet); `test_minuta_google_docs_integration.py` | Nenhum | **Não criar editor próprio** | — |
| L1 | Tags automáticas | **ATENDIDO** | `services/placeholders.py:35-51` — 14 tags, incluindo `processo.numero`, `unidade.nome`, `requerente.nome` (as três citadas na ata). `resolve()` escapa HTML | Nenhum | Nenhuma | — |
| L2 | Template por setor + clonar | **NÃO IMPLEMENTADO** | `models/minuta.py::TemplateDocumento` tem `tenant_id` e `categoria`; **não** tem escopo por unidade nem clonagem | Ata: "modelos vinculados ao setor específico", "criar, **clonar** e gerenciar" | §7.6 + §8 Q1 | Baixo |
| M | Sigilo | **ATENDIDO** | `services/sigilo.py::assert_acesso_processo` (5 níveis, → 404); `test_guarda_anexo_sigiloso.py`; `test_sigilo_enforcement.py` | **Nenhum.** O problema da ata (§54) é exigência burocrática do órgão — a próxima etapa é conversa com o James, não código | **Nenhuma** | — |
| N | Usabilidade | **PARCIAL** | Caso verificável: A4/A5. O exemplo de limite de arquivo citado na ata **já foi corrigido** (`frontend/app/cidadao/abrir/__tests__/upload-limite.test.tsx`) | Ver A4/A5 | §7.2 | Médio |
| O | IA no preenchimento | **PARCIAL** | `services/ia/` + `routers/ia.py`, gateado por `require_modulo("protocolo")` + `require_permission("processo")` + `assert_acesso_processo` (`assistente.py:75`); read-only; `test_ia1_assistente_processo.py` | Só **pergunta sobre processo**. Ata pede auxílio ao **preencher campos** | §7.6 | Baixo |

---

## 6. Funcionalidades já atendidas — NÃO ALTERAR

1. **`services/pagamentos_estados.py`** — o grafo. Não acrescentar estado
   terminal a `AGUARDANDO_VALIDACAO`.
2. **As três dimensões do débito** e o `status` derivado (a unificação é a F5).
3. **`models/pagamentos.py::Alcada`** — seis eixos. A D4 pede três; **não
   reduzir para caber no requisito**.
4. **`pagamentos_autorizacao.py`** — fonte↔conta (RN-06), saldo projetado,
   bloqueio, exceção com justificativa (RN-15), all-or-nothing por grupo.
5. **`pagamentos_conciliacao.py`** + `pagamentos_extrato_parsers.py`.
6. **`pagamentos_contabil.py`** — lote imutável por snapshot JSONB. O snapshot
   existe para que reconstruir CSV antigo não dependa do domínio atual.
7. **`routers/pagamentos_integracao.py`** + `pagamentos_sistemas.py`.
8. **`services/workflow_*`** — motor único.
9. **`services/sigilo.py`** e a disciplina 404-nunca-403.
10. **`services/prazos.py`** (J2) e `sla_dias`/`WorkflowSlaAlerta` (J1) —
    conceitos distintos, separados de propósito.
11. **`services/desentranhamento.py`** — e **não** substituí-lo por "tornar sem
    efeito" (§4.3).
12. **`services/google_docs_service.py`**.
13. **Multi-tenancy**: RLS + `tenant_filter` + `tenant_id` sempre do caller.
14. **A modularização** e o fail-open deliberado de transação sem módulo.

---

## 7. Melhorias comprovadamente necessárias

### 7.1 — Checklist: marca sem documento `P0`

**Problema.** O checklist bloqueia o avanço, mas a marcação é
**autodeclaração**: nada verifica que o documento existe.

**Evidência.** `services/pagamentos_checklist.py:117-124` — `marcar()` grava
`DebitoChecklistMarca(marcado=bool, observacao=str)`. Não recebe nem consulta
`id_anexo`. `ChecklistItem` não aponta para tipo de anexo; `DebitoChecklistMarca`
não tem FK para `AnexoDebito`. O enforcement em `pagamentos_debitos.py:635-640`
confere só a marca. **É possível marcar "Nota fiscal anexada" com zero anexos e
passar pela validação financeira.**

**Requisito.** D5, literalmente: bloquear "caso os itens necessários não sejam
**anexados**". A ata cita nota fiscal como o exemplo (§52).

**Por que P0.** É a única lacuna que permite avançar num rito financeiro sem o
pressuposto que o próprio rito declara exigir.

**Menor alteração.** **Não criar um segundo checklist.** Estender o existente:

- `DebitoChecklistMarca.id_anexo_debito` — FK opcional para
  `pagamentos.anexo_debito`.
- `ChecklistItem.exige_anexo: bool` — default `false`, para não mudar nenhum
  item já cadastrado.
- `marcar()` recusa item com `exige_anexo=true` sem anexo vivo do mesmo débito.
- `checklist_pendente()` volta a considerar pendente o item cujo anexo foi
  excluído depois da marcação.

**Impacto.** Migration aditiva (2 colunas, defaults seguros), service, schema,
router (payload ganha campo opcional), frontend (seletor de anexo quando
`exige_anexo`). **Zero mudança para quem não ligar a flag** — é o que torna a
fatia reversível.

**Compatibilidade.** `exige_anexo` default `false` preserva o existente; nenhum
contrato de API quebra.

**RLS.** As duas tabelas já têm `tenant_id` + RLS; `ADD COLUMN` herda RLS e
grants — **não repetir o boilerplate**. A validação de que o anexo é do **mesmo
débito e tenant** é do service: a FK do Postgres não filtra por tenant.

**Testes.** Passar: `test_pagamentos_validacoes_v2.py`,
`test_pagamentos_fluxo_validacao_autoridade.py`, `test_pagamentos_f2_anexos.py`.
Novos: (1) `exige_anexo` sem anexo → 422; (2) anexo excluído depois → volta a
pendente e bloqueia; (3) anexo de outro débito → 422; (4) anexo de outro tenant
→ 404; (5) `exige_anexo=false` funciona como hoje — **este prova a
retrocompatibilidade**, e sua inversão (ligar a flag, ver o 422) prova a guarda.

### 7.2 — Destinos de encaminhamento: validar antes `P1`

**Problema.** O usuário escolhe o destino e só então descobre que não podia.

**Evidência.** `AcoesProcesso.tsx:167-168` monta o combo com
`api.unidades.list({ page_size: 200 })` — todas as unidades, sem filtro.
`acoes_processo.py:80-82` chama `validar_acao_strict` já dentro de `encaminhar`.
O motor **já sabe** a resposta: `workflow_engine.py:500-501` documenta que
`transicoes_disponiveis` esconde transição cujo destino tem unidade diferente da
do usuário.

**Requisito.** D1, A3/A4/A5, N. A ata quantifica o dano: "bloqueio sem mensagens
orientativas, exigindo a exclusão do arquivo e reinício do procedimento" — não é
só fricção, é **perda de trabalho**.

**Menor alteração.** Não criar regra nova — **expor a que existe**.
`GET /processos/{id}/destinos-permitidos`, reaproveitando
`transicoes_disponiveis` quando há instância ativa e devolvendo a lista completa
quando não há (preserva o comportamento atual). O combo passa a consumi-lo, e
mostra o **motivo** quando a lista vem reduzida.

**A regra do protocolo central fica de fora desta fatia** — ela ainda não está
modelada (§8, Q2). Esta fatia entrega o mecanismo; a regra entra quando decidida.

**Impacto.** 1 endpoint + 1 função de service. Sem model, sem migration.
Segurança: nenhuma mudança de política — `validar_acao_strict` **permanece**, e
o filtro é UX, não barreira.

**Testes.** Passar: `test_workflow_*`, `test_guarda_ordem_rotas.py` (declarar
`/destinos-permitidos` **antes** das paramétricas irmãs). Novos: usuário de
unidade A não recebe B em workflow strict; processo sem workflow recebe tudo;
**teste HTTP com usuário não-SU** — o bypass em `auth/perms.py` retorna antes do
`getattr(item, action)` e esconde esta classe de defeito.

**Nota, não corrigir aqui:** `page_size: 200` é teto silencioso. Tenant com mais
unidades perde destinos sem aviso. Registrar no backlog.

### 7.3 — Assinatura dispara evento de workflow `P1`

**Problema.** Assinar não movimenta o workflow.

**Evidência.** `disparar_evento` é chamado três vezes, nenhuma em assinatura:
`workflow_integration.py:121`, `acoes_processo.py:185`, `:272`.
`services/assinaturas.py` não o importa.

**Requisito.** A6 — a ata descreve o recurso no sistema demonstrado:
"encaminha o processo para o próximo destino logo após a assinatura da
autoridade superior, eliminando etapas manuais" (§35).

**Menor alteração.** Chamar `disparar_evento(db, processo, "assinatura",
usuario_id)` onde a assinatura se conclui.

**Por que é seguro.** Nenhum workflow existente declara transição por
`"assinatura"`, e `validar_acao_strict` libera quando não há instance ativa —
então **o comportamento atual não muda até alguém desenhar um workflow que
reaja**. Isso deve constar do PR.

**Testes.** Novos: workflow com transição por assinatura avança; sem ela, fica;
processo sem instância não quebra.

### 7.4 — Responsável, e as duas visões `P1`

**Problema.** Não há responsável-pessoa, logo não há "visão individual".

**Evidência.** Processo tem `id_unidade_responsavel` (**unidade**).
`id_usuario_responsavel` só existe em `pagamentos.BloqueioSaldo`.
`routers/processos.py:166` filtra por unidade.

**Requisito.** A8/A9. A ata é específica: visão individual = "processos
atribuídos especificamente a uma pessoa"; visão de setor = "todos os trâmites,
**incluindo aqueles pendentes de designação de responsável**" (§32). E há
"diferenças visuais entre processos sem responsável atribuído e aqueles com
responsável definido" (§38).

**Menor alteração.** `processo.id_usuario_responsavel` **nullable** — nulo é o
estado "pendente de designação", que a ata trata como de primeira classe. Um
filtro `escopo=meus|unidade` na listagem. Ação "alterar responsável" reaproveita
o registro de histórico existente (`processo_trail`).

**Não** derivar responsável de permissão, nem de lotação: a ata trata como
atribuição explícita.

**Impacto.** Migration aditiva (1 coluna nullable + índice `(tenant_id,
id_usuario_responsavel)`), service, router, frontend (badge + filtro).

**Testes.** Novos: processo nasce sem responsável; atribuir registra no
histórico; `escopo=meus` não vaza processo de outro usuário; `escopo=unidade`
inclui os sem responsável — **este último é o que prova a semântica da ata**.

### 7.5 — `arquivar`: contrato declarado sem implementação `P1`

**Problema.** `validar_acao_strict` documenta e aceita a ação `"arquivar"`, mas
não existe serviço, endpoint nem ação de catálogo.

**Evidência.** `workflow_integration.py:148` lista
`"encaminhar" | "receber" | "cancelar_encaminhamento" | "arquivar"`. Busca por
`def arquivar` em `acoes_processo.py` e `arquivamento` em `routers/processos.py`:
zero. `seed_bootstrap.py:410-413` semeia só três ações. O frontend **já tem**
intent de badge para `ARQUIVAMENTO`.

**Por que P1.** Não é funcionalidade faltando — é **contrato mentindo**. Um
workflow que declare transição para `"arquivar"` passa pela validação strict e
não encontra ação.

**Requisito.** A13, com o detalhe da ata: arquivamento **com seleção de motivo e
observação opcional** (§41).

**Duas saídas, e a escolha é do negócio** (§8, Q6): implementar (serviço +
endpoint + `ARQUIVAMENTO` em `protocolos.acao` por seed, **e** em
`ci/seed-e2e.sql`, porque o `e2e-assinatura.yml` não roda o `seed_bootstrap`), ou
**remover `"arquivar"` do contrato** até que exista. A segunda é de 1 linha.

**Migration:** nenhuma — `protocolos.acao` é tabela legada e já existe.

### 7.6 — Fatias menores, com gap comprovado

| Item | Gap | Menor mudança | Prio |
|---|---|---|---|
| C2 Kanban | Filas existem, apresentação é lista | Só frontend, sobre `pagamentos_filas` | P2 |
| A7 lote/grupos | Encaminhamento 1-a-1 | Endpoint iterando o serviço existente, all-or-nothing; grupo nomeado é cadastro simples | P2 |
| L2 template por setor | Só escopo de tenant | `id_unidade` nullable em `TemplateDocumento` + precedência unidade > tenant; clonar é POST que copia | P2 |
| A17 numeração de página | Só no PDF montado | Expor o número que `pdf_montagem` já calcula na listagem de anexos | P2 |
| A11 favoritos | Não existe | Tabela `(tenant, usuario, processo)` + 2 endpoints | P3 |
| O IA preenchimento | Só pergunta sobre processo | Ampliar o assistente existente. **Nunca** dar-lhe autoridade: as guardas de `routers/ia.py` e `assistente.py:75` são o piso | P3 |
| G adapter Samuel | Só CSV neutro | Adapter novo **quando houver layout**. Não mexer no `Protocol` antes | P3 |

---

## 8. Pontos que dependem de decisão de negócio

**Q1 (D2 / B / L2) — "Padrão geral + particularização" significa herança ou cópia?**
Hoje é cópia no provisionamento: padrão global novo **não alcança tenant
existente**. Caso concreto da ata: catálogo global de **assuntos** com
customização local. *Pergunta:* (a) a cópia basta, (b) precisa de propagação
explícita ("aplicar padrão a este tenant"), ou (c) precisa de *fallback* em
leitura? **(c) é a mais cara e a que mais mexe em código estável** — toda query
de catálogo ganharia dois níveis. Recomendo **(b)** na dúvida. A mesma resposta
decide L2.

**Q2 (D1 / A3) — Como modelar a regra do protocolo central?**
A ata a declara regulamentada: tramitação passa pelo protocolo central para não
sobrecarregar setores específicos, salvo fluxo automatizado por assunto.
*Pergunta:* é (a) propriedade da **unidade** ("recebe só do protocolo"), (b) do
**assunto** (workflow próprio que já roteia), ou (c) das duas? Hoje só (b) é
expressável. Sem isso, §7.2 entrega o mecanismo mas não a regra.

**Q3 (A10) — Rascunho de processo é o quê?**
Processo hoje nasce protocolado (número, NUP, ação de ABERTURA). Rascunho implica
número não emitido, o que muda a semântica do protocolo. *Pergunta:* processo sem
número, ou formulário salvo? A ata cita "abas de rascunhos para edições em
andamento" (§32) — o que sugere documento em edição, não processo.

**Q4 (A16) — Processo externo é rito ou etiqueta?**
Hoje é `bool`. A ata cita "número externo, setor, órgão, interessados e assunto"
(§33). *Pergunta:* campos estruturados, ou a flag basta?

**Q5 (A18) — Troca de lotação é temporária?**
A ata cita troca "para comissões específicas" (§41). *Pergunta:* é segunda
lotação simultânea, substituição temporária com prazo, ou só um seletor de
contexto? Afeta permissão e a visão de setor.

**Q6 (A13) — `arquivar`: implementar ou remover do contrato?** Ver §7.5.

**Q7 (G) — Layout do sistema Samuel.** O adapter só pode ser escrito com o
layout em mãos. *Pergunta:* arquivo ou API? Quem fornece a especificação?

**Não é pergunta de sistema:** o acesso de Marúsia a processos sigilosos (§54).
A ata registra como exigência burocrática do órgão, criticada pelos presentes, e
a próxima etapa é o Jorge conversar com o James. Nosso sigilo já funciona; **não
há exceção de acesso a implementar**, e inventar uma seria a pior coisa que esta
spec poderia produzir.

---

## 9. Desenho técnico incremental

### 9.1 — Checklist com anexo (§7.1)

- **models** — `ChecklistItem.exige_anexo: bool` (NOT NULL, default `false`);
  `DebitoChecklistMarca.id_anexo_debito: int | None` → `pagamentos.anexo_debito`.
- **migration** — `ADD COLUMN` nas duas. **Sem** boilerplate de RLS/grant
  (herda). `downgrade()` na ordem inversa. Head único.
- **services** — `marcar()` valida anexo (mesmo débito, mesmo tenant, não
  excluído); `checklist_pendente()` reavalia anexo morto.
- **schemas** — `ChecklistItemCreate/Update` ganham `exige_anexo`;
  `ChecklistMarcarIn` ganha `id_anexo_debito` opcional.
- **frontend** — `lib/api.ts` acompanha o `response_model`; seletor de anexo.
- **auditoria** — inalterada (a marca já é append-only).

### 9.2 — Destinos permitidos (§7.2)

- **services** — `acoes_processo.destinos_permitidos(processo, usuario)`.
- **routers** — `GET /processos/{id}/destinos-permitidos`, **antes** das
  paramétricas irmãs.
- **frontend** — troca da query em `AcoesProcesso.tsx` + motivo do filtro.
- **models/migration** — nenhum.

### 9.3 — Evento de assinatura (§7.3)

- **services** — 1 chamada em `assinaturas.py`.

### 9.4 — Responsável (§7.4)

- **models** — `processo.id_usuario_responsavel: int | None` → `utils.usuario`.
- **migration** — `ADD COLUMN` + índice `(tenant_id, id_usuario_responsavel)`.
- **services/routers** — atribuir/alterar (com histórico); filtro
  `escopo=meus|unidade`.
- **frontend** — badge de "sem responsável" e o filtro.

### 9.5 — `arquivar` (§7.5, se Q6 = implementar)

- **services** — `acoes_processo.arquivar(motivo, observacao)`.
- **routers** — `POST /processos/{id}/arquivar`,
  `require_permission("processo", "atualizar")`.
- **seed** — `ARQUIVAMENTO` em `protocolos.acao`, idempotente, no
  `seed_bootstrap` **e** no `ci/seed-e2e.sql`.
- **migration** — nenhuma.

---

## 10. Plano de implementação em PRs pequenos

| PR | Escopo | Depende de | Prio |
|---|---|---|---|
| **1** | Checklist `exige_anexo` + vínculo (§9.1) | — | **P0** |
| **2** | `arquivar`: implementar ou remover do contrato (§9.5) | Q6 | P1 |
| **3** | `GET /destinos-permitidos` (backend + testes) | — | P1 |
| **4** | Combo de encaminhar consome os destinos (frontend) | PR 3 | P1 |
| **5** | Evento `"assinatura"` (§9.3) | — | P1 |
| **6** | Responsável-pessoa + `escopo=meus\|unidade` (§9.4) | — | P1 |
| **7** | Kanban de pagamentos (frontend) | — | P2 |
| **8** | Template por setor + clonar | Q1 | P2 |
| **9** | Numeração de página na interface | — | P2 |
| **10** | Envio em lote + grupos nomeados | PR 3 | P2 |
| **11** | Favoritos | — | P3 |
| **12** | IA no preenchimento | — | P3 |

PRs 3 e 4 são separados de propósito: o backend é testável sozinho, e frontend
que consome endpoint recém-nascido merece revisão própria.

Fora do plano até haver resposta: Q1 (herança), Q2 (protocolo central),
Q3 (rascunho), Q4 (externo), Q5 (lotação), Q7 (Samuel).

---

## 11. Critérios de aceite

**PR 1** — `exige_anexo=true` sem anexo → 422 ao marcar. Anexo excluído depois
→ item volta a pendente e a validação devolve 422. Anexo de outro débito → 422;
de outro tenant → 404. `exige_anexo=false` marca como hoje. `downgrade`
reversível.

**PR 2** — (implementando) processo arquivado não aceita encaminhamento;
`ARQUIVAMENTO` existe após seed em banco limpo **e** no `ci/seed-e2e.sql`; motivo
obrigatório, observação opcional. (removendo) `validar_acao_strict` não menciona
mais `"arquivar"`, com teste que reprova quem reintroduzir sem implementação.

**PR 3** — usuário de unidade A, em workflow strict cujo destino é da unidade B,
não recebe B. Processo sem workflow recebe a lista completa. Teste HTTP **com
usuário não-SU**.

**PR 4** — o combo não oferece destino que o backend recusaria; quando a lista
vem reduzida, a tela diz por quê.

**PR 5** — workflow com transição por `"assinatura"` avança ao assinar; sem ela,
fica parado; processo sem instância não quebra.

**PR 6** — processo nasce sem responsável; atribuição entra no histórico;
`escopo=meus` não vaza processo alheio; `escopo=unidade` **inclui** os sem
responsável.

Transversal: `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest -q`
verde; `cd frontend && npx tsc --noEmit` limpo; `alembic heads` único.

---

## 12. Riscos e regressões possíveis

| Risco | Onde | Mitigação |
|---|---|---|
| `exige_anexo` ligado em tenant com itens legados vira bloqueio surpresa | PR 1 | Default `false`; ligar é ato explícito do admin; teste de retrocompatibilidade obrigatório |
| Filtrar destinos esconder destino legítimo | PR 3/4 | Sem workflow → lista completa. O gate real permanece: o filtro é UX, não segurança |
| Evento `"assinatura"` mover workflow inesperado | PR 5 | Nenhum workflow declara a transição hoje |
| Responsável-pessoa mudar a semântica das filas existentes | PR 6 | Coluna nullable; filtro é opt-in; nenhuma listagem atual muda de default |
| Portar "tornar sem efeito" da demonstração | Todos | §4.3 e §6.11 — a ata o registra como **defeito** |
| Reimplementar checklist/alçada/rito/conciliação | Todos | §6 é a lista de não-toque |
| Teste passar por ser super-usuário | PR 3/6 | Exigir teste com usuário comum |
| Rota literal engolida pela paramétrica | PR 3 | `test_guarda_ordem_rotas.py`; declarar antes |
| Tipo do `api.ts` divergir do `response_model` | PR 1/4/6 | `request<T>` não valida — `test_guarda_contrato_paginado.py` |

---

## 13. Fora de escopo

"Tornar sem efeito" (§4.3). Gestão contratual completa — o contrato permanece
simples, a pedido do Ramom. Reescrita do módulo de pagamentos. Segundo motor de
workflow. Editor rich-text próprio. Unificação de `status` do débito (é a F5).
`SEC-RLS-ROLLOUT`. Redesign geral de UX. Integração com SPU, AssineJá, Guardião,
PROAD (aparecem na ata como comparação e como próximas etapas de **análise**, não
como escopo). Qualquer regra específica de município no código.

---

## 14. Perguntas pendentes

As sete da §8 (Q1–Q7). Duas dependem de material que a própria ata promete nas
próximas etapas:

- **Q7 (Samuel)** — o Ramom ficou de "enviar relatório detalhado sobre o fluxo
  de pagamentos até a próxima segunda-feira". Pode conter o layout.
- **Q2/Q5** — a Marúsia ficou de gravar vídeos do SPU e do AssineJá, e o Ramom de
  compartilhar acesso ao sistema dele. Ver o sistema em uso responde melhor que
  perguntar.

Vale conferir também: a ata registra "prints das telas com marcações e
observações" a caminho (Ramom). Feedback de tela é a fonte natural dos itens de
usabilidade — pode reordenar as prioridades P2 desta spec.
