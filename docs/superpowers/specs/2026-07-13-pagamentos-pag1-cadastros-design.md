# PAG-1 — Fundação + Cadastros do módulo de Pagamentos Municipais

> Design doc (spec). Primeiro sub-projeto da migração do "Sistema de Gestão e
> Autorização de Pagamentos Municipais" (Django) para o aprimora-py, reimplementado
> de forma idiomática no stack próprio (FastAPI + SQLAlchemy + Next.js + Postgres
> multi-tenant com RLS + Celery). Fonte de inspiração: `Sistema de Pagamento/`.

## Context

A prefeitura quer trazer para o aprimora-py a **ideia** e as **telas** de um sistema
de autorização de pagamentos municipais (solicitar → aprovar → autorizar em lote →
pagar, com segregação de funções, alçada e bloqueio por saldo). A decisão de produto
(registrada na sessão de brainstorming) foi: **aproveitar ideias/telas como inspiração
e reimplementar livremente** no stack próprio, **não** portar o modelo/regras do Django
literalmente.

O estudo de UX das 4 telas centrais (Painel, Novo Pedido, Autorização em Lote, Detalhe)
foi aprovado e revelou o modelo de domínio. A arquitetura aprovada é: **máquina de
estados explícita num domínio `pagamentos` próprio** (não o motor de workflow genérico),
reusando ao máximo o que a plataforma já tem.

Este spec cobre **apenas o PAG-1**: a fundação de dados e os **cadastros básicos** que
todo o resto depende. O fluxo do pedido (PAG-2), a autorização em lote + financeiro
(PAG-3) e conciliação/transparência/relatórios (PAG-4+) são sub-projetos seguintes, cada
um com seu próprio spec → plano → implementação.

## Escopo do PAG-1

**Dentro:**
- Schema `pagamentos` + migration com RLS/GRANTs (padrão da migration `0043`/`0044`).
- Models SQLAlchemy e enums de valor (Criticidade, GrupoDespesa).
- Cadastros CRUD (backend + telas admin): `credor`, `natureza_despesa`, `fonte_recursos`,
  `conta_bancaria`, `contrato`, `alcada`.
- **Cifragem em repouso** (Fernet) dos dados bancários do credor, via um helper
  reutilizável em `app/core/crypto.py` (mesmo mecanismo que o PR-D usará para tokens Google).
- Nova transação RBAC `pagamento_cadastro` (admin dos cadastros).
- Validação fonte × grupo de despesa; unicidade por tenant (CNPJ/CPF do credor, códigos).

**Fora (sub-projetos seguintes):**
- `pedido_pagamento`, máquina de estados, `pedido_historico` (PAG-2).
- `ordem_pagamento`, `movimentacao_conta`/saldos, autorização em lote (PAG-3).
- Saldos computados, conciliação bancária, transparência, relatórios (PAG-3/PAG-4+).
- Integração real com SIAFIC (fica como contrato de dados `nota_empenho_ref` num PAG futuro).

## Reuso (não reconstruir)

| Necessidade | Já existe no aprimora-py | Uso no PAG-1 |
|---|---|---|
| Órgão/Secretaria | `UnidadeTrabalho` (`utils.unidade_trabalho`) | `contrato.id_unidade` referencia unidade — **sem** entidade `orgao` nova |
| Multi-tenant + RLS | núcleo (`tenant_id` + policies) | todas as tabelas novas seguem o padrão `0043` |
| RBAC (Transação/Grupo) | `utils.transacao`, `require_permission` | nova transação `pagamento_cadastro`; super-usuário bypassa |
| Cifragem/Fernet | a introduzir no PR-D (minuta) | **antecipar** o helper `app/core/crypto.py` aqui e ambos reusam |
| Padrão CRUD (router/service/schema) | `transporte_regulado`, `minutas` | espelhar 1:1 |
| Telas de lista/CRUD | `CrudPage` + componentes `ui/*` | reusar; páginas em `frontend/app/(app)/pagamentos/cadastros/*` |
| nginx route whitelist | `nginx/default.conf` regex | adicionar `pagamentos` |

## Modelo de dados (schema `pagamentos`, migration `0045`)

Todas as tabelas: `id`, `tenant_id` FK `aprimora_py.tenant.id`, `criado_em`,
`atualizado_em`, `excluido` (soft-delete), `GRANT ... TO aprimora_app`, RLS
`ENABLE/FORCE` + policies `tenant_isolation_select`/`_modify` (padrão `0043`).

