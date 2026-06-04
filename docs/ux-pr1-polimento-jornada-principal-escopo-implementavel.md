# PR UX-1 — Polimento da jornada principal (escopo implementável)

> **Predecessor:** [ux-pr1-polimento-jornada-principal-escopo.md](ux-pr1-polimento-jornada-principal-escopo.md)
> **Status:** consolidado para implementação. Aguarda autorização explícita.
> **Data:** 2026-06-04.
> **Branch sugerido:** `feat/ux1-polimento-jornada-principal`.
> **Tamanho esperado:** 1 PR médio, ~20-25 arquivos frontend, 0 backend.

---

## 0. Decisões fechadas (entram inalteradas)

| ID | Decisão | Resumo |
|---|---|---|
| **D-PROXIMOS-PASSOS** | ✅ entra (versão enxuta) | Card "Próximos passos" no detalhe cidadão, calculado **só no frontend** a partir do payload já existente. 4 mensagens fixas, linguagem cidadã, sem promessa de prazo/resultado. |
| **D-PRINT-MENU** | ✅ entra | Agrupar os 5 botões de impressão do detalhe servidor em 1 dropdown (`ActionsMenu`). Mesmas rotas, mesmas permissões, só menos poluição. |
| **D-DASHBOARD-FILTROS** | ✅ entra | Extrair filtros (Período / Unidade / Serviço / Legado / Export) do `actions` do PageHeader para uma `FilterBar` abaixo do header. Lógica intacta. |
| **D-FIELDSETS-CATALOGO** | ✅ entra | 3 fieldsets no dialog do Catálogo: **Identificação**, **Configuração operacional**, **Orientações ao cidadão**. Schema/validação intactos. |
| **D-LINGUAGEM-ENCERRADO** | ❌ sem replace global | Trocas contextuais apenas: em **processo** concluído pode virar "Encerrado/Concluído"; em **cadastro/serviço/tenant/usuário** mantém "Inativo". |

---

## 1. Componentes a criar/extrair

### 1.1 Criar (5 arquivos novos, pequenos)

