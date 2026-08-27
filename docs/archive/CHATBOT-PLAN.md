# Plano do Assistente Conversacional (Chatbot IA)

**Status:** rascunho · **Autor:** Jorge + assist · **Criado:** 2026-05-28

> ⚠️ **Este documento envelheceu em três pontos. A fatia entregue é a IA-1**, especificada em
> `docs/superpowers/specs/2026-08-07-ia-1-assistente-do-processo-design.md` — leia aquela
> primeiro. O que mudou:
>
> 1. **A trava que este plano declara na última seção caiu.** O sigilo gradual está fechado
>    (`assert_acesso_processo`), então C2 não depende mais dele.
> 2. **Este plano antecede a modularização.** As ferramentas que ele lista pertencem ao módulo
>    `protocolo` e precisariam do gate de contratação (`require_modulo`), que não existia.
> 3. **D3 foi decidido CONTRA o default deste documento.** A IA-1 não usa tool-calling: injeta o
>    processo já autorizado no prompt, e o modelo não tem ferramenta para chamar. Tool-calling
>    volta quando a busca voltar — e a busca depende do item 1.0.8 do backlog, porque ela
>    transforma aquele buraco de latente em explorável.

> Origem: avaliação do chatbot do projeto `ianalisys_v1` (assistente de análise
> para restaurantes). Aproveitamos a **arquitetura** (não o domínio): roteamento
> multi-provider de LLM, streaming SSE com envelope de eventos, persistência de
> conversa, camada de validação factual e orquestração system-prompt + knowledge
> base + contexto de dados. Reescrito **independente** no nosso stack.

## 1. Contexto

Um assistente conversacional no aprimora-py responderia, em linguagem natural e
aterrado nos dados reais, perguntas como:

- "Onde está o protocolo NUP 99999.000123/2026-45?" / "Qual o status do P000045/2026?"
- "Quais são meus processos parados há mais de 30 dias?"
- "Qual classe CCD e prazo de guarda (TTD) se aplicam a este assunto?"
- "Me ajuda a classificar este requerimento."
- "Quanto tempo devo guardar documentos da classe X antes de eliminar?"

O valor: reduzir o atrito de operação (servidor) e de acompanhamento (cidadão)
sobre um sistema cujo modelo de dados é rico mas a navegação é por telas.

**Princípio inegociável (governo):** o bot **nunca** pode vazar dado que o
usuário não poderia ver pela UI. Toda consulta roda sob o mesmo RLS multi-tenant
e o mesmo **sigilo gradual** (`nivel_sigilo` + credencial do usuário) recém
implementados. Resposta errada/inventada sobre um processo é inaceitável → a
camada de validação factual é requisito, não enfeite.

## 2. O que já temos a favor

| Recurso | Onde | Por que ajuda o chatbot |
|---|---|---|
| Multi-tenant + RLS | `SET LOCAL app.tenant_id` + policies | Isolamento automático das consultas do bot |
| **Sigilo gradual** | `processo.nivel_sigilo` + `usuario.nivel_acesso_sigilo` + `niveis_permitidos()` | Bot só "vê" o que o usuário vê — filtro pronto |
| Catálogo de domínio | processos, NUP, CCD, TTD, espécie, manifestante | Fonte de verdade pra grounding |
| Sugestão CCD | `services/temporalidade.sugerir_ccd_por_assunto()` | Vira uma "ferramenta" do bot direto |
| Temporalidade | `services/temporalidade.calcular_temporalidade()` | Responde prazo de guarda sem inventar |
| Motor de notificações | `services/notificacoes.enviar()` | Bot pode disparar avisos (fase futura) |
| Audit log | `audit_log` + service | Trilha de toda ação sugerida/executada pelo bot |
| Stack moderno | FastAPI + SQLAlchemy async + Next.js 15 | SSE e tool-calling encaixam limpo |

## 3. Decisões pendentes do Jorge

