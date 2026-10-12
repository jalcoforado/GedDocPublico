"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  FileEdit,
  Gavel,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api, type SituacaoTramitacao } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { TRAMITACAO_ROTULO } from "@/components/pagamentos/situacoes";
import { SITUACOES_POR_ETAPA } from "@/components/pagamentos/statusFluxo";
import { BotaoExportarCsv } from "@/components/pagamentos/BotoesExportar";
import { fmtMoeda } from "@/components/pagamentos/format";

function StatusBadge({ situacao }: { situacao: SituacaoTramitacao }) {
  const cfg = TRAMITACAO_ROTULO[situacao];
  return <Badge intent={cfg.intent} icon={cfg.icon}>{cfg.label}</Badge>;
}

const ETAPA_INFO = [
  { label: "Rascunho", icon: FileEdit },
  { label: "Gestor", icon: Users },
  { label: "Validação", icon: ShieldCheck },
  { label: "Autoridade", icon: Gavel },
  { label: "Concluído", icon: CheckCircle2 },
] as const;

const POR_PAGINA = 25;

/**
 * Listagem de solicitações, paginada no SERVIDOR.
 *
 * Até 2026-10-12 a tela baixava todos os débitos do tenant e fazia no
 * navegador a busca, o corte por etapa e a contagem dos cartões. Com volume
 * real isso é a base inteira a cada abertura. Hoje o servidor devolve a página
 * (`/debitos/pagina`) e a contagem por situação (`/debitos/contagem-por-situacao`),
 * as duas sobre a mesma busca.
 *
 * Etapa (cartão) e situação (seletor) são filtros excludentes: escolher um
 * limpa o outro. Antes os dois se cruzavam no navegador, e a combinação mais
 * comum — etapa "Gestor" com situação "Autorizada" — dava lista vazia sem
 * explicar por quê.
 */
