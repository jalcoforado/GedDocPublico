"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  ClipboardList,
  FileEdit,
  Gavel,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useMemo, useState } from "react";
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
import { api, type DebitoOut, type SituacaoTramitacao } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { TRAMITACAO_ROTULO } from "@/components/pagamentos/situacoes";
import { getEtapaIndex } from "@/components/pagamentos/statusFluxo";
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

export default function SolicitacoesPage() {
  const { can } = useAuth();

  const [situacaoFiltro, setSituacaoFiltro] = useState<SituacaoTramitacao | "">("");
  const [etapaFiltro, setEtapaFiltro] = useState<number | null>(null);
  const [search, setSearch] = useState("");

  // Listar solicitações (todas, ou filtradas por situação)
  const listQ = useQuery({
    queryKey: ["pag-solicitacoes-fluxo", situacaoFiltro, search],
    queryFn: async () => {
      const debitos = await api.pagamentos.debitos.list({
        situacao_tramitacao: situacaoFiltro || undefined,
      });

      if (search) {
        return debitos.filter(d =>
          d.descricao.toLowerCase().includes(search.toLowerCase()) ||
          d.nome_fornecedor.toLowerCase().includes(search.toLowerCase()) ||
          d.numero_nf?.includes(search) ||
          d.numero_ne?.includes(search)
        );
      }

      return debitos;
    },
  });

  const debitos = useMemo(() => {
    return (listQ.data ?? []) as DebitoOut[];
  }, [listQ.data]);

  const contagemPorEtapa = useMemo(() => {
    const map: Record<number, number> = {};
    debitos.forEach(d => {
      const idx = getEtapaIndex(d.situacao_tramitacao);
      map[idx] = (map[idx] ?? 0) + 1;
    });
    return map;
  }, [debitos]);

  const debitosVisiveis = useMemo(() => {
    if (etapaFiltro === null) return debitos;
    return debitos.filter((d) => getEtapaIndex(d.situacao_tramitacao) === etapaFiltro);
  }, [debitos, etapaFiltro]);

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[{ label: "Pagamentos", href: "/m/pagamentos" }]}
        title="Solicitações de Pagamento"
        description="Acompanhe as solicitações no fluxo de aprovação"
        icon={ClipboardList}
        actions={
          can("pagamento_solicitar") && (
            <Button asChild>
              <Link href="/m/pagamentos/solicitacoes/novo">Nova Solicitação</Link>
            </Button>
          )
        }
      />

      {/* Sumário clicável por etapa */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {ETAPA_INFO.map((etapa, idx) => (
          <button
            key={etapa.label}
            type="button"
            onClick={() => setEtapaFiltro(etapaFiltro === idx ? null : idx)}
            className="text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-card"
          >
            <KpiCard
              label={etapa.label}
              value={contagemPorEtapa[idx] ?? 0}
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
          placeholder="Pesquisar por fornecedor, descrição ou NF..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-64"
        />
        <Select
          value={situacaoFiltro}
          onChange={(e) => setSituacaoFiltro(e.target.value as SituacaoTramitacao | "")}
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
            {!listQ.isLoading && debitosVisiveis.length === 0 && (
              <TR>
                <TD colSpan={6} className="p-0">
                  <EmptyState
                    icon={ClipboardList}
                    title="Nenhuma solicitação encontrada"
                    description={
                      etapaFiltro !== null || situacaoFiltro || search
                        ? "Ajuste os filtros para ver outras solicitações."
                        : "Crie a primeira solicitação de pagamento para começar."
                    }
                    className="border-none rounded-none"
                  />
                </TD>
              </TR>
            )}
            {debitosVisiveis.map((d) => (
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
    </div>
  );
}
