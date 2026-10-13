"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, type LucideIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type SituacaoTramitacao } from "@/lib/api";
import { FilaSecao } from "@/components/pagamentos/FilaSecao";

type IntentKpi = "default" | "success" | "warning" | "danger" | "info";

export interface SecaoDaFila {
  situacao: SituacaoTramitacao;
  /** Título da lista. */
  titulo: string;
  /** Rótulo do cartão de contagem. */
  rotuloKpi: string;
  icon: LucideIcon;
  acaoLabel: string;
  intent?: IntentKpi;
}

interface FilaPorEtapaProps {
  titulo: string;
  descricao: string;
  icon: LucideIcon;
  secoes: SecaoDaFila[];
  vazio: { icon: LucideIcon; titulo: string; descricao: string };
  /** Classe de grade dos cartões (duas ou quatro colunas). */
  gradeKpi?: string;
}

/** Linhas por página de cada seção. */
export const POR_PAGINA_DA_FILA = 10;

/**
 * Uma seção da fila: pede ao servidor só a página visível da situação dela.
 * Antes a página baixava a fila inteira e repartia no navegador — com a fila
 * de concluídas crescendo para sempre, era a que mais pesava.
 */
function SecaoPaginada({ secao, total }: { secao: SecaoDaFila; total: number }) {
  const [page, setPage] = useState(1);
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA_DA_FILA));
  // A fila encolhe quando alguém decide um item: a página atual pode deixar de
  // existir. Em vez de mostrar uma página vazia, recua para a última.
  const pagina = Math.min(page, paginas);

  const q = useQuery({
    queryKey: ["pag-fila-etapa", secao.situacao, pagina],
    queryFn: () =>
      api.pagamentos.debitos.pagina({
        situacao_tramitacao: [secao.situacao],
        page: pagina,
        page_size: POR_PAGINA_DA_FILA,
      }),
    placeholderData: keepPreviousData,
    enabled: total > 0,
  });

  if (total === 0) return null;
  if (q.isLoading) return <Skeleton className="h-40 w-full" />;
  if (q.isError) {
    return (
      <EmptyState
        icon={secao.icon}
        title={`Não foi possível carregar "${secao.titulo}"`}
        description="Tente de novo em instantes. Se persistir, avise o suporte."
      />
    );
  }

  return (
    <div className="space-y-2">
      <FilaSecao
        titulo={secao.titulo}
        icon={secao.icon}
        itens={q.data?.items ?? []}
        acaoLabel={secao.acaoLabel}
      />
      {paginas > 1 && (
        <nav
          className="flex items-center justify-end gap-2"
          aria-label={`Páginas de ${secao.titulo}`}
        >
          <Button
            variant="secondary"
            size="sm"
            aria-label="Página anterior"
            disabled={pagina <= 1}
            onClick={() => setPage(pagina - 1)}
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </Button>
          <span className="text-sm text-foreground-muted">
            Página {pagina} de {paginas}
          </span>
          <Button
            variant="secondary"
            size="sm"
            aria-label="Próxima página"
            disabled={pagina >= paginas}
            onClick={() => setPage(pagina + 1)}
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        </nav>
      )}
    </div>
  );
}

/**
 * Corpo das quatro filas por etapa (gestor, validação, autoridade,
 * concluídas). Os cartões vêm da contagem do servidor — o total real, não o
 * tamanho do que foi baixado — e cada seção pagina por conta própria.
 */
export function FilaPorEtapa({
  titulo,
  descricao,
  icon,
  secoes,
  vazio,
  gradeKpi = "grid grid-cols-2 gap-3",
}: FilaPorEtapaProps) {
  const contagemQ = useQuery({
    queryKey: ["pag-fila-etapa-contagem"],
    queryFn: () => api.pagamentos.debitos.contagemPorSituacao(),
  });
  const contagem = contagemQ.data ?? {};
  const totalDe = (s: SituacaoTramitacao) => contagem[s] ?? 0;
  const totalDaFila = secoes.reduce((soma, s) => soma + totalDe(s.situacao), 0);

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[
          { label: "Pagamentos", href: "/m/pagamentos" },
          { label: "Solicitações", href: "/m/pagamentos/solicitacoes" },
        ]}
        title={titulo}
        description={descricao}
        icon={icon}
      />

      <div className={gradeKpi}>
        {secoes.map((s) => (
          <KpiCard
            key={s.situacao}
            label={s.rotuloKpi}
            value={totalDe(s.situacao)}
            icon={s.icon}
            intent={s.intent}
          />
        ))}
      </div>

      {contagemQ.isLoading && <Skeleton className="h-40 w-full" />}

      {contagemQ.isError && (
        <EmptyState
          icon={vazio.icon}
          title="Não foi possível carregar a fila"
          description="Tente de novo em instantes. Se persistir, avise o suporte."
        />
      )}

      {contagemQ.isSuccess && totalDaFila === 0 && (
        <EmptyState icon={vazio.icon} title={vazio.titulo} description={vazio.descricao} />
      )}

      {secoes.map((s) => (
        <SecaoPaginada key={s.situacao} secao={s} total={totalDe(s.situacao)} />
      ))}
    </div>
  );
}
