# Modularização F3 — prefixo `/m/<slug>` nas URLs

> **Para agentes:** use `superpowers:subagent-driven-development` para executar tarefa a tarefa.

**Objetivo:** as telas de módulo passam a viver em `/m/<slug>/…`; toda URL antiga continua válida
por **308**; nenhum link já enviado quebra.

**Arquitetura:** a spec é `docs/superpowers/specs/2026-07-28-modularizacao-launcher-design.md` §6 e
§7 — leia antes de qualquer tarefa. A F2 já deixou pronto o que a F3 consome: `ROTA_MODULO` /
`moduloDoPathname` (`lib/modulos.ts`), os cinco arquivos de menu (`lib/menus/`), a `Sidebar` com
prop `modulo` e o launcher `/modulos`.

**Stack:** Next.js 15 App Router, `next.config.js` (`redirects()`), nginx, vitest.

## Restrições globais

- **Nada de backend nesta fatia.** Sem migration, sem endpoint novo. O gate de contratação
  (`require_modulo`) e o de permissão já existem e não mudam.
- **O guard do frontend é UX, não segurança.** A barreira real é o backend. Nenhum teste desta
  fatia deve afirmar que o guard protege dado.
- **A regex do nginx MANTÉM todos os tokens atuais** e apenas ganha `m`. Remover token antigo faz a
  URL antiga cair no fallback legado e morrer **antes** de chegar ao Next para ser redirecionada —
  ou seja, mataria justamente o 308 que a fatia existe para oferecer. `notificacao.link_url` é
  registro histórico permanente; na prática os tokens antigos ficam para sempre.
- **`permanent: true`** (308, não 307/302): preserva método e corpo, e há caminhos que recebem POST.
- **`notificacao.link_url` NÃO é migrado.** Linha histórica é registro do que foi enviado, não
  configuração. A *geração* prefixada é F4.
- **Rotas transversais ficam na raiz** (D5): `/home`, `/dashboard`, `/perfil`, `/perfil/notificacoes`,
  `/para-assinar`, `/busca`. Não ganham prefixo e não ganham redirect.
- Um módulo por tarefa. `tsc --noEmit` e `npm test` verdes ao fim de cada uma.
- pt-BR em código, comentário e commit.

---

### Tarefa 1: preservar o destino no login (`?next=`)

Independente do resto e útil sozinha. Hoje `middleware.ts` clona a URL e troca o pathname por
`/login`, **perdendo o destino**. Quem abre `/frotas/veiculos` sem sessão cai no launcher. Com URL
de módulo chegando por e-mail e SMS isso deixa de ser incômodo e vira perda real.

**Arquivos:** `frontend/middleware.ts`, `frontend/app/login/page.tsx`,
`frontend/__tests__/middleware.test.ts` (criar).

- [ ] Middleware grava `?next=<pathname+search>` ao redirecionar para `/login`.
- [ ] O login, após autenticar, navega para `next` quando presente; senão mantém o destino de hoje
      (`/modulos`).
- [ ] **`next` só pode ser caminho interno.** Aceitar valor arbitrário é *open redirect*: rejeite o
      que não comece com `/`, e rejeite `//` e `/\` (que o navegador trata como host externo). Um
      teste com `next=https://evil.example` e outro com `next=//evil.example` têm de provar que o
      destino vira o default.
- [ ] `must_change_password` (SEC-1) **continua tendo precedência** sobre `next` — é regra de
      segurança e há teste que a trava. Confirme antes de mexer.
- [ ] Commit.

### Tarefa 2: o shell `/m/[modulo]` e o primeiro módulo (transporte)

Transporte é o menor módulo de diretório único (8 páginas, 1 diretório): prova o padrão ponta a
ponta com o menor raio de dano.

**Arquivos:** criar `frontend/app/(app)/m/[modulo]/layout.tsx`; mover
`frontend/app/(app)/transporte-regulado/` → `frontend/app/(app)/m/transporte/`; `nginx/default.conf`;
`frontend/next.config.js`; `frontend/lib/menus/transporte.ts`.

- [ ] `layout.tsx` do segmento dinâmico: lê `params.modulo`, renderiza `<Sidebar modulo={slug} />`
      e confere o slug contra `/modulos/me`; não batendo, devolve ao launcher.
