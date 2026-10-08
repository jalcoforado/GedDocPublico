# Contratos G1 — módulo e contrato (desenho)

**Status:** desenho aprovado pelo Jorge em 2026-10-08 ("pode ir"), com as cinco recomendações da
seção 10. **Backend implementado e NÃO executado contra banco** — ver a seção 12. Frontend por
fazer.
**Autoridade:** este documento, sobre o *como* da fatia G1. O *o quê* está em
[`2026-10-08-contratos-convenios-planejamento-escopo.md`](2026-10-08-contratos-convenios-planejamento-escopo.md)
(seção 9, fatia G1; decisões D1–D11 na seção 10).
**Redigido em:** 2026-10-08. Levantamento do código feito nessa data, em `main` (`d2aadd4`).

**O que a G1 entrega, em uma frase:** um sexto módulo contratável, `contratos`, em que o município
cadastra o contrato com os dados que o TCE-CE cobra, registra cada aditivo e cada apostila como
ato próprio, e vê valor e vigência atualizados calculados — com dados de demonstração de
Itaitinga.

**O que a G1 não entrega:** fiscal e gestor, alertas, garantia (G2); o processo de contratação
(G3); ocorrências, medição e saldo (G4); convênios (G5); conferência com o SIM (G6). A seção 9
lista cada exclusão com o motivo.

Há **cinco decisões de desenho** na seção 10 que precisam do seu de-acordo antes de qualquer
código. Cada uma traz recomendação.

---

## 1. O ponto de partida no código

Conferido em 2026-10-08.

- O contrato vive em `pagamentos.contrato` (migration `0045`): número, fornecedor, unidade,
  objeto, vigência, valor, categoria da fila cronológica. Unicidade por `(tenant_id, numero)`
  entre os não excluídos.
- API em `routers/pagamentos_cadastros.py` (`contratos_router`, prefixo `/pagamentos/contratos`),
  cinco rotas, todas sob a transação `pagamento_cadastro`. Regras em
  `services/pagamentos_cadastros.py`. Tela em `app/(app)/m/pagamentos/cadastros/contratos/`.
- **Pagamentos usa do contrato só duas coisas:** `id_unidade` (na autorização, para achar o órgão
  da despesa) e `categoria` (na fila cronológica). Valor e vigência **não são lidos por nenhuma
  regra** — o débito não é validado contra o saldo nem contra a vigência do contrato. Isso torna a
  evolução segura: mudar o significado de valor e vigência não quebra pagamento nenhum.
- O débito aponta para o contrato por `debito.id_contrato`, opcional.
- O fornecedor (`pagamentos.fornecedor`) também é do módulo de pagamentos, sob a mesma transação,
  e carrega dados bancários cifrados.

## 2. O que muda no domínio

Hoje o contrato é uma ficha: um valor, uma vigência, editáveis à vontade. Depois da G1:

- **O contrato tem situação.** Nasce `RASCUNHO`, é assinado e vira `VIGENTE`, termina em
  `ENCERRADO` ou `RESCINDIDO`. "Vencido" **não é situação**: é vigente com data final no passado
  — um fato do calendário, calculado, que a G2 vai transformar em alerta.
- **Valor e vigência originais congelam na assinatura.** A partir de `VIGENTE`, só mudam por
  aditivo ou apostila. É a regra do SIM (aditivo é registro novo, seção 3.1 do planejamento) e
  é o que permite responder "quanto este contrato já foi aditivado".
- **Aditivo e apostila são atos**, com número, data, tipo e justificativa. Não se edita o
  contrato; registra-se o ato.
- **Valor atualizado e vigência atual são calculados**, nunca gravados. Mesma disciplina de
  `Debito.status` desde a F5 de pagamentos: o que se deriva não se armazena, e uma guarda impede
  a regressão.

### 2.1 Situações do contrato

| De | Para | Quem dispara | Exige |
|---|---|---|---|
| — | `RASCUNHO` | criar | campos mínimos |
| `RASCUNHO` | `VIGENTE` | assinar | data de celebração, tipo de objeto, natureza de duração, número em formato SIM |
| `VIGENTE` | `ENCERRADO` | encerrar | data de encerramento |
| `VIGENTE` | `RESCINDIDO` | rescindir | data e motivo |
| `RASCUNHO` | excluído | excluir | — (soft-delete) |

Transição fora da tabela é **409**. Contrato `VIGENTE` ou posterior não se exclui: é registro de
ato administrativo.

### 2.2 Tipos de aditivo

