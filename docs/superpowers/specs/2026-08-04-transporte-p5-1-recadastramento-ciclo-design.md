# Transporte Regulado P5.1 — Ciclo de recadastramento e convocação

**Data:** 2026-08-04 · **Status:** aprovado por Jorge (design), aguardando revisão da spec

## 1. O que é, e o que não é

O município abre periodicamente um **recadastramento**: todo regulado ativo precisa comparecer,
apresentar documentos e ter o veículo vistoriado dentro de uma janela. Quem não comparece fica
inadimplente e pode ser suspenso.

Isto **não** é a renovação de alvará, que já existe (`renovar_alvara`, encadeando registro novo por
`renovado_de`). Renovação trata do **documento de operação**; recadastramento trata de o **titular
continuar elegível**. Um permissionário pode ter alvará válido e estar em falta com o
recadastramento.

### Decisões do Jorge que fixam o escopo

| # | Decisão |
|---|---|
| D1 | **Ciclo + prazo individual.** A prefeitura abre a campanha; cada regulado tem prazo próprio dentro dela. |
| D2 | O rito exige **documentos do regulado E vistoria do veículo** (fatia P5.2). |
| D3 | Prazo vencido **marca em atraso**; suspender é **ato humano** (fatia P5.3). |
| D4 | Prazo individual vem de **regra automática, com ajuste individual permitido**. |
| D5 | Alcança **permissionários e empresas**. |

### Fatiamento (aprovado)

| Fatia | Entrega | O usuário vê |
|---|---|---|
| **P5.1** (esta) | Ciclo, convocação, escalonamento, ajuste | Quem tem que vir e quando |
| **P5.2** | Checklist documental, parecer, amarra da vistoria, fechamento | Atende e fecha |
| **P5.3** | Estado em atraso, relatório, suspensão humana, notificação | Quem não veio, e age |

**P5.1 não entrega:** documento, vistoria, parecer, inadimplência, notificação, suspensão.

## 2. Dois fatos do código que moldam o desenho

Ambos verificados em `backend/app/models/transporte_regulado.py` e
`backend/app/schemas/transporte_regulado.py` em 2026-08-04.

**`Permissionario.situacao` usa masculino, `Empresa.situacao` usa feminino.**

```python
PermissionarioSituacao = Literal["ativo", "pendente", "suspenso", "cassado", "inativo"]
EmpresaSituacao        = Literal["ativa", "pendente", "suspensa", "cassada", "inativa"]
```

Uma consulta que filtre `situacao == "ativo"` nos dois convoca **zero empresas**, sem erro. O
serviço tem de usar o vocabulário certo por entidade, e há teste para isso (§6).

**`numero_permissao` e `data_nascimento` são anuláveis, e empresa não tem nascimento.** `cpf` e
`cnpj` são `nullable=False`. Isso decide o critério de escalonamento (§4): qualquer regra baseada
em número de permissão ou aniversário falharia para parte da base.

## 3. Modelo de dados

Duas tabelas em `transporte_regulado`, com o boilerplate de RLS que o `CLAUDE.md` exige (tenant_id
NOT NULL, índices `(tenant_id, …)`, `ENABLE + FORCE ROW LEVEL SECURITY`, as duas policies com
`NULLIF(current_setting('app.tenant_id', true), '')::int`, grants para `aprimora_app`).

### `recadastramento_ciclo`

| Coluna | Tipo | Nota |
|---|---|---|
| `id`, `tenant_id` | | |
| `nome` | `String(120)` | "Recadastramento 2026" |
| `data_inicio`, `data_fim` | `Date` | janela da campanha; `data_inicio <= data_fim` |
| `criterio_escalonamento` | `String(30)` | `final_documento` \| `sem_escalonamento` |
| `situacao` | `String(20)` | `rascunho` \| `aberto` \| `encerrado` (default `rascunho`) |
| `observacoes` | `Text` | |
| `criado_em`, `atualizado_em`, `excluido` | | soft-delete, como o resto do módulo |

Único parcial por tenant em `nome` `WHERE excluido = false` — dois ciclos "2026" no mesmo município
é erro de digitação, não caso de uso.

### `recadastramento_convocacao`

| Coluna | Tipo | Nota |
|---|---|---|
| `id`, `tenant_id` | | |
| `id_ciclo` | FK `recadastramento_ciclo` | |
| `id_permissionario` | FK, **nullable** | |
| `id_empresa` | FK, **nullable** | |
| `prazo` | `Date` | calculado; ajustável |
| `prazo_original` | `Date` | o que a regra deu, preservado para auditar o ajuste |
| `ajuste_justificativa` | `Text`, nullable | obrigatória **quando há ajuste** |
| `ajustado_por` | FK `utils.usuario`, nullable | |
| `ajustado_em` | `DateTime`, nullable | |
| `situacao` | `String(20)` | `convocado` nesta fatia; P5.2/P5.3 acrescentam valores |
| `criado_em`, `atualizado_em`, `excluido` | | |

**Vínculo com o regulado segue o precedente do `Alvara`**, que já tem `id_permissionario` e
`id_empresa` anuláveis com validação de vínculo no serviço. Preferido a `(tipo, id)` polimórfico
porque preserva integridade referencial real — o banco recusa FK órfã, o par `(tipo, id)` não.
Diferença: aqui é **exatamente um**, não "ao menos um".

Único parcial `(id_ciclo, id_permissionario)` e `(id_ciclo, id_empresa)` `WHERE excluido = false` —
é o que torna a geração idempotente (§5) no banco, e não só no código.

## 4. Escalonamento

Dois critérios, **ambos sempre calculáveis para os dois tipos de regulado**:

