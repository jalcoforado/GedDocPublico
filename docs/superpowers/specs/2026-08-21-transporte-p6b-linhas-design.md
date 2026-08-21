# Transporte Regulado — P6b: linhas e itinerários

**Data:** 2026-08-21 · **Estado:** aprovado em chat, spec para revisão · **Antecede:** plano de implementação

## O que é

A metade que a P6 deixou por fazer, com nome que diz o que é. A P6 descobriu que "rotas/linhas"
eram duas coisas: táxi e mototáxi têm **ponto** (entregue), distrital e escolar têm **linha** —
um trajeto nomeado, outorgado a um operador, com itinerário e horários. O card "Linhas e
Itinerários" está tracejado no hub desde então.

O que o município precisa responder: *quais linhas existem, quem opera cada uma, por onde ela
passa, e em que horários sai.*

Três decisões do Jorge (2026-08-21):

- **Outorga a empresa OU permissionário** — mesmo desenho do veículo regulado: vínculo a
  empresa e/ou permissionário, ao menos um. Cobre distrital (empresas) e escolar (autônomos).
- **Itinerário como paradas ordenadas** — tabela filha com ordem + descrição textual, sem geo.
- **Horários em grade estruturada** — dia da semana + horário de partida, uma linha por par.

## Fora de escopo, explicitamente

- **Geolocalização.** Nem nas paradas, nem na linha. Mesma decisão da P6.
- **Sentido ida/volta.** A parada tem ordem única; se um dia o itinerário de volta divergir da
  ida invertida, é coluna nova (`sentido`) e fatia própria.
- **Vínculo veículo ↔ linha.** Qual ônibus roda em qual linha é escala operacional, não outorga.
- **Validação de conflito de horário entre linhas.** O município cadastra o que outorgou; o
  sistema não arbitra sobreposição.
- **A linha não gateia nada.** Não bloqueia alvará, não entra no recadastramento, não muda
  situação de ninguém — mesma decisão do ponto (P6) e do atraso (P5.3), pelas mesmas razões.

## Modelo

Três tabelas em `transporte_regulado`, migration **0085**, boilerplate RLS completo do módulo
(GUC `app.tenant_id`, `current_setting(..., true)`, `ENABLE + FORCE`, grants para
`aprimora_app` incluindo sequences — os três detalhes que custaram a `0078`).

### `linha`

| coluna | tipo | nota |
|---|---|---|
| `id` | serial PK | |
| `tenant_id` | int NOT NULL → `aprimora_py.tenant` | |
| `nome` | varchar(150) NOT NULL | "Linha Distrital Taperuaba" |
| `codigo` | varchar(40) NULL | código do ato administrativo, quando houver |
| `tipo_servico` | varchar(30) NOT NULL | vocabulário livre do módulo; formulário sugere `distrital`/`escolar`, banco não impõe (mesma razão registrada na P6) |
| `id_empresa` | int NULL → `empresa` | validação same-tenant no serviço |
| `id_permissionario` | int NULL → `permissionario` | idem |
| `origem` | varchar(150) NOT NULL | ponta inicial, texto |
| `destino` | varchar(150) NOT NULL | ponta final, texto |
| `situacao` | varchar(20) NOT NULL default `'ativa'` | `ativa` \| `inativa` — **feminino**: `linha` é feminino, e a lição da P5.1 (`ativo` × `ativa` convocando zero empresas sem erro) é que o vocabulário segue o gênero da entidade e os testes afirmam o valor exato |
| `observacoes` | text NULL | |
| `criado_em` / `atualizado_em` / `excluido` | | padrão do módulo |

Restrições no banco, não só no serviço:

```sql
-- Ao menos um operador. No veículo essa regra mora só no serviço; aqui vai
-- para o banco porque é barata, não tem problema de concorrência e a família
-- P5/P6 já provou que regra fora do banco não segura acesso direto.
ALTER TABLE transporte_regulado.linha
  ADD CONSTRAINT ck_linha_tem_operador
  CHECK (id_empresa IS NOT NULL OR id_permissionario IS NOT NULL);

-- Duas linhas com o mesmo nome no mesmo município são erro de digitação.
CREATE UNIQUE INDEX ux_linha_nome
  ON transporte_regulado.linha (tenant_id, lower(nome))
  WHERE excluido = false;
```

### `linha_parada`