Os seis códigos são os do SIM (tabela 511, campo 7), adotados como estão para a G6 não precisar
de tradução:

| Código | Tipo | Valor | Nova data final |
|---|---|---|---|
| `AA` | Acréscimo | > 0 | não informa |
| `AR` | Redução | > 0 | não informa |
| `AP` | Prazo | = 0 | obrigatória |
| `PA` | Prazo e acréscimo | > 0 | obrigatória |
| `PR` | Prazo e redução | > 0 | obrigatória |
| `RE` | Renovação | > 0 | obrigatória |

O valor é sempre a **diferença, positiva** — inclusive na redução. É como o SIM quer, e guardar
assim elimina a classe de erro "sinal trocado na exportação". Combinação fora da tabela é **422**.
A nova data final tem de ser posterior à vigência atual.

O aditivo tem o mesmo ciclo curto do contrato: `RASCUNHO` → `VIGENTE`, e `ANULADO` para o que
foi assinado por engano. Só o `VIGENTE` entra nos cálculos.

### 2.3 Apostila

Para o que o art. 136 da Lei 14.133 dispensa de aditivo: `REAJUSTE`, `REPACTUACAO`,
`RAZAO_SOCIAL`, `DOTACAO`, `OUTRO`. Reajuste e repactuação levam `valor_delta` (pode ser
negativo) e o índice aplicado; as demais só descrição.

### 2.4 Os valores calculados

| Derivado | Fórmula |
|---|---|
| **Valor inicial atualizado** | valor inicial + Σ apostilas de reajuste e repactuação |
| **Acréscimos** | Σ valor dos aditivos `AA` e `PA` |
| **Supressões** | Σ valor dos aditivos `AR` e `PR` |
| **Renovações** | Σ valor dos aditivos `RE` |
| **Valor atualizado** | valor inicial atualizado + acréscimos − supressões + renovações |
| **Vigência atual** | a maior nova data final entre os aditivos; se não houver, a original |
| **% de acréscimo** | acréscimos ÷ valor inicial atualizado |
| **% de supressão** | supressões ÷ valor inicial atualizado |

Três escolhas embutidas nessa tabela, todas a confirmar com a procuradoria antes de virarem regra
(decisão **Q5**):

- **Acréscimo e supressão não se compensam.** Cada um é medido sozinho contra o limite. É a
  leitura mais conservadora; vem de memória da jurisprudência do TCU, não foi reconferida.
- **Renovação não conta no limite de 25%.** É prorrogação de contrato contínuo com novo período
  de valor, não acréscimo de objeto.
- **A base é o valor inicial atualizado**, como diz o art. 125 — por isso apostila de reajuste
  entra na base e não no numerador.

**O limite não bloqueia.** Passar de 25% (ou de 50% de acréscimo, quando o contrato é marcado
como reforma de edifício ou equipamento) exige justificativa preenchida e deixa o contrato
sinalizado. Bloquear seria errado: há alteração consensual e hipóteses excepcionais que o sistema
não consegue julgar. O planejamento já fixou o princípio — "não bloqueia, exige justificativa
registrada".

## 3. Modelo de dados

### 3.1 Colunas novas em `pagamentos.contrato`

| Coluna | Tipo | Nulo | Para quê |
|---|---|---|---|
| `situacao` | varchar(15) | não, default `VIGENTE` | §2.1. O default é `VIGENTE` para o backfill; contrato novo pelo módulo nasce `RASCUNHO` pelo service. |
| `exercicio` | integer | não | Ano da celebração. O SIM exige número único **por exercício**. Backfill: ano de `vigencia_inicio`. |
| `data_celebracao` | date | sim | SIM 511, campo 5. |
| `tipo_objeto` | char(1) | sim | As 18 categorias do SIM (A–R), campo 6. |
| `natureza_duracao` | varchar(10) | sim | `ESCOPO` ou `CONTINUO`. Arts. 106, 107 e 111 dão regra de vigência diferente a cada um; a G2 precisa disso para o alerta. |
| `reforma` | boolean | não, default false | Liga o limite de 50% do art. 125. |
| `id_processo` | integer | sim | FK para o processo do protocolo, quando existir. |
| `processo_numero` | varchar(15) | sim | Número do processo de contratação como vai ao SIM (campo 21). Texto até a G3. |
| `processo_data_autuacao` | date | sim | SIM, campo 20. |
| `pncp_id` | char(25) | sim | Id do contrato no PNCP (campo 24). |
| `pncp_publicado_em` | date | sim | Para a contagem de prazo da G2. |
| `data_encerramento` | date | sim | Preenchida em `ENCERRADO` e `RESCINDIDO`. |
| `motivo_rescisao` | varchar(500) | sim | — |

