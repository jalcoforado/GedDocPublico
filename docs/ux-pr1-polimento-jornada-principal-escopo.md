# PR UX-1 — Polimento da jornada principal (cidadão / servidor / gestor)

> **Status:** proposta de escopo. Não implementar antes de autorização.
> **Data:** 2026-06-04.
> **Objetivo:** elevar o acabamento visual e a clareza da jornada principal para
> demonstração comercial / piloto, sem mexer em regra de negócio, dados ou
> permissões.

## 1. Contexto e princípios

A plataforma já possui multi-tenant/RLS, Admin SaaS, configuração inicial,
Carta de Serviços, abertura por serviço, checklist documental, complementação,
prazos por serviço (PR 5b), dashboard executivo e assinatura v2. As 11
funcionalidades estão entregues e testadas.

O problema agora não é faltar feature — é o **acabamento desigual** entre telas
e a **inconsistência de microcopy/estados**, que ficam evidentes em demo.
Especificamente:

- Os componentes do design system existem (Button, Card, KpiCard, Skeleton,
  SkeletonKpi, SkeletonRow, EmptyState, Badge, PageHeader, Toast, Dialog,
  Confirm, Table) mas **não são aplicados com consistência** — telas do
  Cidadão ignoram Skeleton e EmptyState; o Catálogo de Serviços usa `<TD>
  Carregando...</TD>` em vez de SkeletonRow; o dashboard usa `<p>Sem dados</p>`
  em vez de EmptyState.
- A linguagem de "ativo / inativo / encerrado / arquivado / em andamento"
  mistura termos técnicos e humanos em telas diferentes.
- O detalhe do processo do servidor concentra 5 botões de impressão + dropdown
  de sigilo em um único PageHeader.actions — visualmente pesado, mobile-hostil.
- O dashboard empilha 19 KpiCards em 3 blocos sem títulos de seção, sem
  separadores visuais — sobrecarga cognitiva em demo executiva.

Este PR é deliberadamente **defensivo**: nada de redesign, nova lib UI, novo
fluxo. Apenas *applying-the-system-we-already-have*, padronização de microcopy
e ajustes pontuais de hierarquia visual.

### Princípios

1. **Reuso antes de criação.** Use o componente que já existe; só crie novo
   wrapper quando o padrão se repete em 3+ lugares.
2. **Não tocar em regra de negócio.** Status, severidade e enums vêm do
   backend; UX-1 só ajusta como são exibidos.
3. **Diff cirúrgico.** Cada mudança deve ser localizável; preferir refator de
   componente compartilhado a mexer em N páginas.
4. **Linguagem cidadã separada.** Cidadão e servidor podem ler labels
   diferentes para o mesmo status (já é o padrão do PR 5b para prazos).

---

## 2. Inventário de achados por jornada

Severidades: **🔴 BLOQUEADOR** (corrige antes de demo) · **🟠 ALTO** ·
**🟡 MÉDIO** · **🟢 BAIXO** · **💡 SUGESTÃO**.

### 2.1 Jornada 1 — Portal público de serviços

Telas auditadas:
- [frontend/app/cidadao/servicos/page.tsx](frontend/app/cidadao/servicos/page.tsx)
- [frontend/app/cidadao/servicos/[slug]/page.tsx](frontend/app/cidadao/servicos/[slug]/page.tsx)
- [frontend/app/cidadao/servicos/[slug]/solicitar/page.tsx](frontend/app/cidadao/servicos/[slug]/solicitar/page.tsx)

