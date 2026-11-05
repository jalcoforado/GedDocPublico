"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Hourglass } from "lucide-react";
import Link from "next/link";

import { nivelDeEspera, textoDoPrazo } from "@/components/TabelaCaixaProcessos";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api } from "@/lib/api";
import { hrefDaCaixa } from "@/lib/caixas-processos";
import { decorridoDesde } from "@/lib/duracao";
import { cn } from "@/lib/utils";

/** Quantos aparecem no painel — o resto está a um clique, na própria caixa. */
export const QUANTOS_PARADOS = 5;

const COR: Record<ReturnType<typeof nivelDeEspera>, string> = {
  normal: "text-foreground",
  atencao: "rounded-full bg-warning-soft px-2 py-0.5 font-medium text-warning-soft-foreground",
  critico: "rounded-full bg-danger-soft px-2 py-0.5 font-medium text-danger-soft-foreground",
};

/**
 * Os processos parados há mais tempo na mesa da unidade — a pergunta "o que
 * está esquecido aqui?", que os quadros (contagens) não respondem.
 *
 * Veio da referência de mercado (SUITE/CE, "Processos em análise por tempo"),
 * com duas diferenças de propósito:
 *
 * - **É a caixa Análise, não uma lista à parte.** Mesmo recorte do quadro "Na
 *   unidade" e mesma ordem da caixa (`ordem=parados`): estas cinco são as
 *   cinco primeiras da lista que "Ver a caixa" abre. Uma consulta própria
 *   divergiria do quadro no primeiro ajuste.
 * - **A cor vem do prazo, não do tempo.** A mesma regra da tabela da caixa
 *   (`nivelDeEspera`): sem prazo, não há do que estar atrasado, e a linha não
 *   pinta — o tempo parado continua à vista. Lá todo número era laranja, e
 *   cor que está em tudo não destaca nada.
 */
export function ParadosHaMaisTempo({ intervalo }: { intervalo: number }) {
  const q = useQuery({
    // Sob o prefixo `["processos"]`: trocar de unidade ativa invalida ele.
    queryKey: ["processos", "painel-parados"],
    queryFn: () =>
      api.processos.list({
        caixa: "analise",
        apenas_ativos: false,
        ordem: "parados",
        page: 1,
        page_size: QUANTOS_PARADOS,
      }),
    staleTime: 60_000,
    refetchInterval: intervalo,
  });

  const itens = q.data?.items ?? [];
  const total = q.data?.total ?? 0;

  return (
    <section aria-labelledby="parados-titulo" className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="parados-titulo" className="font-display text-base font-semibold text-foreground">
          Parados há mais tempo na unidade
        </h2>
        {total > 0 && (
          <Link
            href={hrefDaCaixa("analise")}
            className="inline-flex items-center gap-1 rounded text-sm font-medium text-foreground underline underline-offset-2 hover:no-underline"
          >
            Ver a caixa Análise ({total})
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        )}
      </div>
      <div className="overflow-x-auto rounded-card border border-border bg-surface-1 shadow-card">
        <Table>
          <THead>
            <TR>
              <TH>Processo</TH>
              <TH>Assunto</TH>
              <TH>Responsável</TH>
              <TH className="w-48 text-right">Parado há</TH>
            </TR>
          </THead>
          <TBody>
            {q.isLoading &&
              Array.from({ length: QUANTOS_PARADOS }).map((_, i) => <SkeletonRow key={i} cols={4} />)}
            {q.isError && (
              <TR>
                <TD colSpan={4} className="text-sm text-danger-soft-foreground">
                  Não foi possível carregar a lista.{" "}
                  <button type="button" className="underline" onClick={() => q.refetch()}>
                    Tentar de novo
                  </button>
                </TD>
              </TR>
            )}
            {!q.isLoading && !q.isError && itens.length === 0 && (
              <TR>
                <TD colSpan={4} className="text-sm text-foreground-muted">
                  <span className="inline-flex items-center gap-2">
                    <Hourglass className="h-4 w-4" aria-hidden="true" />
                    Nenhum processo na mesa da unidade agora — nada parado esperando alguém.
                  </span>
                </TD>
              </TR>
            )}
            {itens.map((p) => {
              const prazo = textoDoPrazo(p.prazo_caixa_status, p.prazo_caixa_vence_em);
              return (
                <TR key={p.id}>
                  <TD className="font-mono text-xs tabular-nums">
                    <Link
                      href={`/m/protocolo/processos/${p.id}`}
                      className="font-medium text-foreground underline underline-offset-2 hover:no-underline"
                    >
                      {p.nup ?? p.numero_processo}
                    </Link>
                  </TD>
                  <TD>
                    <div className="line-clamp-1 text-sm">{p.assunto ?? "—"}</div>
                    {p.manifestante && (
                      <div className="line-clamp-1 text-xs text-muted-foreground">{p.manifestante}</div>
                    )}
                  </TD>
                  <TD className="text-sm">
                    {p.responsavel ?? <span className="text-warning-soft-foreground">Sem responsável</span>}
                  </TD>
                  <TD className="text-right text-sm tabular-nums">
                    {p.parado_desde ? (
                      <span className={cn(COR[nivelDeEspera(p.prazo_caixa_status)])}>
                        {decorridoDesde(p.parado_desde)}
                      </span>
                    ) : (
                      <span className="text-foreground-muted">sem movimentação registrada</span>
                    )}
                    {prazo && <span className="mt-0.5 block text-xs text-muted-foreground">{prazo}</span>}
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      </div>
    </section>
  );
}
