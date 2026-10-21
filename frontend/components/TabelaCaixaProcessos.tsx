"use client";

import { Inbox } from "lucide-react";
import Link from "next/link";

import { MarcadoresDaLinha } from "@/components/EtiquetaMarcador";
import { FavoritoStar } from "@/components/FavoritoStar";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import type { PrazoCaixaStatus, ProcessoListItem } from "@/lib/api";
import { decorridoDesde } from "@/lib/duracao";
import { cn } from "@/lib/utils";

export type NivelDeEspera = "normal" | "atencao" | "critico";

/**
 * O destaque da linha vem do PRAZO, calculado no servidor
 * (`services/prazos.py::prazo_da_caixa`): o do encaminhamento vigente ou, sem
 * ele, o do serviço. Até 2026-10-13 vinha de 7 e 15 dias sem movimentação,
 * limiares escolhidos só para a tela ter o que pintar — um processo sem prazo
 * nenhum ficava vermelho, e um vencido ontem ficava sem cor.
 *
 * Sem prazo, a linha não é destacada: o tempo na caixa continua à vista, mas
 * não há do que estar atrasado.
 */
export function nivelDeEspera(status: PrazoCaixaStatus | null | undefined): NivelDeEspera {
  if (status === "atrasado") return "critico";
  if (status === "vencendo") return "atencao";
  return "normal";
}

const DIA_MS = 86_400_000;

