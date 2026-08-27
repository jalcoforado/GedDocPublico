# Roadmap pós-SEC-1 — Funcionalidades de maturidade de mercado

> **Data:** 2026-06-06
> **Status:** backlog / pendências futuras — **nada aqui está autorizado a iniciar.**
>
> Documento de planejamento estratégico que registra as frentes que faltam para o
> `aprimora-py` aproximar-se de soluções maduras como SEI/PEN e plataformas de
> protocolo/GED de mercado. Complementa a análise técnica em
> [docs/archive/analise-arquitetural-protocolo-prefeituras.md](archive/analise-arquitetural-protocolo-prefeituras.md).

---

## 1. Contexto

- **Foco atual:** concluir o **SEC-1** — `must_change_password` e hardening de
  senha temporária. Plano em
  [docs/archive/sec-pr1-must-change-password-escopo-implementavel.md](archive/sec-pr1-must-change-password-escopo-implementavel.md).
- **Estado do SEC-1:** Commit 1 (schema/modelo) commitado; Commit 2 (guard +
  whitelist) implementado e testado, aguardando autorização para commit. Faltam
  os Commits 3–8 do plano (provisionamento, reset, login flag, frontend,
  interceptor, tela, RUNBOOK, Playwright).
- As frentes listadas abaixo são **pendências futuras**. Não devem ser iniciadas
  até que o SEC-1 seja concluído e cada uma seja autorizada individualmente,
  com escopo implementável próprio (padrão dos PRs anteriores).
- O objetivo deste documento é **não esquecer** que essas frentes existem e
  **acordar a ordem recomendada**, evitando que o próximo PR seja escolhido por
  oportunidade em vez de impacto.

---

## 2. Pendências principais

### A. GED-1 — Autos digitais mínimos

**Objetivo.** Criar estrutura de autos digitais dentro do processo — peça
faltante hoje em relação a SEI/PEN e qualquer solução de GED madura.

**Escopo futuro:**

- peças do processo (entidade `peca_processo` ou similar);
- índice dos autos (listagem ordenada com tipo, origem, data, autor);
- capa do processo (já existe em PDF, falta como entidade lógica);
- ordenação cronológica/formal (numeração de páginas/folhas);
- tipo da peça (despacho, parecer, ofício, anexo do cidadão, comprovante…);
- origem da peça: cidadão, servidor, sistema, assinatura;
- data de juntada;
- responsável pela juntada;
- visualização/baixar peça (download individual);
- indicação se a peça está assinada (link com `assinatura_anexo`);
- vínculo com checklist / complementação (rastrear qual documento exigido cada
  peça atende).

**Fora do GED-1:**

- PDF completo dos autos (volume único concatenado) — caro se grande;
- OCR;
- busca full-text (vai para **SEARCH-1**);
- modelos/minutas complexas (vai para **DOC-1**);
- desentranhamento avançado (já existe parcial via `desentranhamento`).

---

### B. FLOW-1 — Fila de trabalho e atribuição

**Objetivo.** Evoluir a tramitação interna para um modelo de fila por
unidade/responsável — hoje o processo "está em uma unidade" mas não há fila
explícita nem atribuição individual.

**Escopo futuro:**

- fila por unidade (caixa de entrada da unidade);
- responsável pelo processo (atribuição individual ao servidor);
- atribuição / reatribuição (operações explícitas com auditoria);
- ciência / recebimento (servidor "pega" o processo);
- prioridades (alta/normal/baixa, ou por SLA restante);
- tarefas internas (sub-itens dentro de um processo);
- processos parados há X dias (alerta operacional);
- visão operacional por servidor / unidade (dashboard de carga).

---

### C. SEARCH-1 — Busca full-text

**Objetivo.** Melhorar localização de processos / documentos — hoje a busca
existe (`/busca`) mas é limitada a colunas indexadas.

**Escopo futuro:**

- busca por número (NUP, protocolo) — refinar o atual;
- interessado (CPF/CNPJ, nome) — refinar o atual;
- serviço;
- assunto;
- texto de documentos (quando houver OCR / indexação) — depende de stack
  decisão (`pg_trgm` + `tsvector` vs. ElasticSearch/Meilisearch);
- filtros por unidade, período, status e serviço (combinatória rica).

---

### D. DOC-1 — Modelos e minutas

**Objetivo.** Aproximar do uso interno de processo eletrônico maduro — hoje
não há modelos editáveis dentro do sistema.

**Escopo futuro:**

- modelos de despacho;
- parecer;
- decisão;
- ofício;
- documento nato-digital (criado dentro do sistema, sem upload);
- versionamento simples (rascunho → assinatura → publicação);
- assinatura de documento interno (reaproveitar `assinatura_v2`).

---

### E. OPS-1 — Operação SaaS por tenant

**Objetivo.** Preparar escala real — hoje o multi-tenant funciona, mas falta
observabilidade e operação por tenant.

**Escopo futuro:**

