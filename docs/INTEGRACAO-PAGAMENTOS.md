# Integração de sistemas com o módulo Pagamentos

Este documento é o contrato que a prefeitura entrega a um sistema externo (ERP
financeiro, sistema contábil, folha de pagamento etc.) que precisa **ler ou
escrever** dados de pagamentos do Aprimora por API, sem passar pela tela de
usuário.

Ele descreve dois caminhos independentes:

1. **API M2M em tempo real** — `/api/v2/integracao/pagamentos/*`: criar
   débito, liquidar, e ler débitos/ordens/baixas por cursor.
2. **Export contábil em lote** — arquivo CSV `neutro-csv-v1` gerado sob
   demanda pela prefeitura (tela **Pagamentos → Export contábil**) e baixado
   uma vez por lote.

Onde a leitura deste texto divergir do código, **o código vence**: as fontes
de verdade são `backend/app/routers/pagamentos_integracao.py`,
`backend/app/auth/sistema_integrado.py`,
`backend/app/services/pagamentos_idempotencia.py` e
`backend/app/services/pagamentos_contabil.py`.

## 1. Autenticação

Toda chamada à API M2M leva o header:

```
X-Api-Key: <prefixo>.<segredo>
```

A chave é emitida uma única vez pela tela **Pagamentos → Cadastros →
Sistemas integrados** (perfil `pagamento_cadastro`) e **não é recuperável
depois** — só o `prefixo` continua visível, para identificar a chave na
lista. Se ela for perdida, a única saída é revogar e criar uma nova.

