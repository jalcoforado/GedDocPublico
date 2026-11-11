"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Archive,
  BarChart3,
  Clock,
  Download,
  FileText,
  Inbox,
  List,
  PenLine,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { FiltrosDoRelatorio } from "@/components/relatorios/FiltrosDoRelatorio";
import { GraficoEntradaSaida } from "@/components/relatorios/GraficoEntradaSaida";
import { Carregando } from "@/components/ui/carregando";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import {
  api,
  assinaturasCsvUrl,
  gerencialPdfUrl,
  relatorioCsvUrl,
  tramitacaoCsvUrl,
} from "@/lib/api";
import {
  ROTA_LISTA_ASSINATURAS,
  ROTA_LISTA_PROCESSOS,
  ROTA_LISTA_TRAMITACAO,
  filtroDaUrl,
  filtroParaUrl,
  fmtData,
  fmtDias,
  fmtMinutos,
  recorteComum,
  type FiltroDaUrl,
} from "@/lib/relatorios";

/**
 * Relatórios do protocolo — página gerencial (SI-34, decisão de 2026-11-11).
 *
 * Uma tela, filtro único no topo, cinco seções. Cada seção conta pela SUA
 * data e diz qual é; "Andamento" é a situação de hoje. Cada número leva à
 * lista que o produziu (mesmo recorte, pela URL) e exporta o CSV dela — o
 * backend garante que o número da seção é o total dessa lista
 * (`tests/test_relatorios_protocolo_medidas.py`).
 *
 * É diferente do Painel de controle (o que a minha unidade tem para fazer
 * agora) e do Dashboard executivo (`/dashboard`, gráficos), que continua
 * separado.
 */

const OPCOES_DIAS_PARADO = [7, 15, 30, 60, 90];

function LinkLista({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border bg-card px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <List className="h-4 w-4" aria-hidden="true" /> {children}
    </Link>
  );
}

function LinkCsv({ href, rotulo }: { href: string; rotulo: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      aria-label={rotulo}
      className="inline-flex h-9 items-center gap-1.5 rounded-md bg-muted px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Download className="h-4 w-4" aria-hidden="true" /> CSV
    </a>
  );
}

function Secao({
  id,
  titulo,
  regra,
  icon: Icon,
  acoes,
  children,
}: {
  id: string;
  titulo: string;
  /** Por qual data a seção conta — dito em toda seção, de propósito. */
  regra: string;
  icon: React.ComponentType<{ className?: string }>;
  acoes?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-labelledby={`secao-${id}`}
      className="space-y-3 rounded-card border border-border bg-card p-4 shadow-card"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand/10 text-brand">
            <Icon className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h2 id={`secao-${id}`} className="font-display text-base font-semibold text-foreground">
              {titulo}
            </h2>
            <p className="text-xs text-foreground-muted">{regra}</p>
          </div>
        </div>
        {acoes && <div className="flex flex-wrap gap-2">{acoes}</div>}
      </div>
      {children}
    </section>
  );
}

/** Número com o seu "ver lista" logo abaixo. */
function NumeroComLista({
  label,
  value,
  hint,
  intent,
  href,
}: {
  label: string;
  value: number;
  hint?: string;
  intent?: "warning" | "danger";
  href: string;
}) {
  return (
    <div className="space-y-2">
      <KpiCard label={label} value={value} hint={hint} intent={intent} />
      <LinkLista href={href}>Ver lista</LinkLista>
    </div>
  );
}

/** "78% no prazo" — só com base que sustente a porcentagem. */
function percentual(noPrazo: number, atrasados: number): string | undefined {
  const base = noPrazo + atrasados;
  if (base === 0) return undefined;
  return `${Math.round((noPrazo / base) * 100)}% dos arquivados com prazo`;
}

/** "+17 vs. 31/08–30/09": diferença em números — com base pequena, % engana. */
function diferenca(atual: number, anterior: number, periodo: { desde: string; ate: string }): string {
  const d = atual - anterior;
  const sinal = d > 0 ? `+${d}` : d < 0 ? `${d}` : "igual";
  return `${sinal} vs. ${fmtData(periodo.desde).slice(0, 5)}–${fmtData(periodo.ate)} (${anterior})`;
}

