# Transporte Regulado — P8: workflows avançados (integração BPM)

**Data:** 2026-08-23 · **Estado:** design aprovado em chat, spec para revisão · **Antecede:** plano de implementação

## O que é

A última fase do programa do transporte: os três fluxos com rito — **ocorrências**, **alvará
(emissão/renovação)** e **recadastramento (convocação)** — passam a ser comandados pelo motor BPM
existente (Fases 19–21), com etapas, condições e SLAs configuráveis por tenant via DSL.

Decisões do Jorge (2026-08-23):

- **Os três fluxos entram**, não um piloto só.
- **O workflow comanda o estado.** A situação da entidade deriva do estado da instância; os
  endpoints de ação viram fachadas sobre transições do DSL.
- **Motor polimórfico único.** `workflow_instance` generalizada, não tabelas espelho no transporte,
  nem embrulhar entidade em processo.
- **Fachadas sobre o motor.** URLs, telas e permissões atuais permanecem; a transição acontece por
  dentro.

## Fora de escopo, explicitamente

- **Editor visual de DSL.** A edição é pelo JSON, como já é para workflow de processo.
- **Workflow para vistoria e linha.** As máquinas delas seguem em código.
- **Notificação nova.** O motor de SLA (Fase 21) já alerta e notifica; nada além dele.
- **Desativar `id_processo`.** A coluna vira caso particular de `entidade_tipo='processo'`, mas
  continua preenchida e lida pelos caminhos de processo — remoção é fatia futura, se um dia valer.

## Princípio reitor: dia 1 idêntico ao dia 0

Cada fluxo ganha uma **definição-semente** cujo DSL espelha exatamente a máquina atual, estado por
estado, transição por transição. Depois do deploy, sem nenhuma edição de DSL, o comportamento
externo (respostas HTTP, códigos de erro, mensagens) é o mesmo de hoje — os testes das fases
anteriores continuam verdes **sem alteração**, e essa é a prova de regressão da fase inteira. A
configurabilidade é o tenant editar o DSL *depois*.

## D1 — motor polimórfico + piloto ocorrências

### Migration (generalização)

Em `aprimora_py.workflow_instance`:

- `entidade_tipo varchar(30) NOT NULL` com CHECK
  `entidade_tipo IN ('processo','ocorrencia','alvara','convocacao')`;
- `entidade_id integer NOT NULL`;
- backfill: linhas existentes ganham `entidade_tipo='processo'`, `entidade_id=id_processo`;
- `id_processo` vira **NULLABLE** (novo tipo não o preenche; caminhos de processo continuam
  preenchendo os dois — `id_processo` e o par polimórfico);
- índice `(tenant_id, entidade_tipo, entidade_id)` parcial `WHERE ativa`;
- **unicidade**: no máximo UMA instância ativa por `(tenant_id, entidade_tipo, entidade_id)` —
  índice único parcial. O motor de processo hoje garante isso só no service; o índice passa a
  cobrir todos os tipos.
- downgrade: reverte colunas/índices; falha alto se houver linha com `entidade_tipo != 'processo'`.

`workflow_transicao_log` e `workflow_sla_alerta` não mudam (FK na instância). RLS/grants: a tabela
já tem policies e grants para `aprimora_app`; conferir (e conceder se faltar) `SELECT` em
`workflow_instance`/`workflow_definition` + `SELECT,INSERT,UPDATE` em `workflow_sla_alerta` para
`aprimora_worker` — enumerado, nunca cobertor, padrão da 0094.

Sem FK dura em `entidade_id` (polimórfico não tem FK): a integridade é do service — a fachada só
cria instância a partir de uma entidade que acabou de carregar com `tenant_filter`. Mesma decisão
registrada do par `(tipo, id)` que o módulo evitou em convocação — aqui é aceita porque a
alternativa (uma coluna FK anulável por tipo) faria a tabela do motor crescer uma coluna por
domínio futuro.

### Providers de contexto

O `compute_contexto` do engine hoje só sabe processo. Vira um **registro por `entidade_tipo`**:

- `processo` → o provider atual, intacto;
- `ocorrencia` → `dias_aberta`, `origem` (`fiscalizacao`/`denuncia`), `id_tipo`, `tem_alvo`
  (bool), `qtd_andamentos`, `situacao_atual`;