`valor_total`, `vigencia_inicio` e `vigencia_fim` **mantêm o nome e passam a significar "o
original"**. Renomear para `valor_inicial` seria mais claro e custaria tocar schemas, export,
seed e a tela de pagamentos sem ganho de comportamento; o significado fica travado por docstring
no modelo e pela guarda da §8.

`objeto` cresce de 255 para 3000 caracteres (o Mapa de Licitações do eContas aceita até 3000). O
SIM aceita 255; a truncagem é problema da G6, não do cadastro.

**Índice único:** `uq_contrato_tenant_numero` sai; entra
`uq_contrato_tenant_exercicio_numero (tenant_id, exercicio, numero) WHERE excluido = false`. Só
afrouxa — nenhuma linha que hoje é válida deixa de ser.

**`numero` continua aceitando 50 caracteres na tabela**, porque há linha gravada pelo cadastro de
pagamentos. A exigência dos 15 caracteres do SIM entra na transição para `VIGENTE` feita pelo
módulo novo — contrato que não vai ao Tribunal com aquele número não é assinado com ele.

`ADD COLUMN` herda RLS e grants; nada a repetir.

### 3.2 Schema `contratos` e as duas tabelas novas

`CREATE SCHEMA contratos` com `GRANT USAGE` para `aprimora_app` — padrão da `0045`.

**`contratos.aditivo`**

| Coluna | Tipo | Observação |
|---|---|---|
| `id`, `tenant_id`, `criado_em`, `atualizado_em`, `excluido` | — | padrão |
| `id_contrato` | integer, FK `pagamentos.contrato` | — |
| `sequencial` | integer | 1º, 2º… por contrato. Único por `(id_contrato, sequencial)` entre não excluídos. |
| `numero` | varchar(15) | Como vai ao SIM. Único por `(tenant_id, exercicio, numero)` — ver nota abaixo. |
| `exercicio` | integer | Ano da assinatura do aditivo. |
| `tipo` | char(2) | §2.2, com `CHECK`. |
| `data_assinatura` | date | — |
| `valor` | numeric(14,2) | ≥ 0, com `CHECK` casando tipo e valor. |
| `nova_vigencia_fim` | date, nulo | `CHECK` casando tipo e presença. |
| `justificativa` | varchar(1000) | Obrigatória quando o limite é ultrapassado. |
| `situacao` | varchar(10) | `RASCUNHO`, `VIGENTE`, `ANULADO`. |
| `pncp_id`, `pncp_publicado_em` | — | O aditivo também tem prazo de PNCP (art. 94). |
| `id_usuario_registro` | integer, FK `utils.usuario` | Quem registrou; vem do token, nunca do payload. |

Nota sobre o número: no SIM, contrato e aditivo dividem **o mesmo campo** ("Número do Contrato",
único no exercício). Um aditivo numerado igual a um contrato do mesmo ano derruba a remessa. O
banco não tem índice único entre duas tabelas; a regra fica no service, com teste, e a G6 a
reconfere.

**`contratos.apostila`**

| Coluna | Tipo | Observação |
|---|---|---|
| padrão + `id_contrato`, `sequencial`, `id_usuario_registro` | — | como no aditivo |
| `tipo` | varchar(15) | §2.3, com `CHECK`. |
| `data` | date | — |
| `valor_delta` | numeric(14,2), nulo | Obrigatório em reajuste e repactuação; pode ser negativo. |
| `indice` | varchar(60), nulo | "IPCA 12 meses 4,83%". |
| `descricao` | varchar(1000) | — |

Apostila não tem rascunho: é registro de um fato já ocorrido. Erro se corrige por exclusão lógica
e novo lançamento.

As duas tabelas levam o boilerplate completo de `CLAUDE.md` §Migrations: `tenant_id` NOT NULL com
FK, índices `(tenant_id, …)`, `ENABLE + FORCE ROW LEVEL SECURITY`, as duas policies com
`NULLIF(current_setting('app.tenant_id', true), '')::int`, `GRANT` na tabela e na sequence para
`aprimora_app`. Nenhuma task Celery escreve nelas na G1 — **sem grant para `aprimora_worker`**.

### 3.3 Catálogo de módulos e transação

- Linha nova em `aprimora_py.modulo`: slug `contratos`, nome "Contratos e Convênios", ícone
  `FileSignature`, contratável.
