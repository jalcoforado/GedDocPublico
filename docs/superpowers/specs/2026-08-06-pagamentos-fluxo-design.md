# Refatoração do módulo de Pagamentos — fluxo, estados e navegação

**Data:** 2026-08-06
**Situação:** proposta, aguardando revisão
**Origem:** pedido do Jorge com diagrama do fluxo em 5 etapas e especificação funcional de 20 seções
**Alvo:** `main` em `caeaafc`; head Alembic `0084`

---

## 1. Por que existe esta spec

O módulo de pagamentos foi entregue em duas ondas (R1 caixa, R2 workflow, mais a Onda C) e é
sólido no que diz respeito a dinheiro: reserva de saldo na conta pagadora, alçadas
multidimensionais, conciliação bancária, relatório de exceções, histórico append-only com IP.
Nada disso é reescrito aqui.

O que está errado é o **rito**. O fluxo implementado não é o fluxo do processo administrativo de
despesa pública, e a interface obriga o usuário a deduzir em que ponto está a partir de um enum
técnico de 16 valores.

Esta spec descreve o estado final e a ordem em que se chega lá. Ela não é um plano de
implementação — esse vem depois, uma fatia por vez.

---

## 2. Diagnóstico do módulo atual

### 2.1 O fluxo está invertido

Implementado hoje (`services/pagamentos_debitos.py`):

```
RASCUNHO → EM_VALIDACAO → VALIDADO → ENVIADO_SECRETARIO → AGUARDANDO_AUTORIZACAO
        → AUTORIZADO → ENVIADO_TESOURARIA → EM_PROCESSAMENTO → PAGO_PARCIAL → PAGO → CONCILIADO
```

O fluxo correto põe o **Gestor da Pasta antes da Validação Financeira**: o mérito e a
conveniência da despesa são juízo do gestor, e não faz sentido gastar conferência documental
numa despesa que o gestor vai recusar. Hoje é o contrário.

Pior: o papel que hoje ocupa a posição do gestor — o "secretário" de `encaminhar()`
([`pagamentos_debitos.py:315`](../../../backend/app/services/pagamentos_debitos.py)) — **não decide
nada**. A função move `VALIDADO → ENVIADO_SECRETARIO` e mais nada. Não autoriza, não devolve, não
rejeita. É um carimbo.

### 2.2 A validação financeira pode encerrar o processo

`rejeitar()` aceita `ST_EM_VALIDACAO` entre os status de origem, e o endpoint
`POST /debitos/{id}/rejeitar` é gateado por `PERM_VALIDAR = ("pagamento_validar",
"pagamento_aprovar")`. O mesmo vale para `suspender()`.

Consequência: quem confere nota fiscal pode matar a solicitação. A conformidade documental é um
juízo técnico vinculado — quem a exerce aponta a inconformidade e devolve; não decide sobre a
despesa. Esta é a regra mais explícita do pedido e a que o código mais claramente viola.

### 2.3 Um campo `status` fazendo o trabalho de três

`Debito.status` (`String(25)`, 16 valores) mistura três eixos ortogonais:

| Eixo | Valores hoje presos no mesmo campo |
|---|---|
| Tramitação | `RASCUNHO`, `EM_VALIDACAO`, `DEVOLVIDO`, `VALIDADO`, `ENVIADO_SECRETARIO`, `AGUARDANDO_AUTORIZACAO`, `AUTORIZADO`, `REJEITADO`, `CANCELADO`, `SUSPENSO` |
| Fila cronológica | *(nenhum — o conceito não existe)* |
| Execução | `ENVIADO_TESOURARIA`, `EM_PROCESSAMENTO`, `PAGO_PARCIAL`, `PAGO`, `CONCILIADO`, `ESTORNADO` |

Como os valores são mutuamente exclusivos, um débito `PAGO_PARCIAL` **não consegue expressar** sua
situação de tramitação, e nenhum débito consegue expressar posição na fila. Esta é a causa raiz da
ambiguidade relatada.

### 2.4 Ordem cronológica não existe

Não há tabela, campo, marco, posição, bloqueio nem exceção. O que existe são
`fila_liberacao()` e `fila_tesouraria()` (`services/pagamentos_filas.py`): consultas ad-hoc que
ordenam por conta bancária e vencimento, recalculadas a cada request, sem nada persistido.

Ordenar por **vencimento** não é ordem cronológica. O marco legal é a **liquidação** (art. 141 da
Lei 14.133/2021; art. 5º da Lei 8.666/93 antes dela), e a ordem é apurada dentro de cada
combinação de fonte de recursos e categoria de contrato — não globalmente. Não há como demonstrar
a um órgão de controle a ordem praticada, nem justificar formalmente um pagamento fora de ordem.

Esta é a lacuna mais grave da lista, porque as outras produzem confusão e esta produz
irregularidade.

### 2.5 Pedido de ajuste é uma string

`devolver(justificativa)` grava uma linha em `debito_historico` e muda o status para `DEVOLVIDO`.
Não existe: responsável designado pela correção, situação da pendência (aberta/respondida/
resolvida), resposta do responsável, prazo, vínculo com campos ou documentos específicos, nem
distinção entre ajuste material e não material.

Na prática o solicitante recebe um texto livre e precisa adivinhar o que corrigir.

### 2.6 Sem versionamento

Um débito devolvido é reeditado **no mesmo registro**. Trocar o fornecedor, o valor ou a nota
fiscal de uma solicitação que já passou por validação sobrescreve os dados; o histórico registra
que houve devolução, mas não o que a solicitação era antes. Não há invalidação explícita de
aprovações que deixaram de valer.

### 2.7 Débito não tem unidade administrativa

`Debito` não possui `id_unidade`. A unidade só é alcançável por `contrato.id_unidade` — logo,
**débito sem contrato não tem unidade nenhuma**. Isso inviabiliza simultaneamente o conceito de
"Unidade Setorial" como origem da solicitação e a chave da fila cronológica.

