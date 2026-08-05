# Transporte Regulado P5.3 — atraso, faltosos, suspensão e reativação

**Data:** 2026-08-05
**Depende de:** P5.1 (ciclo, convocação, prazo) e P5.2 (catálogo, checklist, decisão), ambas em
`main` desde 2026-08-04.

## O problema

A P5.1 diz **quem tem de vir e quando**. A P5.2 diz **o que foi conferido e qual foi a decisão**.
Falta o que acontece com quem **não veio**: hoje o prazo vence e nada muda — a convocação continua
`convocado` para sempre, indistinguível de quem foi convocado ontem.

Esta fatia fecha o ciclo de vida da convocação: identificar o atraso, listar os faltosos, notificá-
los, e — como último recurso e sempre por ato humano — suspender e depois reativar.

## Decisões que governam o desenho

Quatro vieram do Jorge em 2026-08-05 e não são negociáveis aqui:

1. **A suspensão atinge só a convocação.** Não muda `Permissionario.situacao` nem
   `Empresa.situacao`, e não toca em alvará. É reversível e não tem efeito colateral em outro
   módulo. O que fazer com o alvará de um suspenso é decisão separada, fora desta fatia.
2. **Atraso não trava nada.** Quem perdeu o prazo continua podendo marcar checklist e ser deferido
   normalmente. Só a suspensão fecha o atendimento.
3. **Recurso reaproveita a trilha de decisão da P5.2.** Sem tabela nova de recurso: `suspensao` e
   `reativacao` entram como tipos em `recadastramento_decisao`, ao lado de `deferimento`,
   `indeferimento` e `reabertura`. Uma trilha única e cronológica por convocação.
4. **Notificação é manual e em lote nesta fatia.** O operador vê os faltosos e dispara. Sem Celery
   beat. Automatizar depois é barato **desde que o registro de envio já exista** — por isso o
   registro entra agora, mesmo com o disparo manual.

E uma que tomei, com a justificativa, porque é técnica e decorre da nº 2:

5. **"Em atraso" é estado DERIVADO, não coluna.** É `prazo < hoje AND situacao IN ('convocado',
   'em_analise')`, calculado na consulta. Não há coluna `em_atraso` e não há job que a mantenha.

   Persistir exigiria um job diário e criaria uma janela em que o banco discorda do calendário:
   quem vence à meia-noite só "fica atrasado" quando o job roda. Pior, o ajuste de prazo da P5.1
   teria de lembrar de recalcular — e esquecer isso seria silencioso. Derivado, ajustar o prazo
   desfaz o atraso na mesma consulta.

   O que torna isto seguro é justamente a decisão nº 2: **atraso não gateia nada**. É lente de
   leitura, não estado de máquina. Se um dia o atraso passar a bloquear, esta decisão tem de ser
   reexaminada — e o motivo está escrito aqui para que seja.

## Modelo de dados — migration `0083`

### `recadastramento_convocacao.situacao` ganha `suspenso`

Hoje: `convocado` | `em_analise` | `deferido` | `indeferido`. Passa a aceitar `suspenso`.

**Consequência que sai de graça e precisa de teste, não de código:** `SITUACOES_ABERTAS` já é
`("convocado", "em_analise")`, e tanto `marcar_item_recadastramento` quanto `decidir_recadastramento`
já recusam com **409** o que não está nela (verificado no código, não suposto). Logo, suspender
**já** bloqueia marcação e deferimento sem uma linha nova. O teste tem de afirmar isso
explicitamente — comportamento herdado que ninguém escreveu é o que some no próximo refactor.

**Mas a mensagem dos dois 409 fica errada**, e isso é código: hoje elas dizem *"Convocação já
decidida; reabra antes de alterar o checklist"* e *"…reabra antes de decidir"*. Para uma suspensa
nenhuma das duas é verdade — ela não foi decidida, e o caminho é **reativar**, não reabrir.
Mensagem que manda o operador para a porta errada custa um chamado de suporte por ocorrência, então
as duas passam a distinguir o caso suspenso. É a única alteração que a suspensão exige em código
existente da P5.2.

### `recadastramento_decisao.tipo` ganha `suspensao` e `reativacao`

Altera o CHECK da `0082`. O `parecer` continua obrigatório: suspender sem dizer por quê é o tipo de
ato que o cidadão contesta.

### Tabela nova: `recadastramento_notificacao`

Liga a convocação à `aprimora_py.notificacao` já criada pelo motor existente.

| coluna | tipo | nota |
|---|---|---|
| `id` | PK | |
| `tenant_id` | FK tenant, NOT NULL | |
| `id_convocacao` | FK convocação, NOT NULL | |
| `id_notificacao` | FK `aprimora_py.notificacao`, NOT NULL | |
| `id_usuario` | FK usuário, NOT NULL | quem disparou |
| `criado_em` | timestamp, NOT NULL | |

**Sem índice único.** É log: notificar duas vezes é legítimo e frequente (segundo aviso, terceiro
aviso). Mesmo raciocínio de `recadastramento_marca` na P5.2.

Boilerplate de RLS completo, com a GUC `app.tenant_id` e o segundo argumento `true` do
`current_setting` — os três detalhes que custaram 20 policies quebradas no `transporte_regulado`.

## Regras

### Suspender

