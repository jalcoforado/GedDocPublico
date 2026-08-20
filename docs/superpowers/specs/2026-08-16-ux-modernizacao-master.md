# UX-00 — Auditoria visual/UX e especificação da modernização (master)

> **Status**: diagnóstico + especificação. NADA aqui foi implementado. Autorização humana
> necessária antes de qualquer fatia.
>
> **Nota de nomenclatura**: as specs deste diretório usam sufixos `-design`/`-escopo`
> (ex.: `2026-07-17-design-system-v3-design.md`). Este arquivo usa `-master` porque não é a
> spec de uma fatia, e sim o documento-guarda-chuva que as fatias UX-01+ referenciarão;
> cada fatia autorizada ganhará sua própria spec `-design`/`-escopo` no padrão da casa.
>
> **Método**: auditoria por inspeção direta do código (3 varreduras paralelas: shell/navegação,
> páginas por módulo, consistência quantitativa + testes), calibrada pelo checklist da skill
> `ui-ux-pro-max`. Toda afirmação tem evidência `arquivo:linha`. Números de linha refletem o
> working tree em `f8f8b49` (2026-08-16).

---

## 1. Estado atual

**A tese central da auditoria: o problema do GEDPublica não é ausência de design system — é
adoção desigual do design system que já existe, e um app shell que ficou fora dele.**

- O **DS v3 "Institucional Refinado"** (spec `2026-07-17-design-system-v3-design.md`) está
  implementado em `frontend/app/globals.css` (590 linhas): três camadas reais
  (primitivos HSL → semânticos → tokens de componente), verde-petróleo + âmbar, dark mode
  dessaturado estilo Material 3 (não invertido), density, motion tokens, escala de espaço/radius/
  sombra/tipografia com line-heights pareados. `tailwind.config.ts` expõe tudo
  (`rounded-button`, `shadow-card-hover`, `duration-fast`…). **Isto é raro e valioso.**
- **22 componentes em `components/ui/`** com 779 imports pelo app. O miolo CRUD dos módulos
  (transporte 147, pagamentos 120, protocolo 118, frota 100 imports) consome o DS.
- **Mas**: 100 páginas, das quais **52 sem `PageHeader`**; **134 classes de cor crua + 48 hex
  literais** fora de `ui/` (o próprio `tailwind.config.ts:24-28` admite o débito em comentário);
  **78 `<button>` crus**, **33 inputs crus**, **3 modais artesanais sem nenhuma semântica ARIA**;
  e o **app shell inteiro (Sidebar, Header, dropdowns, palette) tem zero imports de `ui/`** —
  o componente mais visível do produto é 100% artesanal.
- **Dois itens de governança da spec DS v3 nunca nasceram**: `docs/design-system.md` não existe
  e o validador `design:check` não está no `package.json`. Sem guarda, o débito de cor crua só
  cresce (o módulo transporte, o mais novo em partes, concentra ~57% das violações).
- **Testes**: 53 arquivos vitest, mas só 5 tocam `ui/` (e o Dialog tem 1 caso). Zero visual
  regression, zero axe, zero teste de dark mode/density/teclado-de-modal. E2E Playwright existe
  (10 specs) mas 7 são API-only, viewport único 1280×720.

**Onde o produto está hoje, em uma frase por lente**: identidade sólida mas aplicada pela metade;
shell funcional porém com defeitos de camada (z-index do drawer) e a11y; navegação sem título de
página nem breadcrumb garantidos; dashboard denso sem priorização e com dois padrões de gráfico;
tabelas remontadas 6× com subconjuntos diferentes de recursos; formulários sem erro por campo;
feedback textual ("Carregando…" ×66) onde deveria haver skeleton; a11y com bom piso global
(focus ring, reduced-motion) e teto baixo nos widgets; mobile sem busca e com popovers estourando
a viewport; performance percebida prejudicada por skeletons que não espelham o layout; e
produtividade com Ctrl+K presente porém raso (busca `includes()`, sem ranking, sem recentes).

## 2. Pontos fortes que DEVEM ser preservados

1. **A arquitetura de tokens em 3 camadas** (`globals.css:29-386`) e o contrato Tailwind
   (`tailwind.config.ts`). Evoluir, nunca substituir. Não criar segundo DS.
2. **`THEME_INIT_SCRIPT`** (`lib/theme.tsx:124-136`, injetado em `app/layout.tsx:34`): zero FOUC
   de tema E densidade, `color-scheme` correto. Padrão a estender (o colapso da sidebar não tem
   equivalente — ver 5.3).
3. **`prefers-reduced-motion` global** (`globals.css:432-441`) e **anel de foco global de duplo
   contorno** (`globals.css:403-407`) — piso de a11y herdado de graça (com uma colisão a corrigir,
   ver §4.7).
4. **`lib/menus/` como fonte única** de Sidebar + CommandPalette com `canSeeItem` compartilhado —
   elimina a classe de bug "aparece num lugar e some no outro". Guardado por `menus.test.tsx`.
5. **`ui/dialog.tsx`**: focus trap correto, ESC, scroll lock, restauração de foco
   (`dialog.tsx:42-82`). O shell deve passar a USÁ-LO, não reinventá-lo.
6. **`ui/combobox.tsx`**: o padrão ARIA combobox mais completo do repo (`:243-332`) — referência
   para consertar o CommandPalette.
7. **Launcher como porta, não pedágio** (`modulos/page.tsx:42-50` auto-redirect com 1 módulo;
   `ModuloSwitcher.tsx:106-109` navega direto) — decisão de produto implementada com rigor.
8. **Estados de erro visíveis e recuperáveis** no `ModuloSwitcher.tsx:65-85` /
   `SidebarModuloHeader.tsx:51-71` — distinção "deu erro" vs "só tem 1 módulo".
9. **Confirmação destrutiva nomeando o registro e a consequência** (`usuarios/page.tsx:217`,
   `veiculos/page.tsx:285`, `AnexosProcesso.tsx:163`) via `ui/confirm.tsx` promise-based.
10. **Empty states duplos** (vazio-de-verdade convida a criar; busca-sem-resultado não) em
    `m/transporte/recadastramento/page.tsx:249-267` — melhor exemplo do repo, com racional escrito.
11. **Estado 403 acionável** nomeando a permissão exata (`dashboard/page.tsx:151-170`).
12. **Tab persistida na URL sem scroll jump** (`processos/[id]/page.tsx:229-237`).
13. **Mobile-first do portal cidadão** (`cidadao/layout.tsx:117-159`): bottom nav com
    `aria-current`, safe areas, `min-h-dvh`.