### 2.8 Débito não tem documentos

Não há anexo de débito: nem modelo, nem tabela, nem endpoint. O checklist documental
(`checklist_item` / `debito_checklist_marca`) marca "conforme" sobre documentos **que o sistema não
guarda**. O validador confere fora do sistema e registra a conclusão dentro dele.

### 2.9 Retenções não existem

Nenhuma tabela, nenhum campo. O `valor_total` do débito é bruto e não há valor líquido.

### 2.10 Navegação

Sete rotas de topo (`/m/pagamentos`, `dashboard`, `contas-a-pagar`, `autorizacao`, `tesouraria`,
`caixa`, `conciliacao`, mais sete de cadastro). Problemas:

- **Não há caixa de trabalho.** O endpoint `GET /pagamentos/minha-fila` existe e **nenhuma tela o
  consome**. O usuário descobre o que lhe cabe navegando pelas listas.
- **"Contas a pagar"** (593 linhas) é uma lista genérica com 12 abas de status técnico. É a mesma
  tela para todos os perfis.
- **O detalhe** (725 linhas) não tem stepper fiel, nem bloco de próxima ação, nem responsável atual.
- **`RitoPagamento`** mostra 5 passos — *Solicitar / Aprovar / Autorizar despesa / Liberar
  pagamento / Pagar*. Não são as 5 etapas do processo; "Liberar" é um ato interno da tesouraria e
  "Aprovar" é ambíguo entre gestor e validação.
- **Nenhuma etapa do fluxo é um item de menu.**

### 2.11 Permissões

Oito transações declaradas em `MODULO_TRANSACOES` (`cli/seed_bootstrap.py`), cinco usadas no menu:

| Transação | Uso hoje | Problema |
|---|---|---|
| `pagamento_solicitar` | criar/editar/enviar/cancelar | ok |
| `pagamento_validar` | validar, devolver, rejeitar | rejeita — não deveria |
| `pagamento_aprovar` | **alias de validar** | nome mente sobre o que faz |
| `pagamento_encaminhar` | `encaminhar()` | sem tela; papel sem decisão |
| `pagamento_autorizar` | autorizar, liberar parcelas, revogar | acumula autorização e liberação |
| `pagamento_pagar` | pagar, estornar, suspender, reativar | tesouraria pode suspender pré-autorização |
| `pagamento_auditar` | leitura de conciliação | subutilizada |
| `pagamento_cadastro` | cadastros e caixa | ok |

Não há transação para o Gestor da Pasta como papel decisório.

### 2.12 Concorrência

Não há controle otimista nas decisões. `autorizar()` usa lock pessimista na conta (correto, é
dinheiro), mas `validar`, `devolver`, `rejeitar` e `encaminhar` não checam versão. Dois usuários
decidindo a mesma etapa: o segundo sobrescreve, e o `_exigir_status` só pega o caso em que o status
já mudou — não o caso de duas decisões concorrentes chegando ao mesmo status por caminhos
diferentes.

### 2.13 O que está bom e deve ser preservado

- Checklist parametrizável por natureza de despesa, com log append-only de marcações.
- Alçadas multidimensionais (`alcada`: usuário × natureza × unidade × fonte × tipo). **A autoridade
  já não é "Prefeito" cravado no código** — o requisito de parametrização está parcialmente
  atendido.
- Segregação solicitante ≠ validador (`RF-SEG-01`, com teste).
- Reserva de saldo na conta pagadora no ato da autorização, com `saldo_antes`/`saldo_projetado_apos`
  gravados para auditoria.
- `debito_historico` append-only com `ip_origem`.
- Conciliação bancária e relatório de exceções.
- Dados bancários de fornecedor cifrados (colunas `*_cif`).

---

## 3. Fluxo alvo

```
                    ┌──── ajuste ────┐   ┌──── ajuste ────┐   ┌──── ajuste ────┐
                    ▼                │   ▼                │   ▼                │
  UNIDADE      GESTOR DA        VALIDAÇÃO         AUTORIDADE          TESOURARIA
  SETORIAL  →  PASTA         →  FINANCEIRA     →  COMPETENTE      →   (execução)
               ↓ rejeita                           ↓ indefere           ↓
               fim                                 fim                  pago
```

### 3.1 Decisões por etapa

| Etapa | Decisões | Encerra o processo? |
|---|---|---|
| Unidade Setorial | enviar, salvar rascunho, responder ajuste, cancelar | cancelar (com justificativa) |
| Gestor da Pasta | **autorizar**, solicitar ajustes, **rejeitar** | sim, rejeitar |
| Validação Financeira | **validar**, solicitar ajustes | **NÃO — e é a regra central** |
| Autoridade Competente | **aprovar e ordenar**, solicitar ajustes, **não aprovar** | sim, não aprovar |
| Tesouraria | programar, enviar, registrar, reprocessar, estornar | não (executa) |

A ausência de rejeição na validação financeira é garantida em três camadas: não existe função de
serviço que leve `AGUARDANDO_VALIDACAO` a um status terminal; o endpoint de rejeição não aceita
essa origem; e há teste que **inverte** a asserção (tenta rejeitar a partir da validação e exige
409).

---

## 4. Modelo de dados

### 4.1 As três dimensões

Três colunas novas em `pagamentos.debito`, cada uma com seu domínio fechado.

**`situacao_tramitacao`** — onde está o processo decisório:

| Valor | Responsável atual |
|---|---|
| `RASCUNHO` | unidade setorial |
| `AGUARDANDO_GESTOR` | gestor da pasta |
| `AJUSTE_GESTOR` | quem o pedido de ajuste designar |
| `AGUARDANDO_VALIDACAO` | validação financeira |
| `AJUSTE_VALIDACAO` | quem o pedido de ajuste designar |
| `AGUARDANDO_AUTORIDADE` | autoridade competente |
| `AJUSTE_AUTORIDADE` | quem o pedido de ajuste designar |
| `AUTORIZADA` | tesouraria (tramitação encerrada com êxito) |
| `REJEITADA_GESTOR` | — terminal |
| `INDEFERIDA_AUTORIDADE` | — terminal |
| `CANCELADA` | — terminal |