- [ ] Slug desconhecido (`/m/inexistente`) devolve ao launcher, não quebra.
- [ ] `git mv` do diretório inteiro — o único import relativo do projeto
      (`frotas/veiculos/page.tsx` → `./documentos-dialog`) é irmão e sobrevive desde que o
      diretório mova junto. Os outros 653 imports usam alias `@/`.
- [ ] Token `m` na regex do `location ~ ^/(...)` do nginx, **sem remover nenhum token**.
- [ ] `redirects()` no `next.config.js`:
      `{ source: '/transporte-regulado/:path*', destination: '/m/transporte/:path*', permanent: true }`.
- [ ] `href` do menu de transporte prefixado, e a `raiz` do módulo no launcher.
- [ ] **Verificar pelo nginx (`:8090`), não só em dev.** Rota de topo nova que não esteja na regex
      "não existe" no `:8090` mesmo funcionando em `:3000` — quase aconteceu com `/modulos`.
- [ ] `curl -I` provando **308** e o `Location` correto; a URL nova respondendo 200.
- [ ] Commit.

### Tarefas 3 a 6: os demais módulos, um por commit

Mesma receita da Tarefa 2, sem o shell (já existe) e sem o token do nginx (já existe). Ordem por
tamanho crescente de risco:

- [ ] **Tarefa 3 — frota**: `/frotas` → `/m/frota` (9 páginas, 1 diretório).
- [ ] **Tarefa 4 — pagamentos**: `/pagamentos` → `/m/pagamentos` (15 páginas, 1 diretório).
- [ ] **Tarefa 5 — administração**: 7 diretórios de topo (`usuarios`, `grupos`,
      `unidades-trabalho`, `organograma`, `auditoria`, `configuracoes`, `jobs`) → `/m/administracao/…`.
      São 7 regras de redirect, uma por diretório.
- [ ] **Tarefa 6 — protocolo**: 14 diretórios, 24 páginas. A maior e a última, porque é a que mais
      links históricos tem. Atenção ao `/relatorios`, que é de protocolo mas tem nome genérico.

Cada tarefa: mover, redirect, prefixar `href` do menu e a `raiz`, `tsc` + `npm test`, conferir no
`:8090`, commit.

### Tarefa 7: guarda de divergência e fecho

O que impede a próxima pessoa de mover uma tela e esquecer o redirect — sem isto, o esquecimento
aparece como link morto em produção, não como teste vermelho.

**Arquivos:** `frontend/__tests__/rotas-modulo.test.ts` (criar), `docs/BACKLOG-PENDENCIAS.md`,
`CLAUDE.md`.

- [ ] Teste: **todo** prefixo de `ROTA_MODULO` tem regra correspondente em `redirects()`, e o
      destino bate com o slug que o mapa declara. Mensagem de falha dizendo que prefixo novo exige
      redirect novo.
- [ ] Teste: **nenhum** diretório de módulo sobrou em `app/(app)/` fora de `m/` — a lista de
      diretórios de topo permitidos é explícita e só contém as transversais da D5.
- [ ] Teste: **todo** slug de `MENUS` (menos `comum`) tem diretório em `app/(app)/m/`.
- [ ] **Prova por inversão obrigatória**, nos três: quebre de propósito (remova um redirect, deixe
      um diretório para trás, apague um `m/<slug>`), veja vermelho, desfaça. Guarda que ninguém viu
      falhar não vale nada — nos seis PRs anteriores desta casa, *todos* os defeitos graves foram
      testes que passavam pelo motivo errado.
- [ ] `CLAUDE.md`: a instrução "rota de topo nova precisa entrar na regex do nginx" ganha a
      contrapartida — tela de módulo nova nasce em `m/<slug>/`, e rota de topo nova fora de `m/` só
      se for transversal.
- [ ] Fechar o item da F3 no backlog.
- [ ] Commit.

## Fora de escopo (é F4)

`public.modulos` / `configuracoes_modulos` fora do ORM; deletar a `Sidebar.tsx` antiga; geração de
`link_url` já prefixada.

## Critério de aceite

Os três roteiros E2E da spec §11: (1) usuário com todos os módulos navega e troca pelo switcher;
(2) usuário sem Pagamentos não vê o card **e** `/m/pagamentos` devolve ao launcher; (3) link antigo
`/pagamentos/contas-a-pagar` → **308** → `/m/pagamentos/contas-a-pagar`. Mais: nenhuma rota de topo
de módulo sem redirect, `tsc --noEmit` limpo, `npm test` verde.