14. **Resposta neutra da validação pública** (`validar/[codigo]/page.tsx:88-101`): inexistente,
    revogado e sigiloso respondem igual — privacidade por design, preservar byte a byte.
15. **Guardas estruturais de navegação** (`rotas-modulo.test.ts`: página órfã, 308, regex nginx).
16. **Higiene de dataviz do dashboard de pagamentos** (`m/pagamentos/dashboard/page.tsx:98-190`):
    tooltip tokenizado, Legend, valores listados como alternativa textual — é o padrão a extrair.
17. **Comentários de decisão de produto no código** (`processos/[id]/page.tsx:609-615`,
    `recadastramento/page.tsx:100-103`) — prática rara; manter.

## 3. Problemas encontrados (com evidência)

Classificação: categoria **A** foundation / **B** shell-navegação / **C** componente compartilhado /
**D** página-fluxo / **E** acessibilidade / **F** perf percebida / **G** produtividade.
Impacto: **P0** bloqueia qualidade mínima / **P1** alto impacto / **P2** refinamento importante /
**P3** nice-to-have.

### P0 — bloqueiam qualidade mínima

| # | Cat | Achado | Evidência |
|---|-----|--------|-----------|
| P0-1 | B/E | Drawer mobile: overlay `z-30` fica ABAIXO do header `z-30` (ordem DOM decide); com o drawer aberto o Header segue clicável por cima do "modal" | `Sidebar.tsx:159,167`, `Header.tsx:20`, `(app)/layout.tsx:31-33` |
| P0-2 | D | **CrudPage não pagina**: `fetchList` aceita `{items,total}` e o total é descartado — 12 telas de cadastro mostram só a primeira página sem indicar que há mais | `CrudPage.tsx:46,150-152` |
| P0-3 | D | `m/transporte/alvaras/[id]` quebra dark mode: 4× `bg-white` + ~20 `text-gray-*` hardcoded (44 cores literais no arquivo — o pior do repo) | `alvaras/[id]/page.tsx:156,190,220,236,160-215` |
| P0-4 | E | 3 modais artesanais `fixed inset-0` sem `role="dialog"`, sem focus trap, sem ESC | `AnexoDesentranhar.tsx:100`, `ProcessoApensados.tsx:397`, `ProcessoVolumes.tsx:260` |

### P1 — alto impacto (seleção; lista completa nos §§4-10)

| # | Cat | Achado | Evidência |
|---|-----|--------|-----------|
| P1-1 | B | Sem busca nenhuma abaixo de 768px: BuscaGlobal é `hidden md:block` e não há ícone de lupa; Ctrl+K não existe em touch | `Header.tsx:51-54` |
| P1-2 | B | Sem título de página garantido: 52/100 páginas sem `PageHeader`; `document.title` estático — todas as abas se chamam igual | `page-header.tsx` (48 usos), `layout.tsx:25-28`, `branding.tsx:22-24` |
| P1-3 | E | Sem skip link no repo inteiro; dezenas de links de sidebar antes do `<main>` sem `id` | grep vazio; `(app)/layout.tsx:34` |
| P1-4 | E | Drawer mobile não é dialog: sem `aria-modal`, sem trap, sem mover foco, sem ESC, nav fechado tabulável fora da tela | `Sidebar.tsx:141-171` |
| P1-5 | B/F | Colapso da sidebar hidrata pós-paint: layout shift de 256px em todo hard reload para quem usa colapsada (o tema tem anti-FOUC; a sidebar não) | `Sidebar.tsx:71,84-88` |
| P1-6 | E | CommandPalette sem padrão combobox (`aria-activedescendant`, `aria-expanded`), sem focus trap, sem scroll lock, `<button role="option">` inválido | `CommandPalette.tsx:319-389` |
| P1-7 | E | NotificacoesBell: `role="dialog"` sem nada de dialog (sem trap, sem ESC, sem foco); e `w-[360px]` fixo estoura viewport <400px | `NotificacoesBell.tsx:43-52,66,83-86` |
| P1-8 | C | Foco de TODO Dialog abre no botão "X Fechar" (o `dialogRef` envolve o header, e o X é o primeiro focável) — afeta CrudPage, veículos, usuários, anexos | `ui/dialog.tsx:48,92-107` |
| P1-9 | D | `m/frota/veiculos`: sem busca, sem filtro, sem paginação — `listAll()` renderiza a frota inteira; e form de 16 campos com zero validação client-side | `veiculos/page.tsx:107,179-200,319-490` |
| P1-10 | D | Lista de processos: filtros e página só em `useState` — voltar/recarregar/compartilhar perde tudo; o `?id_unidade=` linkado da home é ignorado | `processos/page.tsx:33-37`, `home/page.tsx:456` |
| P1-11 | D | Home: se as 4 queries falharem, a tela afirma "Sem pendências críticas. Bom trabalho." — falso negativo em superfície de decisão | `home/page.tsx:124-128,274` |
| P1-12 | D | Dashboard: 19 KPIs com o mesmo peso visual, tooltips recharts default (caixa branca no dark), grid `#e5e7eb` fixo, mesma métrica em 2 cores sem semântica | `dashboard/page.tsx:296-504,529-655` |
| P1-13 | A | Densidade só afeta tabelas: `--density-*` é consumido apenas por `table.tsx` — o controle "Modo compacto" quase não muda a tela | `globals.css:377-386`, `table.tsx:59,87,133` |
| P1-14 | D | Branding do tenant: `cor_primaria` concatenada com `"dd"` assume hex (formato errado = hero ilegível); `--brand-primary` é injetado e **nenhum arquivo consome** — dentro do app o tenant não tem cor | `login/page.tsx:66`, `lib/branding.tsx:19` |
| P1-15 | C | CrudPage: busca sem debounce (1 request/tecla), título `<h1>` artesanal, erro único no fim do grid sem `aria-describedby` nem foco | `CrudPage.tsx:89-91,157,324-331` |
| P1-16 | D | `app/validar` (a superfície que auditor/advogado externo vê primeiro) não importa um único componente do DS | `validar/page.tsx:29-48` |
| P1-17 | E | Login: erro não recebe foco, inputs sem `aria-invalid`, mensagem crua da API; e não há "Esqueci minha senha" (link comentado) | `login/page.tsx:51,201-222` |
| P1-18 | D | Portal cidadão: tabela de 6 colunas em superfície majoritariamente mobile, único fallback é scroll horizontal | `cidadao/processos/page.tsx:54-113` |
| P1-19 | F | Dashboard pagamentos: erro de página inteira vira toast efêmero + bloco sem "Tentar novamente" | `m/pagamentos/dashboard/page.tsx:206-237` |
| P1-20 | C | AnexosProcesso: `text-gray-*` (3×), input de arquivo com classe de marca legada `file:bg-aprimora`, sem progresso de upload, 6 botões por linha | `AnexosProcesso.tsx:74-171,276,293` |