- Transação nova em `utils.transacao`: código `contrato`. Uma só na G1; as fatias seguintes
  trazem as suas (`contrato_fiscalizar` na G2, e assim por diante). Granularidade maior agora
  seria desenhar permissão para papel que ainda não existe.
- `MODULO_TRANSACOES` em `app/cli/seed_bootstrap.py` ganha `"contratos": ("contrato",)`. Sem
  isso `test_guarda_modularizacao.py` reprova — e é o seed que liga a transação ao sistema e ao
  módulo, como hoje.

### 3.4 Migrations

Três, na ordem. **Numeração: o próximo livre na hora de implementar.** `main` está em `0130`, e a
branch `feat/tema-por-prefeitura` já usa `0131` — quem mesclar depois renumera.

1. Catálogo: módulo `contratos` e transação `contrato`. `downgrade` remove a transação só se
   nenhum grupo a recebeu (padrão da `0074`).
2. `pagamentos.contrato`: colunas, backfill de `exercicio` e `situacao`, troca do índice único,
   `objeto` para 3000. `downgrade` recria o índice antigo — e **falha de propósito** se, nesse
   meio-tempo, dois contratos de exercícios diferentes tiverem recebido o mesmo número. É o
   comportamento certo: desfazer em silêncio perderia dado.
3. Schema `contratos` com `aditivo` e `apostila`.

Rodar o agente `migrations-checker` nas três antes do commit.

## 4. Quem contrata o módulo

- **Banco limpo:** `contratar_modulos_iniciais` contrata tudo que é contratável quando o tenant
  não tem nenhuma linha — o módulo novo entra sozinho. `ci/seed-e2e.sql` usa `CROSS JOIN` no
  catálogo e também o pega sem alteração. **Confirmar os dois na implementação**, não assumir.
- **Tenant que já existe** (o `sobral` da VPS, que apresenta como Itaitinga): a migration **não**
  contrata. Contratação é ato comercial; um `INSERT` por migration daria o módulo a todo
  município de uma vez. Quem contrata é o seed de demonstração (§7), no tenant alvo, ou o
  operador pela aba Módulos. Decisão **Q4**.

## 5. API

Router novo `routers/contratos.py`, prefixo `/contratos`, registrado em `main.py` com
`prefix="/api/v2"`. Regras em `services/contratos.py`; o router não decide nada.

| Método e rota | Faz | Gate |
|---|---|---|
| `GET /contratos` | Lista paginada. Filtros: situação, unidade, fornecedor, exercício, texto, `vence_ate` | módulo + `contrato` |
| `GET /contratos/resumo` | Contagens para o painel: vigentes, vencendo em 30/60/90/120 dias, acima do limite | módulo + `contrato` |
| `POST /contratos` | Cria em `RASCUNHO` | `contrato` · inserir |
| `GET /contratos/{id}` | Contrato + derivados da §2.4 + aditivos + apostilas | módulo + `contrato` |
| `PUT /contratos/{id}` | Edita. Em `VIGENTE`, só os campos que não são do ato (§5.1) | `contrato` · atualizar |
| `DELETE /contratos/{id}` | Soft-delete, só `RASCUNHO` | `contrato` · excluir |
| `POST /contratos/{id}/assinar` | `RASCUNHO` → `VIGENTE` | `contrato` · atualizar |
| `POST /contratos/{id}/encerrar` | → `ENCERRADO` | `contrato` · atualizar |
| `POST /contratos/{id}/rescindir` | → `RESCINDIDO` | `contrato` · atualizar |
| `POST /contratos/{id}/aditivos` | Cria aditivo em `RASCUNHO` | `contrato` · inserir |
| `PUT /contratos/{id}/aditivos/{aid}` | Edita, só `RASCUNHO` | `contrato` · atualizar |
| `POST /contratos/{id}/aditivos/{aid}/assinar` | → `VIGENTE`; aplica a regra do limite | `contrato` · atualizar |
| `POST /contratos/{id}/aditivos/{aid}/anular` | → `ANULADO`, com motivo | `contrato` · atualizar |
| `DELETE /contratos/{id}/aditivos/{aid}` | Soft-delete, só `RASCUNHO` | `contrato` · excluir |
| `POST /contratos/{id}/apostilas` | Registra | `contrato` · inserir |
| `DELETE /contratos/{id}/apostilas/{pid}` | Soft-delete | `contrato` · excluir |

Regras que o repositório já cobra, aplicadas aqui:

- **`/contratos/resumo` é declarada antes de `/contratos/{id}`.** A paramétrica engole a literal e
  a requisição morre em 422; `test_guarda_ordem_rotas.py` reprova.
