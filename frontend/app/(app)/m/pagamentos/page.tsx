"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, GitBranch, MessageSquareWarning, Wallet } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { fmtData, fmtMoeda } from "@/components/pagamentos/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api, type Debito, type ParcelaFila, type PendenciaAjuste } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

/**
 * Visão geral de Pagamentos — o que espera pela pessoa, do pedido ao
 * pagamento (redesenho de 2026-11-06).
 *
 * Antes eram sete cartões do mesmo peso, metade deles dizendo "Nada
 * pendente", cada linha um link colorido cortado no meio, e a régua do rito
 * logo acima repetindo as etapas sem número nenhum. Agora a régua É o resumo
 * — cada etapa traz a contagem e leva à fila dela — e embaixo vem uma lista
 * só, com as filas que têm o que fazer.
 */

/** Por fila na lista: o resto está a um clique, na tela da fila. */
const MAX_POR_FILA = 5;

type Fila =
  | { tipo: "debito"; titulo: string; href: string; itens: Debito[] | null }
  | { tipo: "parcela"; titulo: string; href: string; itens: ParcelaFila[] | null };

/** Os cinco atos do rito (Lei 4.320/64), cada um somando as filas dele. */
const ETAPAS: { rotulo: string; legenda: string; filas: string[] }[] = [
  { rotulo: "Solicitar", legenda: "rascunhos seus", filas: ["Meus rascunhos"] },
  {
    rotulo: "Aprovar",
    legenda: "a validar ou decidir",
    filas: ["Aguardando minha validação", "Aguardando decisão do gestor"],
  },
  { rotulo: "Autorizar despesa", legenda: "a autorizar", filas: ["Aguardando autorização"] },
  { rotulo: "Liberar pagamento", legenda: "parcelas a liberar", filas: ["Pagamentos a liberar"] },
  { rotulo: "Pagar", legenda: "parcelas a pagar", filas: ["Tesouraria — a pagar"] },
];

function Etapas({ filas }: { filas: Fila[] }) {
  return (
    <nav
      aria-label="Etapas do pagamento"
      className="grid grid-cols-2 overflow-hidden rounded-card border border-border bg-surface-1 shadow-card sm:grid-cols-3 lg:grid-cols-5"
    >
      {ETAPAS.map((e, i) => {
        const minhas = filas.filter((f) => e.filas.includes(f.titulo) && f.itens !== null);
        const total = minhas.reduce((s, f) => s + (f.itens?.length ?? 0), 0);
        // Leva à primeira fila da etapa que tem algo; senão, à primeira dela.
        const destino = minhas.find((f) => (f.itens?.length ?? 0) > 0) ?? minhas[0];
        const conteudo = (
          <>
            <span className="flex items-center gap-2 text-xs font-medium text-foreground-muted">
              <span
                aria-hidden="true"
                className={cn(
                  "inline-flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-semibold",
                  total > 0 ? "bg-accent text-accent-foreground" : "bg-muted text-foreground-subtle",
                )}
              >
                {i + 1}
              </span>
              {e.rotulo}
            </span>
            <span
              className={cn(
                "font-display text-3xl font-semibold tabular-nums",
                total > 0 ? "text-foreground" : "text-foreground-subtle",
              )}
            >
              {destino ? total : "—"}
            </span>
            <span className="text-xs text-foreground-subtle">{destino ? e.legenda : "sem acesso"}</span>
          </>
        );
        // Divisórias: à direita entre colunas; embaixo só quando quebra linha.
        const caixa = "flex flex-col gap-1.5 border-b border-r border-border px-5 py-4 lg:border-b-0 lg:last:border-r-0";
        return destino ? (
          <Link
            key={e.rotulo}
            href={destino.href}
            aria-label={`${e.rotulo}: ${total} ${e.legenda}`}
            className={cn(caixa, "transition-colors duration-fast hover:bg-surface-2")}
          >
            {conteudo}
          </Link>
        ) : (
          <div key={e.rotulo} className={caixa}>
            {conteudo}
          </div>
        );
      })}
    </nav>
  );
}

