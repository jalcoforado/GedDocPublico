# Transporte Regulado — P6: pontos e vagas

**Data:** 2026-08-05 · **Estado:** spec, aguardando aprovação · **Antecede:** plano de implementação

## O que é

O roadmap dizia só "P6 — Rotas / linhas". Ao escopar, a primeira coisa que apareceu é que
**"rota/linha" são duas coisas diferentes**, e táxi e mototáxi — que é o volume do balcão — não têm
linha nenhuma: têm **ponto**. Uma tabela genérica tentando ser as duas serviria mal a ambas.

Decisão do Jorge: **esta fatia é o ponto**. Linha/itinerário (distrital, escolar) fica para uma
fatia própria, se e quando for pedida.

O objeto regulatório é o **ponto de estacionamento** — a praça onde os táxis ficam — com um número
finito de **vagas numeradas**, cada uma ocupada por no máximo um permissionário de cada vez. O que
o município precisa responder: *quais pontos existem, quantas vagas cada um tem, quem está em cada
vaga hoje, e quem estava antes.*

## Fora de escopo, explicitamente

- **Linha, itinerário, horário, outorga de linha.** Outra fatia.
- **Geolocalização.** Nem `lat/lng`, nem mapa. Endereço em texto resolve o cadastro; mapa é
  funcionalidade própria e não é o que falta hoje.
- **Qualquer bloqueio.** Ver "O ponto não gateia nada", abaixo.
- **Fila de espera por vaga.** Disputa de vaga vaga (sic) é processo administrativo; se virar
  necessidade, é fatia própria e provavelmente usa protocolo, não uma tabela nova aqui.

## Modelo

Duas tabelas em `transporte_regulado`, migration **0084**.

### `ponto`

| coluna | tipo | nota |
|---|---|---|
| `id` | serial PK | |
| `tenant_id` | int NOT NULL → `aprimora_py.tenant` | |
| `nome` | varchar(150) NOT NULL | "Ponto da Praça do Patrocínio" |
| `codigo` | varchar(40) NULL | código do ato administrativo, quando houver |
| `tipo_servico` | varchar(30) NOT NULL | mesmo vocabulário livre do resto do módulo |
| `logradouro` / `numero` / `complemento` / `bairro` / `cep` | | endereço em texto |
| `vagas_total` | int NOT NULL, `CHECK (vagas_total > 0)` | |
| `situacao` | varchar(20) NOT NULL default `'ativo'` | `ativo` \| `inativo` |
| `observacoes` | text NULL | |
| `criado_em` / `atualizado_em` / `excluido` | | padrão do módulo |

Índice único parcial: `(tenant_id, lower(nome)) WHERE excluido = false`. Dois pontos com o mesmo
nome no mesmo município são erro de digitação, não cadastro legítimo.

`tipo_servico` **não** ganha `CHECK` restringindo a `taxi|mototaxi`. O resto do módulo trata o campo
como `String(30)` livre, e apertar só aqui criaria uma incoerência que o próximo desenvolvedor
teria de descobrir. Motofrete com ponto é plausível; o formulário sugere, o banco não impõe.

### `ponto_ocupacao`

| coluna | tipo | nota |
|---|---|---|
| `id` | serial PK | |
| `tenant_id` | int NOT NULL | |
| `id_ponto` | int NOT NULL → `ponto` | |
| `numero_vaga` | int NOT NULL, `CHECK (numero_vaga > 0)` | |
| `id_permissionario` | int NOT NULL → `permissionario` | validação same-tenant no serviço |
| `desde` | date NOT NULL | |
| `ate` | date NULL | NULL = vigente |
| `motivo_liberacao` | varchar(30) NULL | preenchido ao encerrar |
| `observacoes` | text NULL | |
| `criado_em` / `atualizado_em` / `excluido` | | |

**Não existe tabela de vaga.** A vaga é um número, e uma tabela cujo único conteúdo é um inteiro
sequencial é peso sem contrapartida. O que a tabela de vaga daria — exclusividade garantida pelo
banco — os índices abaixo dão igual.

Os dois índices que carregam as regras:

```sql
-- Uma vaga, um ocupante.
CREATE UNIQUE INDEX ux_ponto_ocupacao_vaga_vigente
  ON transporte_regulado.ponto_ocupacao (id_ponto, numero_vaga)
  WHERE ate IS NULL AND excluido = false;

-- Um permissionário, uma vaga.
CREATE UNIQUE INDEX ux_ponto_ocupacao_permissionario_vigente
  ON transporte_regulado.ponto_ocupacao (tenant_id, id_permissionario)
  WHERE ate IS NULL AND excluido = false;
```

**A exclusividade mora no banco, não num `if`.** É a lição da P5.1, escrita naquela spec e
reaproveitada aqui: duas requisições concorrentes de "ocupar a vaga 3" passariam as duas por uma
checagem de serviço, e o segundo `INSERT` gravaria. O serviço continua checando — para devolver 409
com mensagem útil em vez de erro de integridade — mas quem garante é o índice. **Há teste que
prova isso removendo a checagem do serviço e mostrando que o banco ainda barra.**

## Regras

- **Ocupar** exige: ponto ativo, `1 ≤ numero_vaga ≤ ponto.vagas_total`, permissionário do mesmo
  tenant e não excluído. Vaga ocupada → **409**. Permissionário já lotado em outro ponto → **409**,
  com a mensagem dizendo *onde* ele está (senão o atendente não sabe o que fazer).
- **Liberar** encerra a vigência (`ate`, `motivo_liberacao`); não apaga linha.
- **Transferência é liberar + ocupar**, dois atos. Não há endpoint atômico: o histórico fica mais
  legível com os dois eventos, e uma transferência que falhe no meio deixa a vaga **vazia e
  visível**, que é melhor do que deixar estado inconsistente. Limite conhecido: entre um ato e outro
  a vaga fica disputável. Para um balcão municipal isso é aceitável; se um dia não for, o conserto é
  um endpoint de transferência numa transação só.
- **Reduzir `vagas_total`** abaixo do maior `numero_vaga` vigente → **409**. Permitir silenciosamente
  deixaria ocupação órfã fora do mapa da tela — presente no banco, invisível na interface, que é o
  pior dos dois mundos.
- **Excluir ponto** com ocupação vigente → **409**. Soft-delete de ponto não deve deixar ocupação
  apontando para nada.
- **Inativar ponto** é permitido com ocupação vigente: ponto inativo é ponto que não recebe *novos*
  ocupantes, e desalojar todo mundo como efeito colateral de uma mudança de situação seria
  destrutivo e não pedido.

### O ponto não gateia nada

Decisão do Jorge, e é a mesma da P5.3 com o atraso: **nesta fatia o ponto não bloqueia alvará, não
entra na checklist do recadastramento e não muda `Permissionario.situacao`.**

Duas razões. A primeira é que o cadastro herdado não tem ponto nenhum — amarrar o alvará à vaga
travaria emissão no dia seguinte ao deploy, para todo mundo. A segunda é que a regra fica melhor
decidida com o dado na mão do que de antemão.

Como na P5.3, **há teste só para isso** — que emitir alvará para permissionário sem vaga continua
funcionando. Sem ele, alguém "melhora" a coisa amarrando as duas, e o efeito atravessa o módulo
inteiro sem aparecer em revisão.

## Superfície HTTP

`pontos_router`, prefixo `/api/v2/transporte-regulado`, transação `transporte_regulado` (a mesma do
resto do módulo — **não** há código novo em `utils.transacao`, logo nada muda em
`MODULO_TRANSACOES`).

| método | rota | ação | permissão |
|---|---|---|---|
| GET | `/pontos` | lista paginada, filtros `q`, `tipo_servico`, `situacao` | leitura |
| POST | `/pontos` | — | `inserir` |
| GET | `/pontos/{id}` | — | leitura |
| PUT | `/pontos/{id}` | — | `atualizar` |
| DELETE | `/pontos/{id}` | soft-delete | `excluir` |
| GET | `/pontos/{id}/mapa` | as `vagas_total` vagas com o ocupante vigente de cada | leitura |
| GET | `/pontos/{id}/ocupacoes` | histórico paginado, vigentes e encerradas | leitura |
| POST | `/pontos/{id}/ocupacoes` | ocupar | `atualizar` |
| POST | `/pontos/{id}/ocupacoes/{ocupacao_id}/liberar` | liberar | `atualizar` |