| Sev. | Achado | Local |
|---|---|---|
| 🔴 | Botão "Solicitar serviço" no card é um `<Link>` reescrevendo manualmente classes Tailwind (`h-9 px-3 bg-brand …`) em vez de usar `Button` ou `<Button asChild>`. Inconsistência visual com o resto e duplicação de tokens. | [servicos/page.tsx:106-117](frontend/app/cidadao/servicos/page.tsx#L106-L117) |
| 🔴 | Estados vazios e de loading usam `<p>Carregando serviços…</p>` / `<p>Nenhum serviço disponível…</p>` em vez de `SkeletonRow`/`EmptyState`. Tela vazia parece bug em vez de estado válido. | [servicos/page.tsx:26-37](frontend/app/cidadao/servicos/page.tsx#L26-L37), [servicos/[slug]/page.tsx:31-42](frontend/app/cidadao/servicos/[slug]/page.tsx#L31-L42) |
| 🟠 | `prazo_estimado_dias` exibido como "Prazo estimado: 30 dia(s)" — o "(s)" técnico é cabeça de planilha PHP. Linguagem cidadã: "Prazo estimado: até 30 dias". | [servicos/page.tsx:74](frontend/app/cidadao/servicos/page.tsx#L74), [servicos/[slug]/page.tsx:73](frontend/app/cidadao/servicos/[slug]/page.tsx#L73) |
| 🟠 | Documentos obrigatórios marcados só com asterisco vermelho — sem legenda nem hint accessível. Cidadão não sabe que `*` quer dizer obrigatório. | [servicos/page.tsx:91-99](frontend/app/cidadao/servicos/page.tsx#L91-L99) |
| 🟠 | Página de detalhe não tem botão "Solicitar serviço" sticky no mobile — o botão fica no fim do card, scroll longo para chegar. | [servicos/[slug]/page.tsx:114-124](frontend/app/cidadao/servicos/[slug]/page.tsx#L114-L124) |
| 🟡 | Stepper "Solicitar" tem `Step 1 → Step 2` no estado mas não há **indicador visual** de progresso (1 de 2 / 2 de 2). | [solicitar/page.tsx:17-25](frontend/app/cidadao/servicos/[slug]/solicitar/page.tsx#L17-L25) |
| 🟡 | "Solicitação indisponível" sem **explicação do porquê**. Em casos como `solicitar_habilitado=false`, o cidadão fica sem entender. | [servicos/page.tsx:113-117](frontend/app/cidadao/servicos/page.tsx#L113-L117), [servicos/[slug]/page.tsx:119-122](frontend/app/cidadao/servicos/[slug]/page.tsx#L119-L122) |
| 🟡 | Card de serviço não tem hover state nem cursor pointer no `<article>` clicável (só no botão). Affordance pobre. | [servicos/page.tsx:48-50](frontend/app/cidadao/servicos/page.tsx#L48-L50) |
| 🟢 | "Categoria" como uppercase tracking-wide é elegante mas conflita com `Badge intent=neutral` no detail. Padrão é misturado. | [servicos/page.tsx:60-64](frontend/app/cidadao/servicos/page.tsx#L60-L64) vs [servicos/[slug]/page.tsx:50](frontend/app/cidadao/servicos/[slug]/page.tsx#L50) |
| 🟢 | Link "Voltar à Carta de Serviços" é só texto com seta — funciona, mas pode reusar `Button variant="ghost" size="sm"`. | [servicos/[slug]/page.tsx:23-29](frontend/app/cidadao/servicos/[slug]/page.tsx#L23-L29) |
| 💡 | Página `/cidadao/servicos` não tem `PageHeader` (usa h1 cru) — o portal do cidadão **nenhuma** tela usa `PageHeader`. Considerar variante "Cidadão" do PageHeader para identidade. | layout do cidadão |

### 2.2 Jornada 2 — Processo do cidadão

Tela: [frontend/app/cidadao/processos/[id]/page.tsx](frontend/app/cidadao/processos/[id]/page.tsx)

| Sev. | Achado | Local |
|---|---|---|
| 🔴 | 3 cards empilhados (Visão geral + Checklist + Histórico + Anexos + Complementação) **sem nenhuma hierarquia visual**. Em mobile vira parede de scroll. Não há tabs nem agrupamento. Pior do que a tela do servidor, que pelo menos tem tabs. | [processos/[id]/page.tsx:184-391](frontend/app/cidadao/processos/[id]/page.tsx#L184-L391) |
| 🔴 | Estados de loading/erro são `<p>Carregando processo…</p>` planos. Skeleton existe, EmptyState existe — nada é usado. | [processos/[id]/page.tsx:135, 158-178, 335, 366-368](frontend/app/cidadao/processos/[id]/page.tsx#L135) |
| 🟠 | Badge "Em andamento" (success) vs "Encerrado" (neutral) — cor de processo encerrado deveria ser `info` ou `brand`, não cinza neutro. "Encerrado" parece "inativo / cancelado". | [processos/[id]/page.tsx:208-216](frontend/app/cidadao/processos/[id]/page.tsx#L208-L216) |
| 🟠 | "Próximos passos" não existe. Cidadão olha a tela e não sabe **o que tem que fazer agora** (anexar X? esperar?). Faltam **CTAs contextuais** baseados em status documental + complementação aberta. | tela inteira |
| 🟠 | "Nenhum anexo público" como `<p className="text-muted-foreground">` num card sozinho — usar `EmptyState` com ícone Paperclip e mensagem "Quando o servidor anexar documentos ao processo, eles aparecerão aqui." | [processos/[id]/page.tsx:334-336](frontend/app/cidadao/processos/[id]/page.tsx#L334-L336) |
| 🟠 | "Nenhuma movimentação ainda" — mesmo problema; usar `EmptyState` com ícone Clock. | [processos/[id]/page.tsx:366-369](frontend/app/cidadao/processos/[id]/page.tsx#L366-L369) |
| 🟡 | Identifier (NUP) em `font-mono` text-2xl, "aberto em DD/MM HH:MM" em tabular-nums — bom. Mas "Número interno" aparece em texto pequeno embaixo, fácil de confundir. Mostrar só **NUP** e expor "número interno" só num tooltip "ⓘ". | [processos/[id]/page.tsx:194-206](frontend/app/cidadao/processos/[id]/page.tsx#L194-L206) |
| 🟡 | Dialog "Anexar: {nome}" mostra o `<input type="file">` sem estilo — visual nativo destoa do resto. Não há feedback de "arquivo selecionado" antes do submit. | [processos/[id]/page.tsx:429-435](frontend/app/cidadao/processos/[id]/page.tsx#L429-L435) |
| 🟡 | Histórico de movimentações: usa `border-l-2 border-primary` sem distinção entre tipos de movimentação (encaminhamento vs arquivamento vs abertura). Servidor já distingue com badges coloridos por ação. | [processos/[id]/page.tsx:371-389](frontend/app/cidadao/processos/[id]/page.tsx#L371-L389) |
| 🟢 | "Local atual" pode estar `null` e mostra "—". Em vez disso, "Aguardando triagem" ou "Em análise" são mais amigáveis se a unidade for null. | [processos/[id]/page.tsx:240-243](frontend/app/cidadao/processos/[id]/page.tsx#L240-L243) |
| 🟢 | `data-testid="cidadao-processo-detail"` não existe — Playwright e2e do PR 5b só procura por chaves de payload. Bom marcar a região "Próximos passos" para futuro e2e. | tela inteira |
| 💡 | Anexar via Dialog small é ok, mas poderia ser drag-and-drop direto no item do checklist para reduzir 1 clique. UX-2. | [processos/[id]/page.tsx:393-438](frontend/app/cidadao/processos/[id]/page.tsx#L393-L438) |

### 2.3 Jornada 3 — Processo do servidor

Tela: [frontend/app/(app)/processos/[id]/page.tsx](frontend/app/(app)/processos/[id]/page.tsx)

| Sev. | Achado | Local |
|---|---|---|
| 🔴 | **Action overload no PageHeader**: 5 botões (Capa, Etiqueta, Dupla, Completo, Em fila) + dropdown ClassificarSigilo + 4 badges + 1 PrazoBadge — empilhados como `flex-wrap` num único `actions={...}`. Visualmente caótico em desktop, ilegível mobile. | [processos/[id]/page.tsx:365-462](frontend/app/(app)/processos/[id]/page.tsx#L365-L462) |
| 🔴 | Loading state inicial é `<div className="text-muted-foreground">Carregando processo...</div>` sem Skeleton. Tela "pisca" em vez de revelar gradualmente. | [processos/[id]/page.tsx:318-320](frontend/app/(app)/processos/[id]/page.tsx#L318-L320) |
| 🟠 | "Aberto em {data}" aparece **duas vezes**: no `description` do PageHeader e no `CardHeader` da Visão geral. Redundante. | [processos/[id]/page.tsx:361](frontend/app/(app)/processos/[id]/page.tsx#L361), [519-525](frontend/app/(app)/processos/[id]/page.tsx#L519-L525) |
| 🟠 | Badge "Ativo / Inativo" — linguagem técnica. Servidor faz parsing mental: "inativo é arquivado?". Trocar para "Em tramitação / Encerrado" (alinhado com cidadão). | [processos/[id]/page.tsx:368-376](frontend/app/(app)/processos/[id]/page.tsx#L368-L376) |
| 🟠 | Conflito de informação de prazo: `<PrazoBadge>` no header **e** linha "Prazo previsto" no card Visão geral mostram o mesmo dado de jeitos diferentes. Decidir um lugar canônico (recomendo manter no header, simplificar no card). | [processos/[id]/page.tsx:388](frontend/app/(app)/processos/[id]/page.tsx#L388) vs [569-585](frontend/app/(app)/processos/[id]/page.tsx#L569-L585) |
| 🟠 | Botão "Em fila" para geração background tem label hostil — não comunica que é "PDF assíncrono". Substituir por "Gerar PDF em background" com ícone. | [processos/[id]/page.tsx:450-458](frontend/app/(app)/processos/[id]/page.tsx#L450-L458) |
| 🟡 | Tabs sem persistência de scroll quando volta da subnavegação (ex: clica relacionado → volta). Cada `setTab` faz `router.replace` mas perde scroll. | [processos/[id]/page.tsx:251-259](frontend/app/(app)/processos/[id]/page.tsx#L251-L259) |
| 🟡 | "Nenhuma movimentação registrada" — usar `EmptyState`. | [processos/[id]/page.tsx:639-642](frontend/app/(app)/processos/[id]/page.tsx#L639-L642) |
| 🟡 | Botões "Capa / Etiqueta / Etiqueta dupla" são variantes do mesmo tipo de ação (impressão) — agrupar em um dropdown "Imprimir" com 3 opções; libera espaço para o "PDF completo" virar primário visível. | [processos/[id]/page.tsx:391-449](frontend/app/(app)/processos/[id]/page.tsx#L391-L449) |
| 🟡 | "Solicitar complementação" aparece **só** num `<div className="flex justify-end">` na aba Documentos sem destaque — é uma das ações mais importantes do servidor; merece subir como CTA no card Checklist. | [processos/[id]/page.tsx:688-697](frontend/app/(app)/processos/[id]/page.tsx#L688-L697) |
| 🟢 | "Anexos" sem badge de contagem no card (já existe na tab); inserir para consistência. | [processos/[id]/page.tsx:726-734](frontend/app/(app)/processos/[id]/page.tsx#L726-L734) |
| 🟢 | `<RichTextView html={p.corpo} />` cai num `<p>` simples quando não bate o regex `/^\s*<[a-zA-Z]/`. Frágil. Tudo bem para PR UX-1, mas registrar. | [processos/[id]/page.tsx:600-604](frontend/app/(app)/processos/[id]/page.tsx#L600-L604) |
| 💡 | Considerar barra lateral fixa (mobile: bottom sheet) com **estado do processo + ações primárias** sempre visíveis ao rolar — UX-2. | tela inteira |

### 2.4 Jornada 4 — Dashboard executivo

Tela: [frontend/app/(app)/dashboard/page.tsx](frontend/app/(app)/dashboard/page.tsx)

| Sev. | Achado | Local |
|---|---|---|
| 🔴 | **19 KpiCards** em 3 blocos (6 + 5 + 8) sem títulos de seção nem separadores. Demo executiva fica "muro de números". Adicionar `<h2>` ("Volume", "Documental / Complementações", "Prazos") antes de cada grid. | [dashboard/page.tsx:279, 340, 384](frontend/app/(app)/dashboard/page.tsx#L279) |
| 🔴 | Bloco "SLA" (workflow per-node) e bloco "Prazos" (end-to-end PR 5b) coexistem sem **nenhuma explicação de qual é qual**. Gestor confunde. Adicionar tooltip ⓘ no título da seção "Prazos por serviço". | [dashboard/page.tsx:320-335, 383-456](frontend/app/(app)/dashboard/page.tsx#L320-L335) |
| 🟠 | Filtros (Unidade, Serviço, Legado, Período, Exportar) no `actions` do PageHeader — funciona desktop mas em ≤lg vira lista vertical que empurra os KPIs para baixo da dobra. Quebrar em barra de filtros separada abaixo do header. | [dashboard/page.tsx:175-275](frontend/app/(app)/dashboard/page.tsx#L175-L275) |
| 🟠 | Empty states de gráficos são `<p>Sem dados.</p>` planos — usar `EmptyState` minimal (sem CTA, só ícone + texto). | [dashboard/page.tsx:503-504, 535-536, 568-569, 601-604](frontend/app/(app)/dashboard/page.tsx#L503-L504) |
| 🟠 | Ranking por serviço tem **9 colunas**: Serviço / Processos / Compl. abertas / Compl. respondidas / Pendente / Parcial / Completo / S/Docs / Atrasados. Em desktop xl é ok; em ≤lg fica `overflow-x-auto` cego. Considerar coluna "Status documental" agregada (1 célula com 3 micro-bars). UX-2. | [dashboard/page.tsx:606-704](frontend/app/(app)/dashboard/page.tsx#L606-L704) |
| 🟡 | "Sem prazo" KPI tem hint "legado ou serviço sem prazo" — combinar com badge "ⓘ" para explicar que NÃO conta no % no prazo. | [dashboard/page.tsx:409-414](frontend/app/(app)/dashboard/page.tsx#L409-L414) |
| 🟡 | Skeleton de carregamento mostra **6 KpiSkeletons** mas o dashboard tem **19**. Suficiente, mas a percepção de "vai carregar mais" é fraca. Adicionar 2 grids skeleton extras. | [dashboard/page.tsx:117-133](frontend/app/(app)/dashboard/page.tsx#L117-L133) |
| 🟡 | Toggle "Incluir legado" usa `<input type="checkbox">` cru dentro de `<label>` — não usa `Checkbox` do design system. | [dashboard/page.tsx:212-223](frontend/app/(app)/dashboard/page.tsx#L212-L223) |
| 🟢 | Pie chart "Por tipo de processo" usa label que renderiza o texto da categoria diretamente no svg — em mobile vira ilegível. Trocar para legenda lateral. | [dashboard/page.tsx:516](frontend/app/(app)/dashboard/page.tsx#L516) |
| 🟢 | Botões Export PDF/CSV são `<a>` com classes manuais reproduzindo `Button variant="secondary"` — substituir por `<Button asChild>` ou refactor pra `<DownloadButton>`. | [dashboard/page.tsx:251-272](frontend/app/(app)/dashboard/page.tsx#L251-L272) |
| 💡 | "Atrasados > 0" ganhar background row inteira `bg-danger-soft/30` (não só a célula) — chama mais atenção ao gestor. UX-2 se conflitar com legado. | [dashboard/page.tsx:692-699](frontend/app/(app)/dashboard/page.tsx#L692-L699) |

### 2.5 Jornada 5 — Catálogo administrativo de serviços

Tela: [frontend/app/(app)/servicos/page.tsx](frontend/app/(app)/servicos/page.tsx)

| Sev. | Achado | Local |
|---|---|---|
| 🔴 | Estados vazio/loading da tabela usam `<TD colSpan={6}>Carregando...</TD>` e `Nenhum serviço cadastrado.` — usar `SkeletonRow cols={6}` para loading e `EmptyState` para vazio (com botão "Novo serviço" como `action`). | [servicos/page.tsx:244-258](frontend/app/(app)/servicos/page.tsx#L244-L258) |
| 🔴 | Dialog "Novo serviço" tem **16 campos** em grid sm:cols-2 sem nenhuma seção visual. Servidor abre e fica perdido. Agrupar em 3 fieldsets: "Identidade do serviço" (nome/slug/categoria/destaque/ordem), "Apresentação" (descrição curta/detalhada/público/instruções/confirmação), "Operação" (unidade/tipo/assunto/espécie/sigilo/prazo/canal + documentos). | [servicos/page.tsx:326-481](frontend/app/(app)/servicos/page.tsx#L326-L481) |
| 🟠 | "Documentos exigidos" sublista de inputs sem nenhuma instrução: "qual é o critério para 'obrigatório'?" Cidadão poderá enviar sem? Adicionar microcopy. | [servicos/page.tsx:434-469](frontend/app/(app)/servicos/page.tsx#L434-L469) |
| 🟠 | "Slug" sem validação inline — qualquer string aceita; backend é fonte de verdade mas servidor não recebe feedback até salvar. | [servicos/page.tsx:333-349](frontend/app/(app)/servicos/page.tsx#L333-L349) |
| 🟡 | Confirmação de "Desativar/Ativar" via `confirm()` é bom — mas mensagem técnica "Ele deixa de aparecer no portal público." pode ser reforçada: "Cidadãos não conseguirão mais solicitar este serviço a partir de agora. Processos existentes não são afetados." | [servicos/page.tsx:289-296](frontend/app/(app)/servicos/page.tsx#L289-L296) |
| 🟡 | Erros do backend caem em `<div bg-danger-soft>` no fim do dialog. Em formulário grande, servidor não vê — fica fora da dobra. Mostrar **no topo** do dialog também ou scrollar até o erro. | [servicos/page.tsx:476-480](frontend/app/(app)/servicos/page.tsx#L476-L480) |
| 🟢 | `Mostrar inativos` checkbox solto no topo — agrupar visualmente com botão "Novo serviço" (filtro + ação no mesmo bloco). | [servicos/page.tsx:222-231](frontend/app/(app)/servicos/page.tsx#L222-L231) |
| 🟢 | "Categoria" como `<Input>` livre é ótimo para MVP mas vira inferno consolidar depois. Considerar autocomplete a partir das categorias existentes — UX-2. | [servicos/page.tsx:351-353](frontend/app/(app)/servicos/page.tsx#L351-L353) |
| 💡 | Falta preview de "como vai aparecer no portal cidadão" — UX-2. | dialog |

---

## 3. Proposta de padronização

### 3.1 Badges — taxonomia consolidada

| Conceito | Intent | Label cidadão | Label servidor |
|---|---|---|---|
| Processo em curso | `success` (Clock) | Em andamento | Em tramitação |
| Processo concluído | `info` (CheckCircle2) | Concluído | Encerrado |
| Processo sigiloso | `warning` (Lock) | — (não exibir) | Sigiloso · {nível} |
| Processo externo | `info` (Eye) | — | Externo |
| Prazo dentro | `success` (Clock) | Dentro da previsão | Dentro do prazo |
| Prazo vencendo | `warning` (AlertTriangle) | Próximo do prazo | Vencendo |
| Prazo atrasado | `danger` (AlertCircle) | Fora da previsão | Atrasado |
| Documento enviado | `success` (Check) | Enviado | Enviado |
| Documento obrigatório | `warning` | Obrigatório · pendente | Obrigatório · pendente |
| Documento opcional | `neutral` | opcional | opcional |
| Complementação aberta | `warning` | Aguardando seus documentos | Complementação aberta |
| Destaque (portal) | `brand` (Star) | Destaque | Destaque |

**Regra:** badge ≠ status backend. Backend continua mandando enum; o front
mapeia para label. Esta tabela vira a **única fonte de verdade visual** num
helper `lib/badges.ts`.

### 3.2 Cards

- **Card padrão** = `<Card><CardHeader><CardTitle>X</CardTitle></CardHeader><CardContent>…</CardContent></Card>`
  já é o padrão. Manter.
- **Card com contagem**: `<CardTitle>Anexos <span className="text-foreground-muted">({n})</span></CardTitle>`
  — padronizar a posição do contador.
- **Cards de seção** dentro de detalhe de processo: padronizar margem
  vertical em `space-y-6` (servidor já usa, cidadão usa `space-y-4` — alinhar).

### 3.3 Estados vazios

Substituir todo `<p className="text-sm text-muted-foreground">Nenhum X.</p>` por
`<EmptyState icon={X} title="Sem X" description="…" />`. Microcopy padrão:

| Lugar | Título | Descrição |
|---|---|---|
| Lista de serviços (portal) | "Nenhum serviço disponível" | "A prefeitura ainda não publicou serviços para solicitação online." |
| Anexos (cidadão) | "Sem anexos públicos" | "Quando o servidor anexar documentos ao processo, eles aparecerão aqui." |
| Movimentações (cidadão) | "Sem movimentações" | "Assim que o servidor agir no processo, o histórico aparecerá aqui." |
| Movimentações (servidor) | "Sem movimentações" | "Use 'Ações de tramitação' para registrar a primeira movimentação." |
| Dashboard sem dados | "Sem dados no período" | "Tente um período maior ou remova filtros." (com botão "Limpar filtros" como `action`) |
| Catálogo de serviços vazio | "Nenhum serviço cadastrado" | "Cadastre o primeiro serviço da Carta de Serviços." + botão "Novo serviço" |

### 3.4 Skeleton / loading

- Listas: `SkeletonRow` em `<TBody>` (5 linhas).
- Detalhe de processo: skeleton-grid com 1 card grande (header) + 2 cards médios.
- Dashboard: já tem padrão, ajustar para 19 cards (3 blocos × 6).
- Cidadão: **deixar de usar `<p>Carregando…</p>`**. Sempre Skeleton.

Regra: skeleton só para `isLoading` na primeira carga. Refetch (com `data`
prévio) NÃO substitui por skeleton — exibir um `aria-busy` discreto no header.

### 3.5 Erros

- Erro de API: `<div role="alert" className="rounded-md bg-danger-soft …">`
  já é o padrão. Manter.
- Erro de validação inline: usar borda `border-danger` no input + texto vermelho
  embaixo. (Hoje não temos padrão — adotar.)
- Erro de permissão (403): bloco grande com `ShieldAlert` + microcopy
  explicando qual permissão pedir (padrão já existe em dashboard PR 5a — replicar).

### 3.6 Botões primários/secundários

| Cenário | Variant | Tamanho |
|---|---|---|
| CTA único de uma página (Salvar, Confirmar, Solicitar serviço) | `primary` | `md` |
| Cancelar / Voltar / Fechar dialog | `secondary` | `md` |
| Toolbar de header (Capa, Etiqueta, etc) | `ghost` | `sm` |
| Ação destrutiva (Excluir, Desativar) | `danger` | `md` |
| Toggle em barra de filtros | `secondary` | `md` (h-10 alinhado com inputs) |

**Anti-padrão a corrigir:** `<Link>` ou `<a>` reescrevendo classes de Button
manualmente (`servicos/page.tsx:106-117`, `dashboard/page.tsx:251-272`).

### 3.7 Mensagens para cidadão (linguagem cidadã)

Princípios:

1. Verbo na voz ativa, sujeito na 2ª pessoa ("você") quando dá instrução.
2. Sem jargão jurídico/técnico: vetar "SLA", "vencido", "prazo legal",
   "garantia", "tempestivo", "deferido", "indeferido" (já é regra D-CIDADAO
   do PR 5b — estender ao resto).
3. Datas em formato extenso quando possível: "Prazo estimado: até
   15 de julho" no detalhe; "Prazo estimado: até 30 dias" no card de
   listagem.
4. Estados negativos com explicação ("Solicitação indisponível porque o
   atendimento online deste serviço está pausado pela prefeitura.").

### 3.8 Mensagens para servidor

Princípios:

1. Termos técnicos preservados (NUP, encaminhamento, arquivamento, sigilo).
2. Microcopy contextual de tooltip em botões pouco óbvios.
3. Status com cor + ícone + label — nunca só cor.

### 3.9 Linguagem de prazo

(Consolida o D-CIDADAO do PR 5b.)

| Status | Cidadão | Servidor |
|---|---|---|
| `sem_prazo` | — (não exibir) | "Sem prazo" |
| `dentro_do_prazo` | "Dentro da previsão" | "Dentro do prazo" + dias restantes |
| `vencendo` | "Próximo do prazo" | "Vencendo" + dias restantes |
| `atrasado` | "Fora da previsão" | "Atrasado em N dias" |
| `concluido_no_prazo` | — (omitido, já tem badge Concluído) | "Concluído no prazo" |
| `concluido_atrasado` | — | "Concluído com atraso" |

### 3.10 Linguagem de complementação

| Conceito | Cidadão | Servidor |
|---|---|---|
| Solicitação aberta de docs | "Documentos pendentes" | "Complementação aberta" |
| Cidadão respondeu | "Aguardando análise" | "Aguardando análise" |
| Cancelada pelo servidor | "Cancelada" + motivo | "Cancelada" + motivo |
| Histórico | "Documentos pedidos anteriormente" | "Histórico de complementações" |

### 3.11 Linguagem de documentos

- "Documentos exigidos" (não "Documentos obrigatórios" — alguns são
  opcionais).
- Item com `obrigatorio=true`: badge `warning` "Obrigatório · pendente"
  enquanto não enviado; `success` "Enviado" quando enviado.
- Item com `obrigatorio=false`: badge `neutral` "Opcional · pendente" /
  `success` "Enviado".
- Asterisco vermelho: manter, mas com `<abbr title="obrigatório">*</abbr>`
  e legenda no rodapé do card.

---

## 4. Escopo controlado

### 4.1 Entra no UX-1 (estimado em ~1 PR de tamanho médio)

| # | Item | Jornadas | Arquivos prováveis |
|---|---|---|---|
| 1 | Criar `lib/badges.ts` com helpers `statusProcessoBadge(p, modo)`, `prazoBadge(prazo, modo)`, `documentoBadge(item)` consolidando a taxonomia da seção 3.1. | 1–5 | novo |
| 2 | Substituir `<p>Nenhum…</p>` por `EmptyState` em **todas as telas das 5 jornadas** (lista de serviços, detalhe cidadão, detalhe servidor, dashboard, catálogo). | 1–5 | ~10 páginas |
| 3 | Substituir `<p>Carregando…</p>` por `Skeleton*` nas telas do cidadão (jornadas 1 e 2). | 1–2 | 4 páginas |
| 4 | Catálogo de serviços: trocar loading/empty da tabela por `SkeletonRow` e `EmptyState` (com ação "Novo serviço"). | 5 | 1 página |
| 5 | Detalhe servidor: agrupar botões de impressão em um dropdown "Imprimir" (Capa / Etiqueta / Etiqueta dupla / Completo); deixar "Em fila" como secundário; alinhar com PageHeader sem `flex-wrap` cheio. | 3 | 1 página + 1 componente novo `<PrintMenu>` |
| 6 | Detalhe servidor: remover duplicação de "Aberto em" entre PageHeader e Card Visão geral; manter no PageHeader. | 3 | 1 página |
| 7 | Detalhe servidor: trocar badges "Ativo / Inativo" → "Em tramitação / Encerrado". | 3 | 1 página |
| 8 | Detalhe cidadão: adicionar card "Próximos passos" no topo, com 3 cenários condicionais — (a) complementação aberta → CTA "Enviar documentos solicitados"; (b) checklist incompleto → "Anexar documentos"; (c) tudo em ordem → "Acompanhe pelo histórico". Texto reusa dados já no payload, sem nova chamada. | 2 | 1 página + 1 componente `<ProximosPassosCard>` |
| 9 | Detalhe cidadão: ajustar badges "Em andamento" / "Encerrado" para a taxonomia consolidada (encerrado = info, não neutral). | 2 | 1 página |
| 10 | Portal cidadão: trocar `<Link>` manual em ServicoCard por `<Button asChild>` ou padronizar com componente. | 1 | 1 página |
| 11 | Portal cidadão: ajustar microcopy de prazo ("até N dias" em vez de "N dia(s)") + tooltip/abbr em asteriscos de documentos obrigatórios + legenda. | 1 | 3 páginas |
| 12 | Portal cidadão: stepper visual no Solicitar (Step 1 de 2 / Step 2 de 2) — `<Stepper>` simples (CSS, sem lib). | 1 | 1 página + 1 componente `<Stepper>` |
| 13 | Dashboard: adicionar `<h2>` "Volume", "Documental e complementações", "Prazos por serviço" antes de cada bloco de KpiCards; adicionar microcopy `<p>` de 1 linha explicando o bloco. | 4 | 1 página |
| 14 | Dashboard: extrair barra de filtros do `actions` para uma `<DashboardFilters>` abaixo do PageHeader (componente novo, mantém comportamento idêntico). | 4 | 1 página + 1 componente |
| 15 | Dashboard: empty states de gráficos com `EmptyState` minimal. | 4 | 1 página |
| 16 | Dashboard: substituir 6 SkeletonKpi por 19 (3 grids). | 4 | 1 página |
| 17 | Dashboard: trocar `<input type="checkbox">` cru por `<Checkbox>` no toggle Legado. | 4 | 1 página |
| 18 | Dashboard: Pie chart com legenda lateral em vez de label inline. | 4 | 1 página |
| 19 | Catálogo de serviços: agrupar dialog em 3 fieldsets visuais ("Identidade", "Apresentação", "Operação") com `<fieldset>` + `<legend>` estilizados (sem nova lib). Manter campos exatamente como estão. | 5 | 1 página |
| 20 | Catálogo de serviços: erro do backend duplicado no topo do dialog quando o usuário precisa rolar. | 5 | 1 página |
| 21 | Garantir **mobile** funcional em todas as telas auditadas: testar manualmente larguras 360 / 414 / 768 e ajustar overflow / flex-wrap problemáticos. | 1–5 | várias |

### 4.2 Fica para UX-2

- Coluna agregada "Status documental" no ranking do dashboard (substituindo
  Pendente / Parcial / Completo).
- Drag-and-drop de upload no checklist do cidadão.
- Sidebar fixa de "estado do processo + ações" no detalhe servidor.
- Autocomplete de categoria no Catálogo.
- Preview "como aparece no portal" no Dialog do Catálogo.
- Variante "Cidadão" do PageHeader (identidade do portal).
- Linha vermelha em `tr` do ranking quando `atrasados > 0`.
- Filtro "Limpar" no dashboard (depende de UX da DashboardFilters).
- Botão sticky de "Solicitar serviço" no detalhe (mobile).

### 4.3 Não deve ser feito agora

- Redesign de PageHeader, Card ou Button.
- Substituir Tailwind por outra solução de estilo.
- Nova lib UI (shadcn/radix/headlessui).
- Refactor de TanStack Query, providers, layout do app.
- Mexer em RichTextEditor.
- Mexer em assinatura, RLS, permissões, dashboard SQL, regras de prazo.
- Migrações, endpoints, schemas backend.
- Quebrar contratos de API ou ordem de campos do payload (PR 4d, 5a, 5b
  testam shape).

---

## 5. Anti-escopo (vetado)

O PR UX-1 **não pode** conter:

- ✗ Nova regra de negócio.
- ✗ Nova migration ou alteração de schema.
- ✗ Novo endpoint ou alteração de contrato de endpoint existente.
- ✗ Novo dashboard ou nova métrica agregada.
- ✗ Novo fluxo de usuário (ex: novo modo de abertura).
- ✗ Redesign total de uma tela.
- ✗ Nova biblioteca de UI ou estilo.
- ✗ Alteração estrutural grande (Provider tree, layout root, App Router).
- ✗ Refactor de arquitetura (lib/api, hooks compartilhados).
- ✗ Mudança de permissões, papéis ou grupos.
- ✗ Mudança de RLS, tenant_id ou contexto multi-tenant.
- ✗ Mudança de assinatura eletrônica ou de validação pública.
- ✗ Alteração de cálculos (KPI, ranking, prazo, conclusão).
- ✗ Alteração de payload backend (PrazoInfo, PrazoCidadao, DashboardKpis…).
- ✗ Mudança em microcopy de e-mail / notificação / comprovante PDF.
- ✗ Mudança em tema (cores, dark mode, gradients, brand).

Em caso de dúvida sobre se algo está in/out de escopo: **fica para UX-2**.

---

## 6. Testes

### 6.1 Vitest (componentes/telas alteradas)

Adicionar ou estender:

| Suite | Cobertura |
|---|---|
| `components/ui/__tests__/EmptyState.test.tsx` | Renderiza title/description/action; ícone opcional. (Provavelmente já existe; verificar.) |
| `lib/__tests__/badges.test.ts` (novo) | Helpers `statusProcessoBadge`, `prazoBadge`, `documentoBadge` retornam `{intent, label, icon}` correto p/ cada status × modo (admin/cidadão). |
| `components/__tests__/ProximosPassosCard.test.tsx` (novo) | 3 cenários: complementação aberta, checklist incompleto, tudo em ordem. Não chama API. |
| `app/(app)/dashboard/__tests__/page.test.tsx` | Estender: títulos de seção visíveis; barra de filtros agora abaixo do header; empty states usam `EmptyState`. **Não pode quebrar** os 12 testes existentes do PR 5a + 5b. |
| `app/(app)/servicos/__tests__/page.test.tsx` | Estender: SkeletonRow no loading; EmptyState com botão "Novo serviço" no vazio; dialog tem 3 fieldsets. |
| `app/(app)/processos/__tests__/[id]/page.test.tsx` (criar se não existir) | Dropdown "Imprimir" tem 4 itens; badge "Em tramitação" em processo ativo; sem duplicação de "Aberto em". |
| `app/cidadao/processos/[id]/__tests__/page.test.tsx` (criar) | Card "Próximos passos" condicional (3 cenários); EmptyState em movimentações/anexos vazios; skeleton no loading. |
| `app/cidadao/servicos/__tests__/page.test.tsx` | Estender: botão "Solicitar serviço" agora é `<Button>` (não `<a>`); microcopy "até N dias"; legenda de obrigatório. |
| `app/cidadao/servicos/[slug]/solicitar/__tests__/solicitar.test.tsx` | Estender: stepper visual mostra "1 de 2" e "2 de 2". |

### 6.2 Playwright (smoke da jornada principal)

- Estender `tests-e2e/specs/prazos.spec.ts` **não é necessário** — não toca
  contrato.
- Criar `tests-e2e/specs/ux1-smoke.spec.ts` cobrindo:
  1. Cidadão entra no portal → vê lista de serviços (smoke).
  2. Abre um serviço → vê detalhe com prazo formatado "até N dias".
  3. Clica em "Solicitar" → stepper mostra "1 de 2".
  4. Login admin → dashboard → vê 3 seções tituladas + barra de filtros
     separada.
  5. Lista admin de serviços → estado vazio (se vazio no DB) → vê EmptyState
     com "Novo serviço". Em DB com dados, vê tabela normal.

Smoke **HTTP only** (sem screenshots / regressão visual neste PR).

### 6.3 Backend

**Nenhum teste backend nesta jornada.** Se algum componente compartilhado for
tocado (improvável — UX-1 é exclusivamente frontend), justificar no PR.

### 6.4 O que **não** será testado neste PR

- Acessibilidade WCAG (foco visível, contraste 4.5:1, screenreader full
  flow) — fica para UX-3.
- Regressão visual (Percy / Chromatic).
- Performance (Lighthouse).
- i18n (todo o app é pt-BR neste PR).

---

## 7. Entregável final esperado

- **1 PR único**, branch `feat/ux1-polimento-jornada-principal`.
- **0 migrations, 0 endpoints novos, 0 contratos alterados.**
- Diff esperado: ~15-20 arquivos frontend, ~3-5 componentes novos pequenos
  (badges helper, Stepper, PrintMenu, ProximosPassosCard, DashboardFilters).
- Mensagem de commit: `feat(ux): UX-1 — polimento da jornada principal
  (cidadão / servidor / gestor)`.
- Sem mudança de teste backend; pytest 291/291 deve seguir verde sem ajuste.
- Vitest deve crescer (~80 → ~95) sem regressão.
- Playwright deve crescer 1 spec (`ux1-smoke.spec.ts`) sem mexer nos
  existentes.

---

## 8. Critério de "pronto para demo"

Um demo comercial / piloto poderia rodar com confiança quando:

1. Nenhuma tela auditada exibe `<p>Carregando...</p>` ou `<p>Nenhum X.</p>`
   plano.
2. Dashboard cabe na primeira dobra (1366×768) com todas as 3 seções
   identificáveis.
3. Detalhe servidor cabe no header sem quebrar em 4 linhas em desktop padrão.
4. Detalhe cidadão sempre mostra "o que fazer agora" no topo, sem precisar
   rolar.
5. Portal público de serviços tem hover/affordance claros nos cards.
6. Catálogo administrativo abre o dialog "Novo serviço" e o servidor entende
   onde colocar cada coisa.
7. Microcopy de prazo segue 100% a tabela 3.9.
8. Testes vitest + playwright todos verdes.

---

## 9. Decisões em aberto (a confirmar antes de implementar)

Antes de partir para o PR de implementação, eu pediria sua decisão sobre:

- **D-PROXIMOS-PASSOS**: o card "Próximos passos" no detalhe cidadão é a
  mudança mais ambiciosa do escopo. Confirma que **conta como "polimento"**
  ou prefere mover para UX-2?
- **D-PRINT-MENU**: agrupar os 5 botões de impressão do servidor num
  dropdown é uma alteração visual perceptível. Confirma?
- **D-DASHBOARD-FILTROS**: extrair a barra de filtros do `actions` para
  bloco próprio mexe na hierarquia do PageHeader. Confirma?
- **D-FIELDSETS-CATALOGO**: agrupar dialog do catálogo em 3 fieldsets é
  organização visual mas pode levar usuário existente a "perder" um campo
  por um momento. Vale a troca?
- **D-LINGUAGEM-ENCERRADO**: trocar "Inativo" (servidor) por "Encerrado"
  pode confundir quem já usa o sistema. Manter ambos como pílulas distintas
  ou consolidar?

Aguardo decisões para gerar o **escopo implementável consolidado**.
