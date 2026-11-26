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

1. **Primitiva** — rampas HSL completas (`--laranja-*`, `--marinho-*`, `--neutral-*`,
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

Identidade desde 2026-11-06: o laranja do logo Aprimora como marca e o
marinho do wordmark na lateral, sobre neutros frios. (Antes: verde-petróleo +
âmbar.)

| Papel | Light | Dark | Classe |
|---|---|---|---|
| Marca | laranja queimado `--laranja-600` (#C64410, texto branco 4.96:1) | `--laranja-400` (clareia; texto escuro) | `bg-brand`, `text-brand` |
| Acento | laranja vivo `--laranja-500` (#F66628) — CTA da lateral, item ativo; texto escuro | `--laranja-400` | `bg-accent` + `text-accent-foreground` |
| Assinatura do produto | laranja do logo `--assinatura` (só borda/detalhe) + `--assinatura-texto` (texto, AA) | texto clareia | `border-assinatura`, `text-assinatura-texto` — fixa, o tema do município não a sobrescreve; só no rodapé (login, telas internas, portal do cidadão, validação) e no admin de plataforma, via `components/AssinaturaAprimora.tsx` |
| Títulos de página | `--titulo` (= texto) e `--titulo-destaque` (= marca) | idem | `text-titulo` no `PageHeader`; `text-titulo-destaque` na trilha do módulo (`TrilhaDoModulo`). O município troca os dois por `cor_titulos`, e a fonte deles por `fonte_titulos` (lista fechada em `lib/tema-cores.ts::FONTES`) |
| Canvas | `--neutral-25` off-white frio | marinho profundo | `bg-background` |
| Superfícies | `--surface-1..3` (card → popover) | elevação tonal invertida | `bg-surface-1..3` (tailwind.config, aceita `/alpha`) |
| Status | `danger` / `success` / `warning` / `info`, cada um com par `-soft` | fundos `-soft` escurecem, texto clareia | `bg-danger-soft text-danger-soft-foreground` |
| Sidebar | marinho `--marinho-900` (#121C40) | `--marinho-950` | tokens `--sidebar-*` |

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
- **Density**: uma só, a confortável — `--density-*` é a régua de espaço
  (main, cards, linhas de tabela, inputs). O modo compacto saiu em 2026-11-06.

## Padrão de tela (desde 2026-11-10)

Toda tela interna segue o mesmo esqueleto. Quem abre uma tela nova copia
daqui; quem acha uma tela fora dele, conserta.

1. **Cabeçalho = `PageHeader`**, sempre com `icon` (o mesmo do menu/hub),
   `title` em português de gente e `description` de uma frase. Nada de `<h1>`
   solto, nem título laranja: o título é `text-titulo` (o laranja fica na
   trilha e nas ações). Botões da tela vão em `actions`.
2. **Ação de criar** = `Button` primário com `<Plus />` e o nome da coisa, no
   gênero certo: "Nova cidade", "Novo fornecedor" — nunca "Novo" seco.
   Cadastro feito com `CrudPage` passa `icon`, `description` e `novoLabel`.
3. **Ações da linha = `AcoesDaLinha`** (`components/ui/acoes-da-linha.tsx`):
   até 2 botões discretos à vista, o resto no ⋯ "Mais ações", a destrutiva
   (`perigo`) sempre por último e em `danger-outline` — vermelho cheio só no
   botão que CONFIRMA, dentro do diálogo. A coluna nunca quebra em duas linhas.
4. **Números = `KpiCard`** (rótulo, valor, ícone, `intent`). Sem caixa crua
   com número, sem número centralizado colorido, sem enfeite de bolinha.
5. **Filtros = `FilterBar`** acima da tabela, com "Limpar" quando há filtro.
6. **Vazio = `EmptyState`** com ícone, uma frase do que é e, se couber, a
   ação de criar. Texto solto ("Nenhum registro") não.
7. **Valores formatados**: dinheiro `R$ 1.234,56`, data `dd/mm/aaaa`,
   enum por rótulo ("Transporte escolar", não `transporte_escolar`).
8. **Status = `Badge`** com `intent` semântico (success/warning/danger/info/
   neutral). A mesma situação tem a mesma cor em todas as telas.
9. **Links dentro de tabela** (número do processo, placa) em `text-primary`
   com sublinhado no hover — não azul, não vermelho.
10. **Gráfico** pega cor de `lib/chart-theme.ts` (`SERIES`, `GRAFICO`), nunca
    hex. O tema escuro vem de graça.

## Padrão de formulário (desde 2026-11-10)

Formulário bom é o que a pessoa preenche sem precisar perguntar nada.

1. **Campo = `FormField`** (`components/ui/form-field.tsx`): rótulo, controle,
   dica e erro com a fiação ARIA pronta. Nada de `<Label>` + `<Input>` +
   `<p>` montados à mão.
2. **Rótulo curto e de gente** ("Valor total", não "Valor total (R$)"). A
   unidade vai no campo, com `CampoComUnidade` (`prefixo="R$"`,
   `sufixo="km"`). O placeholder é EXEMPLO ("Ex.: OF-123/2026"), nunca o
   rótulo repetido nem a instrução.
3. **Obrigatório = asterisco** (`required`). Num grupo de obrigatórios, o
   campo que não é ganha `opcional`. A dica diz o formato ou para que serve,
   numa linha.
4. **Erro só depois da tentativa**: ao sair do campo ou ao enviar, nunca ao
   abrir a tela. A mensagem diz como consertar ("Use o formato
   000.000.000-00"), não só que está errado. Ao enviar com erro: foco no
   primeiro inválido (`focarPrimeiroInvalido`) e, se forem vários, um resumo
   no topo com link para cada um.
5. **Uma coluna**, lida de cima para baixo. Duas (`GradeCampos`) só para
   pares que andam juntos: cidade + UF, início + fim, quantidade + unidade.
6. **Poucas opções à vista**: 2 a 4 opções → `EscolhaSegmentada` (todas
   nomeadas, com a consequência da escolha embaixo), não `<select>`. Lista
   longa ou que cresce → `Combobox` com busca. Ligar/desligar → checkbox.
7. **Formulário longo = etapas**: `SectionCard` com `step` e `id`, na
   ordem em que a pessoa pensa (quem → o quê → detalhes). Com 3 etapas ou
   mais, `LayoutFormulario` + `RoteiroFormulario` ao lado: o que já está
   feito ✓ e o que falta, cada item levando ao campo.
8. **Ações em `BarraAcoesFormulario`** (fixa embaixo): Cancelar (ghost) →
   secundária ("Salvar como rascunho") → principal com o VERBO do
   formulário ("Abrir processo", "Criar solicitação"; "Salvar" só em
   edição). À esquerda, o status: o que falta (`resumoDoQueFalta`) ou
   "rascunho salvo".
9. **Botão principal nunca desabilitado por validação**: clicar é o que
   mostra o que falta. Desabilitado só enquanto envia (`loading`).
10. **Diálogo** para cadastro curto (≤ 8 campos, `CrudPage`); página
    própria para o resto. Título do diálogo diz o que se edita ("Editar
    cidade").

## Do / Don't

| ✔ Do | ✘ Don't |
|---|---|
| `bg-danger-soft text-danger-soft-foreground` para chip de status | `bg-red-100 text-red-700` (cor literal — ratchet reprova) |
| Criar token semântico apontando para degrau de rampa | Usar `var(--laranja-300)` direto num componente |
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
