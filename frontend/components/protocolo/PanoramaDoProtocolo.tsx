"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Archive, Clock, FileText, Inbox, PauseCircle, PenLine } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { BarraSegmentada, CartaoTendencia, ListaDeBarras, QuadroGrafico, SeletorPeriodo } from "@/components/home/graficos";
import { GraficoEntradaSaida } from "@/components/relatorios/GraficoEntradaSaida";
import { api, gerencialPdfUrl, type GerencialResposta, type PainelUnidade } from "@/lib/api";
import { hrefDaCaixa } from "@/lib/caixas-processos";
import {
  ROTA_LISTA_ASSINATURAS,
  ROTA_LISTA_DOCUMENTACAO,
  ROTA_LISTA_PROCESSOS,
  ROTA_LISTA_TRAMITACAO,
  comVisao,
  filtroParaUrl,
  fmtData,
  fmtDias,
  fmtMinutos,
  type FiltroDaUrl,
  type VisaoProcessos,
} from "@/lib/relatorios";
import { cn } from "@/lib/utils";

/**
 * Panorama do protocolo — o segundo andar do Painel de controle (decisão de
 * 2026-11-14): como o protocolo andou no período, no visual do Panorama do
 * Início (cartão com o número, gráfico com a pergunta no título, cada bloco
 * levando ao relatório que prova o número).
 *
 * Os números vêm de `GET /relatorios/gerencial.json` — o mesmo endpoint, com
 * o mesmo sigilo, rascunho e situação real da tela de Relatórios do SI-34 —
 * e NÃO do dashboard executivo, que ainda conta rascunho e ignora sigilo.
 * Cada "ver" abre a lista com exatamente o recorte que produziu o número; o
 * backend garante que o número é o total dessa lista.
 *
 * Dois recortes convivem nesta tela, e isto fica dito: o andar de cima é "a
 * minha unidade, agora"; este é "o período", na minha unidade por padrão
 * (regra de negócio de hoje) ou em todas, pelo alternador. Filtros finos
 * (tipo, assunto, serviço) ficam nos Relatórios.
 */

const PERIODOS = [
  { value: 7, label: "7 dias" },
  { value: 30, label: "30 dias" },
  { value: 90, label: "90 dias" },
];
/** O "parado" do painel: o mesmo padrão da lista de processos. */
export const DIAS_PARADO_PANORAMA = 15;

const COR = {
  sucesso: "hsl(var(--success))",
  alerta: "hsl(var(--warning))",
  perigo: "hsl(var(--danger))",
  info: "hsl(var(--info))",
  neutro: "hsl(var(--grafico-6))",
};