Enums de valor (em `app/core/choices.py` ou `pagamentos/enums.py`, como `str, Enum`):
- `Criticidade`: URGENTE, ALTA, MEDIA, BAIXA.
- `GrupoDespesa`: PESSOAL, CUSTEIO, INVESTIMENTO, DIVIDA, OUTRAS.

### `pagamentos.credor`
Fornecedor/credor. `cnpj_cpf` único por tenant entre não excluídos (índice parcial).
- `tipo_pessoa` (FISICA|JURIDICA, CHECK), `cnpj_cpf` String(18), `nome` String(200),
  `situacao_cadastral` (REGULAR|PENDENTE|IRREGULAR, default REGULAR, CHECK),
  `motivo_pendencia` String(255) nullable.
- **Dados bancários cifrados** (Text, valor Fernet-encriptado): `banco_cif`, `agencia_cif`,
  `conta_cif`, `chave_pix_cif`. Nunca em texto puro; decifra só no serviço, sob permissão.

### `pagamentos.natureza_despesa`
- `codigo` String(20) único/tenant, `descricao` String(150),
  `criticidade_padrao` (Criticidade, default MEDIA), `ativa` Boolean default true.

### `pagamentos.fonte_recursos`
- `codigo` String(20) único/tenant, `descricao` String(200),
  `grupos_despesa_permitidos` JSONB (lista de códigos de GrupoDespesa; vazio = todos).

### `pagamentos.conta_bancaria`
- `nome` String(150), `banco` String(100), `agencia` String(20), `conta` String(30),
  `id_fonte_recursos` FK, `grupo_despesa` (GrupoDespesa, CHECK),
  `saldo_minimo_alerta` Numeric(14,2) default 0, `ativa` Boolean default true.
- **Validação (serviço):** o `grupo_despesa` tem de estar em
  `fonte_recursos.grupos_despesa_permitidos` (ou lista vazia). 409/422 se incompatível.
- *(Saldo é derivado de movimentações — entra no PAG-3; aqui a conta é só cadastro.)*

### `pagamentos.contrato`
- `numero` String(50) único/tenant, `id_credor` FK, `id_unidade` FK
  `utils.unidade_trabalho.id` (o "órgão"), `objeto` String(255),
  `vigencia_inicio` Date, `vigencia_fim` Date, `valor_total` Numeric(14,2).
- CHECK `vigencia_fim >= vigencia_inicio`. *(saldo consumido/remanescente = PAG-2/3.)*

### `pagamentos.alcada`
Limite de alçada de autorização por usuário × natureza (opcional). Espelha o
`AlcadaAutorizacao` do Django (que amarra ao perfil); no aprimora amarramos ao
**usuário** autorizador — decisão registrada abaixo.
- `id_usuario` FK `utils.usuario.id`, `id_natureza` FK `natureza_despesa` **nullable**
  (nulo = limite geral do usuário), `valor_maximo` Numeric(14,2).
- Unique parcial `(tenant_id, id_usuario, id_natureza)` entre não excluídos.

## Cifragem (Fernet) — `app/core/crypto.py`

Helper reutilizável (também pelo PR-D):
```python
def encrypt(texto: str | None) -> str | None    # Fernet, chave em settings
def decrypt(cifrado: str | None) -> str | None
```
- Chave em `settings.dados_sensiveis_encryption_key` (env var; Fernet base64 de 32 bytes).
- Ausência de chave em dev → erro claro na inicialização do serviço que cifra (não silencioso).
- No `credor`, o serviço cifra na escrita e decifra na leitura; o schema `CredorOut`
  expõe os dados bancários **mascarados** por padrão (ex.: `chave_pix: "***"`), com um
  endpoint/flag separado (sob `pagamento_cadastro`) para revelar — evita vazamento em listas.

## Endpoints (backend) — router `app/routers/pagamentos_cadastros.py`

CRUD por entidade, gated por `require_permission("pagamento_cadastro", <ação>)`
(super-usuário bypassa). Prefixo `/api/v2/pagamentos/...`:
- `/pagamentos/credores` · `/naturezas` · `/fontes` · `/contas` · `/contratos` · `/alcadas`
  → `GET (list)`, `GET /{id}`, `POST`, `PUT /{id}`, `DELETE /{id}` (soft).