- **`final_documento`** — último dígito do CPF (permissionário) ou CNPJ (empresa) distribui os
  regulados em 10 faixas iguais ao longo de `[data_inicio, data_fim]`. O prazo é o fim da faixa.
- **`sem_escalonamento`** — todos recebem `data_fim`.

Nascimento e número de permissão foram **descartados**: são anuláveis, e nascimento não existe para
empresa. Critério que falha para parte da base não é critério, é defeito agendado — e o modo de
falha seria silencioso (prazo nulo ou todos no mesmo dia).

Faixa vazia é aceitável: se nenhum regulado termina em 7, ninguém tem aquele prazo. Não se
redistribui — redistribuir tornaria o prazo de cada um dependente da composição da base, e o
recálculo mudaria prazos já comunicados.

### Ajuste individual

`PUT /recadastramento/convocacoes/{id}/prazo` com `{prazo, justificativa}`. A justificativa é
**obrigatória** — sem ela o ajuste vira favor invisível. Grava `ajustado_por`/`ajustado_em` e
preserva `prazo_original`.

Recusa (409) ajuste em ciclo `encerrado`, e (400) prazo fora da janela do ciclo. Prazo no passado é
**permitido**: regularizar alguém retroativamente é caso real de balcão.

## 5. Geração das convocações

**Ato explícito, não efeito de criar o ciclo.** `POST /recadastramento/ciclos/{id}/gerar-convocacoes`.

Por que não automático: separar a criação do ciclo do momento em que os prazos passam a valer dá ao
operador a chance de conferir a janela e o critério antes de comprometer prazos.

**Idempotente.** Convoca todo permissionário `ativo` e toda empresa `ativa`, não excluídos, que
**ainda não tenham convocação naquele ciclo**. Rodar de novo alcança quem foi cadastrado depois do
primeiro disparo — que é o caso real — sem duplicar nem remarcar quem já tem prazo.

A resposta informa `criadas` e `ja_existentes`. Um `0/0` diz ao operador que não há regulado ativo,
o que é diferente de "funcionou".

Recusa (409) em ciclo `encerrado`. Ciclo em `rascunho` **pode** gerar: é o ensaio antes de abrir.

**Não remove** convocação de quem deixou de ser ativo depois de convocado. Descadastrar é ato
regulatório com efeito próprio, e apagar a linha esconderia que a pessoa foi convocada. P5.3 decide
o que fazer com esses casos.

## 6. Testes

`backend/tests/test_transporte_p5_recadastramento.py`:

| O que trava | Por quê |
|---|---|
| Empresa `ativa` é convocada | O bug do masculino/feminino (§2). **Teste com um permissionário e uma empresa**: filtro errado convoca 1 e o teste que só olha contagem total passaria. |
| Geração é idempotente | Segundo disparo devolve `criadas=0`, e o total no banco não muda. |
| Segundo disparo alcança regulado novo | Idempotência não pode virar "não faz nada". |
| Não convoca `pendente`/`suspenso`/`cassado`/`inativo` | Com um de cada no mesmo tenant. |
| `final_documento` distribui | CPFs terminados em 0 e em 9 caem em prazos diferentes, ambos dentro da janela. |
| `sem_escalonamento` dá `data_fim` a todos | |
| Exatamente um vínculo | Convocação com os dois, ou com nenhum, é 400. |
| Ajuste exige justificativa | Sem ela, 400; com ela, grava autor, data e preserva `prazo_original`. |
| Ajuste fora da janela é 400; em ciclo encerrado é 409 | |
| Isolamento cross-tenant | Ciclo do tenant B não é visível nem ajustável pelo A (404, não 403). |
| HTTP com **usuário comum** | `CLAUDE.md`: a suíte inteira exercitando SU escondeu um 500 em produção. Padrão em `_cria_usuario_comum_transporte`. |
| Ordem de rotas | `/ciclos/{id}/gerar-convocacoes` e `/convocacoes/{id}/prazo` antes da paramétrica irmã. `test_guarda_ordem_rotas.py` já varre a app inteira. |

**Cada negativa com controle positivo na mesma sessão.** "Levantou exceção" não distingue a regra
funcionando de um endpoint quebrado.

## 7. Frontend

`/m/transporte/recadastramento` (lista de ciclos) e `/m/transporte/recadastramento/[id]` (convocados).
Nasce dentro de `m/` — a F3 já exige isso e `__tests__/rotas-modulo.test.ts` reprova o contrário.
**Sem mudança no nginx**, porque `/m` já está na regex.

Busca e filtros **server-side**, com `q` e `page`. Não é preferência: a fatia anterior consertou
exatamente o defeito de filtrar no cliente sobre lista truncada, em que a tela afirmava que um
registro não existia. `api.ts` declara `Paginated<T>` e a tela consome `.items` —
`test_guarda_contrato_paginado.py` reprova o contrário.

Item no menu de transporte (`lib/menus/transporte.ts`) com `perm: "transporte_regulado"`, e a tabela
`PERMISSOES_ESPERADAS` de `__tests__/menus.test.tsx` atualizada.

## 8. Riscos

**A base do município pode ter CPF/CNPJ mal formado** vindo do legado. O escalonamento lê o último
caractere; se não for dígito, o regulado cai na faixa final (`data_fim`) em vez de quebrar. Fica
registrado no relatório de geração — falhar a geração inteira por um cadastro sujo seria pior.

**Recalcular prazos ao mudar a janela do ciclo não está nesta fatia.** Editar `data_fim` de um ciclo
já gerado **não** remarca ninguém. Remarcar em massa prazos já comunicados é decisão de produto, e a
alternativa silenciosa (mudar sem avisar) é a pior das duas.