export default function RelatoriosPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const busca = searchParams.toString();
  const filtro = useMemo(() => filtroDaUrl(new URLSearchParams(busca)), [busca]);
  const recorte = recorteComum(filtro);
  const diasParado = filtro.dias_parado ?? 15;

  const q = useQuery({
    queryKey: ["relatorio-gerencial", busca],
    queryFn: () => api.relatorios.gerencial({ ...recorte, dias_parado: diasParado }),
  });

  function irPara(f: FiltroDaUrl) {
    router.replace(`${pathname}${filtroParaUrl(f)}`, { scroll: false });
  }

  const lista = (rota: string, extra: FiltroDaUrl) => `${rota}${filtroParaUrl({ ...recorte, ...extra })}`;
  const semPeriodo = { desde: undefined, ate: undefined };
  const g = q.data;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={BarChart3}
        title="Relatórios"
        description="Como o protocolo andou no período. Cada seção diz por qual data conta; a lista e o CSV de cada número estão na própria seção."
        actions={
          <a
            href={gerencialPdfUrl({ ...recorte, dias_parado: diasParado })}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <FileText className="h-4 w-4" aria-hidden="true" /> PDF desta página
          </a>
        }
      />

      <FiltrosDoRelatorio valor={recorte} onAplicar={(f) => irPara({ ...f, dias_parado: filtro.dias_parado })} />

      {q.isLoading && <Carregando />}
      {q.error && (
        <div role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
          {q.error instanceof Error ? q.error.message : "Não foi possível gerar o relatório."}
        </div>
      )}

      {g && (
        <>
          <ul className="space-y-0.5 text-xs text-foreground-muted" aria-label="Recorte do relatório">
            {g.descricao_filtros.map((linha) => (
              <li key={linha}>{linha}</li>
            ))}
          </ul>

          <Secao
            id="tendencia"
            titulo="Entrada e saída no tempo"
            regra={`Abertos (pela abertura) e arquivados (pelo arquivamento) por ${
              g.tendencia.granularidade === "mes" ? "mês" : "semana"
            }, de ${fmtData(g.tendencia.desde)} a ${fmtData(g.tendencia.ate)}${
              recorte.desde || recorte.ate ? "" : " (sem período no filtro: as últimas 12 semanas)"
            }. Abertos acima dos arquivados, seguidamente, é estoque crescendo.`}
            icon={TrendingUp}
          >
            <GraficoEntradaSaida tendencia={g.tendencia} />
          </Secao>

          <Secao
            id="entrada"
            titulo="Entrada"
            regra="Processos abertos no período — pela data de abertura."
            icon={Inbox}
            acoes={
              <>
                <LinkLista href={lista(ROTA_LISTA_PROCESSOS, { data_base: "abertura" })}>
                  Ver lista
                </LinkLista>
                <LinkCsv
                  href={relatorioCsvUrl({ ...recorte, data_base: "abertura" })}
                  rotulo="CSV dos processos abertos no período"
                />
              </>
            }
          >
            <div className="grid gap-3 md:grid-cols-[minmax(0,14rem)_1fr]">
              <KpiCard
                label="Abertos"
                value={g.entrada.abertos}
                hint={g.comparacao ? diferenca(g.entrada.abertos, g.comparacao.abertos, g.comparacao) : undefined}
              />
              {g.entrada.por_canal.length > 0 ? (
                <Table>
                  <THead>
                    <TR>
                      <TH>Canal de entrada</TH>
                      <TH className="text-right">Processos</TH>
                      <TH className="text-right">%</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {g.entrada.por_canal.map((c) => (
                      <TR key={c.rotulo}>
                        <TD>{c.rotulo}</TD>
                        <TD className="text-right tabular-nums">{c.count}</TD>
                        <TD className="text-right tabular-nums">
                          {g.entrada.abertos ? ((c.count / g.entrada.abertos) * 100).toFixed(0) : 0}%
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              ) : (
                <p className="text-sm text-foreground-muted">Nenhum processo aberto no período.</p>
              )}
            </div>
            {g.entrada.top_assuntos.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-medium text-foreground">Principais assuntos</h3>
                <ul className="space-y-1.5">
                  {g.entrada.top_assuntos.map((a) => (
                    <li key={a.id_assunto}>
                      <Link
                        href={lista(ROTA_LISTA_PROCESSOS, { id_assunto: a.id_assunto, data_base: "abertura" })}
                        className="group grid grid-cols-[minmax(0,16rem)_1fr_3rem] items-center gap-3 rounded text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <span className="truncate text-foreground group-hover:underline">{a.assunto ?? "—"}</span>
                        <span className="h-2.5 rounded-full bg-muted" aria-hidden="true">
                          <span
                            className="block h-full rounded-full bg-brand"
                            style={{ width: `${(a.count / g.entrada.top_assuntos[0].count) * 100}%` }}
                          />
                        </span>
                        <span className="text-right tabular-nums text-foreground">{a.count}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Secao>

          <Secao
            id="andamento"
            titulo="Andamento"
            regra="Situação de hoje — não usa o período. Unidade, tipo e assunto continuam valendo."
            icon={Activity}
          >
            <div className="grid gap-3 md:grid-cols-3">
              <div className="space-y-2">
                <KpiCard label="Em andamento" value={g.andamento.em_andamento} hint="com uma unidade, sem envio pendente" />
                <LinkLista href={lista(ROTA_LISTA_PROCESSOS, { ...semPeriodo, situacao: "em_andamento" })}>
                  Ver lista
                </LinkLista>
              </div>
              <div className="space-y-2">
                <KpiCard label="Em trânsito" value={g.andamento.em_transito} hint="enviados, ainda não recebidos" intent="info" />
                <LinkLista href={lista(ROTA_LISTA_PROCESSOS, { ...semPeriodo, situacao: "em_transito" })}>
                  Ver lista
                </LinkLista>
              </div>
              <div className="space-y-2">
                <KpiCard
                  label={`Parados há ${g.andamento.dias_parado}+ dias`}
                  value={g.andamento.parados}
                  hint="sem nenhuma movimentação; não arquivados"
                  intent="warning"
                />
                <div className="flex flex-wrap items-center gap-2">
                  <LinkLista
                    href={lista(ROTA_LISTA_PROCESSOS, { ...semPeriodo, parado_ha_dias: g.andamento.dias_parado })}
                  >
                    Ver lista
                  </LinkLista>
                  <label className="flex items-center gap-1 text-xs text-foreground-muted">
                    Parado há
                    <Select
                      aria-label="Dias sem movimentação para contar como parado"
                      className="h-9 w-24"
                      value={diasParado}
                      onChange={(e) => irPara({ ...filtro, dias_parado: Number(e.target.value) })}
                    >
                      {OPCOES_DIAS_PARADO.map((d) => (
                        <option key={d} value={d}>
                          {d} dias
                        </option>
                      ))}
                    </Select>
                  </label>
                </div>
              </div>
            </div>
          </Secao>

          <Secao
            id="saida"
            titulo="Saída"
            regra="Processos arquivados no período — pela data de arquivamento."
            icon={Archive}
            acoes={
              <>
                <LinkLista href={lista(ROTA_LISTA_PROCESSOS, { data_base: "arquivamento" })}>
                  Ver lista
                </LinkLista>
                <LinkCsv
                  href={relatorioCsvUrl({ ...recorte, data_base: "arquivamento" })}
                  rotulo="CSV dos processos arquivados no período"
                />
              </>
            }
          >
            <div className="grid gap-3 md:grid-cols-2">
              <KpiCard
                label="Arquivados"
                value={g.saida.arquivados}
                hint={g.comparacao ? diferenca(g.saida.arquivados, g.comparacao.arquivados, g.comparacao) : undefined}
              />
              <KpiCard
                label="Tempo médio até arquivar"
                value={fmtDias(g.saida.dias_medio_ate_arquivar)}
                hint="da abertura ao arquivamento, dos arquivados no período"
              />
            </div>
          </Secao>

          <Secao
            id="prazos"
            titulo="Prazos"
            regra="Prazo do serviço prometido ao cidadão: abertura + N dias corridos. Só entram processos com prazo; quantos ficaram fora está dito abaixo."
            icon={Clock}
          >
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-foreground">Arquivados no período</h3>
                <div className="grid grid-cols-2 gap-3">
                  <NumeroComLista
                    label="No prazo"
                    value={g.prazos.concluidos_no_prazo}
                    hint={percentual(g.prazos.concluidos_no_prazo, g.prazos.concluidos_atrasados)}
                    href={lista(ROTA_LISTA_PROCESSOS, { data_base: "arquivamento", prazo: "concluido_no_prazo" })}
                  />
                  <NumeroComLista
                    label="Com atraso"
                    value={g.prazos.concluidos_atrasados}
                    intent="danger"
                    href={lista(ROTA_LISTA_PROCESSOS, { data_base: "arquivamento", prazo: "concluido_atrasado" })}
                  />
                </div>
                <p className="text-xs text-foreground-muted">
                  {g.prazos.concluidos_sem_prazo} arquivado(s) no período sem prazo de serviço — fora da conta.
                </p>
              </div>
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-foreground">Em aberto hoje</h3>
                <div className="grid grid-cols-3 gap-3">
                  <NumeroComLista
                    label="Dentro do prazo"
                    value={g.prazos.dentro_do_prazo}
                    href={lista(ROTA_LISTA_PROCESSOS, { ...semPeriodo, prazo: "dentro_do_prazo" })}
                  />
                  <NumeroComLista
                    label="Vencendo"
                    value={g.prazos.vencendo}
                    intent="warning"
                    href={lista(ROTA_LISTA_PROCESSOS, { ...semPeriodo, prazo: "vencendo" })}
                  />
                  <NumeroComLista
                    label="Vencidos"
                    value={g.prazos.atrasados}
                    intent="danger"
                    href={lista(ROTA_LISTA_PROCESSOS, { ...semPeriodo, prazo: "atrasado" })}
                  />
                </div>
                <p className="text-xs text-foreground-muted">
                  {g.prazos.em_aberto_sem_prazo} em aberto sem prazo de serviço — fora da conta. &ldquo;Vencendo&rdquo;:
                  faltam 20% do prazo ou menos.
                </p>
              </div>
            </div>
          </Secao>

          <Secao
            id="gargalos"
            titulo="Gargalos"
            regra="Entradas nas unidades no período (abertura na unidade dona ou recebimento) — pela data de entrada. Atraso: saiu depois do fim do dia do prazo, ou segue lá."
            icon={AlertTriangle}
            acoes={
              <>
                <LinkLista href={lista(ROTA_LISTA_TRAMITACAO, { data_base: "chegada" })}>
                  Ver lista
                </LinkLista>
                <LinkCsv
                  href={tramitacaoCsvUrl({ ...recorte, data_base: "chegada" })}
                  rotulo="CSV da tramitação no período"
                />
              </>
            }
          >
            {g.gargalos.unidades.length > 0 ? (
              <Table>
                <THead>
                  <TR>
                    <TH>Unidade</TH>
                    <TH className="text-right">Entradas</TH>
                    <TH className="text-right">Com prazo</TH>
                    <TH className="text-right">Atrasos</TH>
                    <TH className="text-right">Permanência média</TH>
                  </TR>
                </THead>
                <TBody>
                  {g.gargalos.unidades.map((u) => (
                    <TR key={`${u.id_unidade}-${u.unidade}`}>
                      <TD>{u.unidade ?? "—"}</TD>
                      <TD className="text-right tabular-nums">{u.chegadas}</TD>
                      <TD className="text-right tabular-nums">{u.com_prazo}</TD>
                      <TD className={u.atrasos ? "text-right font-semibold tabular-nums text-danger" : "text-right tabular-nums"}>
                        {u.atrasos}
                      </TD>
                      <TD className="text-right tabular-nums">{fmtDias(u.dias_medio)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            ) : (
              <p className="text-sm text-foreground-muted">Nenhuma entrada em unidade no período.</p>
            )}
            {g.gargalos.cortado && (
              <p className="text-xs text-foreground-muted">
                Recorte grande: a análise cobre os processos mais recentes. Diminua o período para ver todos.
              </p>
            )}
          </Secao>

          <Secao
            id="assinaturas"
            titulo="Assinaturas"
            regra="Pedidos de assinatura feitos no período — pela data do pedido."
            icon={PenLine}
            acoes={
              <>
                <LinkLista href={lista(ROTA_LISTA_ASSINATURAS, { data_base: "pedido" })}>
                  Ver lista
                </LinkLista>
                <LinkCsv
                  href={assinaturasCsvUrl({ ...recorte, data_base: "pedido" })}
                  rotulo="CSV das assinaturas pedidas no período"
                />
              </>
            }
          >
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              <KpiCard label="Pedidas" value={g.assinaturas.total} />
              <KpiCard label="Pendentes" value={g.assinaturas.pendentes} intent="warning" />
              <KpiCard label="Concluídas" value={g.assinaturas.concluidas} />
              <KpiCard label="Canceladas" value={g.assinaturas.canceladas} />
              <KpiCard
                label="Tempo médio"
                value={g.assinaturas.concluidas ? fmtMinutos(g.assinaturas.minutos_medio_conclusao) : "—"}
                hint="do pedido à conclusão"
              />
            </div>
          </Secao>
        </>
      )}
    </div>
  );
}
