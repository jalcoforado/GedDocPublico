# Design System — Aprimora v3 (Institucional Refinado)

> **Status:** vivo · **Autoridade sobre:** Tokens, componentes e padrões de UI.
> **Última verificação:** 2026-08-20 (último commit que tocou este arquivo).
> Índice: [docs/INDEX.md](INDEX.md) · precedência: código > `CLAUDE.md` > este doc.


Doc curto e vivo. Fonte de verdade executável: `frontend/app/globals.css` (tokens),
`frontend/tailwind.config.ts` (mapeamento para classes) e as guardas
(`design-check.mjs`, `contrast-check.mjs`, `tokens-mortos.test.ts`,
`z-index-camadas.test.ts`, `focus-visible-css.test.ts`). Se este doc divergir
do código, o código (e as guardas) vencem — e este arquivo deve ser corrigido.

## Arquitetura de tokens (3 camadas)

1. **Primitiva** — rampas HSL completas (`--green-*`, `--amber-*`, `--neutral-*`,
   `--red/emerald/yellow/blue-*`) + escalas não-cor (`--radius-*`, `--shadow-*`,
   `--text-*`/`--leading-*`, `--z-*`). **Nunca usar primitivo direto em
   componente** — sempre via token semântico. Degraus de rampa sem consumidor
   são a única isenção da guarda de token morto: existem para as próximas fases
   escolherem sem inventar cor literal.
2. **Semântica** — nomes públicos estáveis (`--brand`, `--accent`, `--surface-1..3`,
   `--danger[-soft[-foreground]]` etc.). Dark mode **redefine** esses tokens
   (dessaturado, elevação tonal), nunca cria nomes novos.
3. **Componente** — `--button-*`, `--input-*`, `--card-*`, `--dialog-*`…
   Só referenciam tokens das camadas acima. Token de componente nasce **quando o
   componente o consome** (declarar "para depois" = token morto = guarda vermelha).

Escalas que **não** têm token próprio (o Tailwind é a fonte): espaçamento
(`p-4`, `gap-2`…), pesos (`font-medium`…), tracking (`tracking-tight`…).

## Paleta (semântica)

| Papel | Light | Dark | Classe |
|---|---|---|---|
| Marca | verde-petróleo `--green-700` | `--green-400` (clareia p/ AA) | `bg-brand`, `text-brand` |
| Acento | âmbar `--amber-600` | âmbar clareado | `bg-accent` + `text-accent-foreground` |
| Canvas | `--neutral-25` off-white | verde-escuro profundo | `bg-background` |
| Superfícies | `--surface-1..3` (card → popover) | elevação tonal invertida | `bg-surface-1..3` (tailwind.config, aceita `/alpha`) |
| Status | `danger` / `success` / `warning` / `info`, cada um com par `-soft` | fundos `-soft` escurecem, texto clareia | `bg-danger-soft text-danger-soft-foreground` |
| Sidebar | `--green-900` | `--green-950` | tokens `--sidebar-*` |

**Regra de contraste**: todo par `X`/`X-foreground` ≥ 4.5:1 (AA) nos dois temas
(primary é large-text, ≥ 3:1). `npm run contrast:check` valida os 26 pares;
par novo entra no script no mesmo PR.

**Cor literal é proibida** fora da allowlist: `npm run design:check` é um
ratchet — os offenders atuais estão congelados como baseline e **novos**
reprovam. Precisa de uma cor? Use token; não existe? Crie o token semântico
a partir de um degrau de rampa.

## Escalas

- **Tipografia**: `text-xs..3xl` mapeados a pares `--text-*`/`--leading-*`
  (12/16 → 32/40). Body é `text-base` (14/20). Numerais tabulares: `.tabular-nums`.
- **Radius**: `--radius-sm` badges/inputs internos · `md` buttons/inputs ·
  `lg` cards/dialog · `xl` modais · `2xl` heros · `full` badges pill.
- **Sombras**: `--shadow-xs..xl` (tom frio) + glows `--shadow-brand/accent`
  (com moderação). Dark usa sombras pretas mais fortes.
- **Motion**: `--duration-micro/fast/base/slow` (120–320ms) + `--ease-out`,
  `--ease-out-expo`. `prefers-reduced-motion` zera tudo globalmente.
- **Z-index**: escala semântica `--z-dropdown < sticky < fixed <
  modal-backdrop < modal < popover < tooltip < toast`. Valor cru (`z-[1000]`)
  em camada global reprova na guarda; empilhamento local isento declara razão
  em `z-index-camadas.test.ts`.

## Specs de estado (transversais)

- **Foco**: outline global 2px `--ring` + offset 2px, via `:focus-visible` —
  não deforma o controle nem empilha com `ring-*` de componente. Componente
  que usa `ring-*` próprio remove o outline (`focus-visible:outline-none`).
- **Hover**: nunca só cor de texto — sempre mudança de fundo ou borda.
- **Disabled**: `opacity-50` + `cursor-not-allowed`, sem mudar a cor base.
- **Density**: `data-density="compact"` no `<html>` reduz `--density-pad-*`
  e `--density-row-h`; componentes de dados usam esses tokens.

## Do / Don't

| ✔ Do | ✘ Don't |
|---|---|
| `bg-danger-soft text-danger-soft-foreground` para chip de status | `bg-red-100 text-red-700` (cor literal — ratchet reprova) |
| Criar token semântico apontando para degrau de rampa | Usar `var(--green-300)` direto num componente |
| `z-modal`, `z-toast` (classes da escala) | `z-[1400]` em camada global |
| Declarar token quando o consumidor existe | Declarar token "para o futuro" (guarda de token morto reprova) |
| Redefinir token semântico no bloco dark | Criar variante `--x-dark` nova |
| `npx vitest run __tests__/tokens-mortos.test.ts` antes de mexer em tokens | Editar globals.css e "conferir no olho" |

## Como estender

1. **Cor nova**: degrau de rampa primitiva → token semântico em `:root` **e** no
   bloco dark → mapeamento em `tailwind.config.ts` → par no `contrast-check.mjs`.
2. **Componente novo**: tokens `--<comp>-*` na camada de componente, consumidos
   no mesmo PR; radius/shadow/motion sempre via token.
3. **Utility nova**: só se o Tailwind não gerar equivalente (conferir o
   `tailwind.config.ts` antes — `.bg-surface-*` já caiu nessa duplicação uma vez).