- **Todo GET leva módulo e transação** — `require_modulo("contratos")` e
  `require_permission("contrato")`. GET novo sem transação é reprovado por
  `test_leitura_sem_permissao_nao_cresce_sem_decisao`.
- **`action` só `inserir`, `atualizar` ou `excluir`.** Não existe `"visualizar"`; foi esse o 500
  do transporte.
- `tenant_id` vem de `require_tenant_id`; `situacao`, `exercicio`, `id_usuario_registro` e os
  derivados **não entram em schema de entrada**. Carga por id filtra tenant e `excluido` e devolve
  **404** cross-tenant. Fornecedor, unidade e processo passam por validação same-tenant.
- **Sigilo.** `id_processo` aponta para um processo que pode ser sigiloso. Ao vincular e ao
  devolver número ou assunto do processo, passa por `assert_acesso_processo`; sem credencial, o
  contrato aparece e o vínculo vem vazio — **não** 404 no contrato inteiro.
- Lista devolve `Paginated[ContratoResumoOut]`; no `api.ts`, `request<Paginated<…>>` e a tela
  consome `.items`.

### 5.1 O que se edita em contrato vigente

Livre: `tipo_objeto`, `id_processo`, `processo_numero`, `processo_data_autuacao`, `pncp_id`,
`pncp_publicado_em`, `categoria`. São dados *sobre* o contrato, que costumam chegar depois da
assinatura.

Travado, **409** com mensagem que aponta o caminho: `numero`, `exercicio`, `id_fornecedor`,
`objeto`, `valor_total`, `vigencia_inicio`, `vigencia_fim`, `data_celebracao`. "Altere por
aditivo ou apostila."

### 5.2 Convivência com `/pagamentos/contratos`

As cinco rotas antigas **continuam existindo**. Um município com pagamentos e sem o módulo novo
precisa seguir cadastrando contrato simples para vincular débito — tirar isso quebraria quem já
usa.

A regra de convivência é uma só: **com o módulo `contratos` contratado, a escrita pelas rotas de
pagamentos é recusada com 409** ("este município gerencia contratos no módulo Contratos"). A
leitura segue normal. Sem isso haveria dois caminhos para mudar valor e vigência, e um deles
ignoraria aditivo. Decisão **Q3**.

O contrato criado pela rota antiga nasce `VIGENTE` (o default da coluna) e com `exercicio`
derivado da vigência — é o mesmo tratamento do backfill.

## 6. Frontend

- **Menu:** `frontend/lib/menus/contratos.ts`, registrado em `MENUS` (`lib/menus/index.ts`).
  Itens da G1: Painel, Contratos. Ambos com `perm: "contrato"`, e os dois entram em
  `PERMISSOES_ESPERADAS` de `__tests__/menus.test.tsx`.
- **Slug sem rota legada — atenção.** `SLUGS_MODULO` é derivado de `ROTA_MODULO`, que lista
  prefixos *antigos*. O módulo novo não tem prefixo antigo; se nada for feito, `/m/contratos`
  cai como slug desconhecido e o guard e a Sidebar o tratam como rota transversal. Colocar
  `["/contratos", "contratos"]` em `ROTA_MODULO` resolveria por acidente e criaria uma URL
  legada que nunca existiu, com 308 obrigatório e token novo no nginx para sempre.
  **O desenho:** uma lista explícita de slugs nascidos depois da F3, somada ao conjunto —
  `SLUGS_MODULO = slugs de ROTA_MODULO ∪ SLUGS_SEM_ROTA_LEGADA`. E o
  `__tests__/rotas-modulo.test.ts` ganha a asserção de que todo slug de `MENUS` é reconhecido por
  `moduloDoPathname("/m/<slug>")` — é o teste que teria avisado.
- **Ícone:** `FileSignature` entra em `ICONES_MODULO` (`lib/modulos.ts`); sem isso o launcher
  mostra o ícone genérico, em silêncio.
- **nginx:** nada a fazer. As telas ficam sob `/m/contratos/`, e o token `m` já está na regex.
- **Telas**, todas em `app/(app)/m/contratos/`:

| Rota | Tela |
|---|---|
| `/m/contratos` | Painel: cartões do `/resumo` e a lista dos que vencem primeiro |
| `/m/contratos/contratos` | Lista com filtros e paginação |
| `/m/contratos/contratos/novo` | Formulário de criação |
| `/m/contratos/contratos/[id]` | Detalhe: cabeçalho com valor e vigência atualizados e a barra do percentual aditivado; abas Dados, Aditivos, Apostilas; ações de assinar, encerrar, rescindir |

  Cada uma precisa de `href` que chegue nela no mesmo PR — a guarda de página órfã reprova,
  inclusive a aninhada sob `[id]`.
