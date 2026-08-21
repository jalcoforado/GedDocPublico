# Transporte Regulado — P7: ocorrências regulatórias

**Data:** 2026-08-21 · **Estado:** aprovado em chat, spec para revisão · **Antecede:** plano de implementação

## O que é

O último card tracejado do hub. Ocorrência é o registro de fiscalização e denúncia contra a
operação regulada: *o que aconteceu, contra quem, quem apurou, e o que se decidiu*. Duas portas
de entrada — o balcão municipal (fiscal, atendente) e o portal do cidadão — desembocando na
mesma entidade.

Quatro decisões do Jorge (2026-08-21):

- **Alvo em qualquer combinação** — permissionário, empresa e/ou veículo; o registro guarda o
  que se souber.
- **Ciclo de vida** — registrada → em apuração → procedente | improcedente | arquivada, com
  parecer no ato da decisão.
- **Catálogo de tipos por tenant** — o município cadastra a tipologia (recusa de corrida,
  veículo sem vistoria, excesso de lotação…); dá relatório por tipo.
- **Portal do cidadão incluso** — o cidadão registra, acompanha as suas e é notificado por
  e-mail na decisão.

Duas fatias no mesmo spec, executadas em sequência (o modelo é um só):

- **P7.1 — balcão**: catálogo, ocorrência, trilha, telas administrativas, card do hub.
- **P7.2 — portal**: endpoints do realm cidadão, telas em `app/cidadao/`, e-mail na decisão.

## Fora de escopo, explicitamente

- **Denúncia anônima.** O realm do portal é autenticado; denúncia sem login é outra política
  (moderação, abuso) e outra fatia.
- **Anexos/fotos na denúncia.** O módulo de anexos é do protocolo; trazê-lo para cá é fatia
  própria.
- **Prazo de apuração com alerta.** Mesma decisão do atraso na P5.3: derivável quando se quiser,
  e não gateia nada hoje.
- **Multa/sanção pecuniária.** Integraria com o módulo de pagamentos — fatia própria.
- **A ocorrência não gateia nada.** Não bloqueia alvará, ponto, linha, recadastramento nem muda
  `situacao` de ninguém — mesma decisão registrada em P5.3 (atraso) e P6 (ponto), pelas mesmas
  razões, e com o mesmo teste do não-gate.

## Modelo

Três tabelas em `transporte_regulado`, migration **0093** (head atual: 0092), boilerplate RLS
completo do módulo (GUC `app.tenant_id`, `current_setting(..., true)`, `ENABLE + FORCE`, grants
tabela+sequence a `aprimora_app`, sem grant a worker — nenhuma task escreve aqui; o e-mail da
P7.2 nasce pela mesma via síncrona que o resto do serviço de notificações usa).

### `ocorrencia_tipo`

| coluna | tipo | nota |
|---|---|---|
| `id` | serial PK | |
| `tenant_id` | int NOT NULL → `aprimora_py.tenant` | |
| `nome` | varchar(150) NOT NULL | "Recusa de corrida" |
| `descricao` | text NULL | orientação ao operador/cidadão |
| `ativo` | boolean NOT NULL default true | tipo inativo não aparece para registro novo; ocorrências antigas o mantêm |
| `criado_em` / `atualizado_em` / `excluido` | | padrão do módulo |

Índice único parcial `(tenant_id, lower(nome)) WHERE excluido = false`. Mesmo padrão do
`recadastramento_item` (P5.2), inclusive o limite conhecido lá registrado: editar o `nome`
muda o texto exibido em ocorrências antigas.

### `ocorrencia`

| coluna | tipo | nota |
|---|---|---|
| `id` | serial PK | |
| `tenant_id` | int NOT NULL | |
| `id_tipo` | int NOT NULL → `ocorrencia_tipo` | validação same-tenant no serviço |
| `origem` | varchar(20) NOT NULL, CHECK `IN ('fiscalizacao','denuncia','outro')` | |
| `data_fato` | date NOT NULL | quando aconteceu (≠ quando foi registrada) |
| `descricao` | text NOT NULL | |
| `id_permissionario` | int NULL → `permissionario` | FKs soft; same-tenant no serviço |
| `id_empresa` | int NULL → `empresa` | |
| `id_veiculo` | int NULL → `veiculo` | |
| `referencia_alvo` | varchar(200) NULL | o que o registrante souber ("placa ABC1D23", "ponto da matriz") |
| `id_cidadao` | int NULL → `utils.usuario_externo` | preenchido só quando origem é o portal (P7.2) |
| `situacao` | varchar(20) NOT NULL default `'registrada'`, CHECK `IN ('registrada','em_apuracao','procedente','improcedente','arquivada')` | |
| `observacoes` | text NULL | |
| `criado_em` / `atualizado_em` / `excluido` | | |