function iso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${dia}`;
}

/** Os últimos `dias` dias, hoje incluído, em dia local. */
export function periodoDosUltimos(dias: number, hoje = new Date()): { desde: string; ate: string } {
  const inicio = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate() - (dias - 1));
  return { desde: iso(inicio), ate: iso(hoje) };
}

type Escopo = "minha" | "todas";

export function PanoramaDoProtocolo({
  idUnidade,
  nomeUnidade,
  prazoDoEnvio,
}: {
  idUnidade: number | null;
  nomeUnidade?: string | null;
  /** Prazos da caixa Análise da unidade ativa (`GET /processos/painel`):
   * o "prazo do envio", complemento do prazo do serviço. Só existe para a
   * unidade ativa — em "Todas" o quadro diz isso. */
  prazoDoEnvio?: PainelUnidade["prazos"];
}) {
  const [periodo, setPeriodo] = useState(30);
  const [escopo, setEscopo] = useState<Escopo>(idUnidade ? "minha" : "todas");
  const minha = escopo === "minha" && !!idUnidade;

  const recorte: FiltroDaUrl = {
    ...periodoDosUltimos(periodo),
    ...(minha ? { id_unidade: idUnidade as number, modo_unidade: "envolvida" as const } : {}),
  };

  const q = useQuery({
    queryKey: ["relatorio-gerencial", "painel", periodo, minha ? idUnidade : null],
    queryFn: () => api.relatorios.gerencial({ ...recorte, dias_parado: DIAS_PARADO_PANORAMA }),
    staleTime: 60_000,
  });
  const g = q.data;

  const lista = (rota: string, extra: FiltroDaUrl = {}) => `${rota}${filtroParaUrl({ ...recorte, ...extra })}`;
  const visao = (id: VisaoProcessos) =>
    `${ROTA_LISTA_PROCESSOS}${filtroParaUrl(comVisao({ ...recorte, dias_parado: DIAS_PARADO_PANORAMA }, id))}`;

  return (
    <section aria-labelledby="panorama-protocolo-titulo" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="panorama-protocolo-titulo" className="font-display text-base font-semibold text-foreground">
            Panorama do protocolo
          </h2>
          <p className="text-sm text-foreground-muted">
            Como o protocolo andou nos últimos {periodo} dias
            {minha ? `, na unidade ${nomeUnidade ?? "ativa"} (dona ou onde o processo está)` : ", em todas as unidades"}.
            Cada bloco leva ao relatório que prova o número.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SeletorPeriodo rotulo="Período do panorama" valor={periodo} opcoes={PERIODOS} onChange={setPeriodo} />
          <div role="radiogroup" aria-label="Unidade do panorama" className="inline-flex rounded-md border border-border bg-surface-1 p-0.5 shadow-xs">
            {(
              [
                ["minha", "Minha unidade"],
                ["todas", "Todas"],
              ] as [Escopo, string][]
            ).map(([valor, rotulo]) => (
              <button
                key={valor}
                type="button"
                role="radio"
                aria-checked={escopo === valor}
                disabled={valor === "minha" && !idUnidade}
                title={valor === "minha" && !idUnidade ? "Você não tem unidade ativa" : undefined}
                onClick={() => setEscopo(valor)}
                className={cn(
                  "h-8 rounded px-3 text-xs font-medium transition-colors duration-fast disabled:cursor-not-allowed disabled:opacity-50",
                  escopo === valor
                    ? "bg-brand text-primary-foreground shadow-sm"
                    : "text-foreground-muted hover:bg-muted hover:text-foreground",
                )}
              >
                {rotulo}
              </button>
            ))}
          </div>
          <a
            href={gerencialPdfUrl({ ...recorte, dias_parado: DIAS_PARADO_PANORAMA })}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-8 items-center gap-1.5 rounded-md bg-muted px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <FileText className="h-4 w-4" aria-hidden="true" /> PDF do panorama
          </a>
        </div>
      </div>

      {q.isError && (
        <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
          Não foi possível carregar o panorama.{" "}
          <button type="button" className="underline" onClick={() => q.refetch()}>
            Tentar de novo
          </button>
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-6" aria-label="Números do período">
        <CartaoTendencia rotulo="Abertos" icone={Inbox} href={visao("abertos")} carregando={q.isLoading}
          valor={g ? g.entrada.abertos : "—"} dica="no período, pela data de abertura" />
        <CartaoTendencia rotulo="Arquivados" icone={Archive} href={visao("arquivados")} carregando={q.isLoading}
          valor={g ? g.saida.arquivados : "—"}
          dica={g?.saida.dias_medio_ate_arquivar != null ? `em média ${fmtDias(g.saida.dias_medio_ate_arquivar)} até arquivar` : "no período, pela data de arquivamento"} />
        <CartaoTendencia rotulo="Em andamento" icone={Clock} href={visao("em_andamento")} carregando={q.isLoading}
          valor={g ? g.andamento.em_andamento : "—"} dica={g ? `hoje; mais ${g.andamento.em_transito} em trânsito` : "situação de hoje"} />
        <CartaoTendencia rotulo={`Parados há ${DIAS_PARADO_PANORAMA}+ dias`} icone={PauseCircle} href={visao("parados")} carregando={q.isLoading}
          valor={g ? g.andamento.parados : "—"} dica="sem nenhuma movimentação; hoje" />
        <CartaoTendencia rotulo="Prazo vencido" icone={AlertTriangle} href={visao("vencidos")} carregando={q.isLoading}
          valor={g ? g.prazos.atrasados : "—"} dica="em aberto hoje, prazo do serviço já passou" />
        <CartaoTendencia rotulo="Assinaturas pendentes" icone={PenLine} href={lista(ROTA_LISTA_ASSINATURAS, { data_base: "pedido" })} carregando={q.isLoading}
          valor={g ? g.assinaturas.pendentes : "—"} dica={g ? `de ${g.assinaturas.total} pedidas no período` : "pedidas no período"} />
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <QuadroGrafico
          className="xl:col-span-2"
          pergunta="Quantos processos entram e quantos saem?"
          resposta={
            g
              ? `Abertos (pela abertura) e arquivados (pelo arquivamento) por ${g.tendencia.granularidade === "mes" ? "mês" : "semana"}, de ${fmtData(g.tendencia.desde)} a ${fmtData(g.tendencia.ate)}. Abertos acima dos arquivados, seguidamente, é estoque crescendo.`
              : "Abertos e arquivados ao longo do período."
          }
          acao={{ href: lista(ROTA_LISTA_PROCESSOS), label: "Ver lista de processos" }}
        >
          {q.isLoading ? <Esqueleto altura="h-64" /> : q.isError ? <Falhou /> : g ? <GraficoEntradaSaida tendencia={g.tendencia} /> : null}
        </QuadroGrafico>

        <QuadroGrafico
          pergunta="Os prazos estão sendo cumpridos?"
          resposta="Pelo prazo do serviço, a promessa ao cidadão: abertura + N dias. “Vencendo”: faltam 20% do prazo ou menos."
          acao={{ href: visao("vencidos"), label: "Ver vencidos" }}
        >
          {q.isLoading ? (
            <Esqueleto altura="h-64" />
          ) : q.isError ? (
            <Falhou />
          ) : g ? (
            <div className="space-y-5">
              <Faixa
                titulo="Em aberto hoje"
                segmentos={[
                  { rotulo: "Dentro do prazo", valor: g.prazos.dentro_do_prazo, cor: COR.sucesso, href: visao("dentro_do_prazo") },
                  { rotulo: "Vencendo", valor: g.prazos.vencendo, cor: COR.alerta, href: visao("vencendo") },
                  { rotulo: "Vencidos", valor: g.prazos.atrasados, cor: COR.perigo, href: visao("vencidos") },
                ]}
                vazio="Nenhum processo em aberto com prazo de serviço."
                nota={`${g.prazos.em_aberto_sem_prazo} em aberto sem prazo de serviço.`}
              />
              <Faixa
                titulo="Arquivados no período"
                segmentos={[
                  { rotulo: "No prazo", valor: g.prazos.concluidos_no_prazo, cor: COR.sucesso, href: visao("no_prazo") },
                  { rotulo: "Com atraso", valor: g.prazos.concluidos_atrasados, cor: COR.perigo, href: visao("com_atraso") },
                ]}
                vazio="Nenhum arquivado com prazo de serviço no período."
                nota={`${g.prazos.concluidos_sem_prazo} arquivado(s) sem prazo de serviço.`}
              />
              <PrazoDoEnvio prazos={minha ? prazoDoEnvio : undefined} />
            </div>
          ) : null}
        </QuadroGrafico>
      </div>

      {/* Quatro quadros com pergunta no título: em 1440px, quatro colunas
          espremiam o texto; duas até 2xl. */}
      <div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-4">
        <QuadroGrafico
          pergunta="Por onde os processos entram?"
          resposta="Canal de entrada dos abertos no período."
          acao={{ href: visao("abertos"), label: "Ver abertos" }}
        >
          {q.isLoading ? <Esqueleto altura="h-48" /> : q.isError ? <Falhou /> : g ? (
            <ListaDeBarras
              vazio="Nenhum processo aberto no período."
              itens={g.entrada.por_canal.map((c) => ({ rotulo: c.rotulo, valor: c.count }))}
            />
          ) : null}
        </QuadroGrafico>

        <QuadroGrafico
          pergunta="Onde os processos demoram?"
          resposta="Atrasos por unidade onde o processo deu entrada no período. Atraso: saiu depois do fim do dia do prazo, ou segue lá."
          acao={{ href: lista(ROTA_LISTA_TRAMITACAO, { data_base: "chegada" }), label: "Ver tramitação" }}
        >
          {q.isLoading ? <Esqueleto altura="h-48" /> : q.isError ? <Falhou /> : g ? (
            <>
              <ListaDeBarras
                cor={COR.perigo}
                vazio={g.gargalos.unidades.length ? "Nenhum atraso no período." : "Nenhuma entrada em unidade no período."}
                formato={(n) => `${n} atraso${n === 1 ? "" : "s"}`}
                itens={g.gargalos.unidades
                  .filter((u) => u.atrasos > 0)
                  .slice(0, 5)
                  .map((u) => ({ rotulo: u.unidade ?? "—", valor: u.atrasos }))}
              />
              {g.gargalos.cortado && (
                <p className="mt-2 text-xs text-foreground-muted">Recorte grande: a análise cobre os processos mais recentes.</p>
              )}
            </>
          ) : null}
        </QuadroGrafico>

        <QuadroGrafico
          pergunta="Os documentos estão em dia?"
          resposta="Abertos no período cujo serviço exige documentos; situação de hoje."
          acao={{ href: lista(ROTA_LISTA_DOCUMENTACAO), label: "Ver documentação" }}
        >
          {q.isLoading ? <Esqueleto altura="h-48" /> : q.isError ? <Falhou /> : g ? (
            <Faixa
              segmentos={[
                { rotulo: "Pendentes", valor: g.documentacao.pendentes, cor: COR.alerta, href: lista(ROTA_LISTA_DOCUMENTACAO, { visao: "doc_pendente" }) },
                { rotulo: "Parciais", valor: g.documentacao.parciais, cor: COR.info, href: lista(ROTA_LISTA_DOCUMENTACAO, { visao: "doc_parcial" }) },
                { rotulo: "Completos", valor: g.documentacao.completos, cor: COR.sucesso, href: lista(ROTA_LISTA_DOCUMENTACAO, { visao: "doc_completo" }) },
              ]}
              vazio="Nenhum processo com documento exigido no período."
              nota={
                <Link href={lista(ROTA_LISTA_DOCUMENTACAO, { visao: "compl_aberta" })} className="hover:underline">
                  {g.documentacao.aguardando_cidadao} aguardando complementação do cidadão (hoje)
                </Link>
              }
            />
          ) : null}
        </QuadroGrafico>

        <QuadroGrafico
          pergunta="Como andam as assinaturas?"
          resposta="Pedidos de assinatura feitos no período."
          acao={{ href: lista(ROTA_LISTA_ASSINATURAS, { data_base: "pedido" }), label: "Ver assinaturas" }}
        >
          {q.isLoading ? <Esqueleto altura="h-48" /> : q.isError ? <Falhou /> : g ? (
            <Faixa
              segmentos={[
                { rotulo: "Pendentes", valor: g.assinaturas.pendentes, cor: COR.alerta },
                { rotulo: "Concluídas", valor: g.assinaturas.concluidas, cor: COR.sucesso },
                { rotulo: "Canceladas", valor: g.assinaturas.canceladas, cor: COR.neutro },
              ]}
              vazio="Nenhum pedido de assinatura no período."
              nota={
                g.assinaturas.concluidas
                  ? `Tempo médio até concluir: ${fmtMinutos(g.assinaturas.minutos_medio_conclusao)}.`
                  : "Nenhuma concluída no período."
              }
            />
          ) : null}
        </QuadroGrafico>
      </div>

      {g && (
        <ul className="space-y-0.5 text-xs text-foreground-muted" aria-label="Recorte do panorama">
          {g.descricao_filtros.map((linha) => (
            <li key={linha}>{linha}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * O prazo do envio, como complemento do prazo do serviço (decisão de
 * 2026-11-14: os dois no Panorama, o do serviço como principal). É o prazo da
 * caixa Análise — o do encaminhamento vigente, ou o do serviço quando o envio
 * não fixou um —, o que pinta a linha na caixa. Vale para a mesa da unidade
 * ativa, agora: não segue o período nem existe para "Todas".
 */
function PrazoDoEnvio({ prazos }: { prazos?: PainelUnidade["prazos"] }) {
  const analise = hrefDaCaixa("analise");
  return (
    <div className="space-y-1.5 border-t border-border pt-3" data-testid="prazo-do-envio">
      <p className="text-xs font-medium uppercase tracking-wide text-foreground-subtle">
        Prazo do envio · na mesa da unidade, agora
      </p>
      {!prazos ? (
        <p className="text-xs text-foreground-muted">
          É o prazo que quem encaminhou deu à unidade; aparece em “Minha unidade”.
        </p>
      ) : (
        <>
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {(
              [
                ["Vencido", prazos.vencidos, "text-danger-soft-foreground"],
                ["Vencendo", prazos.vencendo, "text-warning-soft-foreground"],
                ["No prazo", prazos.no_prazo, "text-foreground"],
              ] as const
            ).map(([rotulo, n, cor]) => (
              <li key={rotulo}>
                <Link href={analise} className="inline-flex items-baseline gap-1 rounded hover:underline">
                  <span className="text-foreground-muted">{rotulo}</span>
                  <span className={cn("font-semibold tabular-nums", n > 0 && cor)}>{n}</span>
                </Link>
              </li>
            ))}
          </ul>
          <p className="text-xs text-foreground-muted">
            O do encaminhamento, ou o do serviço quando o envio não fixou um. Sem prazo: {prazos.sem_prazo}.
          </p>
        </>
      )}
    </div>
  );
}

/** Uma barra segmentada com título, mensagem de vazio e uma nota embaixo. */
function Faixa({
  titulo,
  segmentos,
  vazio,
  nota,
}: {
  titulo?: string;
  segmentos: { rotulo: string; valor: number; cor: string; href?: string }[];
  vazio: string;
  nota?: React.ReactNode;
}) {
  const total = segmentos.reduce((s, x) => s + x.valor, 0);
  return (
    <div className="space-y-2">
      {titulo && <p className="text-xs font-medium uppercase tracking-wide text-foreground-subtle">{titulo}</p>}
      {total === 0 ? (
        <p className="py-3 text-sm text-foreground-muted">{vazio}</p>
      ) : (
        <BarraSegmentada segmentos={segmentos} unidade={["processo", "processos"]} />
      )}
      {nota && <p className="text-xs text-foreground-muted">{nota}</p>}
    </div>
  );
}

function Esqueleto({ altura }: { altura: string }) {
  return <div className={cn("animate-pulse rounded-md bg-muted motion-reduce:animate-none", altura)} aria-hidden="true" />;
}

function Falhou() {
  return <p className="py-6 text-center text-sm text-danger-soft-foreground">Não foi possível carregar agora.</p>;
}

export type { GerencialResposta };
