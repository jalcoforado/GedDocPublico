"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CalendarClock,
  FileText,
  Landmark,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  CabecalhoDoGrupo,
  EscolhaDeConta,
  LinhaSelecionavel,
  MedidorDeSaldo,
  contar,
  somar,
} from "@/components/pagamentos/autorizacao-partes";
import { fmtCompetencia, fmtData, fmtDataCurta, fmtMoeda } from "@/components/pagamentos/format";
import { RitoPagamento } from "@/components/pagamentos/RitoPagamento";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { BarraAcoesFormulario } from "@/components/ui/barra-acoes-formulario";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { KpiCard } from "@/components/ui/kpi-card";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { TabList, TabPanel, Tabs } from "@/components/ui/tabs";
import {
  api,
  type FilaAutorizacaoFonteGrupo,
  type FilaLiberacaoGrupo,
  type OrdemPagamento,
} from "@/lib/api";

type Tab = "despesa" | "pagamento";

const INVALIDATE_KEYS = [
  ["pag-fila-autorizacao"],
  ["pag-fila-liberacao"],
  ["pag-fila-tesouraria"],
  ["pag-fila"],
  ["pag-debitos"],
  ["pag-caixa-painel"],
] as const;

export default function AutorizacaoPagamentosPage() {
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<Tab>(searchParams.get("tab") === "pagamento" ? "pagamento" : "despesa");

  return (
    // `Tabs` envolve o header E os painéis: a `TabList` viaja como prop até o
    // `PageHeader`, mas continua DENTRO desta subárvore no React, então o
    // contexto (ids, aria-controls) alcança os dois lados.
    <Tabs value={tab} onChange={(v) => setTab(v as Tab)} className="space-y-4">
      <PageHeader
        icon={ShieldCheck}
        title="Autorizações"
        description="Autorize a despesa, que gera a Ordem de Pagamento, e depois libere o pagamento para a tesouraria."
        tabs={
          <TabList
            aria-label="Etapa da autorização"
            variant="pill"
            tabs={[
              { value: "despesa", label: "Autorizar despesa" },
              { value: "pagamento", label: "Liberar pagamento" },
            ]}
          />
        }
      />

      <RitoPagamento atual={tab === "despesa" ? "autorizar" : "liberar"} />

      <TabPanel value="despesa">
        <TabDespesa />
      </TabPanel>
      <TabPanel value="pagamento">
        <TabPagamento />
      </TabPanel>
    </Tabs>
  );
}

