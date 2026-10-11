"use client";

import { useQuery } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Skeleton } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { fmtData, fmtMoeda } from "@/components/pagamentos/format";
import { TRAMITACAO_ROTULO } from "@/components/pagamentos/situacoes";
import { api, type RegraExcecao, type SituacaoTramitacao } from "@/lib/api";

const SEVERIDADE: Record<string, { label: string; intent: "danger" | "warning" | "neutral" }> = {
  alta: { label: "Alta", intent: "danger" },
  media: { label: "Média", intent: "warning" },
  baixa: { label: "Baixa", intent: "neutral" },
};

/** Rótulo de cada campo que as regras do backend devolvem nas linhas. */
const ROTULO_CAMPO: Record<string, string> = {
  id_debito: "Solicitação", id_conta: "Conta", id_lancamento: "Lançamento",
  descricao: "Descrição", valor: "Valor", saldo: "Saldo", minimo: "Mínimo",
  fornecedor: "Fornecedor", favorecido: "Favorecido", nome: "Nome", banco: "Banco",
  situacao: "Situação", situacao_tramitacao: "Etapa", competencia: "Competência",
  justificativa: "Justificativa", motivo: "Motivo", historico: "Histórico", tipo: "Tipo",
  em: "Em", data: "Data", desde: "Desde", dias_em_aberto: "Dias em aberto",
};
const CAMPOS_MOEDA = new Set(["valor", "saldo", "minimo"]);
const CAMPOS_DATA = new Set(["em", "data", "desde"]);

function Celula({ campo, valor }: { campo: string; valor: unknown }) {
  if (valor === null || valor === undefined || valor === "") return <>—</>;
  if (campo === "id_debito")
    return (
      <Link
        href={`/m/pagamentos/solicitacoes/${valor}`}
        className="font-medium text-primary underline-offset-2 hover:underline"
      >
        #{String(valor)}
      </Link>
    );
  if (CAMPOS_MOEDA.has(campo)) return <span className="tabular-nums">{fmtMoeda(String(valor))}</span>;
  if (CAMPOS_DATA.has(campo)) return <>{fmtData(String(valor))}</>;
  if (campo === "situacao_tramitacao")
    return <>{TRAMITACAO_ROTULO[valor as SituacaoTramitacao]?.label ?? String(valor)}</>;
  return <>{String(valor)}</>;
}

function Regra({ regra }: { regra: RegraExcecao }) {
  const sev = SEVERIDADE[regra.severidade] ?? SEVERIDADE.baixa;
  // As colunas saem das próprias linhas: cada regra devolve um formato.
  const campos = regra.itens.length > 0 ? Object.keys(regra.itens[0]) : [];
  return (
    <SectionCard title={regra.titulo} description={regra.descricao}>
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge intent={sev.intent}>Severidade {sev.label.toLowerCase()}</Badge>
          <span className="text-foreground">
            {regra.total === 1 ? "1 ocorrência" : `${regra.total} ocorrências`}
          </span>
          {regra.exibindo < regra.total && (
            <span className="text-foreground-muted">
              — exibindo as {regra.exibindo} primeiras
            </span>
          )}
        </div>
        {regra.itens.length > 0 && (
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  {campos.map((c) => (
                    <TH key={c}>{ROTULO_CAMPO[c] ?? c.replace(/_/g, " ")}</TH>
                  ))}
                </TR>
              </THead>
              <TBody>
                {regra.itens.map((item, i) => (
                  <TR key={i}>
                    {campos.map((c) => (
                      <TD key={c} className="max-w-[24rem] align-top">
                        <Celula campo={c} valor={item[c]} />
                      </TD>
                    ))}
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        )}
      </div>
    </SectionCard>
  );
}

/**
 * Relatório de exceções (Onda C, C1.2): o que merece conferência humana agora.
 * O endpoint existia desde agosto sem tela — quem audita não tinha como vê-lo.
 */
export default function ExcecoesPagamentosPage() {
  const q = useQuery({
    queryKey: ["pag-relatorio-excecoes"],
    queryFn: () => api.pagamentos.relatorioExcecoes(),
  });
  const comOcorrencia = (q.data?.regras ?? []).filter((r) => r.total > 0);
  const semOcorrencia = (q.data?.regras ?? []).filter((r) => r.total === 0);

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[{ label: "Pagamentos", href: "/m/pagamentos" }]}
        title="Exceções"
        description="Situações do módulo de pagamentos que pedem conferência. É uma foto do momento da consulta."
        icon={ShieldAlert}
      />
      {q.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : q.isError || !q.data ? (
        <EmptyState
          icon={ShieldAlert}
          title="Não foi possível carregar o relatório"
          description="Tente de novo em instantes. Se persistir, avise o suporte."
        />
      ) : (
        <>
          <p className="text-sm text-foreground-muted" role="status">
            {q.data.total_excecoes === 0
              ? "Nenhuma exceção no momento."
              : q.data.total_excecoes === 1
                ? "1 exceção no total."
                : `${q.data.total_excecoes} exceções no total.`}{" "}
            Gerado em {fmtData(q.data.gerado_em)}.
          </p>
          {comOcorrencia.map((r) => (
            <Regra key={r.codigo} regra={r} />
          ))}
          {semOcorrencia.length > 0 && (
            <SectionCard title="Regras conferidas sem ocorrência">
              <ul className="list-disc space-y-1 pl-5 text-sm text-foreground-muted">
                {semOcorrencia.map((r) => (
                  <li key={r.codigo}>{r.titulo}</li>
                ))}
              </ul>
            </SectionCard>
          )}
        </>
      )}
    </div>
  );
}