function Linha({
  href,
  titulo,
  detalhe,
  valor,
  extra,
}: {
  href: string;
  titulo: string;
  detalhe: string;
  valor: string;
  extra?: ReactNode;
}) {
  return (
    <li>
      <Link
        href={href}
        className="flex items-center gap-4 px-5 py-3 transition-colors duration-fast hover:bg-surface-2"
      >
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-foreground">{titulo}</span>
          <span className="block truncate text-xs text-foreground-muted">{detalhe}</span>
        </span>
        <span className="flex shrink-0 flex-col items-end gap-0.5">
          <span className="text-sm font-medium tabular-nums text-foreground">{valor}</span>
          {extra}
        </span>
      </Link>
    </li>
  );
}

function BlocoDaFila({ fila }: { fila: Fila }) {
  const total = fila.itens?.length ?? 0;
  return (
    <section aria-label={fila.titulo}>
      <div className="flex items-center gap-3 border-b border-border bg-surface-2/60 px-5 py-2.5">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground-muted">{fila.titulo}</h3>
        <Badge intent="warning">{total}</Badge>
        <Link
          href={fila.href}
          className="-mx-1.5 ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
        >
          {total > MAX_POR_FILA ? `ver as ${total}` : "abrir a fila"}
          <ArrowRight className="h-3 w-3" aria-hidden="true" />
        </Link>
      </div>
      <ul className="divide-y divide-border">
        {fila.tipo === "debito"
          ? (fila.itens ?? []).slice(0, MAX_POR_FILA).map((d) => (
              <Linha
                key={d.id}
                href={`/m/pagamentos/solicitacoes/${d.id}`}
                titulo={d.nome_fornecedor}
                detalhe={d.descricao}
                valor={fmtMoeda(d.valor_total)}
              />
            ))
          : (fila.itens ?? []).slice(0, MAX_POR_FILA).map((p) => (
              <Linha
                key={p.id}
                href={`/m/pagamentos/solicitacoes/${p.id_debito}`}
                titulo={p.nome_fornecedor}
                detalhe={`${p.descricao_debito} · parcela ${p.numero}`}
                valor={fmtMoeda(p.valor)}
                extra={
                  p.vencida ? (
                    <Badge intent="danger">venceu {fmtData(p.vencimento)}</Badge>
                  ) : (
                    <span className="text-xs tabular-nums text-foreground-subtle">
                      vence {fmtData(p.vencimento)}
                    </span>
                  )
                }
              />
            ))}
      </ul>
    </section>
  );
}

