"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { RitoPagamento } from "@/components/pagamentos/RitoPagamento";
import { fmtData, fmtMoeda } from "@/components/pagamentos/format";
import { api, type Debito, type ParcelaFila } from "@/lib/api";

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

function AbrirTela({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className="mt-3 block text-xs text-primary hover:underline">
      {label} →
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

function CardFila({
  title,
  itens,
  abrirHref,
  abrirLabel,
}: {
  title: string;
  itens: Debito[] | null;
  abrirHref: string;
  abrirLabel: string;
}) {
  if (itens === null) return null;
  return (
    <div className="rounded-lg border border-border bg-surface-1 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        <Badge intent={itens.length > 0 ? "warning" : "neutral"}>{itens.length}</Badge>
      </div>
      <DebitoLista itens={itens} />
      <AbrirTela href={abrirHref} label={abrirLabel} />
    </div>
  );
}

function CardParcelas({
  title,
  itens,
  abrirHref,
  abrirLabel,
}: {
  title: string;
  itens: ParcelaFila[] | null;
  abrirHref: string;
  abrirLabel: string;
}) {
  if (itens === null) return null;
  return (
    <div className="rounded-lg border border-border bg-surface-1 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
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
      <AbrirTela href={abrirHref} label={abrirLabel} />
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

      <div className="rounded-lg border border-border bg-surface-1 px-4 py-3">
        <RitoPagamento />
      </div>

      {fila && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <CardFila
            title="Meus rascunhos"
            itens={fila.solicitar}
            abrirHref="/pagamentos/contas-a-pagar"
            abrirLabel="abrir tela de contas a pagar"
          />
          <CardFila
            title="Aguardando minha validação"
            itens={fila.validar}
            abrirHref="/pagamentos/contas-a-pagar"
            abrirLabel="abrir tela de contas a pagar"
          />
          <CardFila
            title="Aguardando encaminhamento"
            itens={fila.encaminhar}
            abrirHref="/pagamentos/contas-a-pagar"
            abrirLabel="abrir tela de contas a pagar"
          />
          <CardFila
            title="Aguardando autorização"
            itens={fila.autorizar}
            abrirHref="/pagamentos/autorizacao"
            abrirLabel="abrir tela de autorização"
          />
          <CardParcelas
            title="Pagamentos a liberar"
            itens={fila.liberar}
            abrirHref="/pagamentos/autorizacao?tab=pagamento"
            abrirLabel="abrir tela de liberação"
          />
          <CardParcelas
            title="Tesouraria — a pagar"
            itens={fila.pagar}
            abrirHref="/pagamentos/tesouraria"
            abrirLabel="abrir tesouraria"
          />
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
