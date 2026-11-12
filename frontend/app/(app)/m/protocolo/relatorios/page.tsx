"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  FileCheck,
  FileText,
  Inbox,
  List,
  PenLine,
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
import { api, gerencialPdfUrl } from "@/lib/api";
import {
  ROTA_LISTA_ASSINATURAS,
  ROTA_LISTA_DOCUMENTACAO,
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
 * Uma tela, filtro único no topo e quatro grupos — um por tela de destino:
 * Processos (subgrupos Entrada e saída no tempo, Entrada, Andamento, Saída,
 * Prazos), Tramitação, Documentação e Assinaturas. Cada subgrupo conta pela SUA data e diz
 * qual é; Andamento é a situação de hoje. Um "ver lista" por grupo; na lista,
 * o "Mostrar" escolhe o recorte de cada número (`lib/relatorios.ts`,
 * `VISOES_PROCESSOS`), e o backend garante que o número é o total dessa lista
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

/**
 * Grupo = uma tela de destino. Um único "ver lista" por grupo (decisão de
 * 2026-11-11): antes eram 11 botões levando a só 3 telas. O recorte de cada
 * número se escolhe lá, no "Mostrar" da lista.
 */
function Grupo({
  id,
  titulo,
  descricao,
  icon: Icon,
  acao,
  children,
}: {
  id: string;
  titulo: string;
  descricao: string;
  icon: React.ComponentType<{ className?: string }>;
  acao: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={`grupo-${id}`} className="rounded-card border border-border bg-card shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border p-4">
        <div className="flex min-w-0 flex-[1_1_16rem] items-start gap-3">
          <span className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand/10 text-brand">
            <Icon className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h2 id={`grupo-${id}`} className="font-display text-lg font-semibold text-foreground">
              {titulo}
            </h2>
            <p className="text-xs text-foreground-muted">{descricao}</p>
          </div>
        </div>
        <div className="shrink-0">{acao}</div>
      </div>
      <div className="divide-y divide-border">{children}</div>
    </section>
  );
}

/** Subgrupo dentro de um grupo: título, por qual data conta, os números. */
function Subgrupo({
  id,
  titulo,
  regra,
  extra,
  children,
}: {
  id: string;
  titulo: string;
  /** Por qual data conta — dito em todo subgrupo, de propósito. */
  regra: string;
  extra?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={`sub-${id}`} className="space-y-3 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 id={`sub-${id}`} className="text-sm font-semibold text-foreground">
            {titulo}
          </h3>
          <p className="text-xs text-foreground-muted">{regra}</p>
        </div>
        {extra}
      </div>
      {children}
    </section>
  );
}

/** "78% no prazo" — só com base que sustente a porcentagem. */
function percentual(noPrazo: number, atrasados: number): string | undefined {
  const base = noPrazo + atrasados;
  if (base === 0) return undefined;
  return `${Math.round((noPrazo / base) * 100)}% dos arquivados com prazo`;
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
  const g = q.data;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={BarChart3}
        title="Relatórios"
        description="Como o protocolo andou no período. Cada bloco diz por qual data conta; a lista detalhada, com CSV e PDF, abre pelo botão de cada grupo."
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

          <Grupo
            id="processos"
            titulo="Processos"
            descricao="Entrada, andamento, saída e prazos. Na lista, o “Mostrar” escolhe qual destes recortes ver."
            icon={Inbox}
            acao={<LinkLista href={lista(ROTA_LISTA_PROCESSOS, {})}>Ver lista de processos</LinkLista>}
          >
            <Subgrupo
              id="tendencia"
              titulo="Entrada e saída no tempo"
              regra={`Abertos (pela abertura) e arquivados (pelo arquivamento) por ${
                g.tendencia.granularidade === "mes" ? "mês" : "semana"
              }, de ${fmtData(g.tendencia.desde)} a ${fmtData(g.tendencia.ate)}${
                recorte.desde || recorte.ate ? "" : " (sem período no filtro: as últimas 12 semanas)"
              }. Abertos acima dos arquivados, seguidamente, é estoque crescendo.`}
            >
              <GraficoEntradaSaida tendencia={g.tendencia} />
            </Subgrupo>

            <Subgrupo id="entrada" titulo="Entrada" regra="Abertos no período — pela data de abertura.">
              <div className="grid gap-3 md:grid-cols-[minmax(0,14rem)_1fr]">
                <KpiCard label="Abertos" value={g.entrada.abertos} />
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
            </Subgrupo>

            <Subgrupo
              id="andamento"
              titulo="Andamento"
              regra="Situação de hoje — não usa o período. Unidade, tipo e assunto continuam valendo."
              extra={
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
              }
            >
              <div className="grid gap-3 md:grid-cols-3">
                <KpiCard label="Em andamento" value={g.andamento.em_andamento} hint="com uma unidade, sem envio pendente" />
                <KpiCard label="Em trânsito" value={g.andamento.em_transito} hint="enviados, ainda não recebidos" intent="info" />
                <KpiCard
                  label={`Parados há ${g.andamento.dias_parado}+ dias`}
                  value={g.andamento.parados}
                  hint="sem nenhuma movimentação; não arquivados"
                  intent="warning"
                />
              </div>
            </Subgrupo>

            <Subgrupo id="saida" titulo="Saída" regra="Arquivados no período — pela data de arquivamento.">
              <div className="grid gap-3 md:grid-cols-2">
                <KpiCard label="Arquivados" value={g.saida.arquivados} />
                <KpiCard
                  label="Tempo médio até arquivar"
                  value={fmtDias(g.saida.dias_medio_ate_arquivar)}
                  hint="da abertura ao arquivamento, dos arquivados no período"
                />
              </div>
            </Subgrupo>

            <Subgrupo
              id="prazos"
              titulo="Prazos"
              regra="Prazo do serviço prometido ao cidadão: abertura + N dias corridos. “Vencendo”: faltam 20% do prazo ou menos."
            >
              {/* Uma grade só para os cinco: cartões da mesma linha esticam
                  para a mesma altura, e todos têm dica, para não sobrar
                  cartão mais baixo. */}
              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                <p className="col-span-2 text-xs font-medium uppercase tracking-wide text-foreground-muted">
                  Arquivados no período
                </p>
                <p className="hidden text-xs font-medium uppercase tracking-wide text-foreground-muted md:col-span-3 md:block">
                  Em aberto hoje
                </p>
                <KpiCard
                  label="No prazo"
                  value={g.prazos.concluidos_no_prazo}
                  hint={percentual(g.prazos.concluidos_no_prazo, g.prazos.concluidos_atrasados) ?? "dos arquivados com prazo"}
                />
                <KpiCard
                  label="Com atraso"
                  value={g.prazos.concluidos_atrasados}
                  intent="danger"
                  hint="arquivados depois do prazo"
                />
                <p className="col-span-2 text-xs font-medium uppercase tracking-wide text-foreground-muted md:hidden">
                  Em aberto hoje
                </p>
                <KpiCard label="Dentro do prazo" value={g.prazos.dentro_do_prazo} hint="com folga" />
                <KpiCard label="Vencendo" value={g.prazos.vencendo} intent="warning" hint="20% do prazo ou menos" />
                <KpiCard label="Vencidos" value={g.prazos.atrasados} intent="danger" hint="prazo já passou" />
              </div>
              <p className="text-xs text-foreground-muted">
                Fora da conta, por não ter prazo de serviço: {g.prazos.concluidos_sem_prazo} arquivado(s) no
                período e {g.prazos.em_aberto_sem_prazo} em aberto.
              </p>
            </Subgrupo>
          </Grupo>

          <Grupo
            id="tramitacao"
            titulo="Tramitação"
            descricao="Onde os processos demoram. Entradas nas unidades no período (abertura na unidade dona ou recebimento) — pela data de entrada. Atraso: saiu depois do fim do dia do prazo, ou segue lá."
            icon={AlertTriangle}
            acao={<LinkLista href={lista(ROTA_LISTA_TRAMITACAO, { data_base: "chegada" })}>Ver tramitação</LinkLista>}
          >
            <Subgrupo id="gargalos" titulo="Gargalos por unidade" regra="Ordenado por atrasos e, depois, por permanência média.">
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
            </Subgrupo>
          </Grupo>

          <Grupo
            id="documentacao"
            titulo="Documentação"
            descricao="Documentos que o serviço exige e pedidos de complementação ao cidadão. Conta processos."
            icon={FileCheck}
            acao={<LinkLista href={lista(ROTA_LISTA_DOCUMENTACAO, {})}>Ver documentação</LinkLista>}
          >
            <Subgrupo
              id="documentos-exigidos"
              titulo="Documentos exigidos"
              regra="Abertos no período cujo serviço exige documentos — pela data de abertura; situação dos documentos hoje."
            >
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <KpiCard
                  label="Pendentes"
                  value={g.documentacao.pendentes}
                  intent="warning"
                  hint="nenhum obrigatório enviado"
                />
                <KpiCard label="Parciais" value={g.documentacao.parciais} hint="parte dos obrigatórios enviada" />
                <KpiCard label="Completos" value={g.documentacao.completos} hint="todos os obrigatórios enviados" />
              </div>
              <p className="text-xs text-foreground-muted">
                Fora da conta, por não ter documento exigido: {g.documentacao.sem_documentos_exigidos} aberto(s) no
                período.
              </p>
            </Subgrupo>
            <Subgrupo
              id="complementacao"
              titulo="Complementação"
              regra="Pedidos do servidor ao cidadão para mandar documentos. Cada número diz por qual data conta."
            >
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <KpiCard
                  label="Pedida no período"
                  value={g.documentacao.complementacao_pedida}
                  hint="pela data do pedido"
                />
                <KpiCard
                  label="Aguardando o cidadão"
                  value={g.documentacao.aguardando_cidadao}
                  intent="warning"
                  hint="situação de hoje"
                />
                <KpiCard
                  label="Respondida no período"
                  value={g.documentacao.complementacao_respondida}
                  hint="pela data da resposta"
                />
                <KpiCard
                  label="Tempo de resposta"
                  value={fmtDias(g.documentacao.dias_medio_resposta)}
                  hint="média, do pedido à resposta"
                />
              </div>
            </Subgrupo>
          </Grupo>

          <Grupo
            id="assinaturas"
            titulo="Assinaturas"
            descricao="Pedidos de assinatura feitos no período — pela data do pedido."
            icon={PenLine}
            acao={<LinkLista href={lista(ROTA_LISTA_ASSINATURAS, { data_base: "pedido" })}>Ver assinaturas</LinkLista>}
          >
            <Subgrupo id="assinaturas-numeros" titulo="Pedidos no período" regra="Tempo médio só das concluídas.">
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
            </Subgrupo>
          </Grupo>
        </>
      )}
    </div>
  );
}