### P2/P3 — inventário resumido (detalhe nos §§4-10)

- **Shell**: conteúdo sem `max-width` (cada página inventa a sua — 5 valores diferentes);
  5 alturas de controle diferentes na mesma linha do header; 5 dropdowns artesanais com 5
  mecânicas; larguras fixas de popover sem clamp; breakpoint `lg` deixa tablets em drawer
  permanente; `pt-safe` morto sem `viewport-fit=cover`; grupos da sidebar piscam
  fechado→aberto; item ativo por `startsWith` acende múltiplos; em colapsado o item pai vira
  link para o primeiro filho silenciosamente e os grupos somem sem tooltip.
- **Navegação**: três lugares para tema/densidade com três semânticas ARIA; AvatarDropdown
  aponta para `/auditoria` legada e `/perfil` genérico; `/` sempre redireciona a `/login`
  mesmo autenticado; launcher visualmente pobre (só ícone+nome, sem descrição/badge);
  login sem memória do último módulo.
- **Componentes**: Button sem estado `loading`; Input/Select sem estado de erro
  (`aria-invalid`); `aria-sort` no `<button>` e não no `<th>`; TR clicável sem teclado; Toast
  `polite` para erro e sem pausa no hover; Combobox com "limpar" `tabIndex={-1}`;
  actions-menu sem devolver foco no ESC e sem portal (clipping); confirm sem estado async;
  CardTitle `<h2>` fixo; skeleton anuncia "Carregando" N vezes.
- **Faltam no DS** (tudo reimplementado à mão em página): `Alert/Banner` (6 variantes manuais),
  `Tabs`, `Pagination` (4 implementações), `Tooltip` acessível, `FormField` (label+erro+hint),
  `Drawer/Sheet`, `Spinner`, `Popover` posicionado, `Switch`, `RadioGroup`, `DataTable/ListPage`.
- **Páginas**: dashboard com skeleton que promete 12 KPIs e entrega 19 (salto de layout);
  ranking em `<table>` cru de 9 colunas com siglas não explicadas; detalhe de processo com
  tabs sem `tabpanel`/`aria-controls`; timeline artesanal sem agrupamento nem paginação;
  hub de frota sem números (só navegação) duplicado byte-a-byte no de transporte; usuários sem
  EmptyState e com loading `<TR>` textual; datas ISO cruas no transporte; IDs internos expostos
  ("ID: 42", "unidade #12"); card "Veículos Vinculados" permanentemente vazio.
- **Tokens** (16 incoerências catalogadas): `--z-*` (9 tokens) mortos enquanto o app usa
  `z-[1000]` cru (combobox por cima de modal por acidente); `--motion-fast` 120ms ≠
  `--duration-fast` 180ms (dois "fast"); `--space-*` declarado 2×; `--font-weight-*`/
  `--tracking-*` mortos; `--accent-foreground` branco sobre âmbar claro no dark ≈ 2.1:1
  (reprova AA); `--info` não redefinido no dark; aliases `--aprimora*` com 33 usos vivos;
  `.workflow-editor` fora de `@layer`; utilitários `.bg-surface-*` duplicando o config.

## 4. Inconsistências do Design System

1. **Zona morta do shell**: `Sidebar`, `Header`, `AvatarDropdown`, `ModuloSwitcher`,
   `NotificacoesBell`, `BuscaGlobal`, `CommandPalette`, `ThemeToggle`, `DensityToggle`,
   `(launcher)/*`, `validar/page.tsx`, `organograma/*` — zero imports de `ui/`.
2. **Dois idiomas de "escolher opção"**: `ui/select.tsx` nativo cru vs `ui/combobox.tsx`
   custom com portal — visuais divergentes no mesmo form.
3. **Duas gerações de nomenclatura**: `text-muted-foreground` (shadcn) em `NotificacoesBell`
   vs `text-foreground-muted` no resto; `bg-primary/5` vs `bg-brand/10` para o mesmo conceito.
4. **Três overlays, dois valores**: `bg-black/50` (Sidebar, dialog) vs `bg-foreground/30`
   (palette).
5. **Âmbar cravado em RGB** no LoadingBar (`shadow-[0_0_8px_rgba(217,119,6,0.5)]`,
   `LoadingBar.tsx:99`) com o token equivalente existindo (`globals.css:55`).
6. **recharts/xyflow com hex crus** (48 ocorrências) — gráficos e diagramas de workflow não
   trocam de cor no dark mode. Falta um `chart-theme.ts` lendo `hsl(var(--…))`.
7. **Colisão do anel de foco**: o `:focus-visible` global (`globals.css:403-407`) aplica
   box-shadow E `border-radius: var(--radius-md)` em tudo — empilha com o `ring-2` dos
   componentes e deforma `rounded-full` no foco.
8. **7.1 do shell**: h-9/h-10/h-11 na mesma linha do header.
9. **Skeleton × density**: `SkeletonRow` com `px-3 py-3` fixo enquanto `TD` usa
   `var(--density-pad-*)` — alturas divergem em modo compacto (salto ao carregar).
10. **Governança inexistente**: sem `docs/design-system.md`, sem `design:check`, sem regra de
    lint — nada impede o próximo `bg-gray-100`.

## 5. Problemas do App Shell

(Consolidado; evidências no §3.) Os cinco estruturais: **(a)** camadas z-index sem escala
(P0-1; tokens `--z-*` existem e são ignorados); **(b)** drawer/dropdowns/popovers artesanais
sem reutilizar o focus trap do `ui/dialog.tsx` (P1-4/6/7, §3-P2); **(c)** ausência de contrato
de largura do conteúdo (`(app)/layout.tsx:34` sem `max-w`, contra `(plataforma)/layout.tsx:15`
com `max-w-6xl` — dois shells, duas regras); **(d)** anti-FOUC só para tema, não para colapso/
grupos da sidebar (P1-5); **(e)** shell da plataforma é um segundo mini-DS (header próprio,
"Aprimora" hardcoded, sem tema/busca/notificações — trocar de app ao ir para `/admin/tenants`).
Somam-se: mobile sem busca (P1-1), tablets 768-1024 sem menu persistente, dois `QueryClient`
irmãos refazendo `modulos-me` a cada travessia app↔launcher (`providers` em `(app)/layout.tsx:46`
e `(launcher)/layout.tsx:88`), loading do shell como texto cru em vez de skeleton.

