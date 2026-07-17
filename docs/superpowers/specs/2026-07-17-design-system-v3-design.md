# Aprimora Design System v3 — Institucional Refinado (spec)

## Context

Jorge pediu uma passada de UX profissional com design system moderno no app inteiro.
Decisões (AskUserQuestion 2026-07-17): direção **institucional refinado** (identidade
verde-petróleo formalizada, acabamento Linear/Vercel: denso, sereno, tipografia impecável);
**Inter + numerais tabulares** (next/font local); escopo **app inteiro, tela a tela** (62
páginas, 22 componentes ui/). Decisão do controller: a marca recentra no verde-petróleo
(o navy `#1e3a5f` sai de primary); o **âmbar permanece como acento-assinatura** (par
quente/frio com o verde). Método: skill design-system (3 camadas: primitivo → semântico →
componente; scripts generate/validate-tokens).

Estado atual: `globals.css` tem "DS v2" com camada semântica decente (HSL, surfaces tonais,
dark dessaturado, densidade compact) mas SEM primitivos, com identidade dividida
(brand=navy, accent=âmbar, sidebar=verde enxertado) e páginas com padrões desiguais.

## 1. Camada primitiva (novo topo do globals.css)

Ramps HSL completos, nomeados, NUNCA usados direto em componente:
- `--green-50..950` — ramp do verde-petróleo (âncora 700 = atual `164 56% 16%`→ recalibrar
  âncora de marca em ~`166 45% 28%` p/ AA em texto branco; 900/950 para a lateral).
- `--amber-50..950` — ramp do âmbar (âncora 600 = `32 95% 44%`).
- `--neutral-0..950` — neutros com viés frio-esverdeado sutil (substituem os slates),
  0=branco, 25=off-white do canvas (`120 6% 97%` mantido), 950=quase-preto esverdeado.
- `--red/--yellow/--blue/--emerald-*` (5 degraus cada) — bases dos status.
- Escalas não-cor: `--space-0..24` (base 4px), `--radius-xs..xl` (2/4/6/8/12) + `--radius-full`,
  `--shadow-xs..lg` (sombras frias de 1-3 camadas, sutis), `--text-xs..3xl` com line-heights
  pareados (12/16, 13/18, 14/20, 16/24, 18/26, 22/30, 26/34, 32/40), `--font-sans`
  (Inter via next/font, fallback system-ui), pesos 400/500/600/700, `--tracking-tight/wide`,
  `--duration-fast/base` (120/200ms) + `--ease-out-quart`, z-index scale.

## 2. Camada semântica (reescrita da atual, MESMOS NOMES públicos)

Todos os tokens semânticos existentes continuam existindo (zero quebra), mas passam a
referenciar primitivos e a nova identidade:
- `--brand`/`--primary` → verde (âncora `--green-700`); `--brand-light/dark` degraus vizinhos.
- `--accent*` → âmbar (inalterado em valor, agora referenciando ramp).
- Surfaces/foregrounds/borders → neutros novos (viés frio-verde), hierarquia tonal mantida;
  dark mode re-derivado do ramp (dessaturado, superfícies 900→850→800).
- `--sidebar-*` → `--green-900/950` family (mantém o look aprovado).
- Status: soft/solid/foreground por intent (danger/success/warning/info) a partir dos ramps.
- `--ring` = marca com offset; foco visível padronizado.
- Legacy aliases (`--aprimora*`) mantidos.

## 3. Camada de componente + specs

Tokens `--button-*`, `--input-*`, `--table-*`, `--badge-*`, `--dialog-*`, `--card-*`
consumidos pelos 22 componentes de `frontend/components/ui/`. Cada componente ganha spec
de estados completa (default/hover/active/focus-visible/disabled/loading onde couber) —
documentada em `docs/design-system.md` (tabela por componente). Regras transversais:
- foco: ring 2px na cor da marca + offset 2 (visível em ambos os temas);
- hover nunca só cor de texto (sempre bg ou borda);
- disabled: opacidade 50 + cursor-not-allowed (nunca remover do fluxo de teclado sem aria);
- densidade compact continua funcionando (tokens de espaço por densidade).

## 4. Tipografia

Inter via `next/font/google` (self-host automático do Next — sem CDN em runtime) aplicada
no `<body>`; `font-feature-settings: "tnum"` utilitário `.tabular-nums` já usado permanece;
hierarquia: page title 22/30 semibold; section 16/24 semibold; body 14/20; meta/caption
13/18 muted; dados de tabela 14/20; KPI hero 26-32 semibold tabular. Aplicar a escala nos
componentes base (PageHeader, CardTitle, TH etc.) para herdar em todas as telas.

## 5. Sweep tela a tela (62 páginas, por módulo)

Checklist padrão por tela (aplicado em tasks por módulo):
1. `PageHeader` padronizado (título+descrição+ações; ícone onde já há padrão);
2. ritmo de espaçamento (space-6 entre seções, space-4 intra; nada de mt/mb ad hoc);
3. zero cor hardcoded (validate-tokens; exceção: cores de dado dos charts do dataviz);
4. tabelas no padrão único (TH uppercase 12px tracking-wide muted; linhas 44px; zebra off;
   hover surface-2; valores tabular right);
5. forms no padrão (Label/Input/help/erro consistentes; grid 2 col onde couber);
6. estados vazio/carregando/erro presentes (EmptyState/Skeleton/toast);
7. dark mode conferido.

Módulos (ordem): A) Geral (home, dashboard, perfil, configurações, para-assinar);
B) Processos+Protocolo (processos, [id], novo, balcão, ccd, ttd, vencendo-prazo, relatórios);
C) Cadastros GED (assuntos, manifestantes, cidades, bairros, endereços, serviços, tipos-*,
templates-documento, organograma, grupos, usuários, unidades, jobs, auditoria);
D) Frota (8 telas); E) Transporte regulado (4); F) Pagamentos (passada fina — já é o mais
novo); G) telas restantes/admin.

## 6. Governança

- `frontend/design-tokens.json` (fonte) + `node .claude/skills/design-system/scripts/
  generate-tokens.cjs` NÃO será adotado nesta fase (globals.css manual já é o contrato do
  Tailwind); adotamos o **validador**: `validate-tokens.cjs --dir frontend/` no CI local
  (script npm `design:check`) com allowlist para os hex de charts.
- `docs/design-system.md`: paleta, escalas, specs de componentes, do/don't de telas.

## Fora de escopo
Rebrand de logo, telas do portal cidadão (`app/cidadao` — herdam tokens mas sem sweep),
Storybook.

## Verificação
- tsc + suite frontend (vitest dos componentes) verdes; app sobe.
- validate-tokens sem hex fora da allowlist.
- Screenshots claro/escuro das telas-âncora de cada módulo (home, processos/[id], frota,
  pagamentos/dashboard, tesouraria) — revisão visual do controller.
- Contraste AA nos pares principais (spot-check com o validador da skill dataviz p/ os
  pares de status).