- `alvara` → `dias_para_vencer` (negativo se vencido; 9999 sem validade), `tipo_servico`,
  `titular_suspenso` (o predicado da Fase C, reaproveitando
  `_titular_tem_convocacao_suspensa`), `eh_renovacao` (bool, `renovado_de` preenchido);
- `convocacao` → `dias_para_prazo`, `situacao_atual`, `checklist_completo` (bool, a amarra da
  P5.2), `tem_vistoria_aprovada` (bool; `condicional` NÃO conta como aprovada — lição da P5.2).

Cada provider é função async no service do domínio, registrada num dict do engine — o engine não
importa modelo de transporte; o transporte importa o engine (mesma direção de dependência que
`workflow_integration` já usa para processo).

### Fachada e semente de ocorrências (piloto)

Semente `transporte-ocorrencia` (DSL): estados `registrada → em_apuracao →
procedente | improcedente | arquivada` (3 finais); transições `iniciar_apuracao`,
`decidir_procedente`, `decidir_improcedente`, `arquivar` — labels canônicos que a fachada invoca.

Fachadas (mesmos endpoints, mesmos payloads):

- `registrar_ocorrencia` → cria a entidade E a instância (estado inicial `registrada`);
- `iniciar_apuracao` → transição `iniciar_apuracao`;
- `decidir_ocorrencia` → transição `decidir_<resultado>` conforme o payload.

Contrato da fachada (vale para os três fluxos):

1. carrega a entidade (tenant + excluido, como hoje);
2. resolve a instância ativa; **se não existir, cria lazy** no estado equivalente à
   `situacao` atual da entidade (cobre o estoque em produção e entidade criada por caminho
   antigo — sem backfill de instâncias em migration);
3. pede ao engine `executar_transicao` pelo label canônico; DSL do tenant sem essa transição a
   partir do estado atual → **409** com mensagem citando a definição
   (`"O workflow '<slug>' não permite '<label>' a partir de '<estado>'"`);
4. executa o payload próprio do ato (parecer, andamento, vínculo de alvo — nada disso vai para o
   DSL);
5. grava `situacao` da entidade a partir do estado de chegada — **a coluna vira cache
   denormalizado** do estado da instância; listagens e filtros atuais não mudam.

Erros de negócio que hoje são 409 no service (ex.: "só decide em apuração") passam a ser o 409 do
passo 3 quando a semente os espelha — a **mensagem pode mudar**; os testes das fases anteriores
que afirmam substring de mensagem são ajustados se preciso (só mensagem, nunca código ou
semântica).

### Situação ↔ estado

O DSL da semente usa **os mesmos slugs** da coluna `situacao` — o mapeamento estado→situação é
identidade. Estado novo criado pelo tenant grava seu slug direto na coluna (varchar livre; os
CHECKs de situação existentes nas tabelas de transporte, onde houver, são **removidos na migration
do respectivo fluxo** — o guardião passa a ser o DSL; documentar no downgrade).

## D2 — alvará (emissão/renovação)

**Descoberta que muda o desenho:** `Alvara` não tem coluna `situacao` — vigência é derivada de
`data_validade`, e não existe ato de revogação. Então:

- Migration: coluna `situacao varchar(30) NOT NULL DEFAULT 'vigente'` em
  `transporte_regulado.alvara` (backfill: tudo `vigente`; **vencido continua derivado de data**,
  nunca vira estado — estado temporal apodrece);
- Semente `transporte-alvara`: estado único `vigente` + transições `renovar` (para `vigente` do
  alvará novo — ver abaixo) e `revogar` (→ `revogado`, **ato novo** desta fase, com motivo
  obrigatório). Emissão direta continua: `criar_alvara` instancia já em `vigente`, espelhando o
  hoje. O rito com etapas (análise documental → vistoria → deferimento) é exatamente o que o
  tenant pode configurar inserindo estados antes de `vigente`;
- Renovação cria alvará **novo** (desenho da P2.1): a fachada `renovar_alvara` transiciona a
  instância do alvará de origem para o estado final `renovado` e abre instância nova (em
  `vigente`, ou no estado inicial do DSL se o tenant configurou rito) para o alvará filho;
