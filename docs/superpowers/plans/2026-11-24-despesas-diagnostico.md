# Módulo Despesas — Diagnóstico do estado atual e plano de evolução

> Pedido recebido de Jorge em 2026-11-24 (brief de 12 seções + 4 mockups). Este documento é a
> **etapa 2 do próprio brief** ("Antes de implementar, analise profundamente o repositório
> atual"). Nada foi implementado ainda: aqui está o que existe, o que falta, o que o brief
> assume que não tem lastro no banco, e em que ordem vale construir.
>
> O brief chegou **truncado** no meio da fórmula do §12 ("compromissos em aberto eleg…"). A
> definição de disponibilidade residual está reconstruída na seção 3 a partir do código que já
> roda; confirmar contra o texto completo antes de codificar o catálogo de indicadores.

## 1. A premissa a corrigir: não existe módulo "Financeiro"

O brief pede renomear **Financeiro → Despesas**. Não há módulo com esse nome. O que existe é
**`pagamentos`**, um dos cinco módulos contratáveis (`protocolo`, `pagamentos`, `frota`,
`transporte`, `administracao`), com 30 páginas em `frontend/app/(app)/m/pagamentos/`, 9 routers,
27 services e 34 tabelas no schema `pagamentos`.

Isso é boa notícia: o módulo alvo já está construído e é maduro. Mas muda o enquadramento do
trabalho — **não é renomear um módulo fraco, é dar cara executiva a um módulo operacional forte**.

### O que a renomeação pode e não pode tocar

O `CLAUDE.md` trava três coisas que tornam a troca de nome um ato **só de rótulo**:

- **A regex do `nginx/default.conf` só cresce.** O token `pagamentos` fica para sempre; criar
  `/m/despesas` sem manter `/m/pagamentos` mata o 308 que mantém a URL antiga viva.
- **`notificacao.link_url` é registro histórico permanente.** Há links já gravados com
  `/m/pagamentos/…`; `tests/test_guarda_link_url.py` reprova quem nascer com prefixo errado.
- **`permanent: true` (308) é cache de navegador** — destino errado em produção não se conserta
  com redeploy.

**DECIDIDO por Jorge em 2026-11-24:** "a Financeira passa a ser chamada de Despesa, não precisa
mudar internamente". Vale a recomendação abaixo — troca só de rótulo.

**Recomendação:** manter o slug `pagamentos` na URL, nas tabelas, nas transações
(`pagamento_*`), no catálogo `aprimora_py.modulo` e nas APIs. Trocar **só** o rótulo visível —
`frontend/lib/menus/pagamentos.ts`, títulos de página, breadcrumbs e o nome no launcher
`/modulos`. É exatamente o que o §4 do brief autoriza ("Não renomeie indiscriminadamente tabelas,
APIs ou classes internas apenas por causa da mudança do nome comercial"). A alternativa de slug
novo com 308 fica para uma fatia própria, se o Jorge quiser a URL bonita — e aí o custo é o
inventário inteiro de `href`, não o rótulo.

## 2. O que já existe e atende ao brief

Esta é a parte que mais encurta o projeto. O núcleo financeiro que o brief descreve no §12 — o
item que ele próprio chama de "etapa crítica" — **já está implementado e com rigor**.

### 2.1. Saldo e disponibilidade (§5, §6, §12)

`backend/app/services/pagamentos_caixa.py:88` (`saldo_conta`) devolve, por conta:

| Indicador do brief | Campo existente | Como é calculado |
|---|---|---|
| Saldo bancário | `saldo_atual` / `saldo_bancario` | `saldo_inicial + Σ entradas − Σ saídas` |
| Saldo conciliado | `saldo_conciliado` | só movimentações com baixa de conciliação não excluída |
| Valores comprometidos | `comprometido` | `comprometido_conta` (:59) |
| Recursos bloqueados | `bloqueado` | `bloqueado_conta` (:69), vigentes na data |
| Disponibilidade residual | `disponivel` | `saldo_atual − comprometido − bloqueado` |

O `comprometido` já resolve o problema de dupla contagem que o §12 levanta: é a **Σ das parcelas
`A_PAGAR`/`LIBERADA` de débitos com reserva ativa** (autorizados e nem pagos nem conciliados) cuja
**conta pagadora** é aquela conta. Não soma autorizado + empenhado + liquidado; soma saldo
remanescente de parcela. É a definição correta, e `_TEM_RESERVA` é o mesmo predicado em
`pagamentos_caixa.py:27`, `pagamentos_dashboard.py:27` e `pagamentos_autorizacao.py` — uma
verdade só, não três cópias.

### 2.2. Estados da despesa (§8)

`backend/app/services/pagamentos_estados.py` tem **três dimensões independentes** em vez de um
status único: `situacao_tramitacao` (11 valores, com grafo de transições), `situacao_fila` e
`situacao_pagamento`. As situações que o §8 pede para separar já existem ou derivam destas três
sem estado novo:

- Aguardando análise → `AGUARDANDO_GESTOR`
- Aguardando autorização → `AGUARDANDO_AUTORIDADE`
- Autorizadas → `AUTORIZADA`
- Autorizadas e aguardando pagamento → `AUTORIZADA` + `situacao_pagamento` ∉ (`PAGA`, `CONCILIADA`)
- Rejeitadas / Canceladas → `REJEITADA_GESTOR`, `INDEFERIDA_AUTORIDADE`, `CANCELADA`

**Exceção:** "autorizadas e **empenhadas**" vs "autorizadas e **não** empenhadas" não é
computável — ver 3.2.

### 2.3. Simulador de impacto (§10.1)

**Já existe:** `pagamentos_caixa.py:144` (`simular_autorizacao`), com schema próprio
(`SimulacaoAutorizacaoOut`). Hoje serve à tela de autorização; falta a **experiência** de
simulação livre que o §10.1 descreve (escolher conta, valor, data, parcelamento). O motor está
pronto — e já nasce obedecendo à regra do brief de não criar despesa real.

### 2.4. O resto que já está de pé

- **Trilha de auditoria** (§8): `debito_historico`, `debito_versao`, `pedido_ajuste`, tela
  `/m/pagamentos/auditoria`.
- **Segregação de funções** (§8): `alcada` + as transações `pagamento_solicitar/gerir/validar/
  autorizar/pagar/auditar/cadastro`. O brief exige respeitá-las; elas são o gate real.
- **Conciliação bancária** (§11): `extrato`, `lancamento_extrato`, `conciliacao`, tela própria.
- **Snapshot diário de saldos**: `saldo_historico` + `registrar_snapshot_saldos` — é a série
  histórica que o §5 pede para comparação temporal, e ninguém ainda desenhou em cima dela.
- **Painel atual**: `pagamentos_dashboard.py:49` já entrega KPIs, fluxo mensal de 12 meses,
  composição por natureza e por fonte, maiores débitos e alertas.
- **Ordem cronológica** (Lei 14.133): `posicao_cronologica`, chaveada por
  `(unidade, fonte, categoria, exercício)`.
- **Integração contábil** (§2): API M2M `/api/v2/integracao/pagamentos/*` + export CSV
  `neutro-csv-v1`. Documentado em `docs/INTEGRACAO-PAGAMENTOS.md`.

## 3. O que o brief pede e o banco não tem

Esta seção é a que decide o tamanho do projeto. Cada item abaixo é um indicador ou uma dimensão
que **não dá para calcular** com os dados de hoje — e que, se for implementado "por aproximação",
produz número errado numa tela que o prefeito vai usar para decidir.

### 3.1. Orçamento — ausente por inteiro

Não existe dotação, crédito orçamentário, unidade orçamentária, função, subfunção, programa nem
projeto/atividade. `natureza_despesa` (`backend/app/models/pagamentos.py:61`) tem só `codigo` e
`descricao` livres — não há categoria econômica, grupo de natureza, elemento nem subelemento
estruturados.

**Consequência direta:** "disponibilidade orçamentária" (§5, §8), "execução orçamentária" (§9.1)
e sete das dimensões de análise do §9 **não têm fonte**. O mockup 4 mostra "62,8% de execução
orçamentária sobre orçamento atualizado de R$ 153.640.000,00" — esse número não existe no
sistema e não há de onde derivá-lo.

O que existe perto: `GrupoDespesa` (`backend/app/models/pagamentos.py:24`) com
`PESSOAL/CUSTEIO/INVESTIMENTO/DIVIDA/OUTRAS` — que é exatamente o **grupo de natureza da despesa**
da Lei 4.320. É um eixo real e já populado, mas é um só.

### 3.2. Empenho — existe como número, não como valor

`Debito.numero_ne` é `String(30)` nullable, informativo. Não há data de empenho, valor empenhado,
saldo a liquidar nem entidade `empenho`. Logo:

- KPI "despesas empenhadas" (§5.1): **não computável**.
- Separar "autorizadas e empenhadas" de "autorizadas e não empenhadas" (§8): só dá para
  responder "tem número de NE preenchido" — que não é a mesma pergunta.
- O item "Empenhos" que aparece no menu dos mockups 2, 3 e 4: **sem lastro**.

### 3.3. Liquidação — booleano, não valor

`Debito.liquidacao_confirmada` (bool) + `data_liquidacao`. Serve ao rito (guarda antes de
autorizar, RF-VAL-02), não à contabilidade. "Despesas liquidadas" só pode ser
Σ `valor_total` dos débitos com o booleano ligado — liquidação parcial não é representável.

### 3.3-A. O retorno do sistema financeiro não tem onde pousar

**DECIDIDO por Jorge em 2026-11-24:** `valor_empenhado` e `valor_liquidado` entram, para receber
o retorno do sistema financeiro. **IMPLEMENTADO no mesmo dia** — migration `0144`, três colunas
em `pagamentos.debito`, entrada por `POST /debitos/{id}/empenho` e `valor_liquidado` no
`liquidar` da porta M2M, 11 testes em `tests/test_pagamentos_retorno_financeiro.py`. As respostas
do Jorge às cinco perguntas abaixo estão aplicadas: coluna (não tabela), sobrescrita pelo retorno,
campo `revisado`, comprometido intocado, entrada pelos endpoints existentes.

O levantamento mostra que a **saída já existe e a volta não**. `services/pagamentos_contabil.py`
já emite os eventos `debito_empenhado` e `liquidacao` no export `neutro-csv-v1` — mas nenhum dos
dois carrega valor: `debito_empenhado` é ancorado apenas em `Debito.numero_ne` estar preenchido
(e o próprio arquivo registra a limitação de que NE preenchido depois da criação não gera evento
de domínio), e `liquidacao` vem de `confirmar_liquidacao`, cuja assinatura
(`pagamentos_debitos.py:729`) aceita **só data**, nunca valor.

Na porta M2M (`routers/pagamentos_integracao.py`) existem cinco endpoints — `POST /debitos`,
`POST /debitos/{id}/liquidar`, e os três GET de leitura. O `liquidar` também não recebe valor.
Ou seja: **o sistema financeiro não tem como devolver quanto foi empenhado e quanto foi
liquidado**, nem por API nem por arquivo.

**Sobre "em conciliação era para ter isso":** o que existe hoje chama-se conciliação mas é
**conciliação bancária** — `Conciliacao` (`models/pagamentos.py:615`) liga
`lancamento_extrato` ↔ `movimentacao_conta`, isto é, confere **pagamento contra extrato do
banco**. O que o retorno do sistema financeiro exige é outra coisa: **conciliação contábil**,
confrontando empenhado/liquidado do sistema de origem contra o que o Aprimora registrou. Não
existe entidade, tela nem endpoint para isso. É fatia nova, não ajuste da conciliação atual.

**Perguntas de modelagem antes da migration:**

1. **Empenho é campo ou entidade?** Um débito pode ter mais de um empenho (complementação,
   anulação parcial)? Se puder, `valor_empenhado` como coluna mente, e o certo é tabela
   `empenho` 1:N com `numero`, `data`, `valor`, `tipo` (ordinário/estimativo/global).
2. **Liquidação parcial existe?** Se o sistema financeiro devolver liquidações parciais, o
   booleano atual não comporta, e `valor_liquidado` precisa ser acumulável — com `saldo a
   liquidar` derivado (`empenhado − liquidado`).
3. **Quem é a fonte da verdade?** Se o valor vem do sistema financeiro, o Aprimora não pode
   deixar a tela editar o mesmo campo — senão as duas pontas divergem em silêncio. Decidir se
   é campo só-leitura alimentado pela integração, ou editável com marca de origem.
4. **Anulação e estorno de empenho** precisam de representação, senão o "comprometido" passa a
   divergir do empenhado com o tempo.
5. **O caminho de entrada:** novo `POST /debitos/{id}/empenho` e valor no `liquidar`, ou um
   endpoint de conciliação contábil em lote que recebe o retorno inteiro do exercício?

### 3.4. Restos a pagar e exercício

Não há conceito de exercício no débito. Há `competencia` (`YYYY-MM`), `fonte_recursos.exercicio`
e `posicao_cronologica.exercicio`. "Restos a pagar" (§7) e o seletor "Exercício: 2025" dos
mockups 1 e 2 precisam de uma decisão de modelagem antes de qualquer tela.

### 3.5. Receita, folha e convênios

Sem módulo de receita, as "receitas previstas" do §10 não têm fonte, e a previsão financeira fica
**só com o lado da saída** — o que ainda é útil, desde que a tela diga isso. Folha de pagamento e
encargos (§7) não são entidades; aparecem no mockup 4 como maior gasto, mas hoje só entrariam
como débitos comuns. Convênios e contrapartidas (mockup 2) idem.

### 3.6. A dimensão que falta e é barata

**Despesa por secretaria não existe no painel** — `pagamentos_dashboard.py` não agrega por
unidade nenhuma vez. Mas `Debito.id_unidade` é `NOT NULL` desde a F1, e `Contrato.id_unidade`
também. A pergunta nº 10 do prefeito ("quais secretarias estão gastando mais") é respondível
**hoje, só com SQL novo**. É o melhor retorno por esforço do projeto inteiro.

Na mesma faixa: ranking de fornecedores (`id_fornecedor`), ranking de contratos (`id_contrato`),
e as categorias gerenciais — que já têm enum rastreável e validado
(`backend/app/services/pagamentos_cronologia.py:33`: `BENS`, `LOCACOES`, `SERVICOS`, `OBRAS`),
resolvido por `categoria_do_debito` (contrato manda; sem contrato, o campo do débito). O §9 pede
14 categorias gerenciais (medicamentos, combustíveis, alimentação escolar…) — essas **não**
existem, e o próprio brief proíbe inferi-las por aproximação textual. Ou viram cadastro com
vínculo explícito, ou ficam fora.

## 4. Os mockups vs o sistema

As quatro imagens mostram uma sidebar com **Receita, Orçamento, Planejamento, Convênios,
Patrimônio, Compras, Contratos, Pessoas, Relatórios e BI**. Nenhum desses módulos existe — o
sistema tem cinco, e o brief diz para não criar aplicação nova. Tratei os mockups como
**referência visual do módulo Despesas**, não como mapa de navegação a implementar.

Três observações sobre eles:

1. **Mockup 1 usa velocímetro** ("Impacto financeiro das pendências", 11,5%) e **mockups 2 e 4
   usam rosca** — o §9.1 do próprio brief pede para evitar pizza e velocímetro. Conflito a
   resolver: vale a regra ou vale o desenho?
2. Os números são fictícios e **inconsistentes entre as telas** (saldo total R$ 42,68 mi no
   mockup 3 e R$ 48,32 mi no 4; município "Nova Esperança" em três, "Boa Esperança" no quarto).
   Normal em mockup — confirma que são peça de direção visual, não especificação de dado.
3. O padrão visual deles **não é** o design system atual (`docs/design-system.md`). Adotá-los ao
   pé da letra é redesenhar o sistema inteiro, não o módulo.

## 5. Plano proposto

Ordenado por valor para o prefeito ÷ custo, respeitando que cada fatia precisa entrar verde
(guardas de módulo, de rota órfã, de `link_url` e de permissão).

| # | Fatia | Entrega | Dado novo? |
|---|---|---|---|
| 1 | ~~**Rótulo e navegação**~~ | **FEITO** (2026-11-24): "Despesa" no menu, launcher, breadcrumbs, cartão do Início e Panorama. Migration `0145` troca `aprimora_py.modulo.nome`; slug `pagamentos`, URLs, tabelas, transações e API intactos. | Não |
| 2 | ~~**Painel executivo v1**~~ | **FEITO** (2026-11-24): despesa por **secretaria**, maiores **fornecedores** e maiores **contratos** no painel; 6 KPIs com definição e origem; "apurado em" na tela. Sem migration. Ver 5.1 abaixo. | Não |
| 3 | ~~**Disponibilidade por conta**~~ | **FEITO** (2026-11-24): rosca consolidada com total no centro + barra proporcional por conta (disponível / comprometido / bloqueado, mutuamente exclusivas), ordenação, clique até a conta (`/m/pagamentos/caixa?conta=`) e rodapé de leitura. Ver 5.2. | Não |
| 4 | ~~**Central de autorizações executiva**~~ | **FEITO** (2026-11-24): painel de impacto no topo da fila de autorização — total a autorizar, disponível antes/depois **por fonte**, fontes sem lastro e de quem vêm as pendências. `GET /pagamentos/autorizacao/impacto`, só leitura. Ver 5.3. | Não |
| 5 | ~~**Previsão financeira (saída)**~~ | **FEITO** (2026-11-24): tela `/m/pagamentos/previsao` com janelas 7/15/30/60/90, saldo projetado, vencidas e contas que não cobrem os próprios vencimentos. Diz na tela que não inclui receita. Ver 5.4. | Não |
| 6 | ~~**Central de alertas**~~ | **FEITO** (2026-11-24): tela `/m/pagamentos/alertas` com 8 alertas normalizados — severidade, impacto, escopo, **origem** e **ação**. Ver 5.5. | Não |
| 7 | ~~**Catálogo de indicadores (§12)**~~ | **FEITO** (2026-11-24): 18 fichas em `services/pagamentos_catalogo.py` (fonte única), tela `/m/pagamentos/catalogo` com busca. **4 declaram o que o sistema NÃO tem.** Ver 5.6. | Não |
| 8 | ~~**Exploração interativa (§9.2)**~~ | **FEITO** (2026-11-24): clique numa barra recorta o painel inteiro; filtros ativos visíveis, "Ver tudo" restaura. Cinco dimensões: secretaria, natureza, fonte, fornecedor, contrato. Ver 5.7. | Não |
| 9 | **Empenhado e liquidado com valor** | `valor_empenhado`/`valor_liquidado` + caminho de entrada do retorno do sistema financeiro + conciliação contábil. **Aprovada**; modelagem pendente (3.3-A). | **Sim** |
| O1 | **Orçamento — fundação** | **FEITO** (2026-11-24): dotação com classificação funcional-programática, créditos adicionais e anulação, vínculo da despesa, execução orçamentária e tela. Migration `0146`. Ver 5.8. | **Sim** |
| — | *Restos a pagar, receita, folha, reserva orçamentária* | **Bloqueadas.** Cada uma é modelagem + rito, não tela. | **Sim** |

As fatias 1 a 8 entregam a maior parte das 17 perguntas do prefeito **sem nenhuma migration**. As
que ficam de fora são as orçamentárias e as que dependem de receita.

### 5.1. A regra que a fatia 2 fixou: uma medida só

As cinco dimensões do painel (natureza, fonte, secretaria, fornecedor, contrato) medem **a mesma
coisa**: o que saiu da conta como pagamento no período (`movimentacao_conta.origem = 'PAGAMENTO'`,
pelo vínculo com o débito). Isso é escolha, não acaso — e `tests/test_pagamentos_painel_executivo.py`
reprova quem mudar a medida de uma delas.

O motivo é que duas medidas no mesmo painel produzem dois gráficos que discordam sobre quanto a
prefeitura gastou, sem o leitor ter como saber qual acreditar. O defeito não aparece como erro:
aparece como número errado com cara de certo, numa tela usada para decidir.

Duas consequências práticas:

- O ranking de contratos inclui a linha **"Sem contrato"**. No banco de demonstração local ela é
  59% do pago — um ranking que a escondesse estaria errado por mais da metade, e em silêncio.
- A despesa por secretaria usa `Debito.id_unidade`, que só é `NOT NULL` desde a F1. Antes dela,
  débito sem contrato não tinha unidade nenhuma; é por isso que a pergunta nº 10 do prefeito só
  pôde ser respondida agora.

### 5.2. O padrão visual: anatomia do ianalisys, tokens do Aprimora

Jorge pediu (2026-11-24) algo "mais gráfico, mais impactante para vender", contextualizado "tipo
a ianalisys que tá no repositório git". Fui ao repo (`C:\Jorge\ianalisys`) e o que vale a pena
trazer de lá é a **anatomia**, não a identidade:

- **`ChartCard`** (`shell/components/ui/chart-card.tsx`): cabeçalho com subtítulo de contexto,
  corpo de altura fixa com estados de carregando/vazio, e **rodapé de insight** — uma frase curta
  dizendo o que o gráfico significa. Portado como `components/ui/grafico-card.tsx`.
- **`KpiCardV2`**: ícone sem pílula, valor grande, delta com tom semântico, tooltip de definição.
  O `KpiCard` do Aprimora já tinha quase tudo; ganhou a definição na fatia 2.

**Não** trouxe a paleta (navy `#000e1d` / teal `#009c9c`) nem a tipografia Poppins, e isso é
deliberado: o Aprimora é white-label multi-tenant — `lib/chart-theme.ts` existe para as cores
seguirem a identidade de cada prefeitura, e `aparencia` deixa o município trocá-la. Cravar a marca
de uma empresa no produto marcaria toda prefeitura com a identidade de outra, e os valores fixos
quebrariam o tema escuro. A skill `ianalisys-design-system` é para entregáveis **da marca**
(landing, relatório, proposta); o produto municipal é outro contexto.

**A regra do rodapé de insight:** o texto sai do próprio dado — uma concentração, uma proporção,
uma ausência. Frase pronta é pior que rodapé nenhum, porque ocupa o lugar onde o leitor espera
informação. Os três insights implementados:

1. Falta de lastro, quando existe (vence os outros dois).
2. **Vinculação não cadastrada**: `fonte_recursos.tipo_vinculacao` está nulo em todas as fontes do
   banco local, então o painel **diz** que o "disponível" ainda não separa recurso livre de
   vinculado, em vez de insinuar que é tudo livre. É o alerta do §11 do brief, e a alternativa —
   deduzir vinculação do texto da descrição ("FUNDEB", "Saúde") — é a classificação por
   aproximação que o §9 proíbe.
3. **Despesa sem contrato**: 59,4% do pago no banco local. É a leitura que mais surpreende quem
   abre o painel, e some de qualquer ranking que liste só contratos de verdade.

### 5.3. Por que o impacto da autorização é por FONTE, e não o total

O mockup 1 mostra um velocímetro único: "as 12 pendências consomem 11,5% do saldo disponível do
município". **Esse número não decide nada**, e pode decidir errado.

Um débito só pode ser pago por conta da própria fonte — a fonte do empenho é vinculante
(RN-02/05), e a tela de autorização só oferece contas daquela fonte. Então R$ 500 mil parados numa
fonte com R$ 80 mil continuam sem lastro mesmo que o município tenha R$ 40 milhões em outras
contas. Um painel que responda "cabe?" somando o caixa inteiro diz que cabe — e o erro só aparece
quando a autorização recusa, depois de o gestor já ter decidido que daria.

Por isso `impacto_autorizacoes` (`services/pagamentos_filas.py`) devolve **uma linha por fonte**,
com disponível antes, depois e o tamanho da falta; o consolidado existe para dimensionar, não para
decidir, e `fontes_insuficientes` é um campo próprio. A ordenação põe a fonte que não fecha em
primeiro lugar.

A disponibilidade de cada fonte vem de `contas_elegiveis` — **a mesma função** que a tela de
autorização usa para listar contas pagadoras. Calcular por outro caminho (todas as contas da
fonte) daria número maior que o real, porque entrariam contas inativas ou que não admitem
pagamento: o painel prometeria folga que a autorização recusa.

`tests/test_pagamentos_impacto_autorizacoes.py` trava as duas propriedades que importam: o
agrupamento por fonte com a falta calculada, e que **consultar o impacto não autoriza nem reserva
nada** (`id_conta_pagadora` continua nulo depois da consulta).

### 5.4. A contagem dupla que a previsão quase cometeu

O caminho intuitivo para projetar caixa é "pegue o **disponível** e subtraia o que vence". Ele
está errado, e erra para o lado perigoso.

`disponivel` já é `saldo − comprometido − bloqueado`, e `comprometido` é a soma das parcelas em
aberto de débitos autorizados — exatamente as parcelas que a projeção percorre por data de
vencimento. Partir dele desconta cada obrigação **duas vezes** e mostra um caixa futuro menor que
o real, às vezes negativo sem motivo. O ponto de partida correto é o saldo bancário:

    saldo projetado em D = saldo_atual − bloqueado − Σ(parcelas vencendo até D)

Com D longo o bastante para cobrir todos os vencimentos, essa conta chega **exatamente** em
`disponivel`. É a invariante que `test_projecao_reconcilia_com_o_disponivel` trava, e ela foi
verificada contra o banco local: base R$ 1.772.270 − comprometido R$ 35.400 = disponível
R$ 1.736.870, que é o projetado em D+90.

Esse teste já pagou o próprio custo: na primeira execução ele acusou divergência, e a causa era
o arreio autorizando o débito **sem conta pagadora** — estado que a produção não produz (a conta
é gravada no ato de autorizar e é imutável), mas que `comprometido_conta` ignora, porque ela soma
por conta pagadora. A diferença entre as duas somas está documentada no módulo: a projeção é
conservadora e inclui o débito sem conta; se um dia aparecer um, o certo é investigar o débito, e
não "alinhar" os números.

**O que a previsão não tem, e diz:** receita. Não há módulo de receita, então nenhum repasse,
arrecadação ou convênio a receber entra na conta. `considera_receita=False` existe no schema para
a tela ser obrigada a declarar isso, e o aviso aparece **antes** dos números, não num rodapé —
quem lê uma projeção precisa saber o que ela não inclui antes de confiar nela.

### 5.5. As três regras da central de alertas

`services/pagamentos_alertas.py` formaliza o que o painel já detectava solto. O formato é único
e cada campo responde uma pergunta do leitor: o que aconteceu, quanto custa, onde, **de onde saiu
o número** e **o que fazer**. As regras que governam o módulo:

1. **Alerta sem ação não entra.** Aviso que não diz o que fazer é barulho, e barulho treina o
   gestor a ignorar a lista inteira — inclusive o que importa. Há teste travando `acao` e
   `origem` preenchidos em todo item.
2. **Só fato, nunca estatística com cara de irregularidade.** Todo alerta é verificável no banco:
   a parcela venceu, o saldo não cobre, a coluna está vazia. Concentração de fornecedor e gasto
   acima da média **ficaram de fora de propósito** — o §11 do brief proíbe apresentá-las como
   indício de irregularidade, e elas pertencem aos painéis de análise, com outra palavra. A
   própria tela diz isso ao pé.
3. **Severidade é do impacto, não do susto.** Vermelho só para CRÍTICO (dinheiro que já deveria
   ter saído, ou obrigação sem lastro). Se tudo grita, nada é ouvido.

Os oito alertas: parcelas vencidas, vencimentos em 7 dias, conta com compromissos acima do saldo,
conta abaixo do mínimo, fonte que não cobre o que aguarda autorização, **despesa autorizada sem
conta pagadora** (a anomalia que a 5.4 documentou, agora vigiada), fonte sem vinculação cadastrada
e conta sem movimentação no dia.

No banco local sai **um** alerta, informativo: as fontes sem vinculação. É o resultado certo —
lista cheia por padrão teria o mesmo efeito do barulho, e há teste garantindo que banco saudável
não inventa aviso.

### 5.6. O catálogo mora no código, e declara o que não existe

**Onde ele mora.** As 18 fichas vivem em `backend/app/services/pagamentos_catalogo.py`, que é
domínio puro (não toca banco, como `pagamentos_estados.py`). A tela lê pela API e **não guarda
texto de definição nenhum**; este documento aponta para lá em vez de repetir. Escrever definição
em dois lugares produz duas definições em poucas semanas — e aí o painel afirma uma coisa e a
documentação afirma outra, que é justamente a discussão que um catálogo existe para encerrar.

**A metade mais útil é o que não existe.** Quatro fichas têm `disponivel=False` com o motivo:

| Conceito | Por que não existe |
|---|---|
| Disponibilidade orçamentária | Não há dotação, classificação funcional-programática nem crédito cadastrados |
| Saldo contábil | O Aprimora **envia** eventos à contabilidade, mas não recebe o saldo apurado de volta |
| Restos a pagar | A despesa não tem exercício (há competência mensal, que não é a mesma coisa) |
| Reserva orçamentária | Não há dotação a reservar |

Um gestor que procura "execução orçamentária" e não acha nada conclui que esqueceram; um que
encontra a ficha sabe o que falta para o indicador existir. A omissão silenciosa é que engana.

**A ficha que mais evita confusão é a da reserva orçamentária**, e ela não existe. O módulo usa a
palavra "reserva" para outra coisa — a reserva **financeira** da conta pagadora, feita na
autorização. Um prende dotação, o outro prende dinheiro. Há teste exigindo que a ficha avise isso.

**Uma correção que o teste forçou:** "recursos vinculados" estava marcado como disponível sem
fórmula. O teste de completude pegou, e a análise mostrou a nuance — a **regra** de vinculação
está implementada e é obrigatória (só contas da fonte do empenho pagam), mas a **medida** não
existe, porque `tipo_vinculacao` está vazio. A ficha agora diz exatamente isso, em vez de
prometer um número que ninguém calcula.

### 5.7. O filtro vale para tudo, ou não vale

Clicar numa barra recorta **todas** as agregações de despesa paga — secretaria, natureza, fonte,
fornecedor e contrato — pelo mesmo `_filtro_pago`. Não é detalhe de implementação: se o recorte
valesse para uns gráficos e não para outros, a tela mostraria barras de escopos diferentes lado a
lado, e o leitor somaria coisas que não se somam **sem ter como perceber**, porque cada gráfico
continuaria correto isoladamente. `test_recorte_vale_para_todas_as_agregacoes` percorre as cinco
dimensões exigindo que cada uma feche com `total_filtrado`.

**O que não se recorta, e por quê.** Saldo, disponível e comprometido são da **conta bancária**.
Não existe "saldo da Secretaria de Saúde" — a conta não pertence a uma secretaria. Filtrar esses
KPIs inventaria um número, então eles seguem consolidados **e a tela diz isso** quando há recorte
ativo. Um filtro que silenciosamente não se aplica a parte dos números é pior que não ter filtro:
o leitor confia que tudo na tela responde ao recorte. Há teste exigindo que os KPIs de saldo e a
disponibilidade por conta não mudem com o filtro.

Duas decisões menores que vale registrar:

- **A linha "Outras" não é clicável** e não traz `id`. Ela junta várias dimensões; clicar nela não
  seria um recorte, seriam vários ao mesmo tempo.
- **Um recorte por dimensão.** Clicar noutra secretaria troca a secretaria, em vez de empilhar
  duas — duas ao mesmo tempo seria um "ou" que o backend não faz e que o leitor não esperaria.

### 5.8. Orçamento (O1): o que entrou, o que ficou e as escolhas

Jorge autorizou o orçamento em 2026-11-24. A migration `0146` cria `pagamentos.dotacao` e
`pagamentos.credito_adicional` e acrescenta `debito.id_dotacao` e `debito.exercicio`.

**Quatro escolhas que valem registro:**

1. **A classificação funcional-programática mora em colunas da dotação**, não em seis tabelas de
   catálogo (função, subfunção, programa, ação, natureza…). A prefeitura importa a classificação
   pronta do sistema orçamentário dela; seis cadastros mantidos à mão não sobreviveriam. Se um dia
   precisar de hierarquia navegável, vira tabela sem quebrar esta — os códigos continuam os mesmos.
2. **A dotação atualizada é derivada, nunca coluna**: `valor_inicial + Σ créditos − Σ anulações`,
   somada na hora. Guardar o valor sincronizado por código é divergência garantida, e este módulo
   já pagou essa lição ao remover o `status` legado do débito na F5. Há teste travando a ausência
   da coluna.
3. **O sinal é do tipo, não do valor.** `credito_adicional.valor` tem CHECK de não-negativo;
   anulação subtrai por ser do tipo `ANULACAO`. Valor negativo gravado por engano viraria
   suplementação que diminui a dotação, e ninguém confere duas vezes um número positivo numa soma.
   Todo crédito exige o `ato` (lei ou decreto) que o autorizou.
4. **O empenhado vem do retorno do sistema financeiro** (`debito.valor_empenhado`, da 0144), não
   do valor solicitado. O Aprimora não empenha: registra o que foi empenhado e confere.

**As duas ausências que a tela declara, em vez de esconder:**

- **Despesa sem dotação** é contada e mostrada à parte, nunca rateada entre as dotações
  existentes — ratear inventaria execução que não aconteceu. É o que explica a diferença entre o
  que o município gastou e o que o orçamento registra.
- **Despesa sem retorno de empenho** não conta como executada, e a contagem acompanha o número.
  Execução baixa pode ser "gastou pouco" **ou** "o retorno não chegou", e as duas leituras pedem
  ações opostas.

**`id_dotacao` é nullable de propósito:** toda despesa que já existe nasceu sem dotação, e exigir
o vínculo no dia do deploy travaria o módulo. O `exercicio` foi backfilled a partir da
competência, que é NOT NULL e é o mês de referência informado por quem abriu a despesa.

**Catálogo atualizado:** `disponibilidade_orcamentaria` passou a `disponivel=True`, e entraram
`dotacao_atualizada` e `execucao_orcamentaria`. `restos_a_pagar` continua indisponível, mas com
outro motivo — agora é possível (a despesa tem exercício) e falta o processo de virada.
`reserva_orcamentaria` continua fora: reservar dotação é rito próprio, com ato e cancelamento.

**Fora do O1:** reserva orçamentária, restos a pagar (virada de exercício), importação de QDD, e
empenho automático contra a dotação.

## 6. Decisões

### Fechadas (Jorge, 2026-11-24)

1. ~~**Slug**~~ → **"Despesa" é só rótulo.** `/m/pagamentos`, tabelas, transações e APIs ficam.
2. ~~**Empenho/liquidação**~~ → **entram `valor_empenhado` e `valor_liquidado`**, para receber o
   retorno do sistema financeiro. Resolvido: coluna, sobrescrita pelo retorno, campo `revisado`.
3. ~~**Orçamento**~~ → **ENTROU NO ESCOPO** (Jorge, 2026-11-24). Fundação entregue no O1: dotação,
   classificação funcional-programática, créditos adicionais, vínculo da despesa e execução.
   Ver 5.8.
4. ~~**Exercício no débito**~~ → **ENTROU junto com o orçamento** (a dotação é por exercício).
   `debito.exercicio` existe, com backfill da competência. **Restos a pagar continua em aberto**:
   depende do processo de virada de exercício.

### Abertas

5. **Mockups:** valem como direção visual a adaptar ao design system atual, ou como especificação
   de tela a reproduzir? E o velocímetro fica, contra o §9.1 do próprio brief?
6. **Categorias gerenciais do §9** (medicamentos, combustíveis, alimentação escolar…): viram
   cadastro com vínculo explícito, ou o módulo fica com `BENS/LOCACOES/SERVICOS/OBRAS` +
   `PESSOAL/CUSTEIO/INVESTIMENTO/DIVIDA/OUTRAS`, que são rastreáveis hoje?
7. **O §12 truncado:** mandar o texto completo da fórmula de disponibilidade residual.