export default function SolicitacoesPage() {
  const { can } = useAuth();

  const [situacaoFiltro, setSituacaoFiltro] = useState<SituacaoTramitacao | "">("");
  const [etapaFiltro, setEtapaFiltro] = useState<number | null>(null);
  const [busca, setBusca] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  // A busca vai ao servidor: espera a pessoa parar de digitar.
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(busca.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [busca]);

  const situacoes: SituacaoTramitacao[] | undefined = situacaoFiltro
    ? [situacaoFiltro]
    : etapaFiltro !== null
      ? SITUACOES_POR_ETAPA[etapaFiltro]
      : undefined;

  const listQ = useQuery({
    queryKey: ["pag-solicitacoes-fluxo", situacoes, q, page],
    queryFn: () =>
      api.pagamentos.debitos.pagina({
        situacao_tramitacao: situacoes,
        q: q || undefined,
        page,
        page_size: POR_PAGINA,
      }),
    // Mantém a página anterior na tela enquanto a próxima chega.
    placeholderData: keepPreviousData,
  });

  const contagemQ = useQuery({
    queryKey: ["pag-solicitacoes-contagem", q],
    queryFn: () => api.pagamentos.debitos.contagemPorSituacao(q || undefined),
  });

  const data = listQ.data;
  const debitos = data?.items ?? [];
  const paginas = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const contagem = contagemQ.data ?? {};
  const totalDaEtapa = (idx: number) =>
    SITUACOES_POR_ETAPA[idx].reduce((soma, s) => soma + (contagem[s] ?? 0), 0);
  const filtrando = etapaFiltro !== null || !!situacaoFiltro || !!q;

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[{ label: "Pagamentos", href: "/m/pagamentos" }]}
        title="Solicitações de Pagamento"
        description="Acompanhe as solicitações no fluxo de aprovação"
        icon={ClipboardList}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {/* Exporta pela situação escolhida no seletor. A busca por texto e
                o cartão de etapa são só da tela e não entram no arquivo. */}
            <BotaoExportarCsv
              csvUrl={api.pagamentos.debitos.exportarCsvUrl({
                situacao_tramitacao: situacaoFiltro || undefined,
              })}
              rotulo="solicitações de pagamento"
            />
            {can("pagamento_solicitar") && (
              <Button asChild>
                <Link href="/m/pagamentos/solicitacoes/novo">Nova Solicitação</Link>
              </Button>
            )}
          </div>
        }
      />

      {/* Sumário clicável por etapa */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {ETAPA_INFO.map((etapa, idx) => (
          <button
            key={etapa.label}
            type="button"
            aria-pressed={idx === etapaFiltro}
            onClick={() => {
              setEtapaFiltro(etapaFiltro === idx ? null : idx);
              setSituacaoFiltro("");
              setPage(1);
            }}
            className="text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-card"
          >
            <KpiCard
              label={etapa.label}
              value={contagemQ.isLoading ? "…" : totalDaEtapa(idx)}
              icon={etapa.icon}
              intent={idx === etapaFiltro ? "info" : "default"}
              className={idx === etapaFiltro ? "ring-2 ring-info" : undefined}
            />
          </button>
        ))}
      </div>

      {/* Filtros */}
      <div className="flex gap-3 flex-wrap">
        <Input
          aria-label="Pesquisar solicitações"
          placeholder="Pesquisar por fornecedor, descrição, NF ou NE..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="flex-1 min-w-64"
        />
        <Select
          aria-label="Situação"
          value={situacaoFiltro}
          onChange={(e) => {
            setSituacaoFiltro(e.target.value as SituacaoTramitacao | "");
            setEtapaFiltro(null);
            setPage(1);
          }}
        >
          <option value="">Todas as situações</option>
          <option value="RASCUNHO">Rascunho</option>
          <option value="AGUARDANDO_GESTOR">Aguardando Gestor</option>
          <option value="AJUSTE_GESTOR">Ajuste (Gestor)</option>
          <option value="AGUARDANDO_VALIDACAO">Aguardando Validação</option>
          <option value="AJUSTE_VALIDACAO">Ajuste (Validação)</option>
          <option value="AGUARDANDO_AUTORIDADE">Aguardando Autoridade</option>
          <option value="AJUSTE_AUTORIDADE">Ajuste (Autoridade)</option>
          <option value="AUTORIZADA">Autorizada</option>
          <option value="REJEITADA_GESTOR">Rejeitada</option>
          <option value="INDEFERIDA_AUTORIDADE">Indeferida</option>
          <option value="CANCELADA">Cancelada</option>
        </Select>
      </div>

      <p className="text-sm text-foreground-muted" role="status">
        {listQ.isError
          ? "Não foi possível carregar as solicitações."
          : !data
            ? "Carregando…"
            : data.total === 1
              ? "1 solicitação"
              : `${data.total} solicitações`}
      </p>

      {/* Tabela */}
      <div className="border border-border rounded-card overflow-x-auto bg-surface-1 shadow-card">
        <Table>
          <THead>
            <TR>
              <TH>ID</TH>
              <TH>Fornecedor</TH>
              <TH>Descrição</TH>
              <TH className="text-right">Valor</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {listQ.isLoading && Array.from({ length: 5 }).map((_, i) => (
              <SkeletonRow key={i} cols={6} />
            ))}
            {!listQ.isLoading && debitos.length === 0 && (
              <TR>
                <TD colSpan={6} className="p-0">
                  <EmptyState
                    icon={ClipboardList}
                    title="Nenhuma solicitação encontrada"
                    description={
                      filtrando
                        ? "Ajuste os filtros para ver outras solicitações."
                        : "Crie a primeira solicitação de pagamento para começar."
                    }
                    className="border-none rounded-none"
                  />
                </TD>
              </TR>
            )}
            {debitos.map((d) => (
              <TR key={d.id}>
                <TD className="font-mono text-sm">#{d.id}</TD>
                <TD>{d.nome_fornecedor}</TD>
                <TD className="max-w-xs truncate">{d.descricao}</TD>
                <TD className="text-right tabular-nums">{fmtMoeda(d.valor_total)}</TD>
                <TD>
                  <StatusBadge situacao={d.situacao_tramitacao} />
                </TD>
                <TD className="text-right">
                  <Button asChild size="sm" variant="secondary">
                    <Link href={`/m/pagamentos/solicitacoes/${d.id}`}>Ver</Link>
                  </Button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>

      {paginas > 1 && (
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="secondary"
            size="sm"
            aria-label="Página anterior"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </Button>
          <span className="text-sm text-foreground-muted">
            Página {page} de {paginas}
          </span>
          <Button
            variant="secondary"
            size="sm"
            aria-label="Próxima página"
            disabled={page >= paginas}
            onClick={() => setPage(page + 1)}
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      )}
    </div>
  );
}