| Componente | Arquivo | Por que | Reusos |
|---|---|---|---|
| `EmptyState` (já existe) | [frontend/components/ui/empty-state.tsx](frontend/components/ui/empty-state.tsx) | **REUSAR** — não criar nada novo. | ≥ 10 telas. |
| `SectionCard` | `frontend/components/ui/section-card.tsx` (novo) | **EXTRAIR** do helper local em [processos/novo/page.tsx:47-84](frontend/app/(app)/processos/novo/page.tsx#L47-L84). Generalizar removendo `step` obrigatório. | Detalhe cidadão (Próximos passos), Catálogo (3 fieldsets), Detalhe servidor (Documentos/Anexos/Assinaturas). |
| `ActionsMenu` | `frontend/components/ui/actions-menu.tsx` (novo) | Dropdown acessível baseado em `<button>` + `<ul>` controlado (sem nova lib). Itens com `icon`, `label`, `onClick`. | Detalhe servidor (Imprimir), futuras toolbars. |
| `FilterBar` | `frontend/components/ui/filter-bar.tsx` (novo) | Container responsivo que aceita slots `<FilterBar.Group>` e `<FilterBar.Actions>` (right-aligned). Sem lógica de filtro. | Dashboard. Futuro: listas filtráveis. |
| `ProximosPassosCard` | `frontend/components/ProximosPassosCard.tsx` (novo) | Card específico do detalhe cidadão. Recebe `{ processo, checklist, complementacaoAberta }` e renderiza 1 das 4 mensagens. **Componente de domínio**, não de UI genérica. | Detalhe cidadão. |
| `lib/badges.ts` | `frontend/lib/badges.ts` (novo) | Helpers puros: `statusProcessoBadge(p, modo)`, `prazoBadge(prazo, modo)`, `documentoBadge(item)`. Retornam `{ intent, label, icon }`. Sem JSX. | Detalhe cidadão, detalhe servidor, checklist. |

### 1.2 Não criar

- ❌ Stepper visual (deixar para UX-2 se solicitar ressentir).
- ❌ DashboardFilters como componente de domínio — `FilterBar` é genérico, os filtros ficam inline na página.
- ❌ PrintMenu específico — usar `ActionsMenu` genérico.
- ❌ StatusBadge component (só helper `lib/badges.ts`; quem usa é o `<Badge>` existente).

---

## 2. Mudanças por jornada (arquivo a arquivo)

### 2.1 Portal público de serviços

#### A. `frontend/app/cidadao/servicos/page.tsx`

- Linha 4: importar `Search` (lucide) para o EmptyState.
- Linha 7: importar `EmptyState` de `@/components/ui/empty-state`.
- Linhas 26-31 (loading): substituir por grid de 4 skeletons (`SkeletonKpi` repurposed ou cards skeletons em `bg-surface-2/40 animate-pulse h-40`).
- Linhas 33-37 (empty): substituir por:
  ```tsx
  <EmptyState
    icon={Search}
    title="Nenhum serviço disponível"
    description="A prefeitura ainda não publicou serviços para solicitação online."
  />
  ```
- Linhas 106-117 (botão Solicitar): substituir o `<Link>` manual por:
  ```tsx
  <Button asChild size="sm" className="w-full sm:w-auto">
    <Link href={`/cidadao/servicos/${s.slug}`}>Solicitar serviço</Link>
  </Button>
  ```
  (Adicionar `asChild` ao `Button` se necessário — ver §3.)
- Linhas 113-117 (indisponível): adicionar tooltip/título com motivo:
  ```tsx
  <Button variant="secondary" size="sm" disabled
    title="O atendimento online deste serviço está pausado pela prefeitura.">
    Indisponível no momento
  </Button>
  ```
- Linha 74 (prazo): trocar `Prazo estimado: {N} dia(s)` por `Prazo estimado: até {N} dia{N === 1 ? "" : "s"}`.
- Linha 95 (asterisco): trocar `<span className="text-danger"> *</span>` por `<abbr title="Documento obrigatório" className="text-danger no-underline"> *</abbr>`.
- Após a lista de documentos, adicionar legenda:
  ```tsx
  <p className="mt-1 text-[10px] text-foreground-subtle">* obrigatório</p>
  ```
- Linha 48-50 (card): adicionar `transition-all hover:-translate-y-0.5 hover:shadow-md hover:border-border-strong`.

#### B. `frontend/app/cidadao/servicos/[slug]/page.tsx`

- Linhas 31-36 (loading): trocar por SkeletonLine + skeleton-grid.
- Linhas 38-42 (erro): trocar por `EmptyState icon={Search} title="Serviço não encontrado" description="Verifique o link ou volte à Carta de Serviços." action={<Button asChild><Link href="/cidadao/servicos">Voltar</Link></Button>} />`.
- Linha 73: mesma transformação do prazo "até N dias".
- Linhas 104, 95: `<abbr>` + legenda no documentos.
- Linhas 114-124 (botão final): adicionar wrapper sticky-on-mobile:
  ```tsx
  <div className="sticky bottom-4 z-10 -mx-4 mt-4 border-t border-border bg-card/95 px-4 py-3 backdrop-blur sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:p-0 sm:backdrop-blur-none">
    {/* botão atual */}
  </div>
  ```

#### C. `frontend/app/cidadao/servicos/[slug]/solicitar/page.tsx`

- Linha 48 (loading inicial): trocar por skeleton card.
- Linhas 76 (warning indisponível): manter texto, mas adicionar microcopy "Você ainda pode acompanhar serviços abertos em **Meus processos**." com link.
- Linhas 116-117 (contador de chars): trocar por barra de progresso visual minimal:
  ```tsx
  <div className="mt-1 flex items-center gap-2 text-xs">
    <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
      <div className="h-full bg-brand transition-all"
           style={{ width: `${Math.min(100, (corpo.trim().length / 10) * 100)}%` }} />
    </div>
    <span className={cn("tabular-nums",
      canAdvance ? "text-success-soft-foreground" : "text-foreground-muted")}>
      {corpo.trim().length}/10
    </span>
  </div>
  ```
- **Não** adicionar stepper visual (descartado em §1.2).

---

### 2.2 Detalhe do processo do cidadão

#### A. `frontend/app/cidadao/processos/[id]/page.tsx`

- Importar `EmptyState`, `Paperclip`, `Clock`, `MessageCircle` (lucide), `ProximosPassosCard`.
- Linhas 135, 159 (loading): trocar `<p>Carregando…</p>` por skeleton vertical:
  ```tsx
  <div className="space-y-4">
    <div className="h-32 animate-pulse rounded-lg bg-surface-2/40" />
    <div className="h-48 animate-pulse rounded-lg bg-surface-2/40" />
    <div className="h-64 animate-pulse rounded-lg bg-surface-2/40" />
  </div>
  ```
- Linhas 207-216 (badges): manter "Em andamento" mas trocar "Encerrado" `intent="neutral"` → `intent="info"` (D-LINGUAGEM-ENCERRADO: contexto de processo concluído permite essa cor).
- **Após** o card de "Visão geral" (depois da linha 291), **antes** do `complementacao_aberta` (linha 293), inserir:
  ```tsx
  <ProximosPassosCard
    processo={p}
    checklist={checklistQ.data}
    complementacaoAberta={checklistQ.data?.complementacao_aberta}
  />
  ```
- Linhas 334-336 (anexos vazios):
  ```tsx
  <EmptyState
    icon={Paperclip}
    title="Sem anexos públicos"
    description="Quando o servidor anexar documentos ao processo, eles aparecerão aqui."
  />
  ```
- Linhas 366-369 (histórico vazio):
  ```tsx
  <EmptyState
    icon={Clock}
    title="Sem movimentações ainda"
    description="Assim que o servidor agir no processo, o histórico aparecerá aqui."
  />
  ```
- Linhas 201-206 (número interno): mover para tooltip discreto:
  ```tsx
  {p.nup && p.numero_processo && p.nup !== p.numero_processo && (
    <span className="ml-2 align-middle text-xs text-foreground-subtle"
          title={`Número interno: ${p.numero_processo}`}>
      ⓘ
    </span>
  )}
  ```

#### B. `frontend/components/ProximosPassosCard.tsx` (NOVO)

Componente puro — sem chamadas de API. Recebe dados já presentes na página:

```tsx
interface Props {
  processo: CidadaoProcessoDetail;
  checklist: ChecklistDocumentosResponse | undefined;
  complementacaoAberta: ComplementacaoItem | null | undefined;
}
```

Regras de decisão (estritamente nesta ordem de prioridade):

1. **Processo encerrado** (`!processo.ativo`):
   - Ícone: `CheckCircle2` · intent: `success`
   - Título: "Sua solicitação foi concluída."
   - Descrição: "Você pode rever os detalhes e o histórico abaixo."

2. **Complementação aberta** (`complementacaoAberta?.status === "aberta"`):
   - Ícone: `MessageCircle` · intent: `warning`
   - Título: "Responda à solicitação de complementação."
   - Descrição: "O servidor pediu documentos adicionais. Envie o que estiver pendente para que a análise possa continuar."

3. **Checklist incompleto** (`checklist?.status_documental` em `["pendente", "parcial"]`):
   - Ícone: `FileText` · intent: `info`
   - Título: "Envie os documentos pendentes."
   - Descrição: `${checklist.obrigatorios_enviados}/${checklist.obrigatorios_total} obrigatórios enviados. Anexe os que faltam para que a análise possa continuar.`

4. **Padrão** (em andamento sem ação do cidadão):
   - Ícone: `Clock` · intent: `default`
   - Título: "Acompanhe o andamento da solicitação."
   - Descrição: "Não há ação pendente sua no momento. Você verá aqui novas instruções se forem necessárias."

Renderiza com `SectionCard` ou `<Card>` padrão (decidir na implementação por reuso visual; recomendo `<Card>` para não destoar do entorno).

**Vetos de linguagem** (não usar): "garantia", "garantido", "SLA", "prazo legal", "vencimento", "deferido", "indeferido", "deferimento", "indeferimento". Reaproveitar a regra D-CIDADAO do PR 5b — adicionar teste vitest verificando os 9 termos.

---

### 2.3 Detalhe do processo do servidor

#### A. `frontend/app/(app)/processos/[id]/page.tsx`

- Importar `ActionsMenu` de `@/components/ui/actions-menu`, `Printer` (lucide).
- Linhas 318-320 (loading): trocar por skeleton equivalente ao cidadão (3 cards stacked).
- Linhas 365-462 (actions): reorganizar em **3 grupos** dentro do `actions={…}`:
  1. **Badges** (não-actions): `flex flex-wrap gap-1` — Ativo/Inativo + Sigiloso + Externo + Prazo.
  2. **Ações primárias**: `<Button size="sm">` com ícone:
     - "PDF completo" (substitui o botão atual em [445-449](frontend/app/(app)/processos/[id]/page.tsx#L445-L449)).
  3. **ActionsMenu "Imprimir"** com 4 itens:
     - "Capa" → `processoCapaUrl`
     - "Etiqueta" → `etiquetaUnicaUrl`
     - "Etiqueta dupla" → `etiquetaDuplaUrl`
     - "Em fila (background)" → `gerarBg.mutate()`
  4. **ClassificarSigiloDialog** separado.

   Resultado visual: badges à esquerda, "PDF completo" + dropdown "Imprimir ▾" + sigilo à direita.

- Linhas 519-525 (CardHeader visão geral): **remover** a linha "aberto em" (já está no PageHeader.description). Manter só `<CardTitle>` ou trocar `CardTitle` por `<dt>` resumindo o assunto.
- Linhas 368-376: manter "Ativo / Inativo" — D-LINGUAGEM-ENCERRADO veta replace global. Mas mudar `intent`:
  - `Ativo` → mantém `success`.
  - `Inativo` → trocar de `neutral` para `info` quando `p.arquivado` (se houver flag) ou manter `neutral` se só significa "desativado". **Inspecionar `ProcessoDetail.ativo` semântica antes de mudar** — se for sempre "arquivado/encerrado", trocar label para "Encerrado" + intent `info`; senão deixar.
- Linhas 639-642 (movimentações vazias): `EmptyState icon={Clock} title="Sem movimentações registradas" description="Use 'Ações de tramitação' para registrar a primeira movimentação." />`.
- Linhas 688-697 (botão "Solicitar complementação"): mover para **dentro do CardHeader** do checklist (não como `<div className="flex justify-end">` solto). Visual:
  ```tsx
  <Card>
    <CardHeader>
      <div className="flex items-center justify-between gap-2">
        <CardTitle>Documentos exigidos</CardTitle>
        {podeAtualizarProcesso && !aberta && (
          <Button variant="secondary" size="sm" onClick={() => setSolicitarOpen(true)}
                  disabled={!checklistQ.data}>
            Solicitar complementação
          </Button>
        )}
      </div>
    </CardHeader>
  ```
  (Pode exigir refactor mínimo do `ChecklistDocumentosCard` para aceitar `headerSlot`.)
- Linhas 569-585 (linha "Prazo previsto" no card Visão geral): **remover** — o badge no header já mostra. Eliminar duplicação.

#### B. `frontend/components/ui/actions-menu.tsx` (NOVO)

```tsx
"use client";

import { LucideIcon, MoreHorizontal } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export interface ActionsMenuItem {
  label: string;
  icon?: LucideIcon;
  onClick: () => void;
  disabled?: boolean;
}

interface Props {
  label: string;           // ex: "Imprimir"
  icon?: LucideIcon;       // ex: Printer
  items: ActionsMenuItem[];
}
```

Comportamento:
- `<Button variant="secondary" size="sm">` com ícone + label + chevron-down.
- Onclick abre `<ul>` posicionado `absolute right-0 mt-1` com `role="menu"`.
- Fecha em: blur, ESC, click em item, click fora.
- Focus-trap simples com `onKeyDown` (Arrow up/down move; Enter aciona; ESC fecha).
- **Sem nova lib** (não radix, não headlessui).

#### C. `frontend/components/ChecklistDocumentosCard.tsx`

- Adicionar prop opcional `headerSlot?: React.ReactNode` para o botão "Solicitar complementação" subir para o header. Default = sem slot.

---

### 2.4 Dashboard executivo

#### A. `frontend/app/(app)/dashboard/page.tsx`

- Importar `FilterBar` de `@/components/ui/filter-bar`, `Checkbox` de `@/components/ui/checkbox`, `EmptyState`, `Search`.
- Linhas 170-276 (PageHeader): **simplificar** `actions={…}` para vazio ou só Export (decidir abaixo).
- **Inserir após PageHeader** uma `<FilterBar>` com 5 grupos:
  1. **Unidade** (`UnidadePicker`)
  2. **Serviço** (`<select>` existente)
  3. **Legado** (`<Checkbox>` em vez de `<input type="checkbox">` cru)
  4. **Período** (segmented control existente)
  5. **Exportar** (PDF + CSV) — slot `<FilterBar.Actions>` à direita.
- Linhas 212-223 (toggle legado): trocar `<input>` cru por `<Checkbox>`.
- Linha 279, 340, 384 (3 grids de KPIs): inserir headers de seção:
  ```tsx
  <SectionCard title="Volume" icon={FileText}>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">...6 cards</div>
  </SectionCard>

  <SectionCard title="Documentação e complementações" icon={Layers}>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">...5 cards</div>
  </SectionCard>

  <SectionCard title="Prazos por serviço" icon={Clock}
               description="Prazo end-to-end por serviço (PR 5b). Não confundir com SLA por etapa do workflow.">
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">...8 cards</div>
  </SectionCard>
  ```
  (Adaptar `SectionCard` para tornar `step` opcional — ver §1.1.)
- Linhas 117-133 (skeleton de loading): aumentar para 3 grids de 4 KpiSkeletons (= 12 visíveis).
- Linhas 503-504, 535-536, 568-569, 601-604 (empty states de gráficos): substituir por:
  ```tsx
  <EmptyState icon={Search} title="Sem dados no período"
              description="Tente um período maior ou remova filtros." />
  ```
- Linha 411-414 (KPI "Sem prazo"): adicionar tooltip `title="Processos sem prazo cadastrado (legado ou serviço sem prazo definido). Não entra no cálculo de % no prazo."`.
- Linha 396-401 (KPI "Vencendo"): adicionar tooltip explicando regra dos 20%.

#### B. `frontend/components/ui/filter-bar.tsx` (NOVO)

```tsx
interface FilterBarProps {
  children: React.ReactNode;
  className?: string;
}

interface FilterBarGroupProps {
  label?: string;
  children: React.ReactNode;
}

export function FilterBar({ children, className }: FilterBarProps) {
  return (
    <div className={cn(
      "flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface-1 p-3",
      className
    )}>
      {children}
    </div>
  );
}

FilterBar.Group = function FilterBarGroup({ label, children }: FilterBarGroupProps) {
  return (
    <div className="min-w-0">
      {label && (
        <div className="mb-1 text-[10px] uppercase tracking-wide text-foreground-subtle">
          {label}
        </div>
      )}
      {children}
    </div>
  );
};

FilterBar.Actions = function FilterBarActions({ children }: { children: React.ReactNode }) {
  return <div className="ml-auto flex items-end gap-2">{children}</div>;
};
```

Sem lógica de filtro. Só layout responsivo.

---

### 2.5 Catálogo administrativo de serviços

#### A. `frontend/app/(app)/servicos/page.tsx`

- Importar `EmptyState`, `Plus`, `Search`, `SkeletonRow` (já existe em `@/components/ui/skeleton`).
- Linhas 244-251 (loading da tabela):
  ```tsx
  {servicosQ.isLoading && (
    <>
      <SkeletonRow cols={6} />
      <SkeletonRow cols={6} />
      <SkeletonRow cols={6} />
      <SkeletonRow cols={6} />
      <SkeletonRow cols={6} />
    </>
  )}
  ```
- Linhas 252-258 (empty da tabela): **substituir** o `<TR><TD colSpan>` por **EmptyState fora da tabela** (renderizar `<Table>` só se houver itens; senão `<EmptyState />`):
  ```tsx
  {servicosQ.data && servicosQ.data.length === 0 ? (
    <EmptyState icon={ClipboardList}
      title="Nenhum serviço cadastrado"
      description="Cadastre o primeiro serviço da Carta de Serviços do município."
      action={canCreate && <Button onClick={openNew}>Novo serviço</Button>}
    />
  ) : (
    <Table>...</Table>
  )}
  ```
- Linhas 326-481 (Dialog interno): **reorganizar em 3 `SectionCard`s** (ou `<fieldset>` se preferir HTML semântico — recomendo `SectionCard` por consistência):

  **Bloco 1 — Identificação do serviço**
  - `nome`, `slug`, `categoria`, `descricao_curta`, `descricao_detalhada`, `publico_alvo`

  **Bloco 2 — Configuração operacional**
  - `id_unidade_responsavel`, `id_assunto_padrao`, `id_tipo_processo_padrao`,
    `id_especie_documental_padrao`, `prazo_estimado_dias`, `destaque`,
    `ordem_exibicao`, `nivel_sigilo_padrao`, `canal_entrada_permitido` (se exposto)

  **Bloco 3 — Orientações ao cidadão**
  - `instrucoes_cidadao`, `documentos_exigidos` (sublista atual),
    `texto_confirmacao`

  Cada bloco com `description` curta orientando o servidor.

- Linhas 333-349 (slug): validação inline visual:
  - Se `form.slug` não casa `/^[a-z0-9](?:[a-z0-9-]{1,78}[a-z0-9])?$/`, mostrar erro vermelho embaixo sem bloquear digitação.
- Linhas 476-480 (erro do backend): **duplicar** o `<div role="alert">` também **no topo do Dialog** (acima do bloco 1) quando `err` está presente, **e** fazer scroll automático para esse alert no `useEffect` quando `err` muda. Isso garante que servidor vê o erro mesmo com formulário longo.
- Linhas 289-296 (confirm desativar): substituir mensagem por:
  - Ao **desativar**: "Cidadãos não conseguirão mais solicitar este serviço a partir de agora. Processos já abertos não são afetados."
  - Ao **ativar**: "Este serviço voltará a aparecer no portal público para solicitação."
- Linhas 442-444 (sub-empty "Nenhum documento"): trocar por microcopy explicativa:
  ```tsx
  <p className="text-xs text-foreground-muted">
    Nenhum documento exigido. Use <strong>Adicionar</strong> para listar os
    documentos que o cidadão deve anexar (obrigatórios e opcionais).
  </p>
  ```

---

## 3. Ajuste mínimo no design system

### 3.1 `Button` — adicionar suporte a `asChild`

Atualmente [Button](frontend/components/ui/button.tsx) só renderiza `<button>`. Para envolver `<Link>` (necessário em ServicoCard) sem reescrever classes, adicionar prop opcional `asChild`:

```tsx
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  asChild?: boolean;
}

// Quando asChild=true, clonar o filho injetando className.
```

Implementação simples (não usar Radix Slot — implementar com `React.Children.only` + `React.cloneElement`). ~10 linhas.

### 3.2 `SectionCard` — extrair de processos/novo

Mover [SectionCard local](frontend/app/(app)/processos/novo/page.tsx#L47-L84) para `frontend/components/ui/section-card.tsx` com a assinatura ajustada:

```tsx
interface SectionCardProps {
  title: string;
  description?: string;
  icon?: React.ComponentType<{ className?: string }>;
  step?: number;          // mantém para reuso em /processos/novo
  children: React.ReactNode;
  className?: string;
}
```

Atualizar [processos/novo/page.tsx](frontend/app/(app)/processos/novo/page.tsx) para importar do novo path. **Não mudar o comportamento visual** dessa página.

### 3.3 Sem outras mudanças no DS

- `Badge`, `Card`, `KpiCard`, `Skeleton`, `EmptyState`, `Dialog`, `Toast`, `Table` — intactos.

---

## 4. Helper de badges (`lib/badges.ts`)

```ts
import type { LucideIcon } from "lucide-react";
import { AlertCircle, AlertTriangle, Check, CheckCircle2, Clock,
         Eye, Lock, Pause } from "lucide-react";
import type { ProcessoDetail, PrazoInfo, PrazoCidadao,
              CidadaoProcessoDetail, ChecklistItem } from "@/lib/api";

type Intent = "neutral" | "success" | "danger" | "warning" | "info" | "brand";
type Modo = "servidor" | "cidadao";

export interface BadgeSpec {
  intent: Intent;
  label: string;
  icon?: LucideIcon;
}

export function statusProcessoBadge(
  p: { ativo: boolean },
  modo: Modo
): BadgeSpec {
  if (p.ativo) {
    return modo === "cidadao"
      ? { intent: "success", label: "Em andamento", icon: Clock }
      : { intent: "success", label: "Em tramitação", icon: Clock };
  }
  return modo === "cidadao"
    ? { intent: "info", label: "Concluído", icon: CheckCircle2 }
    : { intent: "info", label: "Encerrado", icon: CheckCircle2 };
}

export function prazoBadge(
  prazo: PrazoInfo | PrazoCidadao,
  modo: Modo
): BadgeSpec | null {
  // Reusa lógica que já está inline em [(app)/processos/[id]/page.tsx:85-122]
  // e [cidadao/processos/[id]/page.tsx:50-78]. Centraliza aqui.
  // Detalhamento das 6 vs 5 status já está na tabela 3.9 do escopo predecessor.
}

export function documentoBadge(item: ChecklistItem): BadgeSpec {
  if (item.enviado) return { intent: "success", label: "Enviado" };
  return item.obrigatorio
    ? { intent: "warning", label: "Obrigatório · pendente" }
    : { intent: "neutral", label: "Opcional · pendente" };
}
```

Refatorar `processos/[id]/page.tsx` (servidor + cidadão) para usar `prazoBadge(...)` em vez do switch local. Reduz duplicação e garante consistência de microcopy.

---

## 5. Ordem de implementação (20 passos)

Cada passo deve ser commitado individualmente para facilitar review e rollback.

### Fase A — Fundação do DS

1. **Extrair `SectionCard`** para `components/ui/section-card.tsx`. Atualizar import em `processos/novo/page.tsx`. Vitest: garantir que o teste existente de `/processos/novo` segue verde.
2. **Adicionar `asChild` ao `Button`** com `React.cloneElement`. Vitest: 1 teste novo cobrindo `<Button asChild><a /></Button>` propaga className.
3. **Criar `ActionsMenu`** em `components/ui/actions-menu.tsx`. Vitest: render + ESC fecha + click em item dispara `onClick`.
4. **Criar `FilterBar`** em `components/ui/filter-bar.tsx`. Vitest: render dos slots `Group` e `Actions`.
5. **Criar `lib/badges.ts`** com `statusProcessoBadge`, `prazoBadge`, `documentoBadge`. Vitest: matriz de 6×2 status (PR 5b) + 4 status documental.

### Fase B — Portal cidadão (jornada 1)

6. **Refactor `app/cidadao/servicos/page.tsx`**: skeleton, EmptyState, microcopy de prazo, `<abbr>` + legenda, `<Button asChild>`, hover.
7. **Refactor `app/cidadao/servicos/[slug]/page.tsx`**: skeleton, EmptyState de erro, microcopy de prazo, `<abbr>` + legenda, botão sticky mobile.
8. **Refactor `app/cidadao/servicos/[slug]/solicitar/page.tsx`**: skeleton, barra de progresso de chars, microcopy de indisponível.

### Fase C — Detalhe cidadão (jornada 2)

9. **Criar `ProximosPassosCard`** em `components/ProximosPassosCard.tsx`. Vitest: 4 cenários (encerrado, complementação aberta, checklist incompleto, em ordem) + linguagem vetada.
10. **Refactor `app/cidadao/processos/[id]/page.tsx`**: skeleton, EmptyState em anexos/movimentações, `<ProximosPassosCard>` inserido, badge "Concluído" intent info, tooltip para número interno, helpers de `lib/badges.ts`.

### Fase D — Detalhe servidor (jornada 3)

11. **Refactor `app/(app)/processos/[id]/page.tsx`**: reorganizar `actions` em (Badges) + (PDF completo + ActionsMenu Imprimir + Sigilo); usar `ActionsMenu` para Capa/Etiqueta/Dupla/Em fila.
12. **Refactor `ChecklistDocumentosCard`**: adicionar prop `headerSlot` para botão "Solicitar complementação".
13. **Mover botão "Solicitar complementação"** para o `headerSlot` do `ChecklistDocumentosCard` na aba Documentos.
14. **Remover duplicação** de "Aberto em" entre PageHeader e CardHeader Visão geral; remover linha "Prazo previsto" duplicada no card Visão geral.
15. **EmptyState** em movimentações vazias.
16. **Usar `lib/badges.ts`** no PrazoBadge inline.

### Fase E — Dashboard (jornada 4)

17. **Refactor `app/(app)/dashboard/page.tsx`**: 
    - Inserir `<FilterBar>` abaixo do PageHeader com 5 grupos.
    - Envolver os 3 grids de KPIs em `<SectionCard>` com títulos + microcopy.
    - Trocar `<input>` cru por `<Checkbox>` no Legado.
    - EmptyState nos 4 gráficos vazios.
    - Tooltips em "Sem prazo" e "Vencendo".
    - Aumentar skeleton para 12 KpiSkeletons.

### Fase F — Catálogo (jornada 5)

18. **Refactor `app/(app)/servicos/page.tsx`** — tabela: `SkeletonRow` no loading; `<EmptyState>` (fora da tabela) no vazio.
19. **Refactor `app/(app)/servicos/page.tsx`** — Dialog: 3 `<SectionCard>` para Identificação / Operacional / Orientações; validação inline de slug; erro do backend duplicado no topo.
20. **Microcopy do `confirm`** ao desativar/ativar serviço.

### Fase G — Testes finais

- Rodar vitest completo: deve passar de ~80 para ~95-100 testes.
- Rodar Playwright completo: existentes não devem regredir; adicionar `tests-e2e/specs/ux1-smoke.spec.ts` (3 testes mínimos).
- Verificação manual mobile (360/414/768) em pelo menos:
  - `/cidadao/servicos`
  - `/cidadao/servicos/[slug]`
  - `/cidadao/processos/[id]`
  - `/processos/[id]`
  - `/dashboard`

---

## 6. Testes esperados

### 6.1 Vitest

| Suite | Status | Adição |
|---|---|---|
| `components/ui/__tests__/Button.test.tsx` | criar se não existir | 1 teste novo: `asChild` propaga className para filho. |
| `components/ui/__tests__/SectionCard.test.tsx` | criar | Renderiza title/description/icon/step opcionais. |
| `components/ui/__tests__/ActionsMenu.test.tsx` | criar | Abre/fecha; ESC fecha; click em item dispara `onClick`. |
| `components/ui/__tests__/FilterBar.test.tsx` | criar | Slots `Group` e `Actions` renderizam. |
| `lib/__tests__/badges.test.ts` | criar | Matriz: 2 status processo × 2 modos; 6 status prazo × 2 modos; 4 status documental. |
| `components/__tests__/ProximosPassosCard.test.tsx` | criar | 4 cenários (encerrado, complementação aberta, checklist incompleto, em ordem). **+1 teste de linguagem vetada**: nenhum render contém "SLA", "garantia", "garantido", "prazo legal", "vencimento", "deferido", "indeferido". |
| `app/(app)/dashboard/__tests__/page.test.tsx` | estender | Não pode quebrar os 12 testes PR 5a + 5b. Adicionar: `<FilterBar>` está abaixo do PageHeader; 3 `<SectionCard>` ("Volume", "Documentação e complementações", "Prazos por serviço") visíveis; EmptyState em gráficos vazios. |
| `app/(app)/servicos/__tests__/page.test.tsx` | estender | Loading mostra `SkeletonRow`; vazio mostra `EmptyState` com botão "Novo serviço"; Dialog tem 3 `SectionCard`s identificados por `aria-label` ou heading. |
| `app/cidadao/servicos/__tests__/page.test.tsx` | estender | Botão "Solicitar" agora é `<Button asChild>` (testar via DOM); microcopy "até N dias"; legenda de obrigatório presente; hover state. |
| `app/cidadao/servicos/[slug]/__tests__/detalhe.test.tsx` | estender | Microcopy de prazo "até N dias"; EmptyState quando 404; botão sticky no DOM. |
| `app/cidadao/processos/[id]/__tests__/page.test.tsx` | criar | `ProximosPassosCard` renderizado nos 4 cenários; EmptyState em anexos/movimentações; helpers de `lib/badges.ts` integrados. |
| `app/(app)/processos/[id]/__tests__/page.test.tsx` | criar (se não existir) | `ActionsMenu` "Imprimir" tem 4 itens; botão "Solicitar complementação" agora no header do checklist; sem duplicação de "Aberto em". |

### 6.2 Playwright (`tests-e2e/specs/ux1-smoke.spec.ts`, novo)

3 testes mínimos:

1. **Jornada cidadão completa**:
   - Cidadão entra → `/cidadao/servicos` mostra cards.
   - Clica em um → vê detalhes com `Prazo estimado: até` (regex).
   - Abre processo existente → vê seção `[data-testid="proximos-passos"]`.

2. **Dashboard com seções**:
   - Admin login → `/dashboard` → vê headings "Volume", "Documentação e complementações", "Prazos por serviço".
   - `[role="region"]` ou marcador equivalente para `FilterBar`.

3. **Linguagem cidadã livre de termos vetados** (defesa em profundidade):
   - `/cidadao/processos/{id}` body inteiro NÃO contém:
     `garantia`, `garantido`, `prazo legal`, `"sla"`, `vencimento contratual`, `deferido`, `indeferido`.

Os outros 3 specs (existentes: `prazos.spec.ts` PR 5b, etc.) **não podem regredir**.

### 6.3 Backend

**Zero teste backend.** UX-1 não toca em endpoint, model, schema, dashboard SQL, prazo, assinatura, RLS. Os 291 pytest devem seguir verdes inalterados.

---

## 7. Anti-escopo (vetado)

| Categoria | Veto |
|---|---|
| **Backend** | ✗ migration · ✗ endpoint novo · ✗ alteração de payload · ✗ alteração de schema · ✗ alteração de regra de prazo · ✗ alteração de dashboard SQL · ✗ alteração de service layer |
| **Domínio** | ✗ alteração de assinatura · ✗ alteração de RLS/permissão · ✗ alteração em workflow · ✗ mudança em cálculos (KPI, prazo, conclusão) |
| **Frontend estrutural** | ✗ redesign total · ✗ nova lib UI (radix/shadcn/headlessui) · ✗ tema novo · ✗ modo dark · ✗ refactor grande de providers · ✗ mudança em App Router |
| **Plataforma** | ✗ mobile app · ✗ PWA · ✗ Service Worker · ✗ i18n |
| **Microcopy** | ✗ replace global de "Inativo" → "Encerrado" · ✗ mudança em mensagens de e-mail · ✗ mudança em PDFs/comprovantes |

**Em caso de dúvida sobre se algo está in/out: descartar do PR atual.**

---

## 8. Critério de "pronto"

- [ ] 0 ocorrências de `<p>Carregando…</p>` em telas das 5 jornadas (grep do diff).
- [ ] 0 ocorrências de `<p>Nenhum X.</p>` ou `<p>Sem dados.</p>` em telas das 5 jornadas.
- [ ] Dashboard tem 3 headings de seção identificáveis por `<h2>` ou role.
- [ ] Detalhe cidadão exibe "Próximos passos" antes da Visão geral em todos os cenários.
- [ ] Detalhe servidor: PageHeader ocupa ≤ 2 linhas em desktop 1366px (manual check).
- [ ] Catálogo Dialog tem 3 seções visualmente distintas.
- [ ] Portal cidadão: linguagem de prazo é "até N dias" em todas as 3 telas.
- [ ] pytest backend: 291/291 inalterado.
- [ ] vitest: ≥ 95 testes verdes (vs 80 atuais).
- [ ] Playwright: existentes verdes + `ux1-smoke.spec.ts` 3/3.
- [ ] Mobile manual em 360/414/768: nenhum overflow horizontal nem botão cortado em telas das 5 jornadas.

---

## 9. Mensagem de commit final esperada

```
feat(ux): UX-1 — polimento da jornada principal (cidadão / servidor / gestor)

Aplica o design system existente nas 5 jornadas principais sem alterar
regra de negócio, payload, endpoint, migration ou cálculo.

Fundação:
- Extrai SectionCard para components/ui (de processos/novo).
- Adiciona ActionsMenu, FilterBar, ProximosPassosCard.
- Adiciona prop `asChild` ao Button (cloneElement).
- Centraliza badges em lib/badges.ts (status processo, prazo, documento).

Cidadão (portal + processo):
- Skeleton + EmptyState em todas as telas.
- Card "Próximos passos" com 4 estados calculados no frontend a partir
  do payload existente (D-PROXIMOS-PASSOS).
- Microcopy de prazo "até N dias", legenda de obrigatório, botão sticky
  mobile no detalhe do serviço.

Servidor:
- Botões de impressão agrupados em ActionsMenu "Imprimir" (D-PRINT-MENU).
- Botão "Solicitar complementação" subiu para o header do checklist.
- Remove duplicação de "Aberto em" e "Prazo previsto".

Dashboard:
- Filtros migrados para FilterBar abaixo do PageHeader (D-DASHBOARD-FILTROS).
- 3 SectionCard agrupam as 19 KPI cards por tema.
- Tooltips em "Sem prazo" e "Vencendo"; EmptyState em gráficos.

Catálogo:
- Dialog em 3 SectionCard: Identificação / Operacional / Orientações
  (D-FIELDSETS-CATALOGO).
- SkeletonRow + EmptyState na tabela; validação inline de slug;
  erro do backend espelhado no topo do dialog.

Zero alteração em backend, RLS, assinatura, prazo, dashboard SQL.
Backend pytest 291/291 inalterado.
Vitest 80 → ~98 (adições). Playwright +1 spec (ux1-smoke).
```

---

## 10. Próximo passo

Aguardo "ok" para iniciar a Fase A (passos 1-5 do §5). Implementarei commit
a commit, validando vitest entre cada fase. Não inicio sem autorização.
