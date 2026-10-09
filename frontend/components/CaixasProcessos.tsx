"use client";

import {
  Archive,
  ArrowDownToLine,
  ArrowUpFromLine,
  FileSearch,
  FolderInput,
  type LucideIcon,
  PenLine,
  Send,
  Rows3,
} from "lucide-react";
import Link from "next/link";

import type { CaixaProcesso, CaixasContagem } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * As caixas, na ordem do layout de referência (protótipo Figma "Sistema -
 * Aprimora"). Fonte única da ordem e dos rótulos: a tela valida o `?caixa=`
 * da URL contra esta lista.
 */
export const CAIXAS: { caixa: CaixaProcesso; rotulo: string; icone: LucideIcon }[] = [
  { caixa: "entrada", rotulo: "Caixa de entrada", icone: ArrowDownToLine },
  { caixa: "saida", rotulo: "Caixa de saída", icone: ArrowUpFromLine },
  { caixa: "analise", rotulo: "Análise", icone: FileSearch },
  { caixa: "externos", rotulo: "Externos", icone: FolderInput },
  { caixa: "aguardando_assinatura", rotulo: "Aguardando assinatura", icone: PenLine },
  { caixa: "enviado_para_assinatura", rotulo: "Enviado para assinatura", icone: Send },
  { caixa: "arquivados", rotulo: "Arquivados", icone: Archive },
];

export function caixaDaUrl(valor: string | null): CaixaProcesso | undefined {
  return CAIXAS.find((c) => c.caixa === valor)?.caixa;
}

export function rotuloDaCaixa(caixa: CaixaProcesso): string {
  return CAIXAS.find((c) => c.caixa === caixa)?.rotulo ?? caixa;
}

/**
 * Abrir uma caixa é uma visão NOVA, não um filtro a mais: o link carrega só a
 * caixa e `ativos=0`, descartando busca, assunto e período. É o que mantém a
 * promessa da tela — o número ao lado do rótulo é o total da lista que abre.
 * Somar a caixa aos filtros em curso quebraria essa conta em silêncio.
 */
export function hrefDaCaixa(base: string, caixa: CaixaProcesso | undefined): string {
  return caixa ? `${base}?caixa=${caixa}&ativos=0` : `${base}?ativos=0`;
}

interface Props {
  /** Caminho da tela de Processos, sem query. */
  base: string;
  ativa: CaixaProcesso | undefined;
  /** `undefined` enquanto carrega ou se a contagem falhou — a navegação segue. */
  contagem: CaixasContagem | undefined;
}

/**
 * Coluna de caixas da tela de Processos. Fica DENTRO da tela, e não no lugar
 * da barra lateral como no protótipo: a lateral é o menu do módulo, que tem
 * outras seções além desta.
 *
 * No celular vira uma faixa rolável acima da tabela.
 */
export function CaixasProcessos({ base, ativa, contagem }: Props) {
  const item =
    "flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
  const inativo = "text-foreground-muted hover:bg-muted hover:text-foreground";
  const ativo = "bg-brand/10 font-semibold text-foreground";

  return (
    <nav aria-label="Caixas de processos">
      <ul className="flex gap-1 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
        <li className="shrink-0">
          <Link
            href={hrefDaCaixa(base, undefined)}
            aria-current={ativa === undefined ? "page" : undefined}
            className={cn(item, ativa === undefined ? ativo : inativo)}
          >
            <Rows3 className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span className="whitespace-nowrap lg:flex-1">Todos os processos</span>
          </Link>
        </li>
        {CAIXAS.map(({ caixa, rotulo, icone: Icone }) => {
          const selecionada = ativa === caixa;
          const n = contagem?.[caixa];
          return (
            <li key={caixa} className="shrink-0">
              <Link
                href={hrefDaCaixa(base, caixa)}
                aria-current={selecionada ? "page" : undefined}
                className={cn(item, selecionada ? ativo : inativo)}
              >
                <Icone
                  className={cn("h-4 w-4 shrink-0", selecionada && "text-brand")}
                  aria-hidden="true"
                />
                <span className="whitespace-nowrap lg:flex-1">{rotulo}</span>
                {n !== undefined ? (
                  <span
                    className={cn(
                      "min-w-6 rounded-full px-1.5 text-center text-xs tabular-nums",
                      // Zero não pede atenção: fica apagado, e o que tem
                      // processo salta sem precisar de cor de alerta.
                      n === 0
                        ? "text-foreground-subtle"
                        : selecionada
                          ? "bg-brand text-primary-foreground"
                          : "bg-muted font-medium text-foreground",
                    )}
                  >
                    {n}
                    <span className="sr-only"> {n === 1 ? "processo" : "processos"}</span>
                  </span>
                ) : null}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