| coluna | tipo | nota |
|---|---|---|
| `id` | serial PK | |
| `tenant_id` | int NOT NULL | |
| `id_linha` | int NOT NULL → `linha` | |
| `ordem` | int NOT NULL, `CHECK (ordem > 0)` | |
| `descricao` | varchar(200) NOT NULL | referência textual: "Praça da Matriz", "Entrada do Assentamento" |
| `observacoes` | text NULL | |
| `criado_em` / `atualizado_em` / `excluido` | | |

**`ordem` NÃO tem índice único, de propósito.** Um único parcial em `(id_linha, ordem)` tornaria
reordenar uma dança de colisões (trocar 2↔3 exige estacionar um dos dois num número livre). A
leitura ordena por `(ordem, id)` — estável — e ordem duplicada é inofensiva: as duas paradas
aparecem, em posição determinística. A tela reordena mandando a lista completa; o serviço
renumera 1..N numa transação só.

### `linha_horario`

| coluna | tipo | nota |
|---|---|---|
| `id` | serial PK | |
| `tenant_id` | int NOT NULL | |
| `id_linha` | int NOT NULL → `linha` | |
| `dia_semana` | smallint NOT NULL, `CHECK (dia_semana BETWEEN 0 AND 6)` | 0=segunda … 6=domingo |
| `partida` | time NOT NULL | |
| `criado_em` / `excluido` | | sem `atualizado_em`: horário não se edita, se apaga e recria — é um par (dia, hora), não um registro com ciclo de vida |

```sql
-- Mesmo horário duas vezes no mesmo dia é erro de digitação, e a
-- exclusividade mora no banco (lição P5.1/P6): duas requisições concorrentes
-- passariam as duas por uma checagem de serviço.
CREATE UNIQUE INDEX ux_linha_horario
  ON transporte_regulado.linha_horario (id_linha, dia_semana, partida)
  WHERE excluido = false;
```

O serviço também checa — para devolver 409 com mensagem útil — mas quem garante é o índice, e
**há teste por inversão**: inserção direta no banco, contornando o serviço, esperando
`IntegrityError`.

## Regras

- **Criar/editar linha** exige: operador (empresa e/ou permissionário) do mesmo tenant e não
  excluído — FK "soft", validação same-tenant explícita, 404 cross-tenant. Nome duplicado → 409.
- **Excluir linha** (soft) leva junto paradas e horários? **Não.** Soft-delete só da linha; as
  filhas ficam intactas e invisíveis (toda leitura entra pela linha). Restaurar uma linha um dia
  restaura o itinerário de graça; cascatear o soft-delete destruiria isso sem dar nada em troca.
- **Inativar linha** é livre — linha inativa é linha que não opera, o cadastro permanece.
- **Paradas**: criar informa `descricao` (a `ordem` default é a última + 1); **reordenar** é um
  endpoint que recebe a lista completa de ids na nova ordem e renumera 1..N numa transação —
  id faltando ou sobrando → 422 (payload não bate com o estado, o cliente está desatualizado).
- **Horários**: criar e apagar, sem editar. Duplicado → 409 pela via do serviço, índice por trás.

## Superfície HTTP

`linhas_router` novo em `routers/transporte_regulado.py`, prefixo `/api/v2/transporte-regulado`,
registrado em `main.py`. Transação `transporte_regulado` — **a mesma do resto do módulo**, como
na P6: nenhum código novo em `utils.transacao`, nada muda em `MODULO_TRANSACOES`. GETs com
`require_modulo("transporte")` + `require_permission("transporte_regulado")` sem action;
escritas com a action correspondente.

| método | rota | ação | permissão |
|---|---|---|---|
| GET | `/linhas` | lista paginada; filtros `q` (nome OU código — **nas duas pontas da consulta**: condição duplicada entre lista e contagem já mordeu duas vezes no módulo), `tipo_servico`, `situacao` | leitura |
| POST | `/linhas` | — | `inserir` |
| GET | `/linhas/{id}` | detalhe com paradas ordenadas e grade de horários embutidas (uma viagem, a tela de detalhe consome tudo) | leitura |
| PUT | `/linhas/{id}` | — | `atualizar` |
| DELETE | `/linhas/{id}` | soft-delete | `excluir` |
| POST | `/linhas/{id}/paradas` | acrescenta ao fim | `atualizar` |
| PUT | `/linhas/{id}/paradas/ordem` | **literal antes da paramétrica** — recebe `[ids]`, renumera | `atualizar` |
| PUT | `/linhas/{id}/paradas/{parada_id}` | edita descrição | `atualizar` |
| DELETE | `/linhas/{id}/paradas/{parada_id}` | soft-delete | `atualizar` |
| POST | `/linhas/{id}/horarios` | — | `atualizar` |
| DELETE | `/linhas/{id}/horarios/{horario_id}` | soft-delete | `atualizar` |

