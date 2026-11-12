"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  FileText,
  Hourglass,
  Inbox,
  Timer,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AcoesDoFiltro, RelatorioCabecalho, temFiltro } from "@/components/protocolo/RelatorioCabecalho";
import { RankingEmBarras } from "@/components/protocolo/RankingEmBarras";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Carregando } from "@/components/ui/carregando";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { Input } from "@/components/ui/input";
import { KpiCard } from "@/components/ui/kpi-card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { useToast } from "@/components/ui/toast";
import {
  api,
  tramitacaoCsvUrl,
  tramitacaoPdfUrl,
  type RelatorioFiltroInput,
  type TramitacaoEtapa,
  type TramitacaoPorUnidade,
  type TramitacaoProcesso,
} from "@/lib/api";
import { useFiltroNaUrl } from "@/lib/filtro-na-url";

function fmtDateTime(s: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

function fmtDate(s: string | null) {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("pt-BR");
}

function fmtMin(m: number | null): string {
  if (m === null || m === undefined) return "—";
  // Médias chegam fracionadas (123.4 min); sem arredondar saía "2h 03.4min".
  m = Math.round(m);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  if (h < 24) return `${h}h ${String(rem).padStart(2, "0")}min`;
  const d = Math.floor(h / 24);
  const rh = h % 24;
  return `${d}d ${rh}h`;
}

export default function RelatorioTramitacaoPage() {
  const router = useRouter();
  const toast = useToast();
  // Filtro aplicado mora na URL: recarregar, voltar ou mandar o link reabre o mesmo recorte.
  const [applied, aplicar] = useFiltroNaUrl<RelatorioFiltroInput>();
  const [draft, setDraft] = useState<RelatorioFiltroInput>(applied);
  useEffect(() => setDraft(applied), [applied]);

  const gerarBg = useMutation({
    mutationFn: () => api.jobs.relatorioTramitacao(applied),
    onSuccess: () => {
      toast.success("Relatório enfileirado em background.");
      router.push("/m/administracao/jobs");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });
  const tiposQ = useQuery({
    queryKey: ["tipos-processo"],
    queryFn: () => api.tiposProcesso.list(),
  });

  const relQ = useQuery({
    queryKey: ["relatorio-tramitacao", applied],
    queryFn: () => api.relatorios.tramitacao(applied),
  });

  return (
    <div className="space-y-4">
      <RelatorioCabecalho
        subtitulo="Tramitação (tempo em cada unidade + atrasos)"
        csvUrl={tramitacaoCsvUrl(applied)}
        pdfUrl={tramitacaoPdfUrl(applied)}
        acoesExtras={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => gerarBg.mutate()}
            disabled={gerarBg.isPending}
            title="Gera o PDF em background — útil para recortes grandes"
          >
            {gerarBg.isPending ? "Enfileirando..." : "Gerar em background"}
          </Button>
        }
      />

      <FilterBar>
        <div className="w-full sm:w-56">
          <Label htmlFor="unidade">Unidade</Label>
          <Select
            id="unidade"
            value={draft.id_unidade ?? ""}
            onChange={(e) =>
              setDraft({
                ...draft,
                id_unidade: e.target.value ? Number(e.target.value) : undefined,
              })
            }
          >
            <option value="">Todas</option>
            {unidadesQ.data?.items.map((u) => (
              <option key={u.id} value={u.id}>
                {u.unidade_trabalho}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-full sm:w-48">
          <Label htmlFor="tipo">Tipo de processo</Label>
          <Select
            id="tipo"
            value={draft.id_tipo_processo ?? ""}
            onChange={(e) =>
              setDraft({
                ...draft,
                id_tipo_processo: e.target.value ? Number(e.target.value) : undefined,
              })
            }
          >
            <option value="">Todos</option>
            {tiposQ.data?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.tipo_processo}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-full sm:w-40">
          <Label htmlFor="desde">Aberto desde</Label>
          <Input
            id="desde"
            type="date"
            value={draft.desde?.slice(0, 10) ?? ""}
            onChange={(e) =>
              setDraft({
                ...draft,
                desde: e.target.value ? `${e.target.value}T00:00:00` : undefined,
              })
            }
          />
        </div>
        <div className="w-full sm:w-40">
          <Label htmlFor="ate">Aberto até</Label>
          <Input
            id="ate"
            type="date"
            value={draft.ate?.slice(0, 10) ?? ""}
            onChange={(e) =>
              setDraft({
                ...draft,
                ate: e.target.value ? `${e.target.value}T23:59:59` : undefined,
              })
            }
          />
        </div>
        <div className="flex h-11 items-center gap-2">
          <Checkbox
            id="ativos"
            checked={!!draft.apenas_ativos}
            onChange={(e) => setDraft({ ...draft, apenas_ativos: e.target.checked })}
          />
          <Label htmlFor="ativos" className="!mb-0">
            Apenas ativos
          </Label>
        </div>
        <AcoesDoFiltro
          filtrado={temFiltro(draft) || temFiltro(applied)}
          onGerar={() => aplicar({ ...draft })}
          onLimpar={() => {
            setDraft({});
            aplicar({});
          }}
        />
      </FilterBar>

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
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <KpiCard label="Processos" value={relQ.data.qtd_processos} icon={FileText} />
            <KpiCard
              label="Com atraso"
              value={relQ.data.qtd_processos_com_atraso}
              icon={AlertTriangle}
              intent={relQ.data.qtd_processos_com_atraso > 0 ? "danger" : "default"}
            />
            <KpiCard
              label="Tempo médio por processo"
              value={fmtMin(relQ.data.minutos_medio_por_processo)}
              icon={Timer}
            />
            <KpiCard
              label="Onde mais demora"
              value={maisLenta(relQ.data.por_unidade)?.unidade ?? "—"}
              hint={
                maisLenta(relQ.data.por_unidade)
                  ? `${fmtMin(maisLenta(relQ.data.por_unidade)!.minutos_medio)} em média por passagem`
                  : undefined
              }
              icon={Hourglass}
              intent="warning"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Onde o processo para?</CardTitle>
                <CardDescription>
                  Unidades pelo tempo médio que um processo fica nelas. Em vermelho, as que
                  estouraram prazo.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <RankingEmBarras
                  rotuloDoValor="tempo médio por passagem"
                  vazio={<EmptyState icon={Inbox} title="Sem dados no recorte" className="p-6" />}
                  itens={[...relQ.data.por_unidade]
                    .sort((a, b) => b.minutos_medio - a.minutos_medio)
                    .map((u, i) => ({
                      chave: `${u.id_unidade ?? "null"}-${i}`,
                      rotulo: u.unidade ?? "—",
                      valor: u.minutos_medio,
                      valorTexto: fmtMin(Math.round(u.minutos_medio)),
                      alerta: u.qtd_atrasos > 0,
                      detalhe: (
                        <>
                          {u.qtd_passagens} {u.qtd_passagens === 1 ? "passagem" : "passagens"} ·{" "}
                          {fmtMin(u.minutos_total)} no total
                          {u.qtd_atrasos > 0 && (
                            <span className="font-semibold text-danger-soft-foreground">
                              {" "}
                              · {u.qtd_atrasos} {u.qtd_atrasos === 1 ? "atraso" : "atrasos"}
                            </span>
                          )}
                        </>
                      ),
                    }))}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Quem está parado há mais tempo?</CardTitle>
                <CardDescription>
                  Processos ativos pelo tempo desde que chegaram onde estão agora.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <RankingEmBarras
                  rotuloDoValor="parado há"
                  vazio={
                    <EmptyState icon={Inbox} title="Nenhum processo ativo parado" className="p-6" />
                  }
                  itens={relQ.data.processos
                    .filter((p) => p.ativo && p.minutos_em_andamento > 0)
                    .sort((a, b) => b.minutos_em_andamento - a.minutos_em_andamento)
                    .map((p) => ({
                      chave: p.id,
                      rotulo: (
                        <Link
                          href={`/m/protocolo/processos/${p.id}`}
                          className="font-mono text-primary hover:underline"
                        >
                          {p.numero_processo}
                        </Link>
                      ),
                      valor: p.minutos_em_andamento,
                      valorTexto: fmtMin(p.minutos_em_andamento),
                      alerta: p.teve_atraso,
                      detalhe: (
                        <>
                          em {p.local_atual ?? "—"} · {p.assunto ?? "—"}
                        </>
                      ),
                    }))}
                />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Processos ({relQ.data.processos.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {relQ.data.processos.length === 0 ? (
                <EmptyState
                  icon={Inbox}
                  title="Nenhum processo no recorte"
                  description="Ajuste os filtros acima e gere o relatório de novo."
                />
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
            {!p.ativo && <Badge intent="neutral">Inativo</Badge>}
          </div>
          <div className="text-xs text-muted-foreground">
            {p.manifestante ?? "—"} · {p.assunto ?? "—"}
          </div>
        </div>
        <div className="hidden gap-6 text-xs text-muted-foreground md:flex">
          <Stat label="encs" value={String(p.qtd_encaminhamentos)} />
          <Stat label="unidades" value={String(p.qtd_unidades_visitadas)} />
          <Stat label="total" value={fmtMin(p.minutos_total)} />
          <Stat
            label="em aberto"
            value={p.minutos_em_andamento > 0 ? fmtMin(p.minutos_em_andamento) : "—"}
          />
          <Stat label="local" value={p.local_atual ?? "—"} />
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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="font-medium text-foreground tabular-nums">{value}</div>
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
                <span className="ml-1 font-semibold text-danger-soft-foreground">ATRASO</span>
              )}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

/** A unidade de maior tempo médio por passagem (o topo do ranking). */
function maisLenta(us: TramitacaoPorUnidade[]): TramitacaoPorUnidade | undefined {
  return us.reduce<TramitacaoPorUnidade | undefined>(
    (m, u) => (!m || u.minutos_medio > m.minutos_medio ? u : m),
    undefined,
  );
}