| # | Decisão | Default sugerido |
|---|---|---|
| D1 | **Público-alvo do MVP**: servidor interno, cidadão, ou ambos? | **Servidor interno primeiro** — já tem credencial de sigilo; cidadão entra na fase final, com escopo restrito a "meus processos" |
| D2 | **Provider**: Claude-only no começo ou multi-provider já? | **Claude-only** (Sonnet 4.x), atrás de uma interface `LLMClient` que permita DeepSeek/OpenAI depois. Chaves/infra **nossas** (independência) |
| D3 | **Grounding**: LLM gera SQL livre (como o ianalisys) ou tool-calling com catálogo fixo? | **Tool-calling com catálogo de queries read-only parametrizadas** — mais seguro (sem injeção), idiomático no Claude, e roda sob RLS+sigilo. NUNCA SQL livre do modelo |
| D4 | **Validação factual** no MVP ou fase 2? | **Versão leve no MVP** (toda afirmação cita `id`/`numero`/`NUP` da fonte; recusa firme quando não há dado). Validação pesada (conferir números pós-geração + re-tentar) na fase 4 |
| D5 | **Execução da chamada LLM**: inline no request (SSE) ou worker Celery? | **Inline SSE** (latência menor, igual ianalisys). Celery só se surgir tarefa longa (ex.: sumarizar processo gigante) |
| D6 | **Escopo de ações**: só leitura, ou o bot pode *executar* (encaminhar, classificar)? | **Só leitura + sugestão** no MVP. Ações que mutam estado exigem confirmação explícita do usuário na UI (fase futura), sempre auditadas |

## 4. Arquitetura proposta

### 4.1 Backend (`backend/app/services/ia/` — pacote novo)

- `llm_client.py` — interface `LLMClient` + impl `AnthropicClient` (streaming via
  SDK `anthropic`, suporte a tool-use). Troca de provider por env/config.
- `tools.py` — **catálogo de ferramentas** (tool-use) que o modelo pode chamar.
  Cada ferramenta é uma função Python segura, parametrizada, que roda query
  read-only sob a sessão do usuário (RLS + `niveis_permitidos`). Ex.:
  - `buscar_processo(numero_ou_nup)` → status, localização, última movimentação
  - `meus_processos(filtro_prazo?)` → lista do manifestante/unidade
  - `sugerir_ccd(texto_assunto)` → reusa `sugerir_ccd_por_assunto`
  - `temporalidade_processo(id)` → reusa `calcular_temporalidade`
  - `explicar_termo(termo)` → glossário CONARQ/LAI/NUP (knowledge base)
- `orchestrator.py` — monta o system prompt + injeta knowledge base + roda o
  loop de tool-use (modelo pede ferramenta → executamos → devolvemos resultado →
  modelo responde) e emite eventos SSE.
- `validation.py` (fase 4) — confere que números/ids citados existem no contexto
  das ferramentas chamadas; severidade alta → re-tenta.
- `knowledge/` — markdown do domínio: glossário (protocolo, NUP, CCD, TTD, LAI,
  sigilo), regras de negócio, exemplos. Carregado no boot.

### 4.2 Persistência (migration nova)

Espelha o padrão do ianalisys, com `tenant_id` + RLS em tudo:

- `ia_sessao` — id, tenant_id, id_usuario, canal (`interno|portal`), titulo,
  iniciada_em, encerrada_em (soft-delete).
- `ia_mensagem` — id, sessao_id, tenant_id, role (`user|assistant|tool`),
  conteudo, ferramentas_usadas (json), criada_em.
- `ia_trace` (telemetria) — 1 linha por request: pergunta, ferramentas, latência
  por estágio, provider, tokens in/out, validação_severidade. Índice por
  (tenant_id, criado_em).

### 4.3 Router (`backend/app/routers/ia.py`)

- `POST /ia/chat` — **StreamingResponse SSE**. Envelope de eventos:
  `meta` (sessao_id) · `progresso` (fase) · `tool` (ferramenta chamada) ·
  `texto` (tokens markdown) · `fontes` (ids/nups citados) · `fim`.