**`situacao_fila`** — posição na ordem cronológica:

`NAO_REGISTRADA` · `REGISTRADA` · `BLOQUEADA` · `ELEGIVEL` · `AGUARDANDO_DISPONIBILIDADE` ·
`EXCECAO_AUTORIZADA` · `CONCLUIDA` · `RETIRADA`

**`situacao_pagamento`** — execução:

`NAO_INICIADA` · `PROGRAMADA` · `ENVIADA_BANCO` · `EM_PROCESSAMENTO` · `PAGA_PARCIAL` · `PAGA` ·
`FALHOU` · `CANCELADA` · `ESTORNADA`

As três são independentes e sempre têm valor. Exemplo legítimo e hoje inexprimível:
`AUTORIZADA` + `BLOQUEADA` + `NAO_INICIADA` — "aprovada, mas parada na fila por falta de
disponibilidade".

**Granularidade.** As três vivem no **débito**. A execução continua sendo por parcela
(`pagamentos.parcela`); `situacao_pagamento` do débito é a agregação das parcelas, mantida pelo
serviço — que é o que `PAGO_PARCIAL`/`PAGO` já fazem hoje. Não se cria fila por parcela: o marco
cronológico é a liquidação da obrigação, e a obrigação é o débito.

### 4.2 A coluna `status` legada

`Debito.status` **não é removida na F1**. Ela passa a ser derivada das três dimensões e mantida em
sincronia por uma função única (`_sincronizar_status_legado`), porque hoje é lida por
`pagamentos_conciliacao`, `pagamentos_excecoes`, `pagamentos_dashboard`, `pagamentos_caixa`,
`pagamentos_filas` e pelo frontend inteiro. Convertê-los todos na mesma fatia é um diff grande
demais para revisar com segurança.

A coluna e a função morrem na **F5**, quando todos os consumidores tiverem migrado. Uma guarda
(`test_guarda_status_legado.py`) lista os arquivos que ainda podem ler `Debito.status` e reprova
consumidor novo — a lista só encolhe.

> **Risco registrado.** Coluna derivada mantida por código é uma fonte de divergência. A mitigação
> é a função única mais um teste que, para cada transição do novo fluxo, confere o valor legado
> resultante. Se a divergência aparecer mesmo assim, a resposta é acelerar a F5, não remendar.

### 4.3 Tabelas novas

#### `pagamentos.pedido_ajuste`

```
id, tenant_id, id_debito → debito(id)
versao_debito            int      -- versão vigente quando o pedido foi aberto
etapa_solicitante        varchar  -- GESTOR | VALIDACAO | AUTORIDADE
id_usuario_solicitante   → utils.usuario(id)
motivo                   varchar(255)   NOT NULL
descricao                text           NOT NULL  -- o que precisa ser corrigido
transacao_responsavel    varchar(50)    NOT NULL  -- código de utils.transacao
tipo                     varchar(15)    NOT NULL  -- MATERIAL | NAO_MATERIAL
prazo                    date           NULL
campos_relacionados      jsonb          -- nomes de campos e/ou ids de anexo
situacao                 varchar(15)    NOT NULL  -- ABERTO | RESPONDIDO | RESOLVIDO | CANCELADO
resposta                 text           NULL
id_usuario_resposta      → utils.usuario(id)  NULL
respondido_em            timestamp      NULL
resolvido_em             timestamp      NULL
criado_em                timestamp      NOT NULL
```

O **destinatário é uma transação RBAC**, não uma pessoa: quem tiver a transação vê o pedido na sua
caixa de trabalho. Decisão do Jorge em 2026-08-06 — evita dependência de pessoa (férias,
desligamento) e reaproveita o RBAC existente sem cadastro novo.

Um débito pode ter vários pedidos abertos ao mesmo tempo (a validação financeira pode apontar duas
pendências para responsáveis diferentes). A tramitação só avança quando **todos** os pedidos da
etapa estão `RESOLVIDO`.

#### `pagamentos.debito_versao`

```
id, tenant_id, id_debito → debito(id)
versao         int    NOT NULL   -- número da versão CONGELADA (a anterior)
dados          jsonb  NOT NULL   -- snapshot dos campos materiais
id_pedido_ajuste → pedido_ajuste(id) NULL  -- o ajuste que motivou, se houve
motivo         varchar(255) NOT NULL
id_usuario     → utils.usuario(id)
criado_em      timestamp NOT NULL
```

Append-only. Nunca se apaga versão.

**Campos materiais** (alterá-los cria versão nova e invalida aprovações):
`id_fornecedor`, `valor_total`, `numero_nf`, `numero_ne`, `id_fonte_recursos`, `id_contrato`,
`descricao`, `data_liquidacao`, `id_unidade`, retenções, dados bancários do pagamento.

Tudo o mais é não material: anexar documento complementar, substituir arquivo ilegível, corrigir
observação.

A lista vive numa constante única (`CAMPOS_MATERIAIS`) e há teste que a confronta com as colunas de
`Debito` — coluna nova obriga uma decisão explícita sobre materialidade, em vez de cair no
silêncio.

**Invalidação de aprovações.** Alteração material em débito que já passou de uma etapa faz a
solicitação retornar para a **primeira etapa cujas decisões foram invalidadas**:

| Alteração material ocorrida em | Retorna para |
|---|---|
| `AJUSTE_GESTOR` | `AGUARDANDO_GESTOR` |
| `AJUSTE_VALIDACAO` | `AGUARDANDO_GESTOR` — o mérito da despesa mudou |
| `AJUSTE_AUTORIDADE` | `AGUARDANDO_GESTOR` |

Alteração **não material** retorna para a etapa que pediu o ajuste. A regra dura: mudou credor,
valor, objeto ou documento principal, o gestor decide de novo. As decisões anteriores permanecem no
histórico marcadas como *invalidadas pela versão N*, nunca apagadas.

