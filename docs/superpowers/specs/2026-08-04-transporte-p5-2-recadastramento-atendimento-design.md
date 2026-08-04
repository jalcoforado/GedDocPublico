# Transporte Regulado P5.2 — Atendimento e fechamento do recadastramento

**Data:** 2026-08-04 · **Status:** decisões do Jorge tomadas; spec para revisão

## 1. O que é

A P5.1 entregou **quem tem de vir e quando**. A P5.2 entrega **atender e fechar**: o servidor abre
um convocado, confere os documentos item a item, o sistema confronta as vistorias dos veículos dele,
e a decisão de deferir ou indeferir é registrada com parecer e autor.

Continuação de `2026-08-04-transporte-p5-1-recadastramento-ciclo-design.md`. Leia-a antes: o
vocabulário (`ciclo`, `convocação`, `regulado`) e a armadilha masculino/feminino vêm de lá.

**P5.2 não entrega:** estado em atraso, relatório de faltosos, suspensão, notificação. Tudo isso é
P5.3.

### Decisões do Jorge

| # | Decisão |
|---|---|
| D6 | **Catálogo de itens por tenant**, reusado por todo ciclo — molde do `pagamentos.checklist_item`. |
| D7 | **Cada item declara a quem se aplica**: `permissionario`, `empresa` ou `ambos`. |
| D8 | **Todos os veículos ativos** do regulado precisam de vistoria aprovada válida. |
| D9 | **Fechamento é ato humano com parecer** — deferir/indeferir, com autor registrado. |

### Assunções que eu tomei, e que o Jorge pode reverter

**A1 — Regulado sem veículo nenhum passa na amarra da vistoria, por vacuidade.** "Todos os veículos
ativos aprovados" é verdade quando não há nenhum. A exigência só morde quem tem veículo. Mas a tela
distingue **"nenhum veículo cadastrado"** de **"todos em dia"**: as duas situações satisfazem a
regra e não significam a mesma coisa, e tratá-las como iguais esconderia cadastro incompleto.

**A2 — Vistoria com `data_validade` nula conta como válida.** É o padrão do cadastro herdado;
bloquear por ausência de dado puniria o regulado por falha do município. A tela marca essas como
"sem validade registrada", também distinguíveis.

Ambas são **permissivas de propósito**: a P5.2 introduz uma trava nova, e trava nova que bloqueia
por falta de dado gera fila no balcão em vez de conformidade.

## 2. Fatos do código que moldam o desenho

Verificados em `backend/app/models/transporte_regulado.py` e `schemas/` em 2026-08-04.

```python
VeiculoReguladoSituacao = Literal["ativo", "pendente", "suspenso", "cassado", "inativo"]
ResultadoAvaliacao      = Literal["pendente", "aprovado", "reprovado", "condicional"]
```

**Veículo usa masculino (`ativo`), como permissionário.** A armadilha da P5.1 não se repete aqui —
mas `Empresa.situacao` continua feminina, e a P5.2 volta a filtrar regulados por tipo.

`VeiculoRegulado` tem `id_permissionario` e `id_empresa`, os dois anuláveis: é assim que se sabe de
quem é o veículo. `VeiculoVistoria` tem `resultado`, `data_validade` (anulável) e `id_auditor`.

**`condicional` NÃO é `aprovado`.** A amarra exige `aprovado`. Aceitar condicional seria decisão de
produto, não detalhe de implementação.

## 3. Modelo de dados

Três tabelas em `transporte_regulado`, com o boilerplate de RLS que o `CLAUDE.md` exige.

### `recadastramento_item` — o catálogo (D6, D7)

| Coluna | Tipo | Nota |
|---|---|---|
| `id`, `tenant_id` | | |
| `descricao` | `String(200)` | "CNH válida", "Contrato social" |
| `aplica_a` | `String(20)` | `permissionario` \| `empresa` \| `ambos` |
| `obrigatorio` | `Boolean` | default `true`; só obrigatório trava o deferimento |
| `ordem` | `Integer` | ordenação na tela |
| `ativo` | `Boolean` | item desligado não conta, mas marcas antigas continuam visíveis |
| `criado_em`, `atualizado_em`, `excluido` | | |

Único parcial `(tenant_id, descricao) WHERE excluido = false`.