- Header ausente, mal-formado (sem o `.` separando prefixo e segredo),
  prefixo desconhecido, segredo incorreto, chave revogada ou inativa → **401**
  com a mesma mensagem genérica em todos os casos ("Chave de API ausente,
  inválida ou revogada") — de propósito, para não revelar se um prefixo
  existe.
- Chave válida mas **sem o escopo** exigido pelo endpoint chamado → **403**
  ("Sistema integrado sem escopo de leitura/escrita").
- Chave válida, escopo correto, mas o **tenant da chave não contratou o
  módulo `pagamentos`** → **403** ("Módulo 'pagamentos' não contratado para
  este tenant").
- Se a chamada chegar por um host que já resolveu OUTRO tenant (subdomínio
  divergente do dono da chave), a resposta também é **401** — uma chave nunca
  autentica em nome de um tenant diferente do seu.

### Escopos

Cada chave tem dois escopos independentes, escolhidos na criação:

| Escopo | Libera |
|---|---|
| `escopo_leitura` | `GET /debitos`, `GET /ordens`, `GET /baixas` |
| `escopo_escrita` | `POST /debitos`, `POST /debitos/{id}/liquidar` |

Uma chave pode ter os dois, um só, ou (sem sentido prático, mas permitido)
nenhum — nesse último caso todo endpoint devolve 403.

## 2. Escrita idempotente

As duas rotas de escrita exigem o header `Idempotency-Key` — sem ele, **422**
("Header Idempotency-Key é obrigatório para esta operação."). O valor é
escolhido pelo sistema integrado (recomendado: um UUID por tentativa lógica
de operação, não por retry HTTP).

Contrato de replay (`services/pagamentos_idempotencia.py`):

- **Chave nova** → a operação roda normalmente.
- **Mesma chave + mesmo corpo da requisição (byte a byte)** → devolve a
  resposta gravada da primeira vez, **sem repetir o efeito** (não cria um
  segundo débito, não liquida de novo). É seguro reenviar a mesma requisição
  em caso de timeout de rede.
- **Mesma chave + corpo diferente** → **409** ("Idempotency-Key já usada com
  um payload diferente."). Reusar uma chave para uma operação distinta é erro
  de uso do integrador — escolha uma chave nova.
- Requisição concorrente com a mesma chave, ainda em processamento → **409**
  ("Requisição com esta Idempotency-Key ainda em processamento."). Não há
  retry automático: espere e tente ler o resultado, ou trate como falha
  transitória.

### Exemplo — criar débito

```bash
curl -X POST https://<tenant>.<host>/api/v2/integracao/pagamentos/debitos \
  -H "X-Api-Key: aprm_ab12cd34.6f1e9c...segredo" \
  -H "Idempotency-Key: 8f14e45f-ceea-4f1a-8c8e-0a1b2c3d4e5f" \
  -H "Content-Type: application/json" \
  -d '{
    "id_fornecedor": 12,
    "id_natureza": 3,
    "id_fonte_recursos": 1,
    "id_unidade": 5,
    "valor_total": 1500.00,
    "competencia": "2026-08",
    "descricao": "Aquisição de material de expediente",
    "parcelas": [
      { "numero": 1, "valor": 1500.00, "vencimento": "2026-09-10" }
    ]
  }'
```

Resposta `201`: o mesmo formato de `DebitoOut` usado pela API administrativa
(`id`, `status`, `situacao_tramitacao`, `situacao_fila`,
`situacao_pagamento`, `versao`, `lock_version`, etc. — ver
`services/pagamentos_debitos.py::debito_out`). O campo `id_fornecedor` do
corpo precisa pertencer ao mesmo tenant da chave; `parcelas` exige pelo menos
uma. Campos como `id`, `status`, `id_usuario_solicitante` **não** entram no
payload de entrada — são calculados pelo servidor.

Quem grava o débito, para fins de auditoria: `id_usuario_solicitante` recebe
o usuário humano que **criou a credencial** (não existe usuário por trás de
uma chamada M2M). Se a chave foi criada sem esse vínculo — não deveria
acontecer no fluxo normal — a resposta é **409**.

### Exemplo — liquidar débito

```bash
curl -X POST https://<tenant>.<host>/api/v2/integracao/pagamentos/debitos/42/liquidar \
  -H "X-Api-Key: aprm_ab12cd34.6f1e9c...segredo" \
  -H "Idempotency-Key: 3b6a9f2e-1111-4c22-9999-abcdef012345" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Resposta `200`, mesmo `DebitoOut`. **Esta rota espelha
`POST /debitos/{id}/confirmar-liquidacao` da API administrativa — e não exige
empenho (`numero_ne`) preenchido.** A regra "empenho obrigatório" pertence à
etapa de *autorização* (`autorizar_lote`), que a porta M2M não expõe nesta
fatia; liquidar sem empenho pela API M2M dá certo hoje pelo mesmo motivo que
dá certo pela tela administrativa.

## 3. Leitura por cursor

`GET /debitos`, `GET /ordens` e `GET /baixas` compartilham a mesma
paginação, sem estado no servidor:

| Parâmetro | Tipo | Default | Regra |
|---|---|---|---|
| `cursor` | inteiro | (nenhum = do início) | devolve itens com `id` maior que o cursor |
| `limite` | inteiro | 50 | de 1 a 200 (`_LIMITE_MAXIMO`) |
| `alterado_desde` | datetime ISO-8601 | (nenhum) | só itens alterados/criados a partir daqui |

Resposta:

```json
{ "items": [ ... ], "proximo_cursor": 187 }
```

`proximo_cursor` é `null` quando a página devolvida é a última — **pare de
varrer quando ele vier `null`**, não quando `items` vier vazio (a última
página cheia ainda tem `proximo_cursor` preenchido).

A ordenação é sempre por `id` crescente. `alterado_desde` filtra por
`atualizado_em` quando existe, caindo para `criado_em` quando não
(`OrdemPagamento` é imutável após criada e não tem `atualizado_em` — o filtro
usa `criado_em`).

### Exemplo — varredura completa de débitos alterados numa janela

```bash
CURSOR=""
while :; do
  RESP=$(curl -s "https://<tenant>.<host>/api/v2/integracao/pagamentos/debitos?limite=100&alterado_desde=2026-08-01T00:00:00${CURSOR:+&cursor=$CURSOR}" \
    -H "X-Api-Key: aprm_ab12cd34.6f1e9c...segredo")
  echo "$RESP" | jq -c '.items[]'
  CURSOR=$(echo "$RESP" | jq -r '.proximo_cursor')
  [ "$CURSOR" = "null" ] && break
done
```

### Campos de cada listagem

- **`GET /debitos`** — o mesmo formato de `DebitoOut` da rota de escrita,
  acrescido de `id_evento` (inteiro, PK de `export_contabil_evento`; `null`
  se o débito ainda não foi capturado em nenhum lote de export contábil —
  ver §5 sobre a diferença entre este `id_evento` e o do CSV).
- **`GET /ordens`** — `id`, `numero`, `valor_total`, `id_usuario_autorizador`,
  `id_conta_pagadora`, `valor_reservado`, `saldo_antes`,
  `saldo_projetado_apos`, `excecao_saldo`, `criado_em`, `id_evento` (hoje
  sempre `null` — nenhum dos 5 tipos de evento contábil é ancorado em ordem
  de pagamento).
- **`GET /baixas`** — movimentações de conta de origem `PAGAMENTO`/`ESTORNO`:
  `id`, `id_conta`, `tipo`, `valor`, `origem`, `id_debito`, `id_parcela`,
  `data`, `descricao`, `criado_em`, `id_evento` (mesma regra do de débitos).

## 4. Limites

- **Rate limit na borda (nginx)**: o prefixo `/api/v2/integracao/` é limitado a
  **120 requisições/minuto por IP de origem**, com tolerância de rajada de 20
  (`burst=20 nodelay`). Acima disso o nginx responde **503** antes de chegar à
  aplicação — trate 503 com retry e backoff. O valor é configuração de
  infraestrutura (`nginx/default.conf`, zona `integracao`) e pode ser ajustado
  por ambiente sem mudança neste contrato.
- Tamanho de página: `limite` ≤ 200, default 50.
- Campos de texto seguem os limites do schema de entrada: `descricao` do
  débito até 255 caracteres, `numero_ne`/`numero_nf` até 30/40,
  `justificativa_urgencia` até 255, `competencia` no formato `AAAA-MM`.
- `valor_total` e o `valor` de cada parcela devem ser positivos (`> 0`);
  `parcelas` exige pelo menos um item.

## 5. Export contábil em lote — CSV `neutro-csv-v1`

Complementar à API em tempo real: cada lote captura os eventos contábeis
**ainda não exportados** até uma data-limite escolhida pelo operador na tela
**Pagamentos → Export contábil**, gera um CSV imutável e marca aqueles
eventos como capturados — o próximo lote nunca repete um evento já exportado.

Formato do arquivo: `;` como separador, quebra de linha `\r\n`, BOM UTF-8 no
início (abre direto no Excel pt-BR sem assistente de importação e sem
estragar acentuação). Nomes decimais usam vírgula (`1500,00`), não ponto.

### Colunas

| Coluna | Quando se aplica |
|---|---|
| `id_evento` | Sempre. Ver "id_evento estável" abaixo. |
| `tipo_evento` | Sempre — um de `debito_empenhado`, `liquidacao`, `cancelamento_debito`, `pagamento`, `estorno_parcela`. |
| `id_debito` | Sempre que o evento se liga a um débito (todos os tipos hoje). |
| `ocorrido_em` | Sempre — data/hora local `AAAA-MM-DD HH:MM:SS`. |
| `lote` | Sempre — número do lote que capturou o evento. |
| `numero_empenho` | `debito_empenhado`, `liquidacao`, `cancelamento_debito`, `pagamento`, `estorno_parcela` — vazio se o débito não tinha `numero_ne` gravado no momento (nota: eventos `debito_empenhado` só entram no export depois que o empenho é preenchido; sem ele o evento fica pendente indefinidamente). |
| `fonte` | Mesmos tipos acima que carregam débito — descrição da fonte de recursos. |
| `credor_doc` / `credor_nome` | Mesmos tipos — CNPJ/CPF e nome do fornecedor. |
| `valor` | `debito_empenhado`/`liquidacao`/`cancelamento_debito` (valor total do débito) e `estorno_parcela` (valor estornado). Vazio em `pagamento` (ver `valor_pago`). |
| `vencimento` | Não preenchido pelo adapter atual (sempre vazio — reservado). |
| `data_liquidacao` | Só em `liquidacao`. |
| `numero_ordem` | `pagamento`/`estorno_parcela`, quando o débito tem ordem de pagamento associada. |
| `conta` | `pagamento`/`estorno_parcela` — nome da conta bancária pagadora. |
| `data_pagamento` | Só em `pagamento`. |
| `valor_pago` | Só em `pagamento`. |
| `excecao_saldo` | `pagamento`/`estorno_parcela`, quando há ordem associada — `sim`/`não`. |
| `justificativa` | Idem — justificativa da exceção de saldo na ordem, quando houve. |
| `motivo` | `cancelamento_debito` (motivo do cancelamento) e `estorno_parcela` (motivo extraído da descrição do estorno). |

Campo não aplicável ao tipo de evento da linha: string vazia, nunca `null`
nem coluna ausente — o CSV tem sempre as 19 colunas acima, em todas as
linhas.

### `id_evento` estável — e por que ele NÃO é o mesmo campo da API M2M

No CSV, `id_evento` é a chave natural e estável do evento:
**`<tipo_evento>:<id_origem>`** (ex.: `liquidacao:983`), onde `id_origem` é o
`id` da linha de origem no domínio — `debito_historico.id` para os três tipos
ligados a histórico de débito, `movimentacao_conta.id` para `pagamento`/
`estorno_parcela`. Essa string é o identificador que um sistema contábil deve
usar para deduplicar entre lotes/reimportações: o par `(tenant, id_evento)` é
único para sempre (índice único de `pagamentos.export_contabil_evento`).

O `id_evento` que aparece nas respostas de `GET /debitos` e `GET /baixas` da
**API M2M em tempo real (§3) é outro número**: é o `id` (PK interna) da linha
de `pagamentos.export_contabil_evento`, útil só para saber *se* aquele
débito/movimentação já foi capturado em algum lote (`null` = ainda não). Para
correlacionar com uma linha do CSV, use o par `tipo_evento` + `id_origem` —
não compare os dois campos `id_evento` diretamente, eles não são a mesma
grandeza.

## 6. Referência rápida de erros

| Status | Quando |
|---|---|
| 401 | Chave ausente/mal-formada/inválida/revogada; ou tenant do host diverge do tenant da chave. |
| 403 | Chave sem o escopo exigido; ou módulo `pagamentos` não contratado pelo tenant da chave. |
| 404 | Débito referenciado em `/debitos/{id}/liquidar` não existe (ou não pertence ao tenant da chave). |
| 409 | `Idempotency-Key` reusada com payload diferente; ou requisição com a mesma chave ainda em processamento; ou (fora da API M2M) export contábil sem evento pendente até a data escolhida. |
| 422 | `Idempotency-Key` ausente em rota de escrita; ou corpo da requisição fora do schema (`DebitoCreate`). |
