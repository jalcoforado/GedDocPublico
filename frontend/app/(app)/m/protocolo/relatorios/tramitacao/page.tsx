"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, ChevronUp, Download, FileText } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { FiltrosDoRelatorio } from "@/components/relatorios/FiltrosDoRelatorio";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Carregando } from "@/components/ui/carregando";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import {
  api,
  tramitacaoCsvUrl,
  tramitacaoPdfUrl,
  type RelatorioFiltroInput,
  type TramitacaoEtapa,
  type TramitacaoProcesso,
} from "@/lib/api";
import {
  ROTA_RELATORIOS,
  ROTULO_SITUACAO,
  filtroDaUrl,
  filtroParaUrl,
  fmtData as fmtDate,
  fmtDataHora as fmtDateTime,
  fmtMinutos as fmtMin,
  recorteComum,
  type FiltroDaUrl,
} from "@/lib/relatorios";

/**
 * Tramitação (SI-34) — o "ver lista" da seção Gargalos da página de
 * relatórios: tempo de cada processo em cada unidade e os atrasos. O recorte
 * vem da URL. Atraso = a estadia terminou (ou segue) depois do FIM do dia do
 * prazo do envio que trouxe o processo (`relatorios_tramitacao.py`).
 */
export default function RelatorioTramitacaoPage() {
  const router = useRouter();
  const pathname = usePathname();
  const busca = useSearchParams().toString();
  const filtro = useMemo(() => filtroDaUrl(new URLSearchParams(busca)), [busca]);
  const dataBase = filtro.data_base === "chegada" ? "chegada" : "abertura";
  const consulta: RelatorioFiltroInput = {
    ...recorteComum(filtro),
    data_base: dataBase,
    com_atraso: filtro.com_atraso,
  };

  function irPara(f: FiltroDaUrl) {
    router.replace(`${pathname}${filtroParaUrl(f)}`, { scroll: false });
  }

  // "Gerar em background" saiu em 2026-11-12: gerava o mesmo PDF de 200
  // processos que o botão PDF, deixava o arquivo em Administração → Jobs e o
  // download não confere quem pediu. Endpoint e task continuam; voltar é
  // decisão de card próprio (docs/relatorios-protocolo.md, Limitações).

  const relQ = useQuery({
    queryKey: ["relatorio-tramitacao", busca],
    queryFn: () => api.relatorios.tramitacao(consulta),
  });

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[
          { label: "Relatórios", href: `${ROTA_RELATORIOS}${filtroParaUrl(recorteComum(filtro))}` },
          { label: "Tramitação" },
        ]}
        title="Tramitação"
        description="Quanto tempo cada processo ficou em cada unidade, e onde atrasou."
        actions={
          <div className="flex flex-wrap gap-2">
            <a
              href={tramitacaoCsvUrl(consulta)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center gap-1.5 rounded-md bg-muted px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Download className="h-4 w-4" aria-hidden="true" /> CSV
            </a>
            <a
              href={tramitacaoPdfUrl(consulta)}
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
        onAplicar={(f) => irPara({ ...f, data_base: filtro.data_base, com_atraso: filtro.com_atraso })}
      />

      <div
        role="group"
        aria-label="Filtros desta lista"
        className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-card border border-border bg-card p-3 text-sm shadow-card"
      >
        <label className="flex items-center gap-2">
          <span className="font-medium text-foreground">Período conta pela data de</span>
          <Select
            className="h-9 w-56"
            value={dataBase}
            onChange={(e) => irPara({ ...filtro, data_base: e.target.value as "abertura" | "chegada" })}
          >
            <option value="abertura">abertura do processo</option>
            <option value="chegada">entrada na unidade</option>
          </Select>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border accent-brand"
            checked={!!filtro.com_atraso}
            onChange={(e) => irPara({ ...filtro, com_atraso: e.target.checked || undefined })}
          />
          <span className="font-medium text-foreground">Só processos com atraso</span>
          <span className="text-xs text-foreground-muted">
            (alguma unidade passou do prazo do envio — o mesmo número do cartão “Com atraso”)
          </span>
        </label>
      </div>

      {relQ.isLoading && <Carregando className="text-sm text-muted-foreground" />}
      {relQ.error && (
        <div
          role="alert"
          className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
        >
          {relQ.error instanceof Error ? relQ.error.message : "Erro ao gerar relatório"}
        </div>
      )}

      {relQ.data && (
        <ul className="space-y-0.5 text-xs text-muted-foreground" aria-label="Recorte do relatório">
          {relQ.data.descricao_filtros.map((l) => (
            <li key={l}>{l}</li>
          ))}
          {relQ.data.cortado && (
            <li className="font-medium text-foreground">
              O recorte tem {relQ.data.qtd_processos} processos; a tela detalha os {relQ.data.qtd_listados} mais
              recentes, e atrasos, tempos e médias abaixo são desses. Para todos, use o CSV.
            </li>
          )}
        </ul>
      )}

      {relQ.data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <StatCard label="Processos" value={String(relQ.data.qtd_processos)} />
            <StatCard
              label="Com atraso"
              value={String(relQ.data.qtd_processos_com_atraso)}
              danger={relQ.data.qtd_processos_com_atraso > 0}
            />
            <StatCard
              label="Tempo médio por processo"
              value={fmtMin(relQ.data.minutos_medio_por_processo)}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Tempo por unidade</CardTitle>
            </CardHeader>
            <CardContent>
              {relQ.data.por_unidade.length === 0 ? (
                <p className="text-sm text-muted-foreground">Sem dados.</p>
              ) : (
                <Table>
                  <THead>
                    <TR>
                      <TH>Unidade</TH>
                      <TH className="text-right">Passagens</TH>
                      <TH className="text-right">Atrasos</TH>
                      <TH className="text-right">Tempo total</TH>
                      <TH className="text-right">Tempo médio</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {relQ.data.por_unidade.map((u, i) => (
                      <TR key={`${u.id_unidade ?? "null"}-${i}`}>
                        <TD>{u.unidade ?? "—"}</TD>
                        <TD className="text-right tabular-nums">{u.qtd_passagens}</TD>
                        <TD className="text-right tabular-nums">
                          {u.qtd_atrasos > 0 ? (
                            <span className="font-semibold text-danger">{u.qtd_atrasos}</span>
                          ) : (
                            u.qtd_atrasos
                          )}
                        </TD>
                        <TD className="text-right tabular-nums">{fmtMin(u.minutos_total)}</TD>
                        <TD className="text-right tabular-nums">{fmtMin(u.minutos_medio)}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Processos ({relQ.data.processos.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {relQ.data.processos.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nenhum processo no recorte.</p>
              ) : (
                <div className="space-y-3">
                  {relQ.data.processos.map((p) => (
                    <ProcessoTramitacaoCard key={p.id} p={p} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  danger = false,
}: {
  label: string;
  value: string;
  danger?: boolean;
}) {
  return (
    <div className="rounded-md border border-border bg-card p-3 text-center">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div
        className={"text-xl font-bold tabular-nums " + (danger ? "text-danger" : "text-primary")}
      >
        {value}
      </div>
    </div>
  );
}

function ProcessoTramitacaoCard({ p }: { p: TramitacaoProcesso }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border border-border bg-card">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/m/protocolo/processos/${p.id}`}
              onClick={(e) => e.stopPropagation()}
              className="font-mono text-sm text-primary hover:underline"
            >
              {p.numero_processo}
            </Link>
            {p.teve_atraso && (
              <Badge intent="danger" icon={AlertTriangle}>
                {p.qtd_atrasos} atraso(s)
              </Badge>
            )}
            {p.situacao !== "em_andamento" && (
              <Badge intent={p.situacao === "em_transito" ? "info" : "neutral"}>
                {ROTULO_SITUACAO[p.situacao]}
              </Badge>
            )}
          </div>
          <div className="text-xs text-muted-foreground">
            {p.manifestante ?? "—"} · {p.assunto ?? "—"}
          </div>
        </div>
        {/* Colunas de largura fixa: alinham de uma linha para outra, e o nome
            longo da unidade quebra dentro da sua coluna em vez de invadir as
            vizinhas. */}
        <div className="hidden shrink-0 grid-cols-[3.5rem_4.5rem_4.5rem_4.5rem_minmax(0,13rem)] items-start gap-3 text-xs text-muted-foreground md:grid xl:grid-cols-[3.5rem_4.5rem_4.5rem_4.5rem_minmax(0,18rem)]">
          <Stat label="encs" value={String(p.qtd_encaminhamentos)} />
          <Stat label="unidades" value={String(p.qtd_unidades_visitadas)} />
          <Stat label="total" value={fmtMin(p.minutos_total)} />
          <Stat
            label="em aberto"
            value={p.minutos_em_andamento > 0 ? fmtMin(p.minutos_em_andamento) : "—"}
          />
          <Stat label="local" value={p.local_atual ?? "—"} texto />
        </div>
        {open ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        )}
      </button>
      {open && p.etapas.length > 0 && (
        <div className="border-t border-border px-4 py-3">
          <EtapasTimeline etapas={p.etapas} />
        </div>
      )}
    </div>
  );
}

/** `texto`: valor longo (nome de unidade) — alinhado à esquerda, até duas
 * linhas, e o nome inteiro no title. */
function Stat({ label, value, texto = false }: { label: string; value: string; texto?: boolean }) {
  return (
    <div className={texto ? "min-w-0 text-left" : "text-center"}>
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div
        className={"font-medium text-foreground " + (texto ? "line-clamp-2 break-words" : "tabular-nums")}
        title={texto ? value : undefined}
      >
        {value}
      </div>
    </div>
  );
}

function EtapasTimeline({ etapas }: { etapas: TramitacaoEtapa[] }) {
  return (
    <div className="space-y-2">
      {etapas.map((e, i) => (
        <div
          key={i}
          className={
            "rounded border-l-2 pl-3 py-1 " +
            (e.atrasou
              ? "border-danger bg-danger-soft"
              : e.saiu_em === null
              ? "border-success bg-success-soft"
              : "border-border bg-muted")
          }
        >
          <div className="flex items-baseline justify-between">
            <span className="font-medium text-foreground">{e.unidade ?? "—"}</span>
            <span className="text-xs text-muted-foreground">
              {e.minutos_no_local !== null
                ? fmtMin(e.minutos_no_local)
                : e.saiu_em === null
                ? "em andamento"
                : "—"}
            </span>
          </div>
          <div className="grid grid-cols-1 gap-x-4 text-xs text-muted-foreground md:grid-cols-3">
            <span>chegou: {fmtDateTime(e.chegou_em)}</span>
            <span>saiu: {fmtDateTime(e.saiu_em)}</span>
            <span>
              prazo: {fmtDate(e.prazo_estipulado)}
              {e.atrasou && (
                <span className="ml-1 font-semibold text-danger">ATRASO</span>
              )}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