- **`lib/api.ts`:** tipos espelhando os `*Out` e o grupo de métodos `contratos`. Datas e campos
  opcionais vazios viram `null` antes do envio.
- **Tela antiga de pagamentos** (`/m/pagamentos/cadastros/contratos`): quando o município tem o
  módulo novo, vira somente leitura com um link para `/m/contratos/contratos`. É UX — a barreira
  é o 409 da §5.2.
- `npx tsc --noEmit` antes de commitar.

## 7. Dados de demonstração

A carga é fabricada (decisão D9). Entra como mais um alvo de `seed_demo_operacional`
(`--modulo contratos`), porque esse seed já é dono dos contratos e fornecedores de demonstração e
já passa pelos services.

- **Contrata o módulo** no tenant alvo (§4) e roda **depois** de `seed_itaitinga`, para os
  contratos caírem nas secretarias reais.
- Cerca de 20 contratos, distribuídos pelas secretarias, cobrindo de propósito: os dois tipos de
  duração; um de cada categoria de objeto mais comum (merenda, transporte escolar, combustível,
  locação de imóvel, obra, TI, medicamentos, coleta de resíduos); os seis tipos de aditivo; um
  contrato a 23% de acréscimo e outro acima de 25% com justificativa; uma reforma acima de 25% e
  abaixo de 50%; apostilas de reajuste; um rescindido, um encerrado, dois em rascunho.
- **Datas relativas ao dia em que o seed roda**, para o painel sempre ter contrato vencendo em
  30, 60 e 90 dias. Mesmo motivo do mapa da frota: dado com data fixa envelhece antes da
  apresentação. `reset` + `apply` no dia.
- Fornecedores e valores são **fictícios e marcados como tal**. Não usar nome nem CNPJ de
  empresa real do portal de Itaitinga: é demonstração publicada em VPS.
- `reset --modulo contratos` apaga aditivos e apostilas e devolve os contratos ao que o seed de
  pagamentos criou. O `DELETE FROM pagamentos.contrato` que já existe no reset de pagamentos
  precisa apagar antes as tabelas filhas — senão passa a falhar por FK.

## 8. Testes

Backend, `tests/test_contratos_*.py`:

| Arquivo | Cobre |
|---|---|
| `test_contratos_ciclo.py` | Transições da §2.1; 409 nas ilegais; exclusão só em rascunho; campos travados em vigente |
| `test_contratos_aditivos.py` | As seis combinações de tipo, valor e data; 422 nas inválidas; nova data anterior à vigência atual; numeração colidindo com contrato do mesmo exercício |
| `test_contratos_calculo.py` | A tabela da §2.4 caso a caso; aditivo anulado e em rascunho fora da conta; limite de 25% e de 50%; justificativa obrigatória acima do limite |
| `test_contratos_isolamento.py` | RLS com `app_session` (não `admin_session`); 404 cross-tenant por id em contrato, aditivo e apostila; FK de fornecedor, unidade e processo de outro tenant recusada |
| `test_contratos_http.py` | **Usuário comum**, não super-usuário: lê com a transação, 403 sem ela, 403 com tenant sem o módulo — inclusive o SU |
| `test_contratos_convivencia.py` | §5.2: escrita por `/pagamentos/contratos` vira 409 com o módulo contratado e segue 201 sem ele; débito continua vinculando contrato nos dois casos |
| `test_contratos_sigilo.py` | Vínculo com processo sigiloso some para quem não tem credencial; o contrato não |

O teste de usuário comum não é opcional: o bypass de super-usuário retorna antes do gate e
esconde justamente o defeito que importa (`CLAUDE.md`, §Testes). Padrão em
`test_permissoes_modulo.py::_cria_usuario_comum`. O tenant do teste precisa contratar o módulo,
senão o 403 vem do lugar errado.

**Guarda nova:** `test_guarda_contrato_derivado.py` — nenhum código fora de `services/contratos.py`
escreve `valor_total`, `vigencia_inicio` ou `vigencia_fim` de contrato que não esteja em
rascunho. Com controle contra verde por vacuidade e **invertida antes de valer** (o repositório
já pagou por guarda que nunca falhou). Entra em `docs/INDEX.md` no mesmo commit, ou
`test_guarda_links_docs.py` reprova.