#### `pagamentos.posicao_cronologica`

```
id, tenant_id, id_debito → debito(id)  UNIQUE (tenant_id, id_debito)
-- chave da fila
id_unidade          → utils.unidade_trabalho(id)
id_fonte_recursos   → fonte_recursos(id)
categoria           varchar(20)  -- BENS | LOCACOES | SERVICOS | OBRAS
exercicio           int
-- o marco
marco_em            timestamp NOT NULL   -- data/hora da liquidação; define a ordem
situacao            varchar(30) NOT NULL -- espelha debito.situacao_fila
motivo_bloqueio     varchar(255) NULL
previsao_pagamento  date NULL
registrado_em       timestamp NOT NULL
atualizado_em       timestamp NULL
```

**A posição não é armazenada.** É calculada na leitura por
`row_number() over (partition by <chave> order by marco_em, id)`. Posição gravada desatualiza
silenciosamente a cada inserção; calculada, é sempre verdadeira. O custo é uma window function numa
tabela pequena por tenant.

Índice `(tenant_id, id_unidade, id_fonte_recursos, categoria, exercicio, marco_em)`.

#### `pagamentos.excecao_cronologica`

```
id, tenant_id, id_debito → debito(id)
justificativa       text          NOT NULL
fundamento          varchar(255)  NOT NULL  -- dispositivo legal invocado
id_autoridade       → utils.usuario(id) NOT NULL
data_autorizacao    date          NOT NULL
id_usuario_registro → utils.usuario(id)
documentos          jsonb                    -- ids de anexo
criado_em           timestamp     NOT NULL
```

Append-only. **É o único caminho para pagar fora de ordem.** Não há reordenação por arrastar, nem
endpoint que mude posição: a posição deriva do marco, e o marco é a liquidação. O que existe é
autorizar formalmente a exceção, que passa a aparecer na fila como `EXCECAO_AUTORIZADA` com a
justificativa visível.

#### `pagamentos.lote_pagamento` e `pagamentos.lote_pagamento_parcela`

```
lote_pagamento:
  id, tenant_id, numero varchar(20)
  id_conta_pagadora  → conta_bancaria(id)
  situacao           varchar(20)  -- RASCUNHO | PROGRAMADO | ENVIADO | PROCESSADO | CANCELADO
  data_programada    date NULL
  valor_total        numeric(14,2)
  id_usuario         → utils.usuario(id)
  enviado_em, processado_em, criado_em, atualizado_em, excluido

lote_pagamento_parcela:
  id, tenant_id, id_lote → lote_pagamento(id), id_parcela → parcela(id)
  situacao        varchar(20)  -- PENDENTE | PAGA | FALHOU
  motivo_falha    varchar(255) NULL
  UNIQUE (tenant_id, id_parcela) WHERE situacao <> 'FALHOU'
```

O `ordem_pagamento` existente **não é reaproveitado**: ele é o artefato da *autorização* (quem
ordenou, que saldo reservou, com que alçada) e permanece como está. O lote é o artefato da
*execução* (que parcelas foram ao banco juntas). Confundi-los faria a OP mudar depois de assinada.

#### `pagamentos.retencao`

```
id, tenant_id, id_debito → debito(id)
tipo         varchar(20)   -- IRRF | INSS | ISS | PIS_COFINS_CSLL | OUTRAS
descricao    varchar(150) NULL
base_calculo numeric(14,2) NOT NULL
aliquota     numeric(6,3)  NULL
valor        numeric(14,2) NOT NULL
recolhido    boolean NOT NULL default false
data_recolhimento date NULL
documento_recolhimento varchar(50) NULL
criado_em, atualizado_em, excluido
```

`valor_liquido` do débito = `valor_total` − Σ retenções não excluídas. Derivado, não armazenado.

#### `pagamentos.anexo_debito`

```
id, tenant_id
id_debito  → debito(id)
id_anexo   → protocolos.anexo(id)
id_usuario → utils.usuario(id)
versao_debito int NOT NULL       -- em que versão foi juntado
id_pedido_ajuste → pedido_ajuste(id) NULL  -- se veio em resposta a um ajuste
criado_em, excluido
```

Reaproveita `protocolos.anexo` (armazenamento, upload, download) em vez de criar um segundo
sistema de arquivos. Só o vínculo é novo. `protocolos.anexo_processo` **não** serve: exige
`id_movimentacao`, que é do rito do protocolo.

> **Premissa a validar na F1.** O download de anexo passa hoje por `get_anexo_path_autorizado`,
> que checa sigilo de processo. Anexo de débito não tem processo. A autorização de download de
> anexo de débito será a permissão de leitura do módulo de pagamentos mais o mesmo padrão de
> "autorização antes de resolver o recurso" registrado no CLAUDE.md. O carregador cru continua
> proibido em router.

### 4.4 Campos novos em tabelas existentes

**`pagamentos.debito`:**

| Campo | Tipo | Motivo |
|---|---|---|
| `situacao_tramitacao` | `varchar(30) NOT NULL` | §4.1 |
| `situacao_fila` | `varchar(30) NOT NULL` | §4.1 |
| `situacao_pagamento` | `varchar(20) NOT NULL` | §4.1 |
| `id_unidade` | `→ utils.unidade_trabalho(id) NOT NULL` | §2.7 — não existe hoje |
| `versao` | `int NOT NULL default 1` | versionamento material |
| `lock_version` | `int NOT NULL default 0` | concorrência otimista |
| `id_gestor_decisor` | `→ utils.usuario(id) NULL` | quem autorizou como gestor (segregação) |
| `id_validador` | `→ utils.usuario(id) NULL` | quem validou (já derivável do histórico; materializar simplifica a segregação e a caixa de trabalho) |

`id_unidade` é `NOT NULL` no estado final. A migration a adiciona nullable, faz o backfill
(`contrato.id_unidade` quando há contrato; unidade do solicitante quando não há) e só então aplica
o `SET NOT NULL` — na mesma migration, para não deixar janela.