Três coisas do checklist do módulo que **têm** de acontecer, porque cada uma já mordeu antes:

1. **`pontos_router` registrado em `main.py`** com `prefix="/api/v2"`. Router novo não registrado
   não existe, e nada acusa.
2. **`/pontos/{id}/mapa` e `/ocupacoes` são literais depois de paramétrica** — ordem certa, mas
   `tests/test_guarda_ordem_rotas.py` varre isso de qualquer jeito. O defeito ocorreu **três vezes**
   neste mesmo arquivo.
3. **Endpoint paginado → `request<Paginated<X>>` em `api.ts`.** Declarar `X[]` deixa o `tsc` verde e
   a tela diz "nenhum registro" com dado no banco. `test_guarda_contrato_paginado.py` reprova, mas o
   tipo tem de nascer certo.

## Telas

- **`/m/transporte/pontos`** — lista com busca, tipo e situação; criar/editar/excluir. Coluna
  "ocupação" mostrando `ocupadas/total`, que é o número que o gestor procura.
- **`/m/transporte/pontos/[id]`** — o **mapa de vagas**: as `vagas_total` vagas em grade, cada uma
  livre ou com o nome do ocupante, e os atos de ocupar/liberar na própria vaga. Abaixo, o histórico.

**Link a partir do hub do transporte no mesmo PR.** A guarda de página órfã reprova subpágina de
`m/` sem `href` — e a P2/P4 passou meses com telas prontas alcançáveis só digitando a URL. A guarda
só passou a valer de verdade na P5.3; agora vale.

Nada a mexer no `nginx/default.conf`: `/m/` já está na regex.

## Testes

Backend, arquivo `test_transporte_p6_pontos.py`:

- CRUD e unicidade de nome por tenant.
- Ocupar: caminho feliz; vaga fora de `[1, vagas_total]`; vaga ocupada → 409; permissionário já
  lotado → 409 com o ponto atual na mensagem; permissionário de outro tenant → 404.
- Liberar: encerra vigência, libera a vaga para novo ocupante, mantém a linha antiga.
- `vagas_total` reduzido abaixo do maior ocupado → 409.
- Excluir ponto ocupado → 409; inativar ponto ocupado → 200.
- **Isolamento cross-tenant** em ponto e ocupação.
- **Pelo menos um teste HTTP com usuário comum**, não super-usuário. O bypass de SU em
  `auth/perms.py` retorna **antes** do `getattr(item, action)`, e foi assim que dez rotas do
  transporte ficaram devolvendo 500 para operador não-SU sem a suíte notar. O tenant precisa
  contratar o módulo, senão o gate barra antes e o teste não chega onde importa.
- **O teste do não-gate:** alvará para permissionário sem vaga continua sendo emitido.
- **A prova do índice:** com a checagem do serviço fora do caminho, o banco ainda barra a segunda
  ocupação da mesma vaga.

Frontend: o `rotas-modulo.test.ts` já cobre órfã e prefixo; `tsc --noEmit` limpo.

Toda guarda nova **provada por inversão** antes de considerar a fatia pronta. Guarda verde só
significa alguma coisa depois de ficar vermelha — a de página órfã atravessou duas fatias sem nunca
ter sido invertida, e não protegia nada.

## Assunção que vale conferir

**Um permissionário ocupa no máximo uma vaga**, imposto pelo segundo índice único. Se em Sobral um
mesmo permissionário puder legitimamente ocupar vaga em dois pontos, o índice está errado.

Estou impondo agora, e não depois, porque a assimetria é forte: **soltar a regra é apagar um
índice; apertá-la depois exige limpar dado sujo** que já entrou. Se a premissa cair, o conserto é
um `DROP INDEX` numa migration de duas linhas.