Guardas existentes que esta fatia precisa atravessar: modularização, ordem de rotas, contrato
paginado, RLS de toda tabela sob `aprimora_app`, links de docs, e no frontend `menus.test.tsx` e
`rotas-modulo.test.ts`.

Bateria antes do PR: `alembic heads` (único), `upgrade` e `downgrade -1` das três, suíte completa
com `PYTEST_DB_HOST=db`, a mesma suíte sob `aprimora_app`, `vitest`, `tsc --noEmit`.

## 9. Fora da G1, e por quê

| Fica de fora | Vai para | Por quê |
|---|---|---|
| Fiscal, gestor, portaria, agentes públicos | G2 | Precisa do cadastro de agentes; é a fatia que estreia usuário não-SU de verdade. |
| Alertas de vigência e de prazo de PNCP | G2 | A G1 já guarda as datas e expõe `vence_ate`; o alerta é notificação e job. |
| Garantia contratual | G2 | Tem prazo próprio; anda junto dos alertas. |
| Signatário (CPF do gestor que celebrou, SIM campo 3) | G2 | Vira FK para agente público. Guardar CPF solto agora é coluna a migrar depois. |
| Processo de contratação estruturado | G3 | Na G1 o processo é número e data em texto. |
| Dados de obra (SIM campos 15–18) | G4 | Dependem do cadastro de obras, que nasce com medição. |
| Saldo empenhado, liquidado e pago | G4 | Depende da importação da ASPEC (D13). |
| Anexo do instrumento assinado | G2 | Reaproveita anexos e assinatura; não muda o modelo. |
| Convênios e parcerias | G5 | — |
| Arquivo e conferência do SIM | G6 | — |

## 10. Decisões de desenho — precisam do seu de-acordo

| # | Decisão | Recomendação | Alternativa e custo |
|---|---|---|---|
| **Q1** | Onde mora a tabela de contrato? | **Fica em `pagamentos.contrato`**, com colunas novas. As tabelas novas nascem no schema `contratos`. O dono é quem tem a transação, não o nome do schema. | `ALTER TABLE … SET SCHEMA contratos`: nome honesto, e o Postgres leva FKs e policies junto. Custa tocar o modelo, o SQL cru do seed e conferir grants no schema novo — risco sem ganho de comportamento. Pode ser feito depois, sozinho. |
| **Q2** | Fornecedor para município sem pagamentos | **Adiar.** Na G1 o módulo novo lê e cria fornecedor pelos services existentes, sob a transação `contrato`, sem tocar dados bancários. A transação `pagamento_cadastro` continua valendo para as telas de pagamentos. | Promover fornecedor a cadastro transversal, com transação própria em `comum`. É o desenho final provável, mas mexe em permissão de pagamentos; merece fatia própria, antes do primeiro município que contrate só `contratos`. |
| **Q3** | Escrita de contrato por pagamentos quando há o módulo novo | **Recusar com 409** e deixar a tela antiga somente leitura. | Manter as duas escritas: dois caminhos para mudar valor, um deles ignorando aditivo. |
| **Q4** | Quem contrata o módulo em tenant existente | **Ninguém por migration.** O seed de demonstração contrata no tenant alvo; operador contrata pela aba Módulos. | Backfill em todos os tenants, como a `0073` fez: simples, mas dá o módulo de graça a todo mundo. |
| **Q5** | As três regras do cálculo do limite (§2.4) | **Implementar como descrito, sem bloqueio**, e levar à procuradoria antes do piloto real. Como o limite só sinaliza, errar a regra gera alerta errado, não ato inválido. | Esperar o parecer: trava a fatia inteira por uma regra que não bloqueia nada. |

Uma pendência que **não** é decisão sua, mas da contabilidade de Itaitinga: **como o reajuste por
apostila é informado hoje ao SIM**. A tabela 511 não tem modalidade de apostila; ou o reajuste
vai como aditivo de acréscimo, ou não vai. A resposta não muda a G1 — muda a exportação da G6.

## 11. Ordem de implementação sugerida

> Estado em 2026-10-08: itens 1 a 4 e 6 escritos (branch `feat/contratos-g1`); 5 e 7 por fazer.

Um PR só, mas nesta sequência de commits, cada um verde:

1. Migrations e modelos; `MODULO_TRANSACOES`.
2. Service de contrato com o ciclo de situações; testes de ciclo e isolamento.
3. Aditivo, apostila e o cálculo; testes de cálculo. A guarda do derivado, invertida.
4. Router, schemas, gates; testes HTTP com usuário comum; convivência com pagamentos.
5. Frontend: slug e menu primeiro (com os testes de menu e de rota), depois as telas.
6. Seed de demonstração.
7. Documentação: `CLAUDE.md` (o sexto módulo, a regra do derivado, a convivência da §5.2),
   `docs/INDEX.md`, `BACKLOG-PENDENCIAS.md`.