`/paradas/ordem` é o caso exato do defeito que ocorreu três vezes neste arquivo: literal irmã de
`/{parada_id}`. Declarada antes; `test_guarda_ordem_rotas.py` varre de qualquer jeito.

Paradas e horários usam `atualizar` (não `inserir`/`excluir`): são conteúdo da linha, e quem
pode editar a linha pode editar seu itinerário. Fragmentar em três permissões daria granularidade
que nenhum município pediu.

## Telas

- **`/m/transporte/linhas`** — lista com busca, tipo e situação; coluna do operador (razão
  social ou nome) e contagem de horários/semana. Criar/editar em dialog (`ui/dialog`).
- **`/m/transporte/linhas/[id]`** — detalhe: dados + operador; **itinerário** como lista
  ordenada com reordenação (mover para cima/baixo — sem drag-and-drop: botões funcionam com
  teclado de graça e não pedem dependência nova); **grade de horários** por dia da semana,
  adicionar/remover na própria grade.

Costura no mesmo PR, porque a guarda de órfã reprova o contrário e porque a P2/P4 passou meses
invisível: card do hub vira `ready` (em `lib/transporte-hub.ts`), item de menu em
`lib/menus/transporte.ts` (+ `PERMISSOES_ESPERADAS` em `menus.test.tsx`), `KEYWORDS_POR_HREF`
do Ctrl+K. Tipos em `api.ts`: `request<Paginated<LinhaTransporte>>` na lista — o tipo honesto,
não `X[]`. Interface `LinhaTransporte` (não `Linha`: colide com conceito de linha de tabela).

Nada a mexer no `nginx/default.conf`: `/m/` já está na regex.

## Testes

Backend, `test_transporte_p6b_linhas.py`:

- CRUD; unicidade de nome por tenant; linha sem operador → 422 (payload inválido — o CHECK do
  banco é a rede, o schema/serviço é quem responde); operador de outro tenant →
  404; **operador excluído → recusa** (FK soft não filtra sozinha).
- `situacao` da linha é `ativa`/`inativa` — o teste afirma o valor **exato**, pela lição
  `ativo`×`ativa` da P5.1.
- Paradas: acrescentar ganha `ordem` última+1; reordenar renumera 1..N; reordenar com id
  faltando/sobrando → 422; leitura ordena por `(ordem, id)` com ordem duplicada plantada à mão.
- Horários: criar, duplicado → 409, apagar libera o par para recriação.
- **A prova do índice**: inserção direta de horário duplicado, contornando o serviço →
  `IntegrityError`.
- **Isolamento cross-tenant** nas três tabelas (com `app_session`, não `admin_session`).
- **Pelo menos um teste HTTP com usuário comum** não-SU, com o tenant contratando o módulo —
  o bypass de SU esconde 500 de action errada, já aconteceu com dez rotas deste módulo.
- **O teste do não-gate**: alvará continua sendo emitido para operador de linha, e linha
  inativada não muda situação de ninguém.

Frontend: `rotas-modulo.test.ts` (órfã/prefixo) e `menus.test.tsx` já guardam a costura;
`transporte-hub.test.tsx` atualiza a lista de cards tracejados (sai "Linhas e Itinerários",
fica só "Ocorrências"); `tsc --noEmit` limpo.

Toda guarda nova provada por inversão antes de considerar a fatia pronta.

## Assunções que valem conferir

- **Uma linha, um operador de cada tipo** (no máximo uma empresa E um permissionário, como no
  veículo). Se consórcio/rodízio de operadores for caso real em Sobral, o desenho vira tabela de
  vínculo N:N com vigência — foi oferecido e descartado por ora (2026-08-21).
- **Itinerário único por linha** (sem sentido ida/volta). Soltar depois é coluna nova com
  default; apertar não se aplica.
