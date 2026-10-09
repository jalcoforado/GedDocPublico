"use client";

import { Inbox } from "lucide-react";
import Link from "next/link";

import { FavoritoStar } from "@/components/FavoritoStar";
import { EmptyState } from "@/components/ui/empty-state";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import type { ProcessoListItem } from "@/lib/api";
import { decorridoDesde } from "@/lib/duracao";
import { cn } from "@/lib/utils";

/**
 * A partir de quantos dias sem movimentação a linha pede atenção.
 *
 * São limiares PROVISÓRIOS, escolhidos para a tela ter o que destacar — não
 * vêm de regra de negócio. O critério certo é o prazo do assunto ou do
 * encaminhamento (`data_prazo`), que a listagem ainda não carrega.
 */
export const DIAS_ATENCAO = 7;
export const DIAS_CRITICO = 15;

export type NivelDeEspera = "normal" | "atencao" | "critico";

export function nivelDeEspera(iso: string | null, agora: Date = new Date()): NivelDeEspera {
  if (!iso) return "normal";
  const inicio = new Date(iso).getTime();
  if (Number.isNaN(inicio)) return "normal";
  const dias = (agora.getTime() - inicio) / 86_400_000;
  if (dias >= DIAS_CRITICO) return "critico";
  if (dias >= DIAS_ATENCAO) return "atencao";
  return "normal";
}

const ESPERA: Record<NivelDeEspera, { classe: string; rotulo: string | null }> = {
  normal: { classe: "text-foreground", rotulo: null },
  atencao: {
    classe: "rounded-full bg-warning-soft px-2 py-0.5 font-medium text-warning-soft-foreground",
    rotulo: "atenção",
  },
  critico: {
    classe: "rounded-full bg-danger-soft px-2 py-0.5 font-medium text-danger-soft-foreground",
    rotulo: "parado há muito tempo",
  },
};

interface Props {
  itens: ProcessoListItem[] | undefined;
  carregando: boolean;
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
export function TabelaCaixaProcessos({ itens, carregando }: Props) {
  const vazio = !carregando && (itens?.length ?? 0) === 0;
  return (
    <Table>
      <THead>
        <TR>
          <TH>Nº do processo</TH>
          <TH>Assunto</TH>
          <TH className="text-right">Tempo na caixa</TH>
          <TH>Envolvido</TH>
          <TH>Responsável</TH>
          <TH className="text-right">Ações</TH>
        </TR>
      </THead>
      <TBody>
        {carregando && Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} cols={6} />)}
        {vazio && (
          <TR>
            <TD colSpan={6} className="p-0">
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
          const espera = ESPERA[nivelDeEspera(p.parado_desde ?? null)];
          return (
            <TR key={p.id}>
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
              </TD>
              <TD>
                <div className="line-clamp-1 text-sm">{p.assunto ?? "—"}</div>
                <div className="text-xs text-muted-foreground">{p.tipo_processo ?? ""}</div>
              </TD>
              <TD className="whitespace-nowrap text-right text-sm tabular-nums">
                {p.parado_desde ? (
                  <span className={cn(espera.classe)}>
                    {decorridoDesde(p.parado_desde)}
                    {/* A cor sozinha não informa quem não a enxerga. */}
                    {espera.rotulo ? <span className="sr-only"> — {espera.rotulo}</span> : null}
                  </span>
                ) : (
                  "—"
                )}
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
