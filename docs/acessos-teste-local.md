# Acessos para teste manual

> # AMBIENTE LOCAL / DEV — NÃO USAR EM PRODUÇÃO
>
> **Escopo:** apenas a stack `docker compose` do projeto `aprimora-py` rodando
> na máquina do desenvolvedor.
> Todas as credenciais aqui são seeds de dev versionados no repositório.
> **Nenhum dado deste documento corresponde a usuário/sistema real.**
> **Data:** 2026-06-05.

---

## Sumário

1. [Ambiente](#1-ambiente)
2. [Acesso servidor / admin](#2-acesso-servidor--admin)
3. [Acesso cidadão](#3-acesso-cidadão)
4. [Roteiro de teste manual — servidor / admin](#4-roteiro-de-teste-manual--servidor--admin)
5. [Roteiro de teste manual — cidadão](#5-roteiro-de-teste-manual--cidadão)
6. [Dados de demo recomendados](#6-dados-de-demo-recomendados)
7. [Observações de segurança](#7-observações-de-segurança)
8. [Pendências conhecidas (baseline)](#8-pendências-conhecidas-baseline)

---

## 1. Ambiente

Portas confirmadas via `docker compose ps` em 2026-06-05:

| Camada | URL | Quando usar |
|---|---|---|
| Sistema (nginx) | `http://localhost:8090` | **Uso normal** — frontend + API via proxy reverso |
| Frontend (direto) | `http://localhost:3001` | Inspecionar HMR ou bypassar nginx (sem `/api/v2`) |
| Backend (direto) | `http://localhost:8001/api/v2` | curl/Postman direto na API |
| Swagger / OpenAPI | `http://localhost:8001/docs` | Explorar endpoints (FastAPI auto-doc) |
| OpenAPI JSON | `http://localhost:8001/openapi.json` | Importar em Postman/Insomnia |

> Swagger **não está exposto pelo nginx**. Acesso só via porta `8001`.

Subir e verificar:

```bash
docker compose up -d
docker compose ps
curl -s http://localhost:8090/api/v2/health
```

---

## 2. Acesso servidor / admin

### 2.1 Super Usuário (uso normal)

| Campo | Valor |
|---|---|
| URL de login | `http://localhost:8090/login` |
| E-mail | `admin@local.test` |
| Senha | `admin123` |
| Nome exibido | Usuário Local |
| Perfil | Super Usuário (vê tudo, pode tudo) |
| ID | 2 |

Use para: explorar dashboard, criar/editar serviços, abrir processos,
gerenciar usuários, reset de senha de outros usuários.

### 2.2 Usuário sem permissões (para testar guardas)

| Campo | Valor |
|---|---|
| URL de login | `http://localhost:8090/login` |
| E-mail | `semperm@local.test` |
| Senha | `semperm123` |
| Nome exibido | Usuario Sem Perm |
| Perfil | sem permissões aplicadas (não é Super Usuário) |
| ID | 6 |

Use para: validar 403, telas em modo "somente leitura", botões de ação
escondidos quando `can(...)` retorna `false`.

### 2.3 Login via API (curl)

```bash
curl -s -X POST http://localhost:8090/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@local.test","senha":"admin123"}'
```

```bash
# Identidade do usuário logado (use o access_token retornado acima)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8090/api/v2/auth/me
```

---

## 3. Acesso cidadão

### 3.1 Cidadão de teste já provisionado

| Campo | Valor |
|---|---|
| URL de login | `http://localhost:8090/cidadao/login` |
| CPF (fictício, dev) | `12345678901` (com ou sem pontuação — backend normaliza) |
| Senha | `cidadao123` |
| Nome | Cidadao Teste |
| ID | 1 |
| Tenant | 1 (Sobral) |

> CPF `12345678901` é **fictício**, gerado para o seed de dev. Não corresponde
> a pessoa real.

### 3.2 Como criar um cidadão de teste adicional

**Opção A — pela tela pública:**

1. Acesse `http://localhost:8090/cidadao/cadastrar`.
2. Preencha CPF, nome, e-mail e senha.
3. Submeta — o backend aceita CPFs sintéticos em dev.

**Opção B — via curl:**

```bash
curl -s -X POST http://localhost:8090/api/v2/cidadao/cadastrar \
  -H "Content-Type: application/json" \
  -d '{
    "cpf_cnpj": "99988877766",
    "nome": "Cidadao Demo",
    "email": "demo@cidadao.test",
    "senha": "demo1234"
  }'
```

Em seguida logue em `http://localhost:8090/cidadao/login` com esse CPF + senha.

### 3.3 Login do cidadão via API

```bash
curl -s -X POST http://localhost:8090/api/v2/cidadao/login \
  -H "Content-Type: application/json" \
  -d '{"cpf_cnpj":"12345678901","senha":"cidadao123"}'
```

```bash
# Identidade do cidadão logado
curl -H "Authorization: Bearer $TOKEN" http://localhost:8090/api/v2/cidadao/me
```

---

## 4. Roteiro de teste manual — servidor / admin

### 4.1 Login e dashboard

1. Acesse `http://localhost:8090/login`.
2. Entre com `admin@local.test` / `admin123`.
3. Após o redirect, navegue para `http://localhost:8090/dashboard`.
4. Verifique as 3 seções (cards) introduzidas no UX-1 Fase E:
   - **Visão geral** — KPIs gerais e filtros.
   - **Documentação e complementações** — pedidos pendentes.
   - **Prazos por serviço** — distribuição por assunto.
5. Use a FilterBar no topo para alternar período / serviço.
6. EmptyStates devem aparecer quando o filtro não retorna nada.

### 4.2 Catálogo de serviços (admin)

1. Navegue para `http://localhost:8090/servicos`.
2. Verifique a lista de serviços (a base local tem ~10+ assuntos ativos).
3. Clique em **Novo serviço** ou **Editar** em um existente.
4. Dialog deve mostrar 3 SectionCards (UX-1 Fase F):
   - **Identificação** — nome, slug, descrição.
   - **Configuração operacional** — tipo de processo, prazo, fluxo.
   - **Orientações ao cidadão** — passos, documentos exigidos.
5. EmptyState quando a lista está vazia (filtro estreito).

### 4.3 Detalhe do processo (servidor)

**ID conhecido em dev:** `6` (processo `P000004/2026`, assunto
"Requerimento geral", manifestante CPF `12345678901`).

1. Vá para `http://localhost:8090/processos/6`.
2. Verifique as abas:
   - **Visão geral** — dados básicos, manifestante, datas.
   - **Documentos** — anexos + botão "Solicitar complementação".
   - **Prazo** — card com prazo estimado e progresso.
   - **Assinaturas** (se houver workflow).
3. Botão **ActionsMenu → Imprimir** deve listar 5 opções
   (Capa, Termo de Abertura, Protocolo, etc.).
4. Aba **Documentos → Solicitar complementação documental** deve abrir
   o modal de pedido de complementação (PR 4d).

**Se o ID `6` não existir mais no seu banco** (ex: reset recente):

1. Vá para `http://localhost:8090/processos`.
2. Filtre pela coluna **Manifestante CPF** com `12345678901`.
3. Clique no primeiro resultado para descobrir um ID válido.

Alternativos confirmados em 2026-06-05: `P000014/2026` (id=16) e
`P000834/2026` (id=1617).

---

## 5. Roteiro de teste manual — cidadão

### 5.1 Carta de serviços e abertura de solicitação

1. Acesse `http://localhost:8090/cidadao/login`.
2. Entre com CPF `12345678901` / senha `cidadao123`.
3. Após login, será redirecionado para `/cidadao/processos`.
4. Vá manualmente para `http://localhost:8090/cidadao/servicos` — esta é
   a Carta de Serviços.
5. Clique em qualquer card de serviço para abrir o detalhe.
6. Verifique seções: descrição, **Documentos necessários**,
   **Próximos passos**, **Prazo estimado**.
7. Clique em **Solicitar serviço** → preencha a descrição → envie.
8. Será redirecionado ao detalhe do processo recém-criado.

### 5.2 Detalhe do processo cidadão

1. A partir do passo 8 acima, ou navegando em `/cidadao/processos`,
   clique em um protocolo.
2. URL fica `http://localhost:8090/cidadao/processos/{id}`.
3. Verifique:
   - **Próximos passos** — card com checklist do que falta.
   - **Documentos necessários** — lista de docs exigidos pelo serviço.
   - **Prazo estimado** — card com data estimada de conclusão.
   - **Anexos** — upload de arquivos (drag-and-drop).
   - **Complementação** — se o servidor pediu, aparece o card de resposta.
4. Submeta uma resposta de complementação (se houver pedido aberto).

### 5.3 Fluxo cruzado servidor ↔ cidadão

Para validar a integração ponta-a-ponta:

1. Como **cidadão**, abra um processo novo (passo 5.1).
2. Anote o ID/protocolo.
3. Como **servidor**, abra o mesmo processo em `/processos/{id}`.
4. Solicite complementação documental.
5. Volte como cidadão e responda à complementação.
6. Servidor confere a resposta em `/processos/{id}` aba Documentos.

---

## 6. Dados de demo recomendados

### 6.1 Serviços (assuntos) ativos confirmados em 2026-06-05

| ID | Nome (assunto) | Observação |
|---|---|---|
| 1 | Solicitação de informação | seed |
| 2 | Requerimento geral | seed — usado nos processos do cidadão de teste |
| 3 | Recurso administrativo | seed |
| 5 | Aquisição de licenças de software | seed |
| 6 | Aquisição de materiais de escritório | seed |
| 7 | Aquisição de equipamentos de TI | seed — mais usado em processos novos |
| 8 | Smoke perm | criado por teste de permissão |

> A tabela `protocolos.assunto` **não tem coluna `slug`**. No frontend o
> identificador é derivado do `id`. Para descobrir o slug real, abra a
> Carta de Serviços no portal cidadão e copie a URL ao clicar no card.

### 6.2 Processos de exemplo do cidadão de teste

| ID | Protocolo | NUP | Assunto |
|---|---|---|---|
| 6 | `P000004/2026` | — | Requerimento geral |
| 16 | `P000014/2026` | — | Aquisição de licenças de software |
| 1617 | `P000834/2026` | `99001.000075/2026-49` | Requerimento geral |

Processos com numeração mais alta (a partir de `P002391/2026`) podem ter
sido criados pelo Smoke E2E e são recriados a cada execução do Playwright
— não confiar como exemplo estável.

### 6.3 `ux1-smoke-servico`

**Não existe** um serviço com slug/nome `ux1-smoke-servico` no banco
local. O smoke UX-1 ([tests-e2e/specs/ux1-smoke.spec.ts](tests-e2e/specs/ux1-smoke.spec.ts))
usa assuntos já existentes do seed e cria processos novos a cada execução.

---

## 7. Observações de segurança

- **Credenciais públicas de dev.** Todas as senhas deste documento
  (`admin123`, `semperm123`, `cidadao123`) estão versionadas no repositório
  (em código de teste, seed ou neste arquivo). Elas existem apenas no
  ambiente local.
- **Não usar em produção** sob nenhuma hipótese.
- **Não substituir** este documento por credenciais reais. Senhas de
  produção, tokens, cookies e hashes jamais devem ser commitados.
- **Senhas temporárias de usuários reais** (ex: geradas pelo reset
  administrativo em produção) **não devem ser registradas aqui** — devem
  ser transmitidas uma única vez pelo canal seguro institucional.
- **Após o PR SEC-1** (escopo em
  [docs/sec-pr1-must-change-password-escopo-implementavel.md](sec-pr1-must-change-password-escopo-implementavel.md))
  novos usuários e admins iniciais nascerão com `must_change_password=true`
  e serão obrigados a passar pela tela `/alterar-senha-obrigatoria` no
  primeiro acesso. Este documento precisará ser revisitado quando isso entrar.
- **Cookies separados:** o sistema usa cookies distintos para sessão de
  servidor e sessão de cidadão, então o mesmo navegador pode estar logado
  nos dois portais simultaneamente sem conflito.
- **Rate-limit no nginx:** `/cidadao/login` está limitado a ~5 tentativas/min
  por IP. Se receber 503, esperar 1 minuto e tentar uma única vez.

---

## 8. Pendências conhecidas (baseline)

- **Playwright completo:** 1 falha pré-existente no spec do PHP legacy
  quando o container do monolito PHP não está rodando — esperado e ignorável
  em testes do `aprimora-py` isolado.
- **TypeScript (`tsc --noEmit`):** 21 erros baseline pré-existentes — não
  introduzidos pelas Fases UX-1 A–G. Verificar antes de declarar regressão
  qualquer erro novo acima desse número.
- **Smoke UX-1:** **7/7 passando** no último relatório
  ([tests-e2e/specs/ux1-smoke.spec.ts](../tests-e2e/specs/ux1-smoke.spec.ts),
  commit `f1f0d17`).
- **Vitest (frontend):** **215/215 passando** no último relatório.
- **SEC-1 (must_change_password):** escopo aprovado com ajustes
  ([docs/sec-pr1-must-change-password-escopo-implementavel.md](sec-pr1-must-change-password-escopo-implementavel.md)).
  **Implementação ainda não iniciada** — aguarda autorização explícita
  para o Commit 1.