**`pagamentos.contrato`:** `categoria varchar(20)` — `BENS | LOCACOES | SERVICOS | OBRAS`, exigida
pela chave da fila. Nullable com backfill para `SERVICOS` (o caso mais comum) e um alerta na tela
de contratos para o ente revisar; forçar o operador a classificar retroativamente 100% dos
contratos no dia do deploy trava o módulo.

Débito sem contrato carrega a categoria em `posicao_cronologica.categoria`, informada na
solicitação.

### 4.5 Mapeamento dos status antigos

Decisão do Jorge: **preservar a etapa, sem retroceder processo em andamento**. Como o Gestor da
Pasta não existia, o que já passou da validação não volta para ele.

| `status` atual | `situacao_tramitacao` | `situacao_fila` | `situacao_pagamento` |
|---|---|---|---|
| `RASCUNHO` | `RASCUNHO` | `NAO_REGISTRADA` | `NAO_INICIADA` |
| `EM_VALIDACAO` | `AGUARDANDO_VALIDACAO` | `NAO_REGISTRADA` | `NAO_INICIADA` |
| `DEVOLVIDO` | `AJUSTE_VALIDACAO` | `NAO_REGISTRADA` | `NAO_INICIADA` |
| `VALIDADO` | `AGUARDANDO_AUTORIDADE` | `REGISTRADA` | `NAO_INICIADA` |
| `ENVIADO_SECRETARIO` | `AGUARDANDO_AUTORIDADE` | `REGISTRADA` | `NAO_INICIADA` |
| `AGUARDANDO_AUTORIZACAO` | `AGUARDANDO_AUTORIDADE` | `REGISTRADA` | `NAO_INICIADA` |
| `AUTORIZADO` | `AUTORIZADA` | `ELEGIVEL` | `NAO_INICIADA` |
| `ENVIADO_TESOURARIA` | `AUTORIZADA` | `ELEGIVEL` | `PROGRAMADA` |
| `EM_PROCESSAMENTO` | `AUTORIZADA` | `ELEGIVEL` | `EM_PROCESSAMENTO` |
| `PAGO_PARCIAL` | `AUTORIZADA` | `ELEGIVEL` | `PAGA_PARCIAL` |
| `PAGO` | `AUTORIZADA` | `CONCLUIDA` | `PAGA` |
| `CONCILIADO` | `AUTORIZADA` | `CONCLUIDA` | `PAGA` |
| `REJEITADO` | `REJEITADA_GESTOR` | `NAO_REGISTRADA` | `NAO_INICIADA` |
| `SUSPENSO` | `AJUSTE_VALIDACAO` | `BLOQUEADA` | `NAO_INICIADA` |
| `CANCELADO` | `CANCELADA` | `RETIRADA` | `CANCELADA` |
| `ESTORNADO` | `AUTORIZADA` | `ELEGIVEL` | `ESTORNADA` |

Três decisões que precisam ficar registradas porque perdem informação:

- **`DEVOLVIDO` → `AJUSTE_VALIDACAO`.** O status antigo não guarda *quem* devolveu. Como a
  devolução hoje é gateada por `PERM_VALIDAR`, a validação é a origem correta na esmagadora
  maioria dos casos.
- **`SUSPENSO` → `AJUSTE_VALIDACAO` + `BLOQUEADA`.** Suspensão era um estado terminal-ish sem
  caminho claro. Vira pendência com bloqueio de fila, que é reversível e visível.

**Os estados `AJUSTE_*` existem na F1 sem pedido de ajuste associado**, porque `pedido_ajuste` só
nasce na F2. Nessa janela eles significam apenas "devolvido para correção", com o motivo legível no
histórico — que é exatamente o que o sistema oferece hoje. A migration da **F2** varre os débitos
em `AJUSTE_*` e cria um `pedido_ajuste` sintético para cada um, com o motivo copiado da última
linha de `debito_historico` com `acao IN ('DEVOLVIDO','SUSPENSO')` e
`transacao_responsavel = 'pagamento_solicitar'`. Sem isso, débito devolvido antes da F2 ficaria com
uma aba de pendências vazia e sem caminho de resolução.
- **`CONCILIADO` colapsa em `PAGA`.** A conciliação passa a ser um atributo da parcela
  (já é: `pagamentos.conciliacao`), não um estágio do débito. Nenhuma informação se perde — a
  tabela de conciliação continua lá.

A migration é reversível: o `downgrade()` recalcula `status` a partir das três dimensões pela
tabela inversa e derruba as colunas. Como `status` **continua sendo mantido** durante F1–F4,
o downgrade não perde nada.

**Volume.** Antes de escrever a migration, medir `SELECT status, count(*) FROM pagamentos.debito
GROUP BY status` no banco de dev e na VPS. Se o volume for zero em ambos, o backfill continua
sendo escrito (o CI roda em banco limpo, mas homologação pode receber dados a qualquer momento) —
só não vira o ponto de maior risco do deploy.

---

## 5. Ordem cronológica

### 5.1 Quando o débito entra na fila

No **ato da liquidação** (`confirmar_liquidacao()`), não na autorização. É o que o diagrama diz
("Registro da posição na fila ocorre na LIQUIDAÇÃO") e é o que a lei diz. Consequência prática: um
débito pode estar `REGISTRADA` na fila e ainda `AGUARDANDO_GESTOR` na tramitação — a posição
cronológica é ganha pela liquidação, e perdê-la por demora administrativa seria injusto com o
fornecedor.

`marco_em` é `data_liquidacao` com a hora do registro. Uma vez gravado, **é imutável**, salvo
alteração material da liquidação — que cria versão nova e regrava o marco, com o fato registrado
no histórico.

### 5.2 Elegibilidade

`situacao_fila = ELEGIVEL` exige, simultaneamente:

1. `situacao_tramitacao = AUTORIZADA`;
2. nenhum pedido de ajuste aberto;
3. fornecedor com `situacao_cadastral = REGULAR`;
4. disponibilidade financeira na conta pagadora (senão `AGUARDANDO_DISPONIBILIDADE`);
5. nenhum bloqueio ativo.

A avaliação é uma função pura (`avaliar_elegibilidade(debito) -> (situacao, motivo)`) chamada em
todo ponto que muda algo relevante. **Não é job**: fila que depende de job fica errada entre
execuções, e aqui "errada" significa pagar fora de ordem.

### 5.3 Pagar fora de ordem

A tesouraria seleciona pagamentos elegíveis **em ordem**. Selecionar um débito que tem outro à sua
frente na mesma fila (mesma unidade + fonte + categoria + exercício) devolve **409** com a lista
dos preteridos.

O único caminho é registrar uma `excecao_cronologica` — justificativa, fundamento legal,
autoridade, data, documentos. Registrada, o débito passa a `EXCECAO_AUTORIZADA` e pode ser
selecionado, com a exceção visível na fila e no detalhe.

Não existe endpoint de reordenação. Não existe drag-and-drop.

---

## 6. Perfis e permissões

### 6.1 Transações

| Transação | Perfil | Situação |
|---|---|---|
| `pagamento_solicitar` | Unidade Setorial | existe |
| `pagamento_gerir` | **Gestor da Pasta** | **nova** |
| `pagamento_validar` | Validação Financeira | existe — perde a rejeição |
| `pagamento_autorizar` | Autoridade Competente | existe |
| `pagamento_pagar` | Tesouraria | existe — perde suspender/reativar pré-autorização |
| `pagamento_auditar` | Controle Interno | existe — vira leitura total do módulo |
| `pagamento_cadastro` | Administrador do fluxo | existe |

`pagamento_aprovar` e `pagamento_encaminhar` são **descontinuadas**. Não são removidas de
`utils.transacao` (há concessões em banco): a migration as marca inativas e concede
`pagamento_gerir` a todo grupo que hoje tenha `pagamento_encaminhar` — que é o papel mais próximo
do gestor. Os endpoints `/aprovar` e `/encaminhar` respondem **410 Gone** com mensagem apontando o
substituto, em vez de sumirem: cliente antigo recebendo 404 parece bug de rota.

Transação nova exige entrada em `MODULO_TRANSACOES` (`cli/seed_bootstrap.py`), senão a guarda de
modularização reprova o PR.

### 6.2 Segregação de funções

Regra: a mesma pessoa não pode exercer dois atos decisórios sobre o mesmo débito.

| Ato | Impedido para |
|---|---|
| Autorizar como gestor | o solicitante |
| Validar | o solicitante, o gestor decisor |
| Aprovar e ordenar | o solicitante, o gestor decisor, o validador |
| Executar pagamento | todos os anteriores |

Implementada numa função única (`assert_segregacao(debito, usuario, ato)`), no **serviço** — não no
router — e checada em toda transição. Hoje só existe solicitante ≠ validador.

Super-usuário **não** faz bypass da segregação. É a exceção deliberada ao padrão do projeto: o
bypass de SU existe para permissão, e segregação de funções não é permissão — é controle interno.
Registrado como premissa; há teste com SU tentando validar o próprio débito e recebendo 403.

### 6.3 Concorrência

`lock_version` em `debito`, incrementado a cada transição. Todo endpoint de decisão recebe
`lock_version` no corpo e devolve **409** com o estado atual quando não bate:

> "Esta solicitação foi atualizada por Fulano há 2 minutos (validou a conformidade). Recarregue
> para ver o estado atual antes de decidir."

O frontend, ao receber 409, recarrega e mostra o novo estado — não repete a ação.

---

## 7. Navegação e telas

### 7.1 Menu

Cada etapa do fluxo é um item, como pedido:

```
Pagamentos
  Visão geral                    todos os perfis
  Minha caixa de trabalho        todos os perfis
  Minhas solicitações            pagamento_solicitar
  ── fluxo ──
  Análise do gestor              pagamento_gerir
  Validação financeira           pagamento_validar
  Autorização                    pagamento_autorizar
  Tesouraria                     pagamento_pagar
  ── ──
  Ordem cronológica              todos os perfis (leitura)
  Conciliação                    pagar | autorizar | auditar | cadastro
  Caixa                          pagamento_cadastro
  Cadastros ▸                    pagamento_cadastro
```

`Dashboard` funde-se em `Visão geral`. `Contas a pagar` funde-se em `Minhas solicitações` (para o
setorial) e nas telas de etapa (para os demais) — a lista genérica com 12 abas de status técnico
deixa de existir. A rota `/m/pagamentos/contas-a-pagar` ganha 308 para `/m/pagamentos/solicitacoes`,
porque `notificacao.link_url` já gravou URLs para ela.

Cada item novo entra em `frontend/lib/menus/pagamentos.ts` e na tabela `PERMISSOES_ESPERADAS` de
`__tests__/menus.test.tsx`. Rotas ficam sob `app/(app)/m/pagamentos/` — o token `m` já está na
regex do nginx.

### 7.2 Detalhe da solicitação — a tela central

```
┌────────────────────────────────────────────────────────────────────────┐
│ #2026/0417  ·  Construtora Aurora Ltda  ·  R$ 148.320,00               │
│ Secretaria de Obras                          criada em 12/07/2026      │
│                                                                        │
│ Tramitação: Aguardando autoridade competente                           │
│ Ordem cronológica: Registrada — posição 4 de 17                        │
│ Pagamento: Não iniciado                                                │
├────────────────────────────────────────────────────────────────────────┤
│  ✓ Unidade ──── ✓ Gestor ──── ✓ Validação ──── ● Autoridade ──── ○ Tesouraria │
├────────────────────────────────────────────────────────────────────────┤
│ ⚑ Esta solicitação aguarda sua aprovação.                              │
│   Conferida pela unidade financeira em 28/07 — checklist sem           │
│   inconformidades. Está em 4º lugar na fila de Obras/Fonte 1500.       │
│                                                                        │
│   [ Aprovar e ordenar pagamento ]  [ Solicitar ajustes ]  [ Não aprovar ] │
├────────────────────────────────────────────────────────────────────────┤
│ Resumo │ Despesa │ Fornecedor │ Contrato │ Empenho │ NF e valores │     │
│ Retenções │ Documentos │ Checklist │ Fila │ Pagamento │ Histórico       │
└────────────────────────────────────────────────────────────────────────┘
```