**O alvo é regra de serviço, não CHECK.** Registro de **balcão** exige ao menos um dos três
alvos (422 sem nenhum); **denúncia** pode nascer só com `referencia_alvo` — o cidadão raramente
sabe o id de um permissionário, e o vínculo formal é trabalho da apuração (`vinculo_alvo`,
abaixo). Um CHECK condicionado à `origem` amarraria política de negócio mutável no schema; a
regra que o banco não segura fica escrita aqui e provada por teste. Em compensação, **decidir
`procedente` exige alvo vinculado** — não se conclui procedência contra ninguém — e isso é 409
no serviço, com teste.

Índices: `(tenant_id, situacao)`, `(tenant_id, id_tipo)`, `(tenant_id, id_cidadao)` (a lista
"minhas denúncias" da P7.2 entra por aqui).

### `ocorrencia_andamento`

Trilha **append-only**, mesmo desenho de `recadastramento_decisao` (P5.2/P5.3): a decisão é um
ato com parecer na trilha cronológica, não uma coluna que se sobrescreve.

| coluna | tipo | nota |
|---|---|---|
| `id` | serial PK | |
| `tenant_id` | int NOT NULL | |
| `id_ocorrencia` | int NOT NULL → `ocorrencia` | |
| `ato` | varchar(20) NOT NULL, CHECK `IN ('registro','inicio_apuracao','anotacao','vinculo_alvo','decisao')` | |
| `parecer` | text NULL | obrigatório no serviço quando `ato = 'decisao'` |
| `id_usuario` | int NULL → `utils.usuario` | quem praticou; NULL quando o ato é o registro do próprio cidadão |
| `criado_em` | datetime NOT NULL | |
| `excluido` | boolean NOT NULL default false | trilha não se apaga; o soft-delete existe só pela consistência do módulo |

Sem `atualizado_em`: ato praticado não se edita.

## Regras (máquina de estados)

- **Registrar** (balcão): exige tipo ativo do tenant + ao menos um alvo same-tenant não
  excluído. Nasce `registrada` com ato `registro` na trilha.
- **Iniciar apuração**: só de `registrada` → `em_apuracao`, ato `inicio_apuracao`. Fora disso 409.
- **Anotar**: ato `anotacao` com parecer, permitido em `registrada` e `em_apuracao`. Em situação
  final → 409 (trilha encerrada se reabre por decisão humana? Não — reabertura fica fora de
  escopo; se um dia precisar, é ato novo com regra própria).
- **Vincular alvo**: ato `vinculo_alvo`, permitido em `registrada`/`em_apuracao`; grava os ids
  na própria `ocorrencia` (validação same-tenant) e registra na trilha quem vinculou.
- **Decidir**: só de `em_apuracao` → `procedente` | `improcedente` | `arquivada`, ato `decisao`
  com **parecer obrigatório**. `procedente` sem alvo vinculado → 409. Decidir duas vezes → 409.
- **Excluir ocorrência** (soft): permitido só em `registrada` (registro errado); depois que a
  apuração começou, a trilha é registro administrativo — arquive, não apague. 409 fora de
  `registrada`.
- **Tipos**: CRUD simples; excluir tipo **com ocorrências não excluídas** → 409 (apontamento
  órfão); inativar é sempre permitido.

## Superfície HTTP

### P7.1 — realm municipal

`ocorrencias_router`, prefixo `/api/v2/transporte-regulado/ocorrencias`; transação
`transporte_regulado` (a mesma do módulo, como P6/P6b — nada muda em `MODULO_TRANSACOES`).
GET sem action; escritas com action.

| método | rota | ação | permissão |
|---|---|---|---|
| GET | `/tipos` | catálogo (inclui inativos, flag) | leitura |
| POST | `/tipos` | — | `inserir` |
| PUT | `/tipos/{tipo_id}` | nome/descricao/ativo | `atualizar` |
| DELETE | `/tipos/{tipo_id}` | soft; 409 se em uso | `excluir` |
| GET | `` (raiz) | lista paginada; filtros `q` (descricao/referencia, **nas duas pontas** consulta+contagem), `situacao`, `origem`, `id_tipo` | leitura |
| POST | `` (raiz) | registrar (balcão) | `inserir` |
| GET | `/{ocorrencia_id}` | detalhe com trilha e alvos resolvidos | leitura |
| POST | `/{ocorrencia_id}/apurar` | iniciar apuração | `atualizar` |
| POST | `/{ocorrencia_id}/anotar` | anotação com parecer | `atualizar` |
| POST | `/{ocorrencia_id}/vincular-alvo` | ids de alvo | `atualizar` |
| POST | `/{ocorrencia_id}/decidir` | resultado + parecer | `atualizar` |
| DELETE | `/{ocorrencia_id}` | soft; só `registrada` | `excluir` |

**`/tipos` é literal irmã de `/{ocorrencia_id}` — declarada ANTES.** É o caso exato do defeito
que ocorreu três vezes neste arquivo; `test_guarda_ordem_rotas.py` varre de qualquer jeito.

### P7.2 — realm cidadão

