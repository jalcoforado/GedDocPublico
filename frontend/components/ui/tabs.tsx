"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

interface TabsContextValue {
  value: string;
  onChange: (value: string) => void;
  idBase: string;
  /** Valores cujos painéis estão de fato no DOM agora. */
  montados: ReadonlySet<string>;
  registrar: (value: string, montado: boolean) => void;
}

const TabsContext = React.createContext<TabsContextValue | null>(null);

function useTabs(quem: string): TabsContextValue {
  const ctx = React.useContext(TabsContext);
  if (!ctx) throw new Error(`${quem} deve ser usado dentro de <Tabs>`);
  return ctx;
}

interface TabsProps {
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
  className?: string;
}

/**
 * Tabs controladas com ARIA completo (UX-02 fatia 2.5): tablist/tab/tabpanel
 * ligados por aria-controls/aria-labelledby, roving tabindex e navegação por
 * setas/Home/End com wrap. Seleção segue o foco (padrão APG para conteúdo
 * carregado no cliente).
 */
export function Tabs({ value, onChange, children, className }: TabsProps) {
  const idBase = React.useId();

  // Registro dos painéis montados. Existe por um motivo de acessibilidade, não
  // de arquitetura: `aria-controls` é um IDREF, e IDREF que não resolve é
  // violação de ARIA. Com painel inativo DESMONTADO (o padrão), a aba inativa
  // apontava para um id inexistente — o leitor de tela promete um destino que
  // não está lá. Emitir o atributo só quando o painel existe é o que o APG
  // admite; a alternativa seria manter tudo montado sempre, que custa render e
  // query em aba que ninguém abriu.
  const [montados, setMontados] = React.useState<ReadonlySet<string>>(() => new Set());
  const registrar = React.useCallback((v: string, montado: boolean) => {
    setMontados((antes) => {
      if (antes.has(v) === montado) return antes; // sem troca, sem re-render
      const novo = new Set(antes);
      if (montado) novo.add(v);
      else novo.delete(v);
      return novo;
    });
  }, []);

  const ctx = React.useMemo(
    () => ({ value, onChange, idBase, montados, registrar }),
    [value, onChange, idBase, montados, registrar],
  );
  return (
    <TabsContext.Provider value={ctx}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

export interface TabDef {
  value: string;
  /**
   * Conteúdo do botão. Aceita nó para o caso do contador ao lado do texto
   * ("Documentos [3]"), que o detalhe do processo usa.
   *
   * Quando o rótulo não for texto puro, passe `nomeAcessivel` — o leitor de
   * tela lê o conteúdo inteiro, e "Documentos 3" vira ruído se o número for
   * decorativo. `getByRole("tab", { name })` nos testes também usa este nome.
   */
  label: React.ReactNode;
  /** Nome acessível quando `label` não é texto puro. */
  nomeAcessivel?: string;
  disabled?: boolean;
}

/**
 * Aparência da barra. Não é preferência estética: as duas já existiam nas
 * telas, e trocar a de uma tela ao migrá-la seria regressão visual entregue
 * de carona numa correção de acessibilidade.
 *
 * - `sublinhado` (padrão) — barra com borda embaixo e a ativa sublinhada.
 *   Detalhe do processo, jobs, edição de tenant.
 * - `pill` — botões arredondados, sem borda de barra. As telas de pagamentos
 *   (autorização, tesouraria) usam esta dentro do `PageHeader`.
 */
export type TabVariant = "sublinhado" | "pill";

interface TabListProps {
  tabs: TabDef[];
  "aria-label": string;
  className?: string;
  variant?: TabVariant;
}

const CLASSES_BARRA: Record<TabVariant, string> = {
  sublinhado: "flex gap-1 border-b border-border",
  pill: "flex gap-1 py-2",
};

const CLASSES_BOTAO: Record<TabVariant, { base: string; ativa: string; inativa: string }> = {
  sublinhado: {
    base: "-mb-px border-b-2 px-3 py-2 text-sm font-medium",
    ativa: "border-brand text-brand",
    inativa:
      "border-transparent text-foreground-muted hover:border-border-strong hover:text-foreground",
  },
  pill: {
    base: "rounded-md px-3 py-1.5 text-sm font-medium",
    ativa: "bg-brand/12 text-brand dark:bg-brand/25 dark:text-brand-light",
    inativa: "text-muted-foreground hover:bg-muted hover:text-foreground",
  },
};

export function TabList({ tabs, className, variant = "sublinhado", ...aria }: TabListProps) {
  const { value, onChange, idBase, montados } = useTabs("TabList");
  const refs = React.useRef(new Map<string, HTMLButtonElement>());

  const habilitadas = tabs.filter((t) => !t.disabled);

  function ativar(v: string) {
    onChange(v);
    refs.current.get(v)?.focus();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    const atual = habilitadas.findIndex((t) => t.value === value);
    if (atual < 0) return;
    let proxima: number | null = null;
    if (e.key === "ArrowRight") proxima = (atual + 1) % habilitadas.length;
    else if (e.key === "ArrowLeft") proxima = (atual - 1 + habilitadas.length) % habilitadas.length;
    else if (e.key === "Home") proxima = 0;
    else if (e.key === "End") proxima = habilitadas.length - 1;
    if (proxima === null) return;
    e.preventDefault();
    ativar(habilitadas[proxima].value);
  }

  return (
    <div
      role="tablist"
      {...aria}
      onKeyDown={onKeyDown}
      className={cn(CLASSES_BARRA[variant], className)}
    >
      {tabs.map((t) => {
        const ativa = t.value === value;
        return (
          <button
            key={t.value}
            ref={(el) => {
              if (el) refs.current.set(t.value, el);
              else refs.current.delete(t.value);
            }}
            type="button"
            role="tab"
            id={`${idBase}-tab-${t.value}`}
            aria-selected={ativa}
            aria-label={t.nomeAcessivel}
            aria-controls={montados.has(t.value) ? `${idBase}-panel-${t.value}` : undefined}
            tabIndex={ativa ? 0 : -1}
            disabled={t.disabled}
            onClick={() => onChange(t.value)}
            className={cn(
              "transition-colors duration-fast",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              "disabled:cursor-not-allowed disabled:opacity-50",
              CLASSES_BOTAO[variant].base,
              ativa ? CLASSES_BOTAO[variant].ativa : CLASSES_BOTAO[variant].inativa,
            )}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

interface TabPanelProps {
  value: string;
  children: React.ReactNode;
  className?: string;
  /**
   * Mantém o painel MONTADO quando inativo, apenas escondido.
   *
   * O padrão (`false`) desmonta, que é o certo para painel sem estado: não
   * paga render nem query de aba que ninguém está vendo.
   *
   * Ligue quando a aba tiver **estado local que o usuário perde sem aviso**.
   * O caso que motivou a opção é a edição de tenant: o admin marca módulos, dá
   * uma olhada em "Dados" e volta achando as marcações perdidas. Não há erro,
   * não há toast — o trabalho simplesmente sumiu. Preservar exige manter
   * montado; `key`/lift de estado resolveria também, mas espalha o estado da
   * aba por quem a hospeda.
   *
   * Custo: as queries das abas ocultas disparam junto com a visível. Só ligue
   * quando montar não tiver efeito colateral (sem toast, sem redirect).
   */
  keepMounted?: boolean;
}

export function TabPanel({ value, children, className, keepMounted }: TabPanelProps) {
  const { value: ativa, idBase, registrar } = useTabs("TabPanel");
  const visivel = value === ativa;
  const renderiza = visivel || !!keepMounted;

  // Antes do early return: hook não pode ficar atrás de condicional.
  React.useEffect(() => {
    registrar(value, renderiza);
    return () => registrar(value, false);
  }, [value, renderiza, registrar]);

  if (!renderiza) return null;
  return (
    <div
      role="tabpanel"
      id={`${idBase}-panel-${value}`}
      aria-labelledby={`${idBase}-tab-${value}`}
      // O atributo `hidden` sozinho é derrotado por qualquer `display:` que o
      // CSS aplique — daí a classe junto. E painel oculto sai da ordem de
      // tabulação: `tabIndex={0}` nele deixaria o Tab parar num lugar que o
      // usuário não vê.
      hidden={!visivel}
      tabIndex={visivel ? 0 : -1}
      className={cn(
        "pt-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        !visivel && "hidden",
        className,
      )}
    >
      {children}
    </div>
  );
}