**Por tenant e não por ciclo:** a lista de documentos de um município muda pouco entre campanhas.
Amarrar ao ciclo obrigaria a redigitar tudo todo ano e não haveria de onde herdar.

### `recadastramento_marca` — as marcações (append-only)

| Coluna | Tipo | Nota |
|---|---|---|
| `id`, `tenant_id` | | |
| `id_convocacao` | FK | |
| `id_item` | FK `recadastramento_item` | |
| `marcado` | `Boolean` | |
| `observacao` | `String(255)`, nullable | |
| `id_usuario` | FK `utils.usuario`, nullable | quem marcou |
| `criado_em` | `DateTime` | |

**Append-only, molde do `pagamentos.debito_checklist_marca`.** O estado corrente de um item é a
marca **mais recente** daquele par. Desmarcar depois de marcar é informação, não erro: um servidor
que marcou e voltou atrás deixou rastro, e sobrescrever a linha apagaria isso.

Sem índice único em `(id_convocacao, id_item)` — seria justamente o contrário de append-only.
Índice de leitura em `(tenant_id, id_convocacao)`.

### `recadastramento_decisao` — deferir, indeferir, reabrir (D9)

| Coluna | Tipo | Nota |
|---|---|---|
| `id`, `tenant_id` | | |
| `id_convocacao` | FK | |
| `tipo` | `String(20)` | `deferimento` \| `indeferimento` \| `reabertura` |
| `parecer` | `Text` | obrigatório nos três |
| `id_usuario` | FK `utils.usuario` | **NOT NULL** — decisão sem autor não é decisão |
| `criado_em` | `DateTime` | |

**Tabela, e não colunas na convocação** — diferente do `ajustar_prazo` da P5.1, que usa colunas.
A diferença é que ajuste de prazo tem um estado corrente e um valor original, enquanto a decisão é
uma **sequência**: indeferido, reaberto, deferido. Guardar em coluna obrigaria a apagar a decisão
anterior a cada reabertura, e é exatamente o histórico que a P5.3 vai precisar para o relatório.

`convocacao.situacao` continua sendo o estado corrente, desnormalizado para a listagem não precisar
de subconsulta por linha.

### `recadastramento_convocacao.situacao` — valores novos

`convocado` (P5.1) → `em_analise` → `deferido` \| `indeferido`, e `reabertura` volta para
`em_analise`. P5.3 acrescenta o atraso.

`em_analise` é **gravado**, não derivado: a primeira marca o define. Derivar exigiria uma
subconsulta por linha na listagem, e a P5.3 vai filtrar por ele no relatório.

## 4. A amarra da vistoria (D8)

Para um regulado, `situacao_vistorias()` devolve três coisas — e são três, não um booleano, porque a
tela precisa distinguir os casos de A1 e A2:

- **`veiculos_ativos`** — os `VeiculoRegulado` dele com `excluido = false` e `situacao = "ativo"`.
- **`pendentes`** — os que não têm vistoria `aprovado` válida.
- **`satisfeita`** — `pendentes` vazio.

Vistoria conta se: `resultado = "aprovado"`, `excluido = false`, e `data_validade IS NULL` ou
`data_validade >= hoje` (A2). A referência é **hoje**, não o prazo da convocação — quem decide é o
servidor, no dia em que decide.

Zero veículos ativos → `satisfeita = true` com `veiculos_ativos = []` (A1). A tela diz "nenhum
veículo cadastrado", não "todos em dia".

## 5. Fechamento

**Deferir exige completude; indeferir não.** É a assimetria central desta fatia:

- **Deferir** — todos os itens `obrigatorio` e `ativo` aplicáveis ao tipo do regulado marcados
  `true` (pela marca mais recente), **e** a amarra da vistoria satisfeita. Fora disso, 409.
- **Indeferir** — permitido a qualquer momento. Indeferir por falta de documento é o caso real; um
  sistema que exigisse completude para indeferir só saberia dizer sim.

Parecer obrigatório nos dois, e na reabertura. Autor sempre do token, nunca do payload.

**Reabrir** volta a convocação para `em_analise`. Existe para que um deferimento errado não vire
dívida de SQL — decisão minha, não pedida: fechamento sem desfazer, num sistema municipal, acaba em
`UPDATE` manual no banco de produção.

Ciclo `encerrado` recusa marcar, decidir e reabrir (409), como já recusa gerar e ajustar prazo.