O item 7 não é enfeite: `CLAUDE.md` diz hoje que são **cinco** módulos contratáveis, e é o
documento carregado em toda sessão.

## 12. O que a implementação mudou no desenho, e o que ainda não foi provado

Registrado em 2026-10-08, ao fim da implementação do backend.

### 12.1 Quatro desvios

| O desenho dizia | O que foi feito | Por quê |
|---|---|---|
| §3.2 — schema novo `contratos` para `aditivo` e `apostila` | Ficam em `pagamentos`, como `contrato_aditivo` e `contrato_apostila` | A migration `0078` distribui `USAGE`/`CREATE`, grants e `ALTER DEFAULT PRIVILEGES` de `aprimora_migrator` e `aprimora_worker` por uma **lista fechada de schemas**, e `test_rls_papeis_minimos.py` varre a mesma lista. Schema novo teria de repetir tudo à mão, e o que faltasse só quebraria no seed seguinte. É a mesma razão da decisão Q1. |
| §5 — toda rota com `require_modulo("contratos")` **e** `require_permission` | Só `require_permission("contrato")` | É o arranjo de frota e pagamentos: transação de módulo não contratado é bloqueada dentro de `require_permission`, antes do bypass de super-usuário. `require_modulo` existe para GET que não tinha transação nenhuma. Há teste HTTP provando que o SU de tenant sem o módulo leva 403. |
| §7 — mais um `--modulo` do `seed_demo_operacional` | CLI próprio, `app.cli.seed_demo_contratos` | Lá, `MODULOS` define o que é "todos" e condiciona o reset de usuários; um quarto módulo mudaria o comportamento de um seed que já tem teste. |
| §5 — 16 rotas | 18: entraram `GET` e `POST /contratos/fornecedores` e `GET /contratos/catalogos` | Consequência direta da decisão Q2: quem tem só a transação `contrato` precisa escolher e criar o contratado, e `/pagamentos/fornecedores` está bloqueado para ele. Devolvem só identificação, sem dado bancário. |

Um quinto ponto, menor: a lista do que se edita em contrato vigente (§5.1) virou **lista de
permitidos**, não de proibidos — coluna nova nasce travada. `natureza_duracao` entrou nos
permitidos; `reforma` e `id_unidade` ficaram travados, porque mudam o limite e o órgão da despesa.

### 12.2 O que foi verificado, e o que não foi

O Docker da máquina de desenvolvimento não subiu durante a implementação ("access is denied…
another user has already started Docker Desktop"), e não há Python com dependências nem Node fora
dele. **Nenhuma migration foi aplicada e a suíte não rodou.**

Verificado, com arneses que simulam `fastapi`/`sqlalchemy`:

- `py_compile` de todos os arquivos tocados;
- os 27 casos de `test_contratos_calculo.py` (a função `calcular` é pura);
- `test_guarda_contrato_derivado.py`, verde e depois **invertida de três formas** — atribuição
  direta num service, `UPDATE` em massa num router, e o aditivo escrevendo no contrato. Reprovou
  nas três;
- o roteiro do seed contra as regras puras do service: os 20 contratos e seus atos passam, e o
  painel resultante tem 16 vigentes, 1 vencido, 1 acima do limite.

**Nunca rodou:** as três migrations (inclusive `downgrade`), `test_contratos_servico.py`,
`test_contratos_http.py`, `test_contratos_rls.py`, o seed contra banco, e o efeito das mudanças
sobre a suíte existente de pagamentos. O primeiro verde de verdade vem do CI, que só roda em PR.

Três pontos onde é mais provável aparecer erro na primeira execução, por terem sido escritos sem
retorno do banco:

1. a subconsulta correlacionada de `_vigencia_atual_sql` (filtro e ordenação da listagem);
2. `ContratoOut.model_validate(dict, from_attributes=True)` com o `Calculo` (dataclass) e os
   modelos ORM aninhados;
3. o `downgrade` da `0131`, que apaga a transação só se nenhum grupo **e** nenhum sistema a
   referenciam — depois do `seed_bootstrap`, ela fica.

Uma lacuna de teste declarada: o vínculo com processo sigiloso só tem o caminho da **recusa**
coberto (com `assert_acesso_processo` trocado por um que nega). O caminho em que o usuário tem
credencial exige um processo real e ficou para a G3.