- `GET /pagamentos/credores/{id}/dados-bancarios` → revela dados decifrados (auditado).
- `GET /pagamentos/enums` → Criticidade/GrupoDespesa para popular selects do front.

Schemas Pydantic em `app/schemas/pagamentos.py` (padrão `*Create`/`*Update` whitelist/`*Out`).
Serviços em `app/services/pagamentos_cadastros.py` (tenant_id sempre do caller; unicidade;
validação fonte×grupo; cifragem no credor).

Registrar transação `pagamento_cadastro` na própria migration `0045` (idempotente, padrão
`0028`/`0044`). Registrar routers no `main.py`.

## Frontend

- `frontend/lib/api.ts`: seção `pagamentos.cadastros` (credores/naturezas/fontes/contas/contratos/alcadas) espelhando o padrão existente.
- Páginas em `frontend/app/(app)/pagamentos/cadastros/*` (uma por entidade), reusando
  `CrudPage` onde couber; conta e crédito bancário podem exigir form custom (grupo×fonte,
  máscara/reveal de dados bancários).
- Item de menu "Pagamentos › Cadastros" na `Sidebar.tsx` (perm `pagamento_cadastro`).
- Adicionar `pagamentos` ao regex de rotas do `nginx/default.conf`.

## Decisões de design registradas

- **Órgão = `UnidadeTrabalho`** (não criar entidade `orgao`): evita duplicar a árvore
  organizacional que já existe e é tenant-scoped.
- **Alçada por usuário** (não por grupo): mais simples e fiel ao Django; a segregação de
  funções (PAG-2) usa o rastreio de atores no histórico, não a alçada.
- **Fernet antecipado** neste PAG (em vez de esperar o PR-D da minuta): o primeiro
  consumidor de cifragem que chegar cria o helper; o outro reusa.
- **Saldos ficam no PAG-3**: aqui `conta_bancaria` é cadastro puro; nenhum cálculo de saldo.

## Riscos / atenção

- **Chave Fernet**: sem `dados_sensiveis_encryption_key` configurada, cadastrar credor com
  dados bancários falha explicitamente. Documentar no `.env`/RUNBOOK.
- **Migração de dados**: não há import do banco Django neste PAG (greenfield); se no futuro
  quiser importar cadastros reais, é um PAG separado.
- **CrudPage vs form custom**: `conta_bancaria` (validação fonte×grupo) e `credor` (dados
  cifrados/reveal) provavelmente precisam de página custom, não do `CrudPage` genérico.
- **RLS multi-tenant**: o sistema Django é single-tenant; garantir `tenant_id` em toda
  query (o serviço nunca aceita `tenant_id` do payload) e RLS forçada nas tabelas.

## Verificação (ponta-a-ponta)

Ambiente sobe via `docker compose up -d` (nginx :8090; login `admin@local.test`/`admin123`,
tenant `sobral`).
1. `alembic upgrade head` → migration `0045` aplica; conferir RLS/policies/GRANTs nas 6
   tabelas e a transação `pagamento_cadastro` semeada; testar downgrade (roundtrip).
2. CRUD via API de cada cadastro; unicidade de CNPJ/CPF e códigos (409); validação
   fonte×grupo (422); soft-delete.
3. Credor: gravar dados bancários → conferir no banco que as colunas `*_cif` estão
   **cifradas** (não legíveis); `GET .../dados-bancarios` decifra corretamente; listagem
   normal traz mascarado.
4. Telas admin: criar/editar/excluir cada cadastro logado como super-usuário; item de menu
   visível; rota `/pagamentos/...` responde (sem 502 do nginx).
5. `pytest` do backend (novos testes de cadastros + cifragem) e `tsc` do frontend.

## Próximos sub-projetos (fora deste spec)

- **PAG-2**: `pedido_pagamento` + máquina de estados (solicitar→aprovar→devolver/rejeitar),
  telas Novo Pedido e Detalhe, RBAC `pagamento*` + segregação de funções.
- **PAG-3**: autorização em lote (saldo por conta + alçada + SoD), `ordem_pagamento` (PDF
  WeasyPrint + assinatura v2), movimentações/saldo, execução pela tesouraria, Painel.
- **PAG-4+**: conciliação bancária, transparência pública (LGPD), relatórios.