**Item novo no catálogo não reabre convocação fechada.** O fechamento é uma fotografia do que se
exigia naquele dia. Reabrir em massa por mudança de catálogo remarcaria trabalho já concluído.

## 6. Testes

`backend/tests/test_transporte_p5_2_atendimento.py`.

| O que trava | Por quê |
|---|---|
| Item `aplica_a=empresa` não aparece para permissionário, e vice-versa | D7. **Um de cada tipo no mesmo tenant**, senão o filtro invertido passa. |
| Item `ambos` aparece para os dois | Controle positivo do anterior. |
| Marca é append-only | Marcar, desmarcar, marcar: três linhas, e o estado corrente é a última. |
| Estado corrente vem da marca mais recente | Ordenar por `id` errado inverte tudo em silêncio. |
| Item `obrigatorio=false` não trava o deferimento | Com um obrigatório pendente no mesmo cenário como controle. |
| Item `ativo=false` não trava | E a marca antiga dele continua legível. |
| Deferir sem completude é 409; com completude, 200 | A negativa e o controle. |
| **Indeferir sem completude é 200** | A assimetria. Um teste que só exercitasse deferir não a veria. |
| Veículo ativo sem vistoria aprovada trava o deferimento | Com outro regulado em dia como controle. |
| Vistoria `condicional` NÃO satisfaz | `condicional` é o valor que parece aprovado e não é. |
| Vistoria vencida não satisfaz; `data_validade` nula satisfaz | A2, nos dois sentidos. |
| Regulado sem veículo: `satisfeita=true` e `veiculos_ativos=[]` | A1 — e o teste afirma sobre os dois campos, porque só o booleano não distinguiria. |
| Veículo `pendente`/`suspenso` não entra na conta | Só `ativo`. |
| Decisão grava autor do token | E `id_usuario` é NOT NULL no banco. |
| Reabrir volta para `em_analise` e preserva as decisões anteriores | Três linhas em `recadastramento_decisao`. |
| Ciclo encerrado recusa marcar/decidir/reabrir | 409, com controle antes de encerrar. |
| Isolamento cross-tenant | Item e convocação de outro tenant: 404. |
| HTTP com **usuário comum** | O rito inteiro, não-SU. `CLAUDE.md`: a suíte inteira exercitando SU escondeu um 500. |

**Cada negativa com controle positivo na mesma sessão.** **Prova por inversão obrigatória** em pelo
menos quatro: filtro de `aplica_a` invertido; ordenação da marca mais recente invertida;
`condicional` aceito como aprovado; completude exigida também no indeferimento.

## 7. Frontend

- **`/m/transporte/recadastramento/itens`** — CRUD do catálogo. Segmento estático irmão de
  `[id]`; o Next resolve estático antes de dinâmico, e ids são numéricos, então não há colisão real
  — mas é a mesma classe de armadilha que já custou três 422 no `transporte_regulado.py`, e há
  teste afirmando que a rota existe.
- **`/m/transporte/recadastramento/[id]/convocacao/[convocacaoId]`** — o atendimento: checklist com
  observação por item, painel das vistorias, e os botões de deferir/indeferir/reabrir.
- O painel de vistorias mostra **três estados distintos**: "todos em dia", "nenhum veículo
  cadastrado" (A1) e a lista dos pendentes. Colapsar os dois primeiros num "OK" verde apagaria
  exatamente a informação que A1 pede para preservar.
- O botão **Deferir fica desabilitado** enquanto faltar item ou vistoria, com o motivo ao lado.
  **Indeferir nunca desabilita** (§5).
- Busca e paginação no servidor onde houver lista. `Paginated<T>` no `api.ts`;
  `test_guarda_contrato_paginado.py` reprova o contrário.

**Sem mudança no nginx** — `/m` já está na regex.

## 8. Riscos

**A tabela de marcas cresce sem teto.** Append-only por convocação × item × edição. Um município com
2.000 regulados e 10 itens gera ~20.000 linhas por ciclo, mais as remarcações. É pequeno para
Postgres e não justifica poda nesta fatia, mas justifica o índice `(tenant_id, id_convocacao)`.

**O catálogo é global ao tenant e o histórico é por convocação.** Editar a `descricao` de um item
muda o texto exibido em fechamentos antigos. Preservar o texto no momento da marca resolveria, ao
custo de duplicar dado; fica registrado como limite conhecido, não corrigido aqui.
