"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, Eye, FileText, Lock } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { FiltrosDoRelatorio } from "@/components/relatorios/FiltrosDoRelatorio";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Carregando } from "@/components/ui/carregando";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import {
  NIVEL_SIGILO_LABEL,
  api,
  relatorioCsvUrl,
  relatorioPdfUrl,
  type RelatorioBreakdownItem,
} from "@/lib/api";
import {
  ROTA_RELATORIOS,
  ROTULO_SITUACAO,
  VISOES_PROCESSOS,
  comVisao,
  consultaDaLista,
  filtroDaUrl,
  filtroParaUrl,
  fmtData,
  fmtDataHora,
  recorteComum,
  visaoDe,
  type FiltroDaUrl,
  type VisaoProcessos,
} from "@/lib/relatorios";

/**
 * Lista de processos do relatório (SI-34) — o "ver lista de processos" do
 * grupo Processos da página gerencial. O "Mostrar" escolhe o recorte de cada
 * número daquele grupo (abertos, arquivados, andamento de hoje, prazos): cada
 * opção é a mesma consulta que produziu o número na página.
 */
export default function RelatorioProcessosPage() {
  const router = useRouter();
  const pathname = usePathname();
  const busca = useSearchParams().toString();
  const filtro = useMemo(() => filtroDaUrl(new URLSearchParams(busca)), [busca]);
  const visao = visaoDe(filtro);
  const consulta = consultaDaLista(filtro);
  const dataBase = consulta.data_base;
  const grupos = [...new Set(VISOES_PROCESSOS.map((v) => v.grupo))];

  const q = useQuery({
    queryKey: ["relatorio-processos", busca],
    queryFn: () => api.relatorios.processos(consulta),
  });

  function irPara(f: FiltroDaUrl) {
    router.replace(`${pathname}${filtroParaUrl(f)}`, { scroll: false });
  }

  const r = q.data;
  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[
          { label: "Relatórios", href: `${ROTA_RELATORIOS}${filtroParaUrl(recorteComum(filtro))}` },
          { label: "Processos" },
        ]}
        title="Processos do relatório"
        description="A lista por trás dos números do grupo Processos da página de relatórios, com o mesmo recorte."
        actions={
          <div className="flex flex-wrap gap-2">
            <a
              href={relatorioCsvUrl(consulta)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center gap-1.5 rounded-md bg-muted px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Download className="h-4 w-4" aria-hidden="true" /> CSV
            </a>
            <a
              href={relatorioPdfUrl(consulta)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <FileText className="h-4 w-4" aria-hidden="true" /> PDF
            </a>
          </div>
        }
      />

      <FiltrosDoRelatorio
        valor={recorteComum(filtro)}
        onAplicar={(f) => irPara(comVisao({ ...f, dias_parado: filtro.dias_parado }, visao.id))}
      />

      <div className="flex flex-wrap items-center gap-3 rounded-card border border-border bg-card p-3 text-sm shadow-card">
        <label htmlFor="rel-visao" className="font-medium text-foreground">
          Mostrar
        </label>
        <Select
          id="rel-visao"
          className="h-9 w-72"
          value={visao.id}
          onChange={(e) => irPara(comVisao(filtro, e.target.value as VisaoProcessos))}
        >
          {grupos.map((g) => (
            <optgroup key={g} label={g}>
              {VISOES_PROCESSOS.filter((v) => v.grupo === g).map((v) => (
                <option key={v.id} value={v.id}>
                  {v.id === "parados" ? `Parados há ${consulta.parado_ha_dias ?? filtro.dias_parado ?? 15}+ dias` : v.rotulo}
                </option>
              ))}
            </optgroup>
          ))}
        </Select>
        <span className="text-xs text-foreground-muted">
          {visao.hoje
            ? "Situação de hoje: o período do filtro não se aplica (unidade, tipo e assunto, sim)."
            : `No período do filtro, pela data de ${dataBase === "arquivamento" ? "arquivamento" : "abertura"}.`}
        </span>
      </div>

      {q.isLoading && <Carregando />}
      {q.error && (
        <div role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
          {q.error instanceof Error ? q.error.message : "Não foi possível gerar o relatório."}
        </div>
      )}

      {r && (
        <>
          <ul className="space-y-0.5 text-xs text-foreground-muted" aria-label="Recorte do relatório">
            {r.descricao_filtros.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <KpiCard label="Total" value={r.totais.total} />
            <KpiCard label="Em andamento" value={r.totais.em_andamento} />
            <KpiCard label="Em trânsito" value={r.totais.em_transito} intent="info" />
            <KpiCard label="Arquivados" value={r.totais.arquivados} />
            <KpiCard label="Sigilosos" value={r.totais.sigilosos} />
            <KpiCard label="Externos" value={r.totais.externos} />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Quebra titulo="Por tipo de processo" linhas={r.por_tipo_processo} />
            <Quebra titulo="Por unidade dona" linhas={r.por_unidade_proprietaria} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>
                {r.cortado
                  ? `Processos (os ${r.processos.length} mais recentes de ${r.totais.total})`
                  : `Processos (${r.processos.length})`}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {r.cortado && (
                <p className="mb-3 text-sm text-foreground-muted">
                  A lista na tela tem limite; os totais acima contam o recorte inteiro. Para todos os processos, use o CSV.
                </p>
              )}
              <Table>
                <THead>
                  <TR>
                    <TH>Número</TH>
                    <TH>Aberto em</TH>
                    <TH>Situação</TH>
                    <TH>{dataBase === "arquivamento" ? "Arquivado em" : "Última movimentação"}</TH>
                    <TH>Manifestante</TH>
                    <TH>Tipo</TH>
                    <TH>Unidade dona</TH>
                    <TH>Onde está</TH>
                  </TR>
                </THead>
                <TBody>
                  {r.processos.length === 0 && (
                    <TR>
                      <TD colSpan={8} className="text-center text-foreground-muted">
                        Nenhum processo no recorte.
                      </TD>
                    </TR>
                  )}
                  {r.processos.map((p) => (
                    <TR key={p.id}>
                      <TD>
                        <Link
                          href={`/m/protocolo/processos/${p.id}`}
                          className="font-mono text-xs text-primary hover:underline"
                        >
                          {p.numero_processo}
                        </Link>
                      </TD>
                      <TD className="text-xs tabular-nums">{fmtDataHora(p.data_hora_abertura)}</TD>
                      <TD>
                        <div className="flex flex-wrap gap-1">
                          <Badge intent={p.situacao === "em_transito" ? "info" : "neutral"}>
                            {ROTULO_SITUACAO[p.situacao]}
                          </Badge>
                          {!p.publico && (
                            <Badge intent="warning" icon={Lock}>
                              {NIVEL_SIGILO_LABEL[p.nivel_sigilo]}
                            </Badge>
                          )}
                          {p.externo && <Badge intent="info" icon={Eye}>Externo</Badge>}
                        </div>
                      </TD>
                      <TD className="text-xs tabular-nums">
                        {dataBase === "arquivamento"
                          ? fmtDataHora(p.data_hora_arquivamento)
                          : fmtData(p.ultima_movimentacao)}
                      </TD>
                      <TD className="text-sm">{p.manifestante ?? "—"}</TD>
                      <TD className="text-sm">{p.tipo_processo ?? "—"}</TD>
                      <TD className="text-sm">{p.unidade_proprietaria ?? "—"}</TD>
                      <TD className="text-sm">{p.local_atual ?? "—"}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function Quebra({ titulo, linhas }: { titulo: string; linhas: RelatorioBreakdownItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{titulo}</CardTitle>
      </CardHeader>
      <CardContent>
        {linhas.length === 0 ? (
          <p className="text-sm text-foreground-muted">Sem dados.</p>
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Item</TH>
                <TH className="text-right">Qtd</TH>
                <TH className="text-right">%</TH>
              </TR>
            </THead>
            <TBody>
              {linhas.map((l) => (
                <TR key={l.label}>
                  <TD>{l.label}</TD>
                  <TD className="text-right tabular-nums">{l.count}</TD>
                  <TD className="text-right tabular-nums">{l.pct.toFixed(1).replace(".", ",")}%</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