- métricas por tenant (processos abertos, usuários ativos, storage, etc.);
- armazenamento usado (consumo vs. `limite_armazenamento_mb` do plano);
- usuários ativos (consumo vs. `limite_usuarios` do plano);
- processos por tenant;
- backup / restore (rotina automatizada + procedimento manual);
- limites por plano (enforcement, hoje só registrado em `tenant.plano`);
- logs estruturados por tenant (filtros prontos por `tenant_slug`);
- runbook de incidente (canal, escalonamento, checklist).

---

### F. GOVBR-1 — Login gov.br cidadão

**Objetivo.** Aumentar legitimidade do portal cidadão — hoje cidadão usa
CPF/senha; cadastro é responsabilidade do próprio.

**Escopo futuro:**

- autenticação gov.br (OAuth2, selo prata/ouro);
- vínculo de cidadão (federar identidade gov.br com `usuario_externo` local);
- compatibilidade com fluxo atual (não quebrar login CPF/senha);
- análise de impacto LGPD (dados retornados pelo gov.br, retenção, escopo).

> **Atenção ao escopo do projeto:** memória de projeto registra "mobile e
> gov.br fora do escopo atual" — esta frente fica aqui apenas como pendência
> reconhecida. Iniciar exige reabertura formal do escopo.

---

### G. TECH-1 — Zerar baseline TypeScript

**Objetivo.** Transformar `tsc --noEmit` em gate real de CI — hoje há 21 erros
baseline pré-existentes que o pipeline tolera.

**Escopo futuro:**

- corrigir os 21 erros baseline (catalogar, agrupar por causa raiz);
- remover exceções (`// @ts-ignore`, `as any` ad-hoc);
- garantir `tsc --noEmit` verde em CI (gate bloqueia merge se aparecer erro
  novo).

> **Por que vem cedo na ordem:** quanto mais código novo entra com `any` ou
> ignore, mais caro fica corrigir depois. Janela ideal é logo após o SEC-1,
> antes do GED-1 começar a engordar o frontend.

---

## 3. Ordem recomendada depois do SEC-1

1. **GED-1** — Autos digitais mínimos (lacuna mais visível vs. SEI/PEN).
2. **TECH-1** — Zerar TypeScript baseline (janela curta antes do frontend
   crescer com GED).
3. **OPS-1** — Métricas / backup / restore por tenant (pré-requisito de
   produção real).
4. **FLOW-1** — Fila de trabalho e atribuição (impacto operacional grande
   no usuário servidor).
5. **SEARCH-1** — Busca full-text (depende do GED-1 para ter o que buscar).
6. **DOC-1** — Modelos e minutas (depende do GED-1 e da assinatura interna).
7. **GOVBR-1** — Login gov.br cidadão (exige reabertura de escopo).

A ordem é uma **recomendação**, não uma dependência rígida — exceto onde
explicitado (SEARCH-1 e DOC-1 dependem de GED-1).

---

## 4. Anti-escopo imediato

**Nenhuma das frentes abaixo pode ser iniciada agora.** Estão listadas para que,
se surgirem como sugestão durante o SEC-1, sejam recusadas e remetidas a este
documento:

- **GED** completo (autos digitais — fica como **GED-1** futuro);
- **gov.br** (cidadão e/ou servidor — fica como **GOVBR-1** futuro);
- **IA** / chatbot (existe iniciativa separada em `CHATBOT-PLAN.md`, fora deste roadmap);
- **WhatsApp** (já há canal de notificação, expansão fica como tema posterior);
- **OCR** (depende de stack decisão; entra dentro de **SEARCH-1**);
- **Workflow builder** complexo (motor `strict mode` atual já atende; UI de
  edição de DSL fica pra muito depois);
- **Billing** (cobrança por plano — depende de **OPS-1** e de decisão de modelo
  comercial);
- **Integração PEN / Tramita GOV** (interoperabilidade entre órgãos — exige
  conformidade e adesão formal);
- **App mobile** (memória de projeto: explicitamente fora de escopo);
- **Assinatura ICP avançada** (PAdES nível LTA/LTV, carimbo do tempo
  qualificado — `assinatura_v2` cobre o nível atual exigido).

**Foco imediato:** concluir o **SEC-1** (Commits 3–8 do plano implementável).

---

## 5. Como usar este documento

- **Antes de propor um novo PR:** verificar se está nesta lista. Se estiver,
  abrir escopo dedicado em `docs/<area>-<id>-<nome>-escopo.md` no padrão dos PRs
  anteriores (proposta → escopo implementável → autorização para Commit 1 →
  commits incrementais).
- **Ao concluir uma frente:** marcar aqui como concluída com link para o PR /
  commit final.
- **Se aparecer uma frente nova:** adicionar como item adicional (H, I, …) com
  objetivo + escopo, manter a ordem recomendada sob revisão.
- **Não usar este documento como autorização** — ele só *registra*. Cada
  início exige autorização explícita do mantenedor.