## 6. Problemas das páginas

(Consolidado por superfície; evidências no §3.)

- **Dashboard executivo**: sem priorização (19 KPIs iguais), dois padrões de gráfico
  concorrentes no produto (o de pagamentos é o correto), tooltips nativos `title=` para os
  conceitos mais difíceis, `<select>` e exports artesanais, skeleton mentiroso, filtros
  instantâneos aqui vs "Filtrar" explícito em processos (dois modelos mentais).
- **Home**: falso negativo de erro (P1-11), `ActionCard` duplicando `kpi-card` com mapa de
  intents paralelo, dois "heroes" concorrentes, ID interno exposto, copy prometendo
  personalização inexistente.
- **Processos**: a melhor dupla lista+detalhe do app; falta estado na URL (P1-10), ordenação
  (o `TH sortable` existe e nenhuma listagem usa), ARIA de tabs pela metade, timeline
  artesanal, anexos com 6 botões/linha e cores cruas.
- **CRUD admin**: CrudPage multiplica defeitos por 12 telas (P0-2, P1-15); usuários (fora do
  CrudPage) sem EmptyState/skeleton; modais "Novo"/"Editar" sem nome da entidade.
- **Pagamentos**: melhor dataviz; erro sem retry (P1-19), linha clicável sem teclado, KPIs
  clicáveis indistinguíveis dos não-clicáveis, truncamento agressivo dependente de hover.
- **Frota**: hub sem informação (8 cards sem números); veículos P1-9; badge colapsando 5
  estados em 2.
- **Transporte**: o contraste do repo — recadastramento tem o melhor form/empty-state do app,
  e alvarás tem o pior arquivo do app (P0-3); relatorio/alvaras somam 33 cores literais;
  datas ISO cruas; a11y do módulo: 9 `aria-`, 0 `focus-visible`.
- **Público**: validar fora do DS (P1-16); cidadão com tabela em mobile (P1-18), rota
  `servicos/` inalcançável por navegação, "Sair" na bottom nav sem confirmação.

## 7. Acessibilidade

Piso bom (focus ring global, reduced-motion global, dialog e combobox de referência), teto
baixo. Consolidado: sem skip link (P1-3); landmarks colidindo (dois `<header>` — shell e
PageHeader); drawer/palette/sino sem padrão de dialog (P1-4/6/7); menus `role="menu"` sem
teclado de menu (AvatarDropdown, ModuloSwitcher); `aria-pressed` num grupo que é radiogroup
(ThemeToggle) vs `menuitemradio` correto no AvatarDropdown — duas semânticas para o mesmo
controle; ícone-só sem nome acessível na sidebar colapsada; `aria-sort` no elemento errado;
TR clicável sem foco; toasts de erro `polite` sem pausa; gráficos sem alternativa textual
(exceto pagamentos); tabs sem `tabpanel`; erro de form sem `aria-describedby`/foco; 3 modais
sem ARIA nenhuma (P0-4); `sr-only` usado 5× no repo inteiro. **Zero automação axe.**

## 8. Responsividade

Mobile: sem busca (P1-1), popovers com largura fixa estourando <400px (P1-7), palette com
`pt-[10vh]` + teclado virtual = 2 itens visíveis, grid 2 colunas fixo no form do CrudPage,
tabela do cidadão sem fallback de cards (única tela onde é obrigatório — e o repo tem
exatamente 1 fallback tabela→card em todo o app). Tablet 768-1024: drawer permanente com
espaço de sobra para sidebar colapsada; login sem hero (nem desktop nem mobile). Desktop
largo: conteúdo sem max-width estica infinito; launcher `max-w-3xl` + `md:grid-cols-3`
desalinha com 5-6 módulos. `h-dvh + overflow-hidden` no shell quebra auto-hide da barra do
Safari e pull-to-refresh. Alvos de toque: ThemeToggle 28px, fechar-drawer 32px (mobile-only!).

## 9. Perceived performance

- "Carregando…" textual ×66 vs `SkeletonRow` em 5 páginas + CrudPage — o skeleton existe e
  não é usado; onde é, às vezes mente (dashboard: 12 prometidos, 19 entregues) ou diverge da
  densidade (SkeletonRow fixo).
- Layout shifts estruturais: colapso da sidebar pós-hidratação (P1-5), grupos piscando,
  `unidadeNome` resolvendo "—"→nome linha a linha (`veiculos/page.tsx:113-114`).
- Refetch sem indicação: dashboard `refetchInterval: 60s` muda números sem "atualizado há X";
  dois QueryClients refazem `modulos-me` a cada travessia; palette sem `staleTime` (1 request
  por tecla, sem cache).
- Nenhuma mutação otimista; toda ação invalida a query inteira do processo.
- Transição de página existe (`animate-page-in` 220ms) — adequada, manter.

## 10. Produtividade (usuários intensivos)

- **Ctrl+K existe mas é raso**: busca `includes()` da query inteira (sem tolerância a ordem/
  acento), sem ranking (resultados remotos sempre antes do comando exato), sem recentes/
  histórico, sem highlight do match, sem Ctrl+Enter para nova aba, resultados navegando para
  listas genéricas em vez do registro (`CommandPalette.tsx:210,219,226-244`).
- **Enter não submete filtros** (não há `<form>` na lista de processos); busca do CrudPage
  dispara por tecla sem debounce.
- **Sem estado na URL** = sem back/forward/bookmark de filtros (P1-10) — o custo diário mais
  alto para operador de protocolo.
- **Ordenação de tabela**: suportada pelo DS, usada em zero listagens.
- **Paginação sem page-size nem "ir para"**; CrudPage sem paginação nenhuma.
- **Densidade prometida e não entregue** (P1-13) — usuários intensivos são exatamente quem
  ativa modo compacto.
- **Preferências espalhadas** em 3 UIs sem tela canônica; sem memória do último módulo no login.
- Atalhos além de Ctrl+K: inexistentes (sem `?` de ajuda, sem `g p` de navegação, sem j/k em
  listas). Não recomendo investir nisso antes do básico (URL, Enter, ordenação) — ver backlog.

## 11. Tecnologias adicionais avaliadas

Regra aplicada: dependência só com problema concreto que o código atual não resolve bem.