- `GET /ia/sessoes` · `GET /ia/sessoes/{id}/mensagens` · `PUT`/`DELETE` sessão ·
  `POST /ia/feedback` (👍/👎).
- Auth: usuário interno (JWT) ou cidadão (sessão do portal). A credencial de
  sigilo e o tenant saem do mesmo lugar que o resto da API → ferramentas herdam.

### 4.4 Frontend (Next.js 15)

- `frontend/app/(app)/assistente/page.tsx` — página de chat (servidor).
- `frontend/lib/useChat.ts` — hook gerenciando estado + leitor SSE (`fetch` +
  `ReadableStream`). Referência: `useChat.ts` do ianalisys, reescrito p/ Next.
- Componentes: `ChatInput`, `MessageBubble`, drawer de histórico (Cmd+K),
  render de "fontes" clicáveis (link pro processo citado).
- Reaproveita tokens/skeleton/empty states que já padronizamos.

## 5. Fases

| Fase | Objetivo | Saída |
|---|---|---|
| **C1 — Fundação** | Conversa que funciona, sem grounding | migration (ia_sessao/mensagem/trace), `LLMClient` Claude, `POST /ia/chat` SSE só com system prompt, persistência, UI de chat básica no Next |
| **C2 — Grounding seguro** | Bot responde sobre dados reais | `tools.py` com 4-5 ferramentas read-only sob RLS+sigilo; loop tool-use no orchestrator; evento `fontes` |
| **C3 — Conhecimento** | Bot entende o domínio | knowledge base CONARQ/LAI/NUP + system prompt com regras (recusa firme, não inventar, idioma, sigilo de infra) |
| **C4 — Validação + telemetria** | Confiabilidade de governo | `validation.py` (confere números/ids citados), `ia_trace`, feedback 👍/👎 |
| **C5 — Multi-provider** (opcional) | Custo/resiliência | interface já pronta → DeepSeek/OpenAI + budget por tenant |
| **C6 — Portal cidadão** | Cidadão acompanha por chat | escopo restrito a "meus processos" (CPF/CNPJ), sem dados internos |

Esforço aproximado: **C1 ~1 semana · C2 ~1 semana · C3 ~3-4 dias · C4 ~1 semana ·
C5 ~3-4 dias · C6 ~1 semana.** MVP útil (C1+C2+C3) em ~2,5 semanas.

## 6. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| **Vazamento de sigilo** (bot mostra processo acima da credencial) | Ferramentas rodam sob RLS + `niveis_permitidos()` do usuário; teste de regressão dedicado |
| **Alucinação** (inventar status/número) | Tool-calling (sem SQL livre) + regra "não inventar" + validação factual (C4) + citar fonte sempre |
| **Injeção** (prompt do usuário vira SQL/comando) | Modelo nunca escreve SQL; só chama ferramentas parametrizadas com tipos validados |
| **LGPD** (dado pessoal em prompt/trace) | `ia_trace` não grava conteúdo sensível cru; minimizar PII no prompt; retenção curta do trace |
| **Custo por tenant** | Budget/limite por tenant (C5) + provider barato no caminho comum |
| **Acoplamento ao ianalisys** | Reescrita independente; só o **padrão** é reutilizado, nada de código/chaves deles |

## 7. Próximos passos

1. Jorge revisa decisões **D1–D6**.
2. Alinhado: começo por **C1** (fundação) e este doc é reaberto com o roteiro
   detalhado (migration, schemas, rotas, telas).
3. Pré-requisito barato: definir provider + obter chave (nossa conta), env
   `IA_PROVIDER` / `ANTHROPIC_API_KEY`.

---

**Observação de estado:** a feature de **sigilo gradual** está pausada num ponto
seguro (migration 0019 aplicada no dev; falta regenerar dump CI + testes +
frontend). O chatbot **depende** dela pra enforcement de acesso — convém fechar
o sigilo antes de iniciar C2.