- **O gate da Fase C vira condição de DSL**: a transição `renovar` da semente carrega
  `condicao: "not titular_suspenso"`. O 409 com a mensagem atual é **preservado pela fachada**
  (ela avalia o predicado antes e responde a mensagem da Fase C) — o teste da Fase C continua
  verde sem edição; a condição no DSL existe para o tenant poder vê-la e ajustá-la;
- Alvará revogado: `renovar` a partir de `revogado` → 409 do passo 3.

## D3 — recadastramento + painel visual

- Semente `transporte-recadastramento`: `convocado → em_analise → deferido | indeferido`, mais
  `suspenso` (entrada a partir de `convocado`/`em_analise`; saída `reativar` volta ao estado de
  origem — o DSL guarda o estado anterior no contexto da instância, que o engine já suporta via
  `estado_anterior`);
- Fachadas: `decidir_recadastramento`, `suspender_convocacao`, `reativar_convocacao` (+ a entrada
  em análise). A assimetria da P5.2 (**deferir exige completude; indeferir não**) vira condição
  de DSL na transição `deferir` (`checklist_completo`), com a fachada preservando a mensagem
  atual — mesmo padrão do gate C1 no D2;
- As notificações da Fase C (job + ato) **não mudam**: continuam lendo `situacao`, que segue
  existindo como cache;
- **Painel de workflow** nas três telas (`OcorrenciaDetalhe`, alvarás, recadastramento): timeline
  de estados percorridos (do `workflow_transicao_log`) + estado atual + SLA do estado, reusando o
  componente do `ProcessoWorkflowPanel` no que der. Só leitura — os botões de ação continuam
  sendo os atos existentes.

## SLA

O beat `verificar_sla_workflows` generaliza junto com o motor: passa a computar `dias_no_estado`
por instância independente do tipo (já é assim — a data vem do log), e o **provider** entra só na
notificação/contexto. Estados das sementes nascem **sem SLA** (comportamento de hoje: nenhum
alerta novo); tenant configura `sla_dias` por estado no DSL quando quiser.

## Permissões e módulos

Nada novo: as fachadas mantêm os `require_permission`/`require_modulo` atuais de cada ato. A
edição de `workflow_definition` continua sob a transação `workflow` (módulo `protocolo`) — **isso
significa que editar DSL de transporte exige hoje o módulo protocolo**; aceito nesta fase e
registrado como pendência (mover a transação `workflow` para `comum`, decisão futura do Jorge).

## Testes (além das guardas de sempre)

- **Regressão por identidade**: as suítes das fases P5–C inteiras verdes sem edição semântica
  (só mensagens, se preciso) — é o teste do princípio reitor.
- Migration D1: upgrade/downgrade; backfill confere `entidade_tipo='processo'` em linha antiga;
  varredura RLS verde; unicidade de instância ativa provada por inversão (segunda instância ativa
  do mesmo alvo → IntegrityError).
- Lazy: entidade do estoque (sem instância) sofre um ato → instância nasce no estado equivalente
  e o ato completa.
- 409 do DSL: remover uma transição da definição do tenant → o ato correspondente responde 409
  com a mensagem citando slug/label/estado.
- Condição de DSL: `titular_suspenso` e `checklist_completo` provados nos dois sentidos.
- Estado novo de tenant: inserir estado intermediário no DSL de alvará → emissão entra nele e a
  coluna `situacao` grava o slug novo.
- HTTP com usuário comum num caminho de fachada por fluxo (lição do 500 do transporte).
- Vocabulário: asserções com os valores exatos (`suspenso` masculino na convocação etc.).

## Assunções que valem conferir

- `executar_transicao` do engine aceita ser chamada com contexto vindo de provider não-processo
  sem mexer na assinatura (se precisar de refactor, é interno ao D1).
- O componente do painel de processo é reaproveitável sem fork grande; se não for, o painel do
  transporte nasce próprio e menor.
- Remover CHECKs de situação (onde existirem nas 3 tabelas) não quebra nenhum consumidor que
  dependa do CHECK como documentação — a varredura é parte do D1/D2/D3 de cada fluxo.
