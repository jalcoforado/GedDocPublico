"use client";

import { ArrowDown, ArrowRight, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type IntentDaSaida = "success" | "warning" | "danger" | "info" | "neutral";

export interface SaidaDoPasso {
  /** O que a pessoa decide. */
  label: string;
  /** Para onde o item vai. */
  destino: string;
  icon: LucideIcon;
  intent: IntentDaSaida;
}

export interface PassoDoFluxo {
  key: string;
  /** O ato, no infinitivo — é o que o operador faz ali. */
  titulo: string;
  responsavel: string;
  descricao: string;
  icon: LucideIcon;
  saidas: SaidaDoPasso[];
  /** Tela onde o passo é trabalhado. */
  tela: { href: string; label: string };
  /** Unidade do que é contado ("processo", "processos"). */
  unidade?: [string, string];
}

export interface FaseDoFluxo<P extends PassoDoFluxo = PassoDoFluxo> {
  titulo: string;
  descricao: string;
  passos: P[];
}

function plural(n: number, [um, varios]: [string, string]): string {
  return n === 1 ? `1 ${um}` : `${n} ${varios}`;
}

function CartaoDoPasso({
  passo,
  numero,
  quantidade,
  destaque,
  podeAbrir,
  rotuloDoDestaque,
  unidadePadrao,
  ultimo,
}: {
  passo: PassoDoFluxo;
  numero: number;
  quantidade: number | null;
  destaque: boolean;
  podeAbrir: boolean;
  rotuloDoDestaque: string;
  unidadePadrao: [string, string];
  ultimo: boolean;
}) {
  const Icon = passo.icon;
  const temTrabalho = (quantidade ?? 0) > 0;
  const unidade = passo.unidade ?? unidadePadrao;

  return (
    <li className="flex min-w-0 flex-col lg:flex-1 lg:flex-row" data-testid={`passo-${passo.key}`}>
      <div
        className={cn(
          "flex min-w-0 flex-1 flex-col gap-3 rounded-card border bg-surface-1 p-4 shadow-card",
          destaque ? "border-brand/60 ring-1 ring-brand/30" : "border-border",
        )}
      >
        <div className="flex items-start gap-3">
          <div
            className={cn(
              "relative flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
              destaque ? "bg-brand/12 text-brand" : "bg-muted text-foreground-muted",
            )}
          >
            <Icon className="h-5 w-5" aria-hidden="true" />
            <span
              aria-hidden="true"
              className="absolute -left-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full border border-border bg-surface-1 text-[11px] font-semibold tabular-nums text-foreground"
            >
              {numero}
            </span>
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-display text-sm font-semibold leading-tight text-foreground">
              <span className="sr-only">Passo {numero}: </span>
              {passo.titulo}
            </h3>
            <p className="text-xs text-foreground-muted">{passo.responsavel}</p>
          </div>
        </div>

        {(destaque || quantidade !== null) && (
          <div className="flex flex-wrap items-center gap-1.5">
            {destaque && <Badge intent="info">{rotuloDoDestaque}</Badge>}
            {quantidade !== null && (
              <Badge intent={temTrabalho ? "warning" : "neutral"}>
                {temTrabalho ? `${plural(quantidade, unidade)} aqui agora` : "Nada aqui agora"}
              </Badge>
            )}
          </div>
        )}

        <p className="text-sm text-foreground-muted">{passo.descricao}</p>

        <ul className="space-y-1.5" aria-label={`Saídas de ${passo.titulo}`}>
          {passo.saidas.map((s) => (
            <li key={s.label} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
              <Badge intent={s.intent} icon={s.icon}>
                {s.label}
              </Badge>
              <span className="text-foreground-muted">{s.destino}</span>
            </li>
          ))}
        </ul>

        {podeAbrir && (
          <div className="mt-auto pt-1">
            <Button asChild size="sm" variant={temTrabalho ? "primary" : "secondary"}>
              <Link href={passo.tela.href}>{passo.tela.label}</Link>
            </Button>
          </div>
        )}
      </div>

      {!ultimo && (
        <div
          aria-hidden="true"
          className="flex shrink-0 items-center justify-center py-1 text-foreground-subtle lg:px-1 lg:py-0"
        >
          <ArrowDown className="h-4 w-4 lg:hidden" />
          <ArrowRight className="hidden h-4 w-4 lg:block" />
        </div>
      )}
    </li>
  );
}

interface FasesDoFluxoProps<P extends PassoDoFluxo> {
  fases: FaseDoFluxo<P>[];
  /** Quanto há no passo agora. `null` = não dá para saber; o cartão não
   *  inventa um zero. */
  quantidadeDe: (passo: P) => number | null;
  /** O passo é da pessoa logada: borda de destaque e a etiqueta. */
  destaque: (passo: P) => boolean;
  /** Mostra o atalho para a tela de trabalho. */
  podeAbrir: (passo: P) => boolean;
  rotuloDoDestaque?: string;
  /** Unidade do que se conta quando o passo não diz a sua. */
  unidadePadrao: [string, string];
  /** Como chamar cada seção no rótulo acessível. "Fase" quando as seções são
   *  etapas de um mesmo caminho; "Fluxo" quando são caminhos independentes. */
  rotuloDaSecao?: string;
  /** Recomeça a numeração em cada seção. Para caminhos independentes: numerar
   *  de 1 a N através deles sugeriria uma ordem que não existe. */
  numerarPorSecao?: boolean;
}

/**
 * As fases de um processo de trabalho, cada uma como uma linha de passos
 * numerados (coluna em tela estreita). Só apresenta: de onde vêm as
 * quantidades e de quem é cada passo, quem decide é o módulo que o usa
 * (`pagamentos/MapaDoProcesso`, `protocolo/MapaDoProtocolo`).
 *
 * Cada passo responde quatro perguntas de quem opera: quem faz, o que faz, o
 * que pode decidir e para onde cada decisão leva.
 */
export function FasesDoFluxo<P extends PassoDoFluxo>({
  fases,
  quantidadeDe,
  destaque,
  podeAbrir,
  rotuloDoDestaque = "Sua etapa",
  unidadePadrao,
  rotuloDaSecao = "Fase",
  numerarPorSecao = false,
}: FasesDoFluxoProps<P>) {
  let numero = 0;
  return (
    <>
      {fases.map((fase) => (
        <section
          key={fase.titulo}
          aria-label={`${rotuloDaSecao}: ${fase.titulo}`}
          className="space-y-3"
        >
          <div>
            <h2 className="font-display text-base font-semibold text-foreground">{fase.titulo}</h2>
            <p className="text-sm text-foreground-muted">{fase.descricao}</p>
          </div>
          <ol className="flex flex-col lg:flex-row lg:items-stretch">
            {fase.passos.map((passo, idx) => {
              numero = numerarPorSecao ? idx + 1 : numero + 1;
              return (
                <CartaoDoPasso
                  key={passo.key}
                  passo={passo}
                  numero={numero}
                  quantidade={quantidadeDe(passo)}
                  destaque={destaque(passo)}
                  podeAbrir={podeAbrir(passo)}
                  rotuloDoDestaque={rotuloDoDestaque}
                  unidadePadrao={unidadePadrao}
                  ultimo={idx === fase.passos.length - 1}
                />
              );
            })}
          </ol>
        </section>
      ))}
    </>
  );
}