function Pendencias({ itens }: { itens: PendenciaAjuste[] }) {
  return (
    <section
      aria-labelledby="pendencias-ajuste"
      className="overflow-hidden rounded-card border border-border bg-surface-1 shadow-card"
    >
      {/* A cor do alerta fica no ícone; uma faixa inteira em âmbar pesava
          demais, sobretudo no tema escuro. */}
      <div className="flex items-center gap-3 border-b border-border px-5 py-3">
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-warning-soft text-warning-soft-foreground">
          <MessageSquareWarning className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
        <h2 id="pendencias-ajuste" className="font-display text-base font-semibold text-foreground">
          Pendências para você responder
        </h2>
        <Badge intent="warning">{itens.length}</Badge>
      </div>
      <ul className="divide-y divide-border">
        {itens.slice(0, MAX_POR_FILA).map((p) => (
          <li key={p.id_pedido}>
            <Link
              href={`/m/pagamentos/solicitacoes/${p.id_debito}`}
              title={p.motivo}
              className="flex items-center gap-4 px-5 py-3 transition-colors duration-fast hover:bg-surface-2"
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-foreground">{p.descricao_debito}</span>
                <span className="block truncate text-xs text-foreground-muted">{p.motivo}</span>
              </span>
              {p.prazo && (
                <span className="shrink-0 whitespace-nowrap text-xs tabular-nums text-foreground-muted">
                  até {fmtData(p.prazo)}
                </span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function PagamentosHomePage() {
  const filaQ = useQuery({
    queryKey: ["pag-fila"],
    queryFn: () => api.pagamentos.minhaFila(),
  });
  // O painel de caixa exige `pagamento_cadastro` no backend. Para os demais
  // perfis a consulta devolvia 403 e a seção aparecia como "Nenhuma conta
  // cadastrada" — informação falsa. Quem não pode ver não consulta nem vê.
  const { can } = useAuth();
  const veCaixa = can("pagamento_cadastro");
  const painelQ = useQuery({
    queryKey: ["pag-caixa-painel"],
    queryFn: () => api.pagamentos.caixa.painel(),
    enabled: veCaixa,
  });

  const fila = filaQ.data;
  const painel = painelQ.data ?? [];

  // `null` numa fila = o perfil não alcança aquela etapa: ela some da lista
  // e a etapa aparece como "sem acesso".
  const filas: Fila[] = fila
    ? [
        { tipo: "debito", titulo: "Meus rascunhos", href: "/m/pagamentos/solicitacoes", itens: fila.solicitar },
        { tipo: "debito", titulo: "Aguardando minha validação", href: "/m/pagamentos/solicitacoes/validacao", itens: fila.validar },
        { tipo: "debito", titulo: "Aguardando decisão do gestor", href: "/m/pagamentos/solicitacoes/gestor", itens: fila.encaminhar },
        { tipo: "debito", titulo: "Aguardando autorização", href: "/m/pagamentos/solicitacoes/autoridade", itens: fila.autorizar },
        { tipo: "parcela", titulo: "Pagamentos a liberar", href: "/m/pagamentos/autorizacao?tab=pagamento", itens: fila.liberar },
        { tipo: "parcela", titulo: "Tesouraria — a pagar", href: "/m/pagamentos/tesouraria", itens: fila.pagar },
      ]
    : [];
  const comItens = filas.filter((f) => (f.itens?.length ?? 0) > 0);
  const pendencias = fila?.pendencias_ajuste ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Wallet}
        title="Visão geral"
        description="O que espera por você em Pagamentos, do pedido ao pagamento."
        actions={
          <Button asChild variant="secondary">
            <Link href="/m/pagamentos/fluxo">
              <GitBranch className="h-4 w-4" aria-hidden="true" />
              Fluxo do processo
            </Link>
          </Button>
        }
      />

      {!fila ? (
        <div role="status" className="space-y-6 animate-aparece-depois motion-reduce:animate-none">
          <span className="sr-only">Carregando…</span>
          <Skeleton aria-hidden="true" role="presentation" className="h-28 rounded-card" variant="shimmer" />
          <Skeleton aria-hidden="true" role="presentation" className="h-64 rounded-card" variant="shimmer" />
        </div>
      ) : (
        <>
          <Etapas filas={filas} />

          {pendencias.length > 0 && <Pendencias itens={pendencias} />}

          <section
            aria-labelledby="na-sua-mesa"
            className="overflow-hidden rounded-card border border-border bg-surface-1 shadow-card"
          >
            <h2
              id="na-sua-mesa"
              className="border-b border-border px-5 py-4 font-display text-base font-semibold text-foreground"
            >
              Na sua mesa
            </h2>
            {comItens.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-5 py-10 text-center">
                <CheckCircle2 className="h-8 w-8 text-success" aria-hidden="true" />
                <p className="text-sm font-medium text-foreground">Nada esperando por você.</p>
                <p className="text-xs text-foreground-muted">
                  Quando um débito chegar a uma etapa sua, ele aparece aqui.
                </p>
              </div>
            ) : (
              comItens.map((f) => <BlocoDaFila key={f.titulo} fila={f} />)
            )}
          </section>
        </>
      )}

      {veCaixa && (
        <section aria-labelledby="caixa-titulo" className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 id="caixa-titulo" className="font-display text-base font-semibold text-foreground">
              Caixa
            </h2>
            <Link
              href="/m/pagamentos/caixa"
              className="-mx-1.5 rounded px-1.5 py-0.5 text-sm font-medium text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
            >
              ver caixa
            </Link>
          </div>
          <Table>
            <THead>
              <TR>
                <TH>Conta</TH>
                <TH className="text-right">Disponível</TH>
                <TH className="text-right">Comprometido</TH>
                <TH className="text-right">Saldo atual</TH>
              </TR>
            </THead>
            <TBody>
              {!painelQ.isLoading && painel.length === 0 && (
                <TR>
                  <TD colSpan={4} className="py-6 text-center text-sm text-muted-foreground">
                    Nenhuma conta cadastrada.
                  </TD>
                </TR>
              )}
              {painel.map((c) => (
                <TR key={c.id_conta}>
                  <TD>{c.nome}</TD>
                  <TD className="text-right tabular-nums">{fmtMoeda(c.disponivel)}</TD>
                  <TD className="text-right tabular-nums">{fmtMoeda(c.comprometido)}</TD>
                  <TD className="text-right text-base font-semibold tabular-nums">
                    {fmtMoeda(c.saldo_atual)}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </section>
      )}
    </div>
  );
}