/** Carregando: os cartões e dois grupos, no lugar onde vão aparecer. */
function Esqueleto() {
  return (
    <div className="space-y-4" aria-busy="true">
      <div className="grid gap-3 sm:grid-cols-3">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
      <Skeleton className="h-56 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

/** Marcar/desmarcar um id, ou um grupo inteiro de ids. */
function useSelecao() {
  const [selecionados, setSelecionados] = useState<number[]>([]);
  const set = useMemo(() => new Set(selecionados), [selecionados]);
  return {
    selecionados,
    set,
    limpar: () => setSelecionados([]),
    alternar: (id: number) =>
      setSelecionados((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id])),
    alternarVarios: (ids: number[]) => {
      const todos = ids.length > 0 && ids.every((id) => set.has(id));
      setSelecionados((cur) =>
        todos ? cur.filter((id) => !ids.includes(id)) : Array.from(new Set([...cur, ...ids])),
      );
    },
  };
}

// ---------------------------------------------------------------------------
// Aba "Autorizar despesa" — fila APROVADO agrupada por FONTE (v2.0). Por fonte,
// o autorizador escolhe a CONTA PAGADORA entre as contas ativas da fonte e
// autoriza (gera OP, reserva o valor na conta escolhida).
// ---------------------------------------------------------------------------

function TabDespesa() {
  const qc = useQueryClient();
  const toast = useToast();
  const sel = useSelecao();
  // conta pagadora escolhida por fonte (id_fonte -> id_conta)
  const [contaPorFonte, setContaPorFonte] = useState<Record<number, number>>({});
  // Fonte marcada sem conta: o erro aparece no campo dela, não num botão cinza.
  const [fonteSemConta, setFonteSemConta] = useState<number | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const filaQ = useQuery({
    queryKey: ["pag-fila-autorizacao"],
    queryFn: () => api.pagamentos.filas.autorizacao(),
  });

  const grupos = useMemo(() => filaQ.data ?? [], [filaQ.data]);

  // Pré-seleciona a conta quando a fonte tem exatamente uma conta elegível (RF-AUT-10).
  useEffect(() => {
    setContaPorFonte((cur) => {
      const next = { ...cur };
      let mudou = false;
      for (const g of grupos) {
        if (next[g.id_fonte] === undefined && g.contas_elegiveis.length === 1) {
          next[g.id_fonte] = g.contas_elegiveis[0].id_conta;
          mudou = true;
        }
      }
      return mudou ? next : cur;
    });
  }, [grupos]);

  const todosDebitos = useMemo(() => grupos.flatMap((g) => g.debitos), [grupos]);
  // Só dá para marcar o que tem conta de onde sair.
  const marcaveis = useMemo(
    () => grupos.filter((g) => g.contas_elegiveis.length > 0).flatMap((g) => g.debitos.map((d) => d.id)),
    [grupos],
  );
  const urgentes = todosDebitos.filter((d) => d.urgente).length;

  // Grupos com débitos selecionados, com a conta escolhida e a soma.
  const gruposSelecionados = useMemo(
    () =>
      grupos
        .map((g) => {
          const debs = g.debitos.filter((d) => sel.set.has(d.id));
          const soma = somar(debs, (d) => d.valor_total);
          const contaId = contaPorFonte[g.id_fonte];
          const conta = g.contas_elegiveis.find((c) => c.id_conta === contaId);
          return { grupo: g, debs, soma, contaId, conta };
        })
        .filter((x) => x.debs.length > 0),
    [grupos, sel.set, contaPorFonte],
  );
  const somaSelecionados = gruposSelecionados.reduce((acc, x) => acc + x.soma, 0);
  const semContaEscolhida = gruposSelecionados.filter((x) => x.contaId === undefined);
  const algumExcede = gruposSelecionados.some(
    (x) => x.conta && x.soma > (Number(x.conta.disponivel) || 0),
  );

  function escolherConta(grupo: FilaAutorizacaoFonteGrupo, idConta: number) {
    setContaPorFonte((cur) => ({ ...cur, [grupo.id_fonte]: idConta }));
    if (fonteSemConta === grupo.id_fonte) setFonteSemConta(null);
  }

  function pedirAutorizacao() {
    const falta = semContaEscolhida[0];
    if (falta) {
      setFonteSemConta(falta.grupo.id_fonte);
      document
        .getElementById(`conta-fonte-${falta.grupo.id_fonte}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    setConfirmOpen(true);
  }

  const autorizarM = useMutation({
    mutationFn: () =>
      api.pagamentos.autorizar(
        gruposSelecionados.map((x) => ({
          id_fonte: x.grupo.id_fonte,
          id_conta_pagadora: x.contaId as number,
          debito_ids: x.debs.map((d) => d.id),
        })),
      ),
    onSuccess: (ops: OrdemPagamento[]) => {
      INVALIDATE_KEYS.forEach((key) => qc.invalidateQueries({ queryKey: key }));
      const total = ops.reduce((acc, o) => acc + (Number(o.valor_total) || 0), 0);
      toast.success(
        ops.length === 1
          ? `Ordem de Pagamento gerada — ${fmtMoeda(total)}`
          : `${ops.length} Ordens de Pagamento geradas — ${fmtMoeda(total)}`,
        ops.length === 1
          ? {
              action: {
                label: "Abrir PDF",
                onClick: () => window.open(api.pagamentos.ordens.pdfUrl(ops[0].id), "_blank", "noopener"),
              },
            }
          : undefined,
      );
      sel.limpar();
      setConfirmOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (filaQ.isLoading) return <Esqueleto />;
  if (filaQ.isError) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title="Não foi possível carregar a fila de autorização"
        description="Tente de novo em instantes. Se persistir, avise o suporte."
      />
    );
  }
  if (grupos.length === 0) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title="Nada aguardando autorização"
        description="As despesas aprovadas pela chefia aparecem aqui, agrupadas por fonte de recursos, para você escolher a conta pagadora e emitir a Ordem de Pagamento."
      />
    );
  }

  const tudoMarcado = marcaveis.length > 0 && marcaveis.every((id) => sel.set.has(id));

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <KpiCard
          label="Aguardando autorização"
          value={contar(todosDebitos.length, "despesa", "despesas")}
          hint={`em ${contar(grupos.length, "fonte", "fontes")} de recursos`}
          icon={ShieldCheck}
        />
        <KpiCard label="Valor na fila" value={fmtMoeda(somar(todosDebitos, (d) => d.valor_total))} icon={Wallet} />
        <KpiCard
          label="Urgentes"
          value={urgentes}
          hint={urgentes > 0 ? "marcadas como urgentes por quem pediu" : "nenhuma com urgência"}
          icon={AlertCircle}
          intent={urgentes > 0 ? "danger" : "default"}
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-foreground-muted">
          Marque as despesas e escolha a conta de cada fonte. Cada fonte vira uma Ordem de Pagamento.
        </p>
        {marcaveis.length > 1 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => (tudoMarcado ? sel.limpar() : sel.alternarVarios(marcaveis))}
          >
            {tudoMarcado ? "Desmarcar todas" : `Marcar todas (${marcaveis.length})`}
          </Button>
        )}
      </div>

      {grupos.map((grupo) => {
        const ids = grupo.debitos.map((d) => d.id);
        const semConta = grupo.contas_elegiveis.length === 0;
        const contaId = contaPorFonte[grupo.id_fonte];
        const contaSel = grupo.contas_elegiveis.find((c) => c.id_conta === contaId);
        const marcadosNoGrupo = grupo.debitos.filter((d) => sel.set.has(d.id));
        const somaGrupo = somar(marcadosNoGrupo, (d) => d.valor_total);
        return (
          <section
            key={grupo.id_fonte}
            aria-label={`Fonte ${grupo.codigo_fonte}`}
            className="overflow-hidden rounded-card border border-border bg-card shadow-card"
          >
            <CabecalhoDoGrupo
              titulo={`Fonte ${grupo.codigo_fonte}`}
              subtitulo={grupo.descricao_fonte}
              marcados={marcadosNoGrupo.length}
              total={ids.length}
              quantidade={contar(ids.length, "despesa", "despesas")}
              valorTotal={somar(grupo.debitos, (d) => d.valor_total)}
              onMarcarTodos={() => sel.alternarVarios(ids)}
              desabilitado={semConta}
              rotuloMarcarTodos={`Marcar todas as despesas da fonte ${grupo.codigo_fonte}`}
            />

            <div className="space-y-3 border-b border-border bg-surface-2/40 px-4 py-3">
              {semConta ? (
                <Alert intent="warning" title="Nenhuma conta ativa nesta fonte">
                  Para autorizar estas despesas, cadastre ou ative uma conta bancária ligada à fonte{" "}
                  {grupo.codigo_fonte}.{" "}
                  <Link href="/m/pagamentos/cadastros/contas" className="font-medium underline underline-offset-2">
                    Abrir contas bancárias
                  </Link>
                </Alert>
              ) : (
                <>
                  <EscolhaDeConta
                    id={`conta-fonte-${grupo.id_fonte}`}
                    contas={grupo.contas_elegiveis}
                    valor={contaId}
                    onChange={(idConta) => escolherConta(grupo, idConta)}
                    erro={
                      fonteSemConta === grupo.id_fonte
                        ? "Escolha de qual conta sai o dinheiro desta fonte."
                        : undefined
                    }
                  />
                  {contaSel && <MedidorDeSaldo selecionado={somaGrupo} disponivel={contaSel.disponivel} />}
                </>
              )}
            </div>

            <ul className="divide-y divide-border">
              {grupo.debitos.map((d) => (
                <LinhaSelecionavel
                  key={d.id}
                  marcada={sel.set.has(d.id)}
                  onAlternar={() => sel.alternar(d.id)}
                  desabilitada={semConta}
                  rotulo={`Selecionar ${d.nome_fornecedor} — ${fmtMoeda(d.valor_total)}`}
                  titulo={d.nome_fornecedor}
                  selos={d.urgente && <Badge intent="danger" icon={AlertCircle}>Urgente</Badge>}
                  descricao={d.descricao}
                  detalhe={
                    <>
                      <span title={d.natureza_descricao}>{d.natureza_codigo}</span> · competência{" "}
                      {fmtCompetencia(d.competencia)}
                      {d.aprovado_por && (
                        <> · aprovada por {d.aprovado_por} em {fmtDataCurta(d.aprovado_em)}</>
                      )}
                    </>
                  }
                  valor={d.valor_total}
                  href={`/m/pagamentos/solicitacoes/${d.id}`}
                />
              ))}
            </ul>
          </section>
        );
      })}

      {sel.selecionados.length > 0 && (
        <BarraAcoesFormulario
          status={
            <span className="text-sm">
              <span className="font-semibold text-foreground">
                {contar(sel.selecionados.length, "despesa", "despesas")}
              </span>{" "}
              · <span className="font-semibold tabular-nums text-foreground">{fmtMoeda(somaSelecionados)}</span>
              {semContaEscolhida.length > 0 ? (
                <span className="text-warning-soft-foreground">
                  {" "}
                  · falta a conta da{" "}
                  {semContaEscolhida.map((x) => `Fonte ${x.grupo.codigo_fonte}`).join(", ")}
                </span>
              ) : (
                <> · {contar(gruposSelecionados.length, "Ordem de Pagamento", "Ordens de Pagamento")}</>
              )}
            </span>
          }
        >
          <Button variant="ghost" onClick={sel.limpar}>
            Limpar seleção
          </Button>
          <Button onClick={pedirAutorizacao}>
            {gruposSelecionados.length > 1
              ? `Autorizar e gerar ${gruposSelecionados.length} OPs`
              : "Autorizar e gerar a OP"}
          </Button>
        </BarraAcoesFormulario>
      )}

      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Autorizar estas despesas?"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => autorizarM.mutate()} loading={autorizarM.isPending}>
              {gruposSelecionados.length > 1
                ? `Autorizar e gerar ${gruposSelecionados.length} OPs`
                : "Autorizar e gerar a OP"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-sm text-foreground">
            {contar(sel.selecionados.length, "despesa", "despesas")}, somando{" "}
            <span className="font-semibold tabular-nums">{fmtMoeda(somaSelecionados)}</span>. Cada fonte gera
            uma Ordem de Pagamento e reserva o valor na conta escolhida —{" "}
            <span className="font-medium">não dá para desfazer</span>.
          </p>
          <ul className="space-y-2">
            {gruposSelecionados.map(({ grupo, soma, conta, debs }) => (
              <li key={grupo.id_fonte} className="space-y-2 rounded-lg border border-border bg-surface-2/40 p-3">
                <div className="flex items-start justify-between gap-3 text-sm">
                  <div className="min-w-0">
                    <p className="font-medium text-foreground">Fonte {grupo.codigo_fonte}</p>
                    <p className="flex items-center gap-1 truncate text-xs text-foreground-muted">
                      <Landmark className="h-3 w-3 shrink-0" aria-hidden="true" />
                      {conta ? conta.nome : "—"} · {contar(debs.length, "despesa", "despesas")}
                    </p>
                  </div>
                  <span className="shrink-0 whitespace-nowrap font-semibold tabular-nums text-foreground">
                    {fmtMoeda(soma)}
                  </span>
                </div>
                {conta && <MedidorDeSaldo selecionado={soma} disponivel={conta.disponivel} />}
              </li>
            ))}
          </ul>
          {algumExcede && (
            <Alert intent="warning">
              Alguma conta não tem disponível para o que foi marcado: o servidor vai recusar a
              autorização por saldo insuficiente.
            </Alert>
          )}
        </div>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Aba "Liberar pagamento" — fila de liberação (A_PAGAR de débitos
// AUTORIZADO/PAGO_PARCIAL), agrupada pela conta de onde sai o dinheiro.
// ---------------------------------------------------------------------------

function TabPagamento() {
  const qc = useQueryClient();
  const toast = useToast();
  const sel = useSelecao();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [dataPrevista, setDataPrevista] = useState("");

  const filaQ = useQuery({
    queryKey: ["pag-fila-liberacao"],
    queryFn: () => api.pagamentos.filas.liberacao(),
  });

  const grupos = useMemo(() => filaQ.data ?? [], [filaQ.data]);
  const todasParcelas = useMemo(() => grupos.flatMap((g) => g.parcelas), [grupos]);
  const vencidas = todasParcelas.filter((p) => p.vencida).length;
  const somaSelecionados = somar(
    todasParcelas.filter((p) => sel.set.has(p.id)),
    (p) => p.valor,
  );

  const resumoPorConta = useMemo(
    () =>
      grupos
        .map((g) => ({ grupo: g, soma: somar(g.parcelas.filter((p) => sel.set.has(p.id)), (p) => p.valor) }))
        .filter((r) => r.soma > 0),
    [grupos, sel.set],
  );

  const liberarM = useMutation({
    mutationFn: () => api.pagamentos.parcelas.liberar(sel.selecionados, dataPrevista || null),
    onSuccess: () => {
      INVALIDATE_KEYS.forEach((key) => qc.invalidateQueries({ queryKey: key }));
      toast.success(
        sel.selecionados.length === 1
          ? "Parcela liberada para a tesouraria."
          : `${sel.selecionados.length} parcelas liberadas para a tesouraria.`,
      );
      sel.limpar();
      setDataPrevista("");
      setConfirmOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (filaQ.isLoading) return <Esqueleto />;
  if (filaQ.isError) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title="Não foi possível carregar a fila de liberação"
        description="Tente de novo em instantes. Se persistir, avise o suporte."
      />
    );
  }
  if (grupos.length === 0) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title="Nada aguardando liberação"
        description="Autorize despesas na aba ao lado: as parcelas das despesas autorizadas aparecem aqui para você liberar à tesouraria."
      />
    );
  }

  const todosIds = todasParcelas.map((p) => p.id);
  const tudoMarcado = todosIds.length > 0 && todosIds.every((id) => sel.set.has(id));

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <KpiCard
          label="Aguardando liberação"
          value={contar(todasParcelas.length, "parcela", "parcelas")}
          hint={`em ${contar(grupos.length, "conta", "contas")}`}
          icon={ShieldCheck}
        />
        <KpiCard label="Valor a liberar" value={fmtMoeda(somar(todasParcelas, (p) => p.valor))} icon={Wallet} />
        <KpiCard
          label="Vencidas"
          value={vencidas}
          hint={vencidas > 0 ? "já passaram do vencimento" : "nenhuma vencida"}
          icon={CalendarClock}
          intent={vencidas > 0 ? "danger" : "default"}
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-foreground-muted">
          Marque as parcelas que a tesouraria pode pagar. Elas saem da conta indicada em cada grupo.
        </p>
        {todosIds.length > 1 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => (tudoMarcado ? sel.limpar() : sel.alternarVarios(todosIds))}
          >
            {tudoMarcado ? "Desmarcar todas" : `Marcar todas (${todosIds.length})`}
          </Button>
        )}
      </div>

      {grupos.map((grupo: FilaLiberacaoGrupo) => {
        const ids = grupo.parcelas.map((p) => p.id);
        const marcadas = grupo.parcelas.filter((p) => sel.set.has(p.id));
        return (
          <section
            key={grupo.id_conta}
            aria-label={grupo.nome_conta}
            className="overflow-hidden rounded-card border border-border bg-card shadow-card"
          >
            <CabecalhoDoGrupo
              titulo={grupo.nome_conta}
              subtitulo={`Disponível ${fmtMoeda(grupo.disponivel)}`}
              selo={grupo.abaixo_minimo && <Badge intent="warning">Abaixo do mínimo</Badge>}
              marcados={marcadas.length}
              total={ids.length}
              quantidade={contar(ids.length, "parcela", "parcelas")}
              valorTotal={somar(grupo.parcelas, (p) => p.valor)}
              onMarcarTodos={() => sel.alternarVarios(ids)}
              rotuloMarcarTodos={`Marcar todas as parcelas de ${grupo.nome_conta}`}
            />
            {marcadas.length > 0 && (
              <div className="border-b border-border bg-surface-2/40 px-4 py-3">
                <MedidorDeSaldo selecionado={somar(marcadas, (p) => p.valor)} disponivel={grupo.disponivel} />
              </div>
            )}
            <ul className="divide-y divide-border">
              {grupo.parcelas.map((p) => (
                <LinhaSelecionavel
                  key={p.id}
                  marcada={sel.set.has(p.id)}
                  onAlternar={() => sel.alternar(p.id)}
                  rotulo={`Selecionar parcela ${p.numero} de ${p.nome_fornecedor} — ${fmtMoeda(p.valor)}`}
                  titulo={p.nome_fornecedor}
                  selos={
                    p.vencida && (
                      <Badge intent="danger" icon={CalendarClock}>
                        Vencida há {contar(p.dias_atraso, "dia", "dias")}
                      </Badge>
                    )
                  }
                  descricao={p.descricao_debito}
                  detalhe={
                    <>
                      Parcela {p.numero} de {p.qtd_parcelas} · vence {fmtData(p.vencimento)}
                      {p.op_numero && (
                        <>
                          {" "}
                          · OP{" "}
                          {p.op_id ? (
                            <a
                              href={api.pagamentos.ordens.pdfUrl(p.op_id)}
                              target="_blank"
                              rel="noopener"
                              className="inline-flex items-center gap-0.5 hover:text-foreground hover:underline"
                            >
                              {p.op_numero}
                              <FileText className="h-3 w-3" aria-hidden="true" />
                            </a>
                          ) : (
                            p.op_numero
                          )}
                        </>
                      )}
                    </>
                  }
                  valor={p.valor}
                  href={`/m/pagamentos/solicitacoes/${p.id_debito}`}
                />
              ))}
            </ul>
          </section>
        );
      })}

      {sel.selecionados.length > 0 && (
        <BarraAcoesFormulario
          status={
            <span className="text-sm">
              <span className="font-semibold text-foreground">
                {contar(sel.selecionados.length, "parcela", "parcelas")}
              </span>{" "}
              · <span className="font-semibold tabular-nums text-foreground">{fmtMoeda(somaSelecionados)}</span>
            </span>
          }
        >
          {/* Rótulo visível: só o campo de data, solto na barra, não dizia
              para que servia. */}
          <Label htmlFor="lib-data-prevista" className="mb-0 text-xs font-normal text-foreground-muted">
            Previsão de pagamento <span className="text-foreground-subtle">(opcional)</span>
          </Label>
          <Input
            id="lib-data-prevista"
            type="date"
            value={dataPrevista}
            onChange={(e) => setDataPrevista(e.target.value)}
            className="h-9 w-40"
          />
          <Button variant="ghost" onClick={sel.limpar}>
            Limpar seleção
          </Button>
          <Button onClick={() => setConfirmOpen(true)}>
            {sel.selecionados.length === 1 ? "Liberar a parcela" : `Liberar ${sel.selecionados.length} parcelas`}
          </Button>
        </BarraAcoesFormulario>
      )}

      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Liberar para a tesouraria?"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => liberarM.mutate()} loading={liberarM.isPending}>
              {sel.selecionados.length === 1 ? "Liberar a parcela" : `Liberar ${sel.selecionados.length} parcelas`}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-sm text-foreground">
            {contar(sel.selecionados.length, "parcela", "parcelas")}, somando{" "}
            <span className="font-semibold tabular-nums">{fmtMoeda(somaSelecionados)}</span>, vão para a
            tesouraria pagar.
            {dataPrevista ? (
              <>
                {" "}
                Previsão de pagamento: <span className="font-semibold">{fmtData(dataPrevista)}</span>.
              </>
            ) : (
              " Sem data prevista."
            )}
          </p>
          <ul className="space-y-2">
            {resumoPorConta.map(({ grupo, soma }) => (
              <li
                key={grupo.id_conta}
                className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface-2/40 px-3 py-2 text-sm"
              >
                <span className="flex min-w-0 items-center gap-1.5 truncate text-foreground" title={grupo.nome_conta}>
                  <Landmark className="h-3.5 w-3.5 shrink-0 text-foreground-muted" aria-hidden="true" />
                  {grupo.nome_conta}
                </span>
                <span className="shrink-0 whitespace-nowrap font-semibold tabular-nums">{fmtMoeda(soma)}</span>
              </li>
            ))}
          </ul>
        </div>
      </Dialog>
    </div>
  );
}