- Exige `situacao ∈ SITUACOES_ABERTAS`. Já decidida ou já suspensa → **409**.
- Exige **prazo vencido**. Suspender quem está dentro do prazo é erro de operação, não escolha →
  **409**, com mensagem dizendo o prazo.
- Grava decisão `tipo='suspensao'` com parecer e usuário; muda a situação para `suspenso`.

### Reativar

- Exige `situacao == 'suspenso'` → senão **409**.
- Grava decisão `tipo='reativacao'` com parecer; volta para **`convocado`**.
- Volta para `convocado` e não para `em_analise` mesmo que estivesse em análise antes: reativar é
  recomeçar o atendimento, e inferir o estado anterior exigiria guardá-lo. As marcas de checklist
  **não** são apagadas — são log append-only e continuam valendo.

### `reabertura` não aceita suspenso

A `reabertura` da P5.2 destrava convocação **decidida**. Para suspensa o caminho é `reativacao`.
Deixar as duas portas abertas para o mesmo estado produziria trilhas ambíguas: uma suspensão
desfeita por "reabertura" não se distingue de um indeferimento desfeito.

### Notificar em lote

- Entrada: lista de ids de convocação do ciclo.
- Para cada uma, resolve o contato do regulado (`email`/`telefone` do permissionário ou da empresa)
  e chama `services/notificacoes.enviar`.
- **Regulado sem contato não derruba o lote.** `telefone` e `email` são anuláveis nos dois modelos,
  então isto é caso comum, não borda. Cada item volta com resultado próprio — `enviada` ou
  `sem_contato` — e a tela mostra a contagem dos dois. Falhar o lote inteiro por um cadastro
  incompleto tornaria o recurso inutilizável exatamente no município que mais precisa dele.
- Registra em `recadastramento_notificacao` **uma linha por notificação criada**.
- A ser confirmado na implementação: o motor resolve preferência **por usuário**, e aqui o
  destinatário não é usuário do sistema. Se a preferência bloquear destinatário sem `id_usuario`,
  o envio precisa ser explícito quanto a isso — e nunca silenciosamente descartado.

### Relatório de faltosos

Leitura, por ciclo. KPIs (convocados, atendidos, em atraso, suspensos) mais a lista dos atrasados
com nome, documento, prazo, dias de atraso e última notificação. Molde do relatório da P4.

## Endpoints

Todos sob `/api/v2/transporte-regulado/recadastramento`, reusando a transação
`transporte_regulado` — **nenhuma transação nova**, então `MODULO_TRANSACOES` não muda e a guarda de
modularização não é afetada.

| método | rota | ação |
|---|---|---|
| GET | `/ciclos/{id}/faltosos` | relatório |
| POST | `/convocacoes/{id}/suspender` | ato humano com parecer |
| POST | `/convocacoes/{id}/reativar` | ato humano com parecer |
| POST | `/ciclos/{id}/notificar` | lote |

**Rota de segmento literal antes da paramétrica irmã.** `/ciclos/{id}/faltosos` e
`/ciclos/{id}/notificar` são seguras por virem depois de `{id}`, mas a ordem entra na revisão:
o defeito das 422 por sombreamento ocorreu **três vezes** neste arquivo, e
`tests/test_guarda_ordem_rotas.py` reprova.

## Telas

- **`/m/transporte/recadastramento/[id]`** (convocados) ganha selo de atraso, filtro "só atrasados"
  e a ação de notificar em lote.
- **`/m/transporte/recadastramento/[id]/faltosos`** — o relatório. Precisa de `href` a partir da
  tela do ciclo **no mesmo PR**: `__tests__/rotas-modulo.test.ts` reprova página órfã desde a P5.2.
- A tela de atendimento ganha os botões Suspender e Reativar, cada um exigindo parecer, e o aviso
  de que suspensa não aceita marcação.

## Testes

Além do caminho feliz:

- Suspender dentro do prazo → 409.
- Suspender já suspensa → 409.
- **Suspensa recusa marcação de checklist e deferimento** — o comportamento herdado de
  `SITUACOES_ABERTAS`, afirmado explicitamente.
- Reativar o que não está suspenso → 409; reabertura sobre suspensa → 409.
- Atraso é derivado: **ajustar o prazo para o futuro tira a convocação dos faltosos na mesma
  consulta**, sem job. É o teste que prova a decisão nº 5.
- Faltoso sem `email` nem `telefone` volta `sem_contato` e **não** impede o resto do lote.
- Notificar duas vezes cria duas linhas — o log não deduplica.
- Pelo menos um **teste HTTP com usuário comum**, não super-usuário: em `auth/perms.py` o bypass de
  SU retorna antes do `getattr(item, action)`, e foi assim que 10 rotas do transporte devolveram 500
  por meses sem nenhum teste acusar.

Cada guarda nova entra com a inversão feita e registrada.

## Fora de escopo, deliberadamente

- **Notificação automática por job.** Decisão nº 4. O registro entra agora para que a automação
  depois seja só o gatilho.
- **Efeito da suspensão sobre alvará ou situação do regulado.** Decisão nº 1.
- **Prazo de recurso.** Sem entidade própria (decisão nº 3), não há prazo para interpor nem
  julgamento formal — a reativação é o deferimento do recurso, e o parecer é o julgamento. Se o
  município precisar cobrar prazo de recurso, é fatia própria.
- **UI de paginação nas telas do transporte.** Dívida conhecida, teto de 50, registrada no backlog e
  não desta fatia.