| Tecnologia | Veredito | Justificativa |
|---|---|---|
| **Floating UI** (`@floating-ui/react-dom`, ~5KB) | **Única candidata recomendada** (na UX-02, decisão explícita do Jorge) | Problema concreto: 5 popovers artesanais com posição fixa sem colisão de viewport (`ModuloSwitcher.tsx:146`, `AvatarDropdown.tsx:110`, `NotificacoesBell.tsx:86` estourando <400px, actions-menu com clipping em `overflow-hidden`, combobox com flip manual de ~30 linhas). Benefício: posicionamento+colisão+flip corretos num primitivo `ui/popover.tsx`. Custo: 1 dep pequena, sem CSS próprio. Risco: baixo (biblioteca de cálculo, não de render). **Alternativa sem dep**: manter flip manual do combobox e adicionar `max-w-[calc(100vw-2rem)]` + detecção de borda à mão em cada popover — funciona, mas é a 6ª reimplementação do mesmo cálculo. |
| **Radix primitives** | **Não agora** | O repo já tem dialog com trap correto, combobox ARIA-completo e actions-menu com roving tabindex. Adotar Radix agora = reescrever 3 componentes bons e introduzir um segundo idioma de componente (exatamente o que o princípio central proíbe). Reavaliar apenas se, após UX-02, os gaps de teclado restantes se mostrarem caros de manter à mão. |
| **Motion (framer-motion)** | **Não** | As animações necessárias (fade/scale/slide 150-300ms) já existem como tokens+keyframes CSS (`tailwind.config.ts:166-204`) com reduced-motion global. Nenhum requisito de gesto/spring/layout-animation identificado. |
| **cmdk** | **Não** | O problema do palette é lógica (ranking, normalização de acento, recentes) — código puro de ~100 linhas — e ARIA, cujo padrão de referência já existe no próprio `combobox.tsx`. |
| **TanStack Virtual** | **Adiar** | Virtualização só se justificaria na timeline de processos longos e na frota sem paginação; a correção certa é paginar/agrupar (UX-05/09). Reavaliar com dados reais de Sobral. |
| **axe-core / @axe-core/playwright / jest-axe** (devDependencies) | **Recomendada** (UX-13) | Problema concreto: zero automação de a11y num sistema público sujeito a acessibilidade legal (LBI). Dev-only, não entra no bundle. |
| **@tanstack/react-table** | **Não** | O `ui/table.tsx` + extração de um `DataTable` fino cobre ordenação/paginação dos casos reais. Headless table engine é peso sem demanda (sem colunas dinâmicas, sem agrupamento). |

**Resumo: nenhuma dependência de runtime obrigatória; 1 recomendada opt-in (Floating UI) e
axe em dev.**

## 12. Arquitetura visual alvo

Evolução do DS v3, não substituição:

1. **Uma única fonte de superfície**: todo pixel do app (shell incluso) consome tokens
   semânticos; cor crua permitida apenas em `chart-theme.ts` (allowlist explícita, como a
   spec DS v3 já previa).
2. **Shell como consumidor do DS**: Sidebar/Header/popovers construídos sobre os mesmos
   primitivos das páginas (`ui/popover`, `ui/dialog`, tokens `--z-*` adotados). Grid do shell
   com contrato: sidebar 256/68px, header 56px, conteúdo `max-w-7xl mx-auto` por padrão com
   opt-out por página (dashboards full-width).
3. **Camada de composição nova (a lacuna real)**: entre `ui/` e as páginas, componentes de
   *padrão de tela* — `ListPage/DataTable` (tabela+filtros+URL-state+skeleton+empty+paginação),
   `FormField`, `FormDialog`, `Alert`, `Tabs`, `Pagination`, `PageShell` (PageHeader
   obrigatório). É isso que elimina as 6 cópias divergentes de listagem — não mais telas
   artesanais sobre primitivos bons.
4. **Identidade**: manter verde-petróleo + âmbar (é distintiva e séria); o impacto visual novo
   vem de hierarquia (KPIs com prioridade, heroes contidos, page headers consistentes),
   profundidade disciplinada (escala de sombra já existe) e microinterações já tokenizadas —
   não de rebrand. Branding por tenant: decidir entre consumir `--brand-primary` de verdade
   (accent do tenant em pontos controlados) ou remover a injeção morta — hoje é promessa
   não cumprida.
5. **Dark mode como cidadão de primeira classe**: eliminar as 134+48 cores sem variante dark;
   consertar os 2 pares AA reprovados; gráficos tematizados.
6. **Título e lugar sempre**: `document.title` por rota + PageHeader/breadcrumb garantidos
   pelo `PageShell`, não opt-in.

## 13. Princípios visuais alvo

1. **Denso e sereno** (direção DS v3 mantida): informação alta, ruído baixo; espaçamento pela
   escala, nunca ad hoc.
2. **Hierarquia antes de decoração**: cada tela tem 1 elemento primário; KPI hero ≠ KPI de
   apoio; 1 CTA primário por superfície.
3. **Token ou nada**: cor, raio, sombra, z-index, duração — sempre via token; violação
   reprovada por guarda automatizada (não por revisão humana).
4. **Motion com causa**: entrada/saída/continuidade espacial apenas; 150-300ms; reduced-motion
   sagrado. Nada de ornamento.
5. **Estados completos por contrato**: toda listagem nasce com loading (skeleton fiel) +
   vazio (acionável, duplo quando há busca) + erro (com retry) — garantido pelo componente de
   composição, não pela disciplina de quem escreve a tela.
6. **Teclado é caminho principal**, não fallback: foco visível, ordem lógica, ESC/Enter
   consistentes, `sr-only` onde ícone é só.
7. **Seriedade pública**: neutralidade da validação, confirmação destrutiva com consequência,
   nada de dark patterns, contraste AA mínimo em ambos os temas.
8. **Mobile do cidadão ≠ desktop do servidor**: portal cidadão mobile-first (cards, bottom
   nav); app do servidor desktop-first com degradação honesta (drawer correto, busca presente,
   popovers clampados).

## 14. Estratégia de migração incremental

**Ordem determinada pela auditoria** (difere da sugestão do prompt — justificativa em cada
fase): primeiro guardas + fundação (senão o débito volta enquanto se migra), depois os
componentes de composição (eles são pré-requisito de shell e páginas), depois shell (maior
superfície visível), depois as classes de página em ordem de retorno/esforço (CrudPage
multiplica por 12; transporte é o pior estado), com a11y/testes transversais embutidos em
cada fatia e um hardening final.

Regras de execução (todas as fases):
- **Zero mudança funcional**: nenhuma alteração de API, rota, permissão ou regra de negócio.
  Redesign de componente preserva props públicas ou faz a migração de todos os call sites no
  mesmo PR.