- **As três dimensões sempre visíveis no cabeçalho**, em português, sem enum.
- **Stepper de 5 etapas** com cinco tratamentos visuais distintos (concluída, atual, futura, com
  ajuste pendente, encerrada por decisão) — e **nunca só por cor**: cada estado tem ícone e texto.
- **Bloco "o que precisa ser feito agora"** — frase completa, não rótulo. É o bloco que responde à
  pergunta que motivou este trabalho.
- **Ações contextuais** com uma primária destacada; ações que o perfil não pode executar são
  **ocultadas**, exceto quando a indisponibilidade é informativa ("aguardando a validação
  financeira concluir") — aí aparece o motivo, não um botão cinza.
- **Abas**, não uma página de 700 linhas rolando.

### 7.3 Minha caixa de trabalho

A tela operacional principal. Consome `GET /pagamentos/minha-caixa` (sucessor de `minha-fila`, que
já existe e não tem tela). Mostra **só o que exige ação do usuário**, considerando etapa, perfil e
pedidos de ajuste endereçados às suas transações.

Por item: número, fornecedor, unidade, valor, etapa, pendência, **tempo aguardando**, próxima ação
esperada. Busca, filtros, ordenação, paginação (`Paginated<T>` — o tipo em `api.ts` tem de casar
com o `response_model`, conforme a guarda de contrato paginado).

### 7.4 Telas de etapa

`Análise do gestor`, `Validação financeira`, `Autorização` e `Tesouraria` são a mesma lista
filtrada por etapa, com colunas e ações próprias. Reaproveitam um componente
`ListaEtapa` — quatro cópias divergiriam.

**Validação financeira** ganha layout de conferência: documentos e checklist lado a lado em telas
largas, empilhados em telas estreitas.

**Autorização** ganha visão executiva: fornecedor, objeto, contrato, empenho, liquidação, NF, bruto,
retenções, líquido, fonte, resultado do checklist, pendências anteriores, posição na fila, decisões.

### 7.5 Ordem cronológica

Agrupada por chave de fila. Colunas essenciais: posição, marco, fornecedor, documento, líquido,
situação. O resto (bloqueio, justificativa, disponibilidade, previsão) em painel lateral. Exceções
autorizadas marcadas com ícone **e** texto.

### 7.6 Central da tesouraria

Sete passos: selecionar elegíveis → criar lote → revisar → programar → enviar → processar retorno →
comprovante. Cabeçalho permanente com quantidade, valor total, conta pagadora, fonte, bloqueados,
erros e situação do lote.

### 7.7 Nova solicitação

Formulário em 7 seções **na mesma rota** (perder contexto entre páginas é pior que rolar):
identificação · fornecedor e contrato · empenho e liquidação · NF e valores · retenções e dados
bancários · documentos · revisão e envio. Rascunho salvo a cada seção; alerta de NF possivelmente
duplicada (a checagem já existe em `pagamentos_debitos.py:69`); resumo antes de enviar; proteção
contra envio duplo.

### 7.8 Padrões de interface

Design system atual (`components/ui/`, `CrudPage`, Tailwind). **Nenhuma biblioteca nova.** Onde o
DS não tiver o componente (stepper de processo, painel lateral de detalhe, linha do tempo), o
componente nasce em `components/ui/` como reutilizável, não em `components/pagamentos/` como
específico.

Botões dizem o que fazem: *Enviar para o gestor*, *Aprovar e ordenar pagamento*, *Validar
conformidade*. Nunca *OK*, *Confirmar*, *Processar*.

Justificativa obrigatória em: pedido de ajuste, rejeição, não aprovação, cancelamento, estorno,
exceção cronológica, remoção de parcela de lote, invalidação de aprovação.

Ações críticas confirmam com **resumo do impacto**, não com "tem certeza?".

Mensagens de erro dizem o que aconteceu e o que fazer:

> "Não foi possível programar o pagamento porque a solicitação está bloqueada na ordem cronológica.
> Motivo: fornecedor com pendência cadastral. Consulte a aba Fila antes de tentar novamente."

Informação importante **atualiza a tela**; toast só para confirmação de ação sem consequência de
estado.

---

## 8. Auditoria

Toda transição grava em `debito_historico` (que ganha `versao_debito`, `situacao_*_anterior` e
`situacao_*_nova`) **e** em `aprimora_py.audit_log` via `services/audit.log()`, seguindo a
convenção `<entidade>.<verbo>`: `debito.autorizado_gestor`, `debito.validado`,
`debito.ajuste_solicitado`, `debito.versao_criada`, `posicao_cronologica.registrada`,
`excecao_cronologica.autorizada`, `lote_pagamento.enviado`.

Registra-se usuário, perfil, unidade, data/hora, ação, situações anterior e nova, justificativa,
versão, campos alterados, documentos incluídos/removidos, IP.

Nada de tramitação ou decisão é apagado fisicamente. Cancelamento é lógico; correção é versão nova.

---

## 9. Fatias

Cada fatia é um PR: código, testes, migration quando houver, documentação, e a suíte verde antes de
seguir.

### F1 — Fundação do fluxo

Três dimensões; etapa do Gestor da Pasta; remoção da rejeição na validação financeira; `id_unidade`;
`versao`; `lock_version`; segregação completa; transação `pagamento_gerir`; migration com o
mapeamento do §4.5; `status` legado derivado; menu por etapa; detalhe com stepper, três dimensões e
bloco de próxima ação.

*Aceite:* validação financeira não consegue encerrar (teste por inversão); as três dimensões
aparecem no detalhe; nenhum débito existente fica em estado inválido; suíte verde nos dois papéis
de banco.

### F2 — Ajustes e versionamento

`pedido_ajuste`; `debito_versao`; `anexo_debito`; `CAMPOS_MATERIAIS`; invalidação de aprovações;
retorno à etapa correta; aba de pendências no detalhe; responder ajuste na caixa de trabalho;
**backfill dos pedidos sintéticos** para os débitos que a F1 deixou em `AJUSTE_*` (§4.5).

*Aceite:* alteração material cria versão e invalida aprovações; versão anterior recuperável;
pendência chega a quem tem a transação designada; nenhum débito em `AJUSTE_*` fica sem pedido.

### F3 — Ordem cronológica

`posicao_cronologica`; `excecao_cronologica`; `categoria` em contrato; marco na liquidação; posição
por window function; `avaliar_elegibilidade`; 409 ao preterir; tela da fila; aba Fila no detalhe.

*Aceite:* posição correta e auditável; preterir sem exceção é bloqueado; exceção exige os cinco
campos.

### F4 — Tesouraria

`lote_pagamento`; `retencao`; programação; envio; retorno; comprovante; falha e reprocesso;
recolhimentos; central da tesouraria.

*Aceite:* lote só aceita elegível; pagamento falho reprocessa; retenções compõem o líquido.

### F5 — Fechamento

Visão geral com indicadores clicáveis; caixa de trabalho refinada; estados vazios, erro,
carregamento, sem permissão, conflito; acessibilidade e responsividade; **remoção da coluna
`status`** e da guarda; e2e do fluxo completo.

*Aceite:* os 23 cenários do §17 do pedido cobertos; `status` fora do código; lint/tsc/testes/build
verdes.

---

## 10. Testes

Os 23 cenários pedidos viram testes nomeados. Além deles, o que a história deste repositório manda:

- **Teste HTTP com usuário comum** em toda rota nova. O bypass de super-usuário em `auth/perms.py`
  retorna antes do `getattr(item, action)` — foi assim que 10 rotas do transporte devolveram 500
  para não-SU passando por toda a bateria. O tenant precisa contratar `pagamentos`, senão o gate
  barra antes com 403 e o teste não chega onde importa.
- **Provar por inversão.** Toda guarda estrutural nova é verificada quebrando de propósito o que
  ela protege e conferindo que fica vermelha. A guarda de página órfã passou duas fatias verde sem
  nunca ter sido invertida, e não protegia nada.
- **Rota literal antes da paramétrica.** `/debitos/elegiveis` antes de `/debitos/{id}`. Já ocorreu
  três vezes no transporte; `test_guarda_ordem_rotas.py` varre e reprova.
- **`Paginated<X>` em `api.ts`** onde o `response_model` for paginado. Declarar `X[]` deixa o `tsc`
  verde e a tela diz "nenhum registro" com registros no banco.
- **Nada de id de FK cravado.** O CI roda em banco limpo.
- **Schema `Update` com campo opcional** não pode gravar `null` em coluna `NOT NULL` — descartar o
  nulo explícito é obrigação de todo `atualizar_*`.
- **Migration:** head único, `downgrade()` na ordem inversa, RLS `ENABLE + FORCE`, as duas policies
  com `NULLIF(current_setting('app.tenant_id', true), '')::int`, grants para `aprimora_app` na
  tabela e na sequence.

---

## 11. Premissas

1. **A coluna `status` sobrevive até a F5**, derivada das três dimensões. Diff menor e revisável;
   risco de divergência mitigado por função única e teste por transição.
2. **A fila é por débito, não por parcela.** O marco é a liquidação da obrigação.
3. **Posição calculada, nunca armazenada.**
4. **Destinatário do ajuste é transação RBAC**, não pessoa (decisão do Jorge, 2026-08-06).
5. **Alteração material sempre volta ao gestor**, mesmo quando o ajuste veio da validação ou da
   autoridade. Mudou credor, valor, objeto ou documento principal, o mérito é reexaminado.
6. **Super-usuário não faz bypass de segregação de funções.** Exceção deliberada ao padrão.
7. **`ordem_pagamento` não vira lote.** São artefatos de atos distintos.
8. **`categoria` de contrato nasce nullable com backfill `SERVICOS`** e alerta para revisão.
9. **Anexo de débito reaproveita `protocolos.anexo`**, com tabela de vínculo própria.
10. **Endpoints descontinuados devolvem 410**, não 404.
11. **A conciliação passa a ser atributo da parcela**, não estágio do débito.
12. **Débitos existentes não retrocedem** (decisão do Jorge, 2026-08-06).

---

## 12. Riscos

| Risco | Mitigação |
|---|---|
| `status` derivado diverge das três dimensões | função única + teste por transição; F5 remove |
| Backfill de `id_unidade` sem origem confiável | contrato quando há; unidade do solicitante quando não; relatório das linhas resolvidas por fallback |
| Backfill de `categoria` classifica errado | nullable + default `SERVICOS` + alerta; não bloqueia operação |
| `pagamento_gerir` não concedida → gestor sem ninguém | migration concede a quem tem `pagamento_encaminhar`; se ninguém tiver, seed concede ao grupo admin e a Visão geral alerta |
| Escopo grande demais para uma revisão | cinco PRs com autorização entre eles |
| Fila errada = irregularidade, não só bug | elegibilidade avaliada em função pura chamada nas transições, nunca por job |
| Frontend com dois contratos durante F1–F4 | tipos em `api.ts` casando com `response_model`; guarda de contrato paginado |

---

## 13. Fora de escopo

Integração bancária real (CNAB/API de banco) — a F4 entrega o registro do envio e do retorno, não
o transporte. Mobile e gov.br, por decisão anterior. Reescrita da conciliação. Object storage para
anexos (decisão pendente, ver `project_storage_decision`).