`cidadao_denuncias_router`, prefixo `/api/v2/cidadao/denuncias`, dependência
`get_current_cidadao` (NUNCA `require_permission` — outro realm, sem transação municipal).

| método | rota | nota |
|---|---|---|
| GET | `/tipos` | só tipos ativos, para o formulário |
| POST | `` | cria ocorrência `origem='denuncia'`, `id_cidadao` do token, situacao `registrada`, sem alvo obrigatório |
| GET | `` | **só as do próprio cidadão** (`id_cidadao` do token); devolve tipo, descricao, situacao e datas — NUNCA trilha, pareceres ou alvos |

O contorno do que o cidadão vê é contrato: a saída do realm cidadão usa schema próprio
(`DenunciaCidadaoOut`) sem os campos internos — não reaproveitar `OcorrenciaOut` "filtrando na
tela", que é como campo interno vaza por engano.

### Notificação na decisão (P7.2)

Ao decidir ocorrência **com `id_cidadao`**: cria `Notificacao` (canal email,
`destinatario_email` = e-mail do `usuario_externo`; `id_usuario` NULL) com texto **neutro** —
"sua denúncia nº N foi analisada; acompanhe no portal" — sem resultado nem dados do apurado no
e-mail (e-mail vaza; o portal autenticado mostra a situação). Cidadão sem e-mail: segue sem
notificar, sem erro — registrado como limite conhecido. Segue o fluxo do serviço de notificações
existente (conferir `services/notificacoes*` na implementação e usar a mesma via, não INSERT
manual).

## Telas

### P7.1 (admin)

- **`/m/transporte/ocorrencias`** — lista com filtros (situação, origem, tipo, busca); colunas
  nº/tipo/alvo-ou-referência/origem/data do fato/situação. Registrar em dialog (tipo, data,
  descrição, alvos com busca no servidor — padrão Input+`q` da P6b, não Combobox).
- **`/m/transporte/ocorrencias/[id]`** — detalhe: dados + alvos, trilha cronológica, e os atos
  (apurar/anotar/vincular/decidir) habilitados conforme a situação.
- **`/m/transporte/ocorrencias/tipos`** — catálogo (CrudPage-like simples).
- Card do hub "Ocorrências" vira `ready` — **o último tracejado sai**; item de menu +
  `PERMISSOES_ESPERADAS` + `KEYWORDS_POR_HREF`, tudo no mesmo PR (guarda de órfã).

### P7.2 (portal)

- **`/cidadao/denuncias`** — lista das minhas, com situação; **`/cidadao/denuncias/nova`** —
  formulário (tipo, descrição, referência). Navegação a partir do layout do portal existente.
- `nginx`: rota `/cidadao` já está na regex — sem mexida. Conferir mesmo assim no PR.

## Testes

Backend, `test_transporte_p7_ocorrencias.py`:

- Catálogo: unicidade de nome por tenant; excluir tipo em uso → 409; inativo some do
  formulário e permanece nas ocorrências antigas.
- Balcão: registrar sem alvo → 422; com alvo cross-tenant → 404; máquina de estados completa
  (cada transição ilegal → 409, incluindo decidir de `registrada`, decidir duas vezes,
  anotar em situação final, excluir fora de `registrada`).
- `procedente` sem alvo → 409; com alvo vinculado via `vinculo_alvo` → passa.
- Trilha: cada ato gera linha; decisão exige parecer (422 sem).
- Cidadão (P7.2): cria denúncia sem alvo; **só vê as suas** (duas contas de cidadão no mesmo
  tenant, cross-check); a saída NÃO contém trilha/parecer/alvo (asserção sobre as chaves do
  JSON, não só sobre valores); decisão gera `Notificacao` email com destinatario correto e
  texto sem o resultado; cidadão sem e-mail não explode.
- **Isolamento RLS sob `app_session`** nas três tabelas (lição da P6b: a spec exigia e o plano
  dropou — desta vez o plano tem task explícita).
- **HTTP com usuário comum** municipal (não-SU, tenant contratando o módulo) e **HTTP com
  cidadão autenticado** (realm próprio — ver fixtures de cidadão nos testes do portal
  existentes).
- **Não-gate:** alvará continua sendo emitido para permissionário com ocorrência aberta e até
  procedente.

Frontend: guardas existentes (órfã, menus, hub — `semHref` vira `[]` e o teste do hub passa a
afirmar lista vazia, o que é um marco), `tsc` limpo.

## Assunções que valem conferir

- **Uma decisão encerra; não há reabertura.** Se o município precisar reabrir ocorrência
  decidida, é ato novo com regra própria (fatia futura). Encerrado ≠ apagado: a trilha fica.
- **Denúncia entra sem moderação prévia** — nasce `registrada` como qualquer outra. Se abuso
  virar problema real, moderação é fatia própria.
- **O e-mail é o único canal ao cidadão.** Sem sino in-app no portal (não existe essa infra) e
  sem WhatsApp.