/** Meia-noite local do dia de `d`, para contar dias de calendário. */
function diaDe(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

/**
 * O prazo em palavras: "vence em 3 dias", "vence hoje", "prazo vencido há 2
 * dias". Conta dias de CALENDÁRIO — "vence amanhã" às 23h não é "vence em 0
 * dias". Devolve `null` quando não há prazo.
 */
export function textoDoPrazo(
  status: PrazoCaixaStatus | null | undefined,
  venceEm: string | null | undefined,
  agora: Date = new Date(),
): string | null {
  if (!status || status === "sem_prazo" || !venceEm) return null;
  const vence = new Date(venceEm);
  if (Number.isNaN(vence.getTime())) return null;
  const dias = Math.round((diaDe(vence) - diaDe(agora)) / DIA_MS);
  if (status === "atrasado") {
    if (dias >= 0) return "prazo vencido hoje";
    return dias === -1 ? "prazo vencido ontem" : `prazo vencido há ${-dias} dias`;
  }
  if (dias <= 0) return "vence hoje";
  return dias === 1 ? "vence amanhã" : `vence em ${dias} dias`;
}

const ESPERA: Record<NivelDeEspera, { classe: string; prazo: string }> = {
  normal: { classe: "text-foreground", prazo: "text-muted-foreground" },
  atencao: {
    classe: "rounded-full bg-warning-soft px-2 py-0.5 font-medium text-warning-soft-foreground",
    prazo: "font-medium text-warning-soft-foreground",
  },
  critico: {
    classe: "rounded-full bg-danger-soft px-2 py-0.5 font-medium text-danger-soft-foreground",
    prazo: "font-medium text-danger-soft-foreground",
  },
};

interface Props {
  itens: ProcessoListItem[] | undefined;
  carregando: boolean;
  /** Com seleção (caixas que têm ação em lote): uma coluna de caixas de
   *  marcar à esquerda, e a do cabeçalho marca ou desmarca a página. */
  selecao?: {
    ids: Set<number>;
    alternar: (id: number) => void;
    alternarPagina: (marcar: boolean) => void;
  };
}

/**
 * Tabela de uma caixa de trabalho — colunas do layout de referência
 * (protótipo Figma "Sistema - Aprimora"): número, assunto, tempo na caixa,
 * envolvido, responsável.
 *
 * Diverge do protótipo no alinhamento, de propósito: lá tudo é centralizado,
 * e texto centralizado não forma coluna para o olho descer. Aqui texto alinha
 * à esquerda e o tempo, que é o que se compara entre linhas, à direita com
 * algarismos de largura fixa.
 */
export function TabelaCaixaProcessos({ itens, carregando, selecao }: Props) {
  const vazio = !carregando && (itens?.length ?? 0) === 0;
  const colunas = selecao ? 7 : 6;
  const todosMarcados =
    !!selecao && (itens?.length ?? 0) > 0 && (itens ?? []).every((p) => selecao.ids.has(p.id));
  const algumMarcado = !!selecao && (itens ?? []).some((p) => selecao.ids.has(p.id));
  return (
    <Table>
      <THead>
        <TR>
          {selecao && (
            <TH className="w-10">
              <Checkbox
                aria-label={todosMarcados ? "Desmarcar todos desta página" : "Marcar todos desta página"}
                checked={todosMarcados}
                ref={(el) => {
                  if (el) el.indeterminate = algumMarcado && !todosMarcados;
                }}
                onChange={() => selecao.alternarPagina(!todosMarcados)}
                disabled={(itens?.length ?? 0) === 0}
              />
            </TH>
          )}
          <TH>Nº do processo</TH>
          <TH>Assunto</TH>
          <TH className="text-right">Tempo na caixa</TH>
          <TH>Envolvido</TH>
          <TH>Responsável</TH>
          <TH className="text-right">Ações</TH>
        </TR>
      </THead>
      <TBody>
        {carregando && Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} cols={colunas} />)}
        {vazio && (
          <TR>
            <TD colSpan={colunas} className="p-0">
              <EmptyState
                icon={Inbox}
                title="Nenhum processo nesta caixa"
                description="Quando houver, eles aparecem aqui."
                className="border-0 bg-transparent"
              />
            </TD>
          </TR>
        )}
        {itens?.map((p) => {
          const href = `/m/protocolo/processos/${p.id}`;
          const espera = ESPERA[nivelDeEspera(p.prazo_caixa_status)];
          const prazo = textoDoPrazo(p.prazo_caixa_status, p.prazo_caixa_vence_em);
          return (
            <TR key={p.id}>
              {selecao && (
                <TD className="w-10">
                  <Checkbox
                    aria-label={`Selecionar ${p.nup ?? p.numero_processo ?? "processo"}`}
                    checked={selecao.ids.has(p.id)}
                    onChange={() => selecao.alternar(p.id)}
                  />
                </TD>
              )}
              <TD className="font-mono text-xs tabular-nums">
                <div className="flex items-center gap-1">
                  <FavoritoStar processo={p} size="sm" />
                  <Link
                    href={href}
                    className="rounded text-foreground underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {p.nup ?? p.numero_processo ?? "Rascunho"}
                  </Link>
                </div>
                {/* Junto ao número, como os ícones do SEI: é a coluna que o
                    olho percorre para achar o processo, e o assunto já ocupa
                    duas linhas (assunto e tipo). */}
                <MarcadoresDaLinha marcadores={p.marcadores} />
              </TD>
              <TD>
                <div className="line-clamp-1 text-sm">{p.assunto ?? "—"}</div>
                <div className="text-xs text-muted-foreground">{p.tipo_processo ?? ""}</div>
              </TD>
              <TD className="whitespace-nowrap text-right text-sm tabular-nums">
                {p.parado_desde ? (
                  <span className={cn(espera.classe)}>{decorridoDesde(p.parado_desde)}</span>
                ) : (
                  "—"
                )}
                {/* O motivo do destaque vai em texto visível: a cor sozinha não
                    informa quem não a enxerga, nem diz QUANDO vence. */}
                {prazo ? (
                  <span
                    className={cn("mt-0.5 block text-xs", espera.prazo)}
                    title={
                      p.prazo_caixa_origem === "encaminhamento"
                        ? "Prazo fixado no encaminhamento"
                        : "Prazo do serviço, contado da abertura"
                    }
                  >
                    {prazo}
                  </span>
                ) : null}
              </TD>
              <TD className="text-sm">{p.manifestante ?? "—"}</TD>
              <TD className="text-sm">
                {p.responsavel ?? (
                  <span className="text-warning-soft-foreground">Sem responsável</span>
                )}
              </TD>
              <TD className="text-right">
                <Link
                  href={href}
                  className="inline-flex h-9 items-center rounded-md border border-transparent px-3 text-xs font-medium text-primary transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Abrir →
                </Link>
              </TD>
            </TR>
          );
        })}
      </TBody>
    </Table>
  );
}
