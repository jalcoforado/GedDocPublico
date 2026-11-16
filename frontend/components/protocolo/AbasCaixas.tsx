"use client";

import { useQuery } from "@tanstack/react-query";
import { Rows3 } from "lucide-react";
import Link from "next/link";
import { useRef } from "react";

import type { CaixaProcesso } from "@/lib/api";
import { api } from "@/lib/api";
import { IndicadorDeAba } from "@/components/ui/indicador-aba";
import { CAIXAS, ROTA_PROCESSOS, hrefDaCaixa } from "@/lib/caixas-processos";
import { cn } from "@/lib/utils";

/**
 * As caixas de trabalho como abas da tela de Processos, cada uma com o seu
 * contador. Moravam no menu lateral, oito itens com o mesmo caminho: o menu
 * virava o filtro de uma tela só. Aqui ficam onde o recorte acontece.
 *
 * **Não são `role="tab"`**, pelo mesmo motivo do antigo `RelatoriosNav` (SI-34 o trocou por uma página só): cada aba é
 * um link que troca a URL (`?caixa=`), não um painel na mesma página. O padrão
 * é `<nav>` + links + `aria-current="page"` no ativo.
 *
 * "Todos" não leva número: não é uma caixa, e o total da lista aberta já
 * aparece no rodapé da tabela. A contagem é a mesma do painel de controle
 * (`GET /processos/caixas`) — o número da aba é o total da lista que ela abre.
 * Se a contagem falhar, as abas continuam navegáveis, só sem número.
 */
export function AbasCaixas({ caixa }: { caixa: CaixaProcesso | undefined }) {
  const contagemQ = useQuery({
    queryKey: ["processos-caixas"],
    queryFn: () => api.processos.caixas(),
    // Encaminhar e receber mudam os números; ao voltar para a lista, reconta.
    staleTime: 0,
  });
  const contagem = contagemQ.data;
  const lista = useRef<HTMLUListElement>(null);

  const abas = [
    { chave: "todos", rotulo: "Todos", titulo: "Todos", href: ROTA_PROCESSOS, icone: Rows3, ativo: !caixa, n: undefined },
    ...CAIXAS.map((c) => ({
      chave: c.caixa,
      rotulo: c.rotuloCurto,
      titulo: c.rotulo,
      href: hrefDaCaixa(c.caixa),
      icone: c.icone,
      ativo: caixa === c.caixa,
      n: contagem?.[c.caixa],
    })),
  ];

  return (
    <nav aria-label="Caixas de trabalho" className="border-b border-border">
      <ul ref={lista} className="relative -mb-px flex gap-0.5 overflow-x-auto">
        {abas.map((a) => {
          const Icone = a.icone;
          return (
            <li key={a.chave} className="shrink-0">
              <Link
                href={a.href}
                title={a.rotulo === a.titulo ? undefined : a.titulo}
                aria-current={a.ativo ? "page" : undefined}
                className={cn(
                  "flex h-10 items-center gap-1 whitespace-nowrap rounded-t-md border-b-2 border-transparent px-2 text-sm font-medium transition-colors duration-fast min-[1700px]:gap-1.5 min-[1700px]:px-3",
                  a.ativo
                    ? "text-primary"
                    : "text-foreground-muted hover:border-border-strong hover:bg-muted hover:text-foreground",
                )}
              >
                {/* O ícone só aparece a partir de 1700px: abaixo disso as nove
                    abas não cabem lado a lado com ele — o conteúdo perde a barra
                    lateral (288px) e o respiro do main (medido a 1500). */}
                <Icone className="hidden h-4 w-4 shrink-0 min-[1700px]:block" aria-hidden="true" />
                <span>{a.rotulo}</span>
                {a.rotulo !== a.titulo && <span className="sr-only"> ({a.titulo})</span>}
                <Contador n={a.n} ativo={a.ativo} />
              </Link>
            </li>
          );
        })}
        {/* O sublinhado da aba ativa desliza de uma caixa para a outra. */}
        <li aria-hidden="true" className="contents">
          <IndicadorDeAba lista={lista} seletor='[aria-current="page"]' chave={caixa ?? "todos"} />
        </li>
      </ul>
    </nav>
  );
}

function Contador({ n, ativo }: { n: number | undefined; ativo: boolean }) {
  if (n === undefined) return null;
  return (
    // Zero não pede atenção: fica apagado. O que tem processo salta sem
    // precisar de cor de alerta — mesma regra que o menu seguia.
    <span
      className={cn(
        "min-w-5 rounded-full px-1.5 text-center text-xs tabular-nums",
        n === 0
          ? "text-foreground-subtle"
          : ativo
            ? "bg-primary font-semibold text-primary-foreground"
            : "bg-muted font-semibold text-foreground",
      )}
    >
      {n}
      <span className="sr-only"> {n === 1 ? "processo" : "processos"}</span>
    </span>
  );
}
