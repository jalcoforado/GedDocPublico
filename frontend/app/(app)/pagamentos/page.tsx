"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type Debito, type ParcelaFila } from "@/lib/api";

function fmtMoeda(v: string): string {
  const n = Number(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function fmtData(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y.slice(2)}`;
}

// Filas podem ter dezenas de itens (massa real): cada card mostra os primeiros e
// aponta para a lista completa, mantendo a home compacta.
const MAX_ITENS_CARD = 8;

function VerTodas({ total, href }: { total: number; href: string }) {
  if (total <= MAX_ITENS_CARD) return null;
  return (
    <Link href={href} className="mt-2 block text-xs text-primary hover:underline">
      + {total - MAX_ITENS_CARD} outras — ver todas
    </Link>
  );
}

function DebitoLista({ itens }: { itens: Debito[] }) {
  if (itens.length === 0) {
    return <p className="text-sm text-muted-foreground">Nada pendente.</p>;
  }
  return (
    <>
      <ul className="space-y-1">
        {itens.slice(0, MAX_ITENS_CARD).map((d) => (
          <li key={d.id} className="flex items-center justify-between gap-2 text-sm">
            <Link
              href={`/pagamentos/contas-a-pagar/${d.id}`}
              className="min-w-0 flex-1 truncate text-primary hover:underline"
            >
              {d.nome_fornecedor} — {d.descricao}
            </Link>
            <span className="shrink-0 tabular-nums">{fmtMoeda(d.valor_total)}</span>
          </li>
        ))}
      </ul>
      <VerTodas total={itens.length} href="/pagamentos/contas-a-pagar" />
    </>
  );
}

function CardFila({ title, itens }: { title: string; itens: Debito[] | null }) {
  if (itens === null) return null;
  return (
    <div className="rounded-lg border border-border bg-surface-1 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        <Badge intent={itens.length > 0 ? "warning" : "neutral"}>{itens.length}</Badge>
      </div>
      <DebitoLista itens={itens} />
    </div>
  );
}

function CardAutorizar({ itens }: { itens: Debito[] | null }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [selecionados, setSelecionados] = useState<number[]>([]);

  const autorizarM = useMutation({
    mutationFn: () => api.pagamentos.autorizar(selecionados),
    onSuccess: (op) => {
      qc.invalidateQueries({ queryKey: ["pag-fila"] });
      qc.invalidateQueries({ queryKey: ["pag-debitos"] });
      toast.success(`Ordem de pagamento ${op.numero} gerada.`);
      setSelecionados([]);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (itens === null) return null;

  function toggle(id: number) {
    setSelecionados((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  return (
    <div className="rounded-lg border border-border bg-surface-1 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Aguardando autorização</h2>
        <Badge intent={itens.length > 0 ? "warning" : "neutral"}>{itens.length}</Badge>
      </div>
      {itens.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nada pendente.</p>
      ) : (
        <>
          <ul className="space-y-1">
            {itens.slice(0, MAX_ITENS_CARD).map((d) => (
              <li key={d.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selecionados.includes(d.id)}
                  onChange={() => toggle(d.id)}
                />
                <Link
                  href={`/pagamentos/contas-a-pagar/${d.id}`}
                  className="min-w-0 flex-1 truncate text-primary hover:underline"
                >
                  {d.nome_fornecedor} — {d.descricao}
                </Link>
                <span className="shrink-0 tabular-nums">{fmtMoeda(d.valor_total)}</span>
              </li>
            ))}
          </ul>
          <VerTodas total={itens.length} href="/pagamentos/contas-a-pagar" />
          <Button
            className="mt-3"
            size="sm"
            disabled={selecionados.length === 0 || autorizarM.isPending}
            onClick={() => autorizarM.mutate()}
          >
            {autorizarM.isPending ? "Autorizando..." : "Autorizar selecionados"}
          </Button>
        </>
      )}
    </div>
  );
}

function CardParcelas({ itens }: { itens: ParcelaFila[] | null }) {
  if (itens === null) return null;
  return (
    <div className="rounded-lg border border-border bg-surface-1 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Parcelas a pagar</h2>
        <Badge intent={itens.length > 0 ? "warning" : "neutral"}>{itens.length}</Badge>
      </div>
      {itens.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nada pendente.</p>
      ) : (
        <>
          <ul className="space-y-1">
            {itens.slice(0, MAX_ITENS_CARD).map((p) => (
              <li
                key={p.id}
                className={
                  "flex items-center justify-between gap-2 text-sm " +
                  (p.vencida ? "text-danger-soft-foreground" : "")
                }
              >
                <Link
                  href={`/pagamentos/contas-a-pagar/${p.id_debito}`}
                  className="min-w-0 flex-1 truncate hover:underline"
                  title={`${p.nome_fornecedor} — ${p.descricao_debito} (parcela ${p.numero})`}
                >
                  {p.vencida && "⚠ "}
                  {p.nome_fornecedor}
                </Link>
                <span className="shrink-0 whitespace-nowrap tabular-nums">
                  {fmtMoeda(p.valor)} · {fmtData(p.vencimento)}
                </span>
              </li>
            ))}
          </ul>
          <VerTodas total={itens.length} href="/pagamentos/contas-a-pagar" />
        </>
      )}
    </div>
  );
}

export default function PagamentosHomePage() {
  const filaQ = useQuery({
    queryKey: ["pag-fila"],
    queryFn: () => api.pagamentos.minhaFila(),
  });
  const painelQ = useQuery({
    queryKey: ["pag-caixa-painel"],
    queryFn: () => api.pagamentos.caixa.painel(),
  });

  const fila = filaQ.data;
  const painel = painelQ.data ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-aprimora">Pagamentos — o que precisa de mim</h1>
        <p className="text-sm text-muted-foreground">
          Resumo dos débitos e parcelas que aguardam sua ação.
        </p>
      </div>

      {fila && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <CardFila title="Meus rascunhos" itens={fila.solicitar} />
          <CardFila title="Aguardando minha aprovação" itens={fila.aprovar} />
          <CardAutorizar itens={fila.autorizar} />
          <CardParcelas itens={fila.pagar} />
        </div>
      )}

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Caixa</h2>
          <Link href="/pagamentos/caixa" className="text-sm text-primary hover:underline">
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
      </div>
    </div>
  );
}