- **Fatias pequenas**: cada fatia é um PR mergeável, verde em `tsc` + vitest, com rollback =
  revert do PR (nenhuma fatia tem migração de dado).
- **Verificação visual**: screenshots claro/escuro das telas-âncora afetadas em cada PR
  (processo já usado no DS v3); visual regression automatizado entra na UX-13 e passa a
  cobrir as fases seguintes.
- **Teste primeiro onde há contrato**: guarda estrutural (grep/AST) para regras "não pode
  voltar" (cor crua, página sem PageHeader, modal fora do Dialog), no espírito das guardas
  existentes do repo (`rotas-modulo.test.ts`).

## 15. Backlog UX priorizado (fases e fatias)

### UX-01 — Fundação: tokens, guardas e correções de base
*Por que primeiro: estanca o débito (guarda) e conserta colisões que afetariam toda fase
seguinte (foco, z-index, dark AA).*

- **Objetivo**: `globals.css` sem tokens mortos/duplicados; escala `--z-*` adotada; anel de
  foco sem colisão; pares AA do dark corrigidos; validador de tokens no CI; doc do DS.
- **Fatias**:
  - 1.1 Limpeza de tokens (remover `--motion-*`/`--space-*` duplicados, `--font-weight-*`/
    `--tracking-*`/`--z-*` mortos OU adotá-los — decisão por token, documentada), mover
    `.workflow-editor` para `@layer components`, deduplicar `.bg-surface-*`.
  - 1.2 Corrigir `:focus-visible` global (remover `border-radius` forçado; não empilhar com
    `ring-*` dos componentes) — `globals.css:403-407`.
  - 1.3 Adotar `--z-*`: mapear os 8 valores crus (`z-[1000]` etc.) para a escala; combobox
    deixa de vencer modal por acidente.
  - 1.4 Dark AA: redefinir `--accent-foreground` e `--info` no dark; verificar pares com o
    validador da skill dataviz.
  - 1.5 **Guarda `design:check`** (script + CI): reprova cor literal Tailwind/hex fora da
    allowlist (`chart-theme.ts`, quando existir) — realiza o item da spec DS v3 que nunca
    nasceu. Baseline: os 134+48 atuais entram como "known offenders" a queimar por fase (a
    guarda impede NOVOS, estilo ratchet).
  - 1.6 `docs/design-system.md` (paleta, escalas, specs de estado, do/don't) — curto, vivo.
- **Arquivos**: `globals.css`, `tailwind.config.ts`, `package.json` (script), CI workflow,
  novo teste de guarda.
- **Dependências**: nenhuma. **Risco**: baixo (1.2/1.3 têm efeito visual amplo → screenshots
  antes/depois das âncoras). **Resultado visual**: foco limpo, combobox/modal em ordem;
  invisível no resto. **Resultado UX**: nenhum direto; habilita tudo.
- **Aceite**: `design:check` no CI verde com baseline congelada; zero token morto (grep);
  contraste AA nos pares de status em ambos os temas; suíte vitest + tsc verdes.
- **Testes**: guarda ratchet nova; teste de contraste dos pares (script). **Screenshot**: sim
  (âncoras claro/escuro). **Rollback**: revert.

### UX-02 — Primitivos que faltam + correções dos existentes
*Por que agora: shell (UX-03) e páginas dependem destes componentes.*

- **Objetivo**: fechar as lacunas do `ui/` e os defeitos P1/P2 dos componentes existentes.
- **Fatias**:
  - 2.1 `Dialog`: foco inicial no primeiro campo (não no X — `dialog.tsx:48,92-107`),
    `aria-describedby`, mousedown-fora não fecha em drag.
  - 2.2 `Toast`: erro `assertive`/`role=alert`, pausa no hover/foco, limite de fila.
  - 2.3 `Button` com `loading` (spinner + `aria-busy` + bloqueio de duplo clique); `confirm`
    com estado async; `asChild` repassando ref.
  - 2.4 `Input`/`Select`/`Textarea` com estado de erro (`aria-invalid` + borda danger) +
    novo `FormField` (Label+controle+hint+erro com `aria-describedby` e foco no primeiro
    inválido).
  - 2.5 `Alert` (4 intents, substitui as 6 variantes manuais), `Tabs` (ARIA completo),
    `Pagination` (com page-size), `Spinner`.
  - 2.6 `Popover` base (decisão Floating UI vs manual — ver §11) e migração de
    actions-menu (portal + devolução de foco) e combobox (limpar focável) para ele.
  - 2.7 `Table`: `aria-sort` no `<th>`, TR clicável com `tabIndex`/Enter, `SkeletonRow`
    respeitando density.
- **Arquivos**: `components/ui/*` (7 novos, 8 retocados) + testes.
- **Dependências**: UX-01; decisão Floating UI. **Risco**: médio (Dialog/Toast têm muitos
  call sites — mudanças são aditivas ou de comportamento interno). **Resultado visual**:
  componentes com estados completos. **Resultado UX**: foco certo ao abrir modal, erros
  audíveis, loading verdadeiro em botões.
- **Aceite**: cada componente novo/retocado com teste de interação E teclado (vitest +
  user-event); zero regressão nos 5 testes ui/ existentes.
- **Testes**: componente+teclado para dialog (trap/ESC/restauração), toast, tabs, formfield,
  pagination, popover, combobox, actions-menu (setas/Home/End). Adicionar mock de
  `matchMedia` ao `vitest.setup.ts`. **Screenshot**: não (coberto por testes de DOM).
  **Rollback**: revert por fatia.

### UX-03 — App Shell
*Por que aqui: maior superfície visível; agora tem primitivos para se apoiar.*

- **Fatias**:
  - 3.1 Camadas e drawer: z-index pela escala (conserta P0-1); drawer mobile vira
    Dialog-pattern (trap, ESC, `inert`, foco, fecha ao clicar link atual); overlay unificado.
  - 3.2 Anti-FOUC do colapso + grupos (estender `THEME_INIT_SCRIPT`); larguras da sidebar
    normalizadas (68px → token).
  - 3.3 Contrato de largura do conteúdo: `max-w` padrão no `<main>` com opt-out; ritmo de
    padding único.
  - 3.4 Header: alturas unificadas (h-10), busca presente em mobile (ícone → palette),
    popovers sobre `ui/popover` com clamp de viewport (sino ≤ `calc(100vw-1rem)` ou
    bottom-sheet), rótulos `sr-only` onde só há ícone.
  - 3.5 Skip link + landmarks (`<header aria-label>`, `<main id>`, PageHeader deixa de
    renderizar `<header>` aninhado); `document.title` por rota (hook no PageShell).
  - 3.6 Sidebar colapsada: tooltips acessíveis nos ícones, sem troca silenciosa de destino
    (2.4 do shell), indicação de módulo preservada; item ativo por segmento (não
    `startsWith`).
  - 3.7 Preferências: uma superfície canônica (aba em `/perfil`), AvatarDropdown como
    radiogroup correto, ThemeToggle/DensityToggle consistentes; links do avatar corrigidos
    (`/m/administracao/auditoria`, `/perfil/notificacoes`).
  - 3.8 Tablets 768-1024: sidebar colapsada persistente em vez de drawer.
  - 3.9 Densidade de verdade: `--density-*` consumido por PageHeader, cards, forms e `<main>`
    (realiza a promessa do "Modo compacto") — P1-13.
- **Dependências**: UX-02. **Risco**: médio-alto (componente mais visível; mitigar com
  screenshots por fatia e testes existentes de Sidebar/Switcher). **Resultado visual**:
  shell alinhado, denso, com larguras e alturas consistentes. **Resultado UX**: mobile
  utilizável (busca, drawer correto), teclado de ponta a ponta no shell, título de aba real.
- **Aceite**: axe manual sem violações críticas no shell; drawer testado por teclado;
  `menus.test`/`Sidebar.modulo.test` verdes; screenshots âncora nos 2 temas × 3 larguras
  (360/768/1440).
- **Testes**: interação+teclado do drawer e popovers; teste de `document.title`.
  **Screenshot**: sim. **Rollback**: revert por fatia (3.1 e 3.2 independentes).

### UX-04 — Composição de página: PageShell, ListPage/DataTable, FormDialog
*Por que antes das páginas: é o multiplicador — cada tela migrada depois custa horas, não dias.*

- **Fatias**:
  - 4.1 `PageShell`/`PageHeader` obrigatório: title+breadcrumb+description+actions;
    guarda estrutural "página sem PageHeader não entra" (ratchet sobre as 52 atuais).
  - 4.2 `ListPage`/`DataTable`: tabela + toolbar de filtros (padrão único: Enter submete,
    chips de ativos, limpar) + **estado na URL** (searchParams) + ordenação + paginação +
    skeleton fiel + empty duplo + erro com retry. Extraído dos 6 padrões existentes,
    preservando o melhor de cada (draft-filters de processos, debounce de recadastramento,
    empty duplo).
  - 4.3 `FormDialog`/`useFormDialog`: submit no `<form>`, erro por campo via FormField, foco
    no primeiro inválido, título com nome da entidade, grid responsivo.
  - 4.4 `chart-theme.ts`: paleta categórica tokenizada + `TooltipChart` + defaults recharts
    (grid `hsl(var(--border))`), com allowlist no `design:check`.
- **Dependências**: UX-02. **Risco**: baixo (componentes novos, nada migra ainda).
  **Aceite**: testes de componente+interação+teclado dos 4; documentados no
  `docs/design-system.md`. **Screenshot**: não. **Rollback**: revert.

### UX-05 — CrudPage e listagens administrativas (12+ telas de uma vez)
*Maior retorno por esforço da auditoria.*

- **Fatias**: 5.1 CrudPage sobre ListPage+FormDialog (paginação P0-2, debounce, PageHeader,
  ordenação, checkbox do DS, `permCode` honrado); 5.2 usuários/unidades-trabalho migradas
  (EmptyState, skeleton, ações em ActionsMenu); 5.3 grids/entradas restantes da administração.
- **Dependências**: UX-04. **Risco**: médio (12 telas de uma vez — mitigado por serem todas o
  MESMO componente; smoke manual por tela). **Resultado UX**: paginação real, busca sã,
  ordenação, headers com breadcrumb nas 12+.
- **Aceite**: total exibido = total do backend; 1 request por busca digitada (debounce 300ms);
  vitest do CrudPage novo; screenshots de 2 telas âncora. **Rollback**: revert.

### UX-06 — Processos (fluxo central do produto)
- **Fatias**: 6.1 lista sobre ListPage (filtros na URL — P1-10, ordenação, honrar
  `?id_unidade=`); 6.2 detalhe: Tabs do DS (tabpanel/aria-controls), timeline como componente
  (agrupamento por data, paginação), prioridade da aba Visão (ações de tramitação acima do
  trajeto); 6.3 AnexosProcesso: tokens, ActionsMenu, upload com progresso, EmptyState;
  6.4 modais apensados/volumes/desentranhar sobre `ui/dialog` (parte do P0-4).
- **Dependências**: UX-04. **Risco**: médio (tela mais usada; preservar tab-na-URL).
- **Aceite**: back/forward/bookmark de filtros funciona; axe sem críticos no detalhe; testes
  de tabs por teclado. **Screenshot**: sim (lista+detalhe, 2 temas). **Rollback**: revert por
  fatia.

### UX-07 — Dashboards e Home
- **Fatias**: 7.1 dashboard executivo: hierarquia de KPIs (hero vs apoio), chart-theme
  (tooltips/grid/cores — P1-12), Tooltip acessível substituindo `title=`, ranking sobre
  DataTable, filtros consistentes, skeleton fiel, indicador "atualizado há X"; 7.2 home:
  tratamento de erro das 4 queries (P1-11), ActionCard → kpi-card, um hero só, sem ID
  interno; 7.3 dashboard pagamentos: erro com retry, KPIs clicáveis afordantes, linha
  navegável por teclado; padrão de alerta com limite/ordenação por urgência.
- **Dependências**: UX-04 (chart-theme). **Risco**: baixo-médio. **Aceite**: gráficos legíveis
  em dark; toda métrica ambígua com tooltip acessível; alternativa textual por gráfico.
  **Screenshot**: sim. **Rollback**: revert.

### UX-08 — Remediação transporte + módulos visuais (workflow/organograma)
*O pior estado do repo, isolado numa fase para não contaminar as demais.*

- **Fatias**: 8.1 `alvaras/[id]` reescrita sobre DS (P0-3; nomes em vez de IDs; card vazio
  resolvido ou removido); 8.2 alvaras/relatorio/veiculos-do-transporte: cores → tokens,
  datas pt-BR, focus-visible; 8.3 recadastramento: FilterBar + FormField (mantendo o
  empty-duplo e o debounce que já são referência); 8.4 workflow/organograma: hex → tokens via
  chart-theme (18 hex), botões → DS, focus-visible.
- **Dependências**: UX-04. **Risco**: baixo (telas de menor tráfego; dark mode só melhora).
- **Aceite**: `design:check` ratchet zera o módulo transporte; dark mode íntegro nas 4 telas.
  **Screenshot**: sim (antes/depois dark). **Rollback**: revert.

### UX-09 — Frota + pagamentos operacional
- **Fatias**: 9.1 veículos sobre ListPage (busca/filtro/paginação — P1-9) + form com
  validação client-side (placa, anos) via FormField; badge de situação 5 estados; 9.2 hub de
  frota com números (padrão do hub de pagamentos) e `ModuleHubGrid` extraído (dedup com
  transporte); 9.3 autorizacao/tesouraria: inputs artesanais → DS.
- **Dependências**: UX-04/05. **Risco**: baixo. **Aceite**: placa inválida barrada no client
  com erro no campo; frota de 500 veículos paginada. **Screenshot**: 9.1. **Rollback**: revert.

### UX-10 — Experiência pública (cidadão, validar, login)
- **Fatias**: 10.1 validar sobre DS (P1-16; mantendo neutralidade byte a byte); 10.2 cidadão:
  cards mobile na lista de processos (P1-18), EmptyState com CTA "abrir processo", rota
  servicos alcançável, "Sair" com confirmação; 10.3 login: fix do branding hex (P1-14 —
  validar formato ou usar `color-mix`), erro com foco/aria-invalid, loading com spinner,
  decisão sobre "esqueci minha senha" (produto), hero em tablets.
- **Dependências**: UX-02. **Risco**: baixo. **Aceite**: lista do cidadão utilizável em
  360px sem scroll horizontal; login com axe limpo. **Screenshot**: sim (mobile 360px).
  **Rollback**: revert.

### UX-11 — Navegação avançada e produtividade
- **Fatias**: 11.1 CommandPalette: padrão combobox (referência: `combobox.tsx`), ranking
  (exato > prefixo > contém, comandos antes de remotos empatados), normalização de acentos,
  recentes (localStorage), highlight, `staleTime`, resultados levando ao registro; palette
  disponível no launcher/plataforma; 11.2 launcher: cards com descrição+badge, grid
  responsivo, memória do último módulo (login aterrissa nele, `/modulos` a um clique);
  11.3 `/` respeitando sessão; breadcrumbs completos nas rotas profundas.
- **Dependências**: UX-03. **Risco**: baixo. **Aceite**: "novo processo" digitado acha a ação
  em 1º; teste de teclado do palette completo. **Screenshot**: launcher. **Rollback**: revert.

### UX-12 — Feedback e perf percebida (varredura transversal)
- **Fatias**: 12.1 varredura "Carregando…"→Skeleton (66 ocorrências, por módulo); 12.2 erros
  de página com retry padronizado (`Alert` + botão); 12.3 QueryClient único compartilhado
  entre route groups; `staleTime` global sensato; 12.4 mutações otimistas onde barato
  (marcar notificação lida, toggles).
- **Dependências**: UX-04. **Risco**: baixo. **Aceite**: zero "Carregando…" textual em tela
  de módulo; travessia app↔launcher sem spinner. **Screenshot**: não. **Rollback**: revert.

### UX-13 — Hardening de acessibilidade + regressão visual (automação)
- **Fatias**: 13.1 axe automatizado (jest-axe nos componentes; @axe-core/playwright nas
  âncoras) com baseline zero-críticos; 13.2 visual regression Playwright
  (`toHaveScreenshot`) das telas-âncora × 2 temas × 2 larguras — passa a rodar no CI para as
  fases futuras; 13.3 varredura final de teclado (tab order, `sr-only` em ícones-só
  restantes); 13.4 projetos Playwright mobile (viewport 375) para cidadão.
- **Dependências**: UX-03..10 (audita o resultado). **Risco**: baixo. **Aceite**: CI reprova
  regressão visual e violação axe crítica. **Rollback**: revert (só testes/CI).

### UX-14 — Polish final
- **Fatias**: microinterações restantes com causa (transição de tabs, stagger de listas ≤
  50ms — só onde orienta), revisão de copy (IDs internos, promessas não cumpridas),
  consistência final de espaçamento, queima do restante da baseline do `design:check` até
  zero, atualização do `docs/design-system.md`.
- **Aceite global de encerramento**: ver §16.

**Fases do prompt não adotadas como estavam**: "UX-03 Navigation & discovery" foi dividida
(shell na UX-03 daqui; palette/launcher na UX-11, porque dependem do shell e rendem menos que
CrudPage/processos); "UX-07 Feedback" virou transversal (UX-12) — cada fase já entrega seus
estados via componentes de composição, e a varredura final só caça o resto.

## 16. Critérios globais de aceite (programa inteiro)

1. **Tokens**: `design:check` com baseline **zero** (nenhuma cor literal/hex fora da
   allowlist de charts); zero token morto.
2. **Dark mode**: nenhuma tela com fundo/texto ilegível; pares de status AA nos 2 temas.
3. **Estrutura**: 100% das páginas com PageHeader/`document.title`; breadcrumb em rotas ≥ 2
   níveis; guarda estrutural ativa.
4. **Listagens**: toda listagem com skeleton fiel + empty acionável + erro com retry +
   paginação com total + estado na URL; ordenação onde o dado é ordenável.
5. **Formulários**: erro por campo com `aria-describedby` e foco no primeiro inválido; submit
   por Enter; botão com loading.
6. **A11y**: axe sem violações críticas nas âncoras; todo modal/popover com trap-ou-dismiss
   correto, ESC e devolução de foco; navegação completa por teclado no shell; skip link.
7. **Responsivo**: app do servidor utilizável em 768px (drawer correto, busca presente,
   popovers clampados); portal cidadão sem scroll horizontal em 360px.
8. **Perf percebida**: zero "Carregando…" textual; zero layout shift estrutural no load
   (sidebar, skeletons fiéis); CLS visualmente imperceptível nas âncoras.
9. **Motion**: tudo em 150-300ms via tokens; reduced-motion íntegro (incl. `scrollIntoView`).
10. **Regressão**: visual regression + axe no CI; suíte vitest de `ui/` cobrindo interação e
    teclado dos componentes com comportamento (dialog, tabs, combobox, palette, toast,
    actions-menu, pagination, formfield).
11. **Zero regressão funcional**: nenhuma mudança de API/rota/permissão; testes estruturais
    existentes (`menus`, `rotas-modulo`, contrato paginado) verdes em todas as fases.
