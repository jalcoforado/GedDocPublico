"use client";

import { AlertTriangle, Wallet } from "lucide-react";
import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { GraficoCard } from "@/components/ui/grafico-card";
import { Select } from "@/components/ui/select";
import type { ContaDisponibilidadeItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { GRAFICO } from "@/lib/chart-theme";

/**
 * "Onde está o dinheiro, e quanto dele é meu para usar."
 *
 * Duas leituras na mesma tela: a ROSCA responde o consolidado num relance
 * (com o total no centro, que é o número que o prefeito procura primeiro), e
 * a LISTA abre conta a conta, cada uma com sua barra proporcional.
 *
 * As três faixas são MUTUAMENTE EXCLUSIVAS e somam o saldo bancário:
 * disponível + comprometido + bloqueado = saldo. É o que impede a barra de
 * ficar maior que o dinheiro que existe — empilhar autorizado, empenhado e
 * liquidado (que se sobrepõem) daria exatamente esse erro.
 *
 * Quando comprometido + bloqueado passa do saldo, `disponivel` é negativo: a
 * conta ganha faixa vermelha de insuficiência e sobe para o topo da lista. O
 * negativo não é arredondado para zero — a falta é a informação mais
 * importante da tela.
 */

const fmtBRL = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const fmtCompacto = (v: number) =>
  v.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    notation: "compact",
    maximumFractionDigits: 1,
  });

const pct = (parte: number, todo: number) => (todo <= 0 ? 0 : (parte / todo) * 100);

const fmtPct = (v: number) =>
  `${v.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;

type Ordem = "disponibilidade" | "saldo" | "comprometido" | "nome";

const ORDENS: { value: Ordem; label: string }[] = [
  { value: "disponibilidade", label: "Menor disponibilidade" },
  { value: "saldo", label: "Maior saldo" },
  { value: "comprometido", label: "Maior comprometido" },
  { value: "nome", label: "Nome da conta" },
];

interface Totais {
  saldo: number;
  disponivel: number;
  comprometido: number;
  bloqueado: number;
  insuficiencia: number;
}

interface Linha {
  id_conta: number;
  nome: string;
  banco: string;
  fonte_codigo: string | null;
  fonte_descricao: string | null;
  saldo_atual: number;
  /** Clampado em zero: é o que as faixas desenham. */
  disponivel: number;
  /** O valor real, que pode ser negativo. */
  disponivelReal: number;
  comprometido: number;
  bloqueado: number;
  insuficiencia: number;
}

function ordenar(linhas: Linha[], ordem: Ordem): Linha[] {
  const copia = [...linhas];
  switch (ordem) {
    case "saldo":
      return copia.sort((a, b) => b.saldo_atual - a.saldo_atual);
    case "comprometido":
      return copia.sort((a, b) => b.comprometido - a.comprometido);
    case "nome":
      return copia.sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
    default:
      // Risco primeiro: a conta que pode faltar dinheiro é a que o gestor
      // precisa ver, e "maior saldo" a jogaria para o fim da lista.
      return copia.sort((a, b) => a.disponivelReal - b.disponivelReal);
  }
}

/** Barra proporcional de uma conta — as três faixas, lado a lado. */
function BarraDaConta({ l }: { l: Linha }) {
  const base = Math.max(l.saldo_atual, l.comprometido + l.bloqueado, 1);
  const faixas = [
    { chave: "disp", valor: l.disponivel, cor: GRAFICO.positivo, rotulo: "Disponível" },
    { chave: "comp", valor: l.comprometido, cor: GRAFICO.alerta, rotulo: "Comprometido" },
    { chave: "bloq", valor: l.bloqueado, cor: GRAFICO.neutro, rotulo: "Bloqueado" },
  ].filter((f) => f.valor > 0);

  return (
    <div
      className="flex h-2.5 w-full overflow-hidden rounded-full bg-surface-2"
      role="img"
      aria-label={
        `${l.nome}: ${fmtBRL(l.disponivelReal)} disponível de ${fmtBRL(l.saldo_atual)}` +
        (l.insuficiencia > 0 ? `, insuficiência de ${fmtBRL(l.insuficiencia)}` : "")
      }
    >
      {faixas.map((f) => (
        <span
          key={f.chave}
          title={`${f.rotulo}: ${fmtBRL(f.valor)}`}
          style={{ width: `${pct(f.valor, base)}%`, backgroundColor: f.cor }}
        />
      ))}
      {l.insuficiencia > 0 && (
        <span
          title={`Insuficiência: ${fmtBRL(l.insuficiencia)}`}
          className="animate-pulse motion-reduce:animate-none"
          style={{
            width: `${pct(l.insuficiencia, base)}%`,
            backgroundColor: GRAFICO.negativo,
          }}
        />
      )}
    </div>
  );
}

function TooltipRosca({
  active,
  payload,
  total,
}: {
  active?: boolean;
  payload?: { name: string; value: number }[];
  total: number;
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  return (
    <div className="rounded-md border border-border bg-surface-1 px-3 py-2 text-xs shadow-md">
      <p className="font-semibold text-foreground">{p.name}</p>
      <p className="tabular-nums text-foreground-muted">
        {fmtBRL(p.value)} · {fmtPct(pct(p.value, total))}
      </p>
    </div>
  );
}

/**
 * A leitura do rodapé, tirada do PRÓPRIO dado — nunca frase pronta.
 *
 * Ordem de prioridade: falta de lastro vence tudo; depois a lacuna de
 * vinculação (que impede o painel de afirmar o que é dinheiro livre); depois
 * concentração. Sem nada a dizer, devolve null e o rodapé some — rodapé
 * genérico ocupa o lugar onde o leitor espera informação.
 */
function lerODado(linhas: Linha[], totais: Totais, semVinculacao: number): ReactNode | null {
  if (linhas.length === 0) return null;

  if (totais.insuficiencia > 0) {
    const n = linhas.filter((l) => l.insuficiencia > 0).length;
    return (
      <>
        <strong className="font-semibold text-foreground">
          {fmtBRL(totais.insuficiencia)}
        </strong>{" "}
        em compromissos {n === 1 ? "de uma conta" : `de ${n} contas`} não têm saldo que os
        cubra. Antes de autorizar nova despesa nessas contas, é preciso entrada de recurso
        ou remanejamento.
      </>
    );
  }

  if (semVinculacao > 0) {
    return (
      <>
        {semVinculacao === linhas.length
          ? "Nenhuma conta tem a vinculação da fonte cadastrada"
          : `${semVinculacao} de ${linhas.length} contas não têm a vinculação da fonte cadastrada`}
        , então o “disponível” acima ainda <strong className="font-semibold text-foreground">
        não separa recurso livre de vinculado</strong>. Preencher a vinculação em Cadastros →
        Fontes de recursos é o que torna este número utilizável para decidir.
      </>
    );
  }

  const comprometidoPct = pct(totais.comprometido, totais.saldo);
  const maior = [...linhas].sort((a, b) => b.saldo_atual - a.saldo_atual)[0];
  return (
    <>
      Comprometido responde por{" "}
      <strong className="font-semibold text-foreground">{fmtPct(comprometidoPct)}</strong> do
      saldo. A conta “{maior.nome}” concentra {fmtPct(pct(maior.saldo_atual, totais.saldo))} do
      dinheiro em caixa.
    </>
  );
}

export function DisponibilidadeContas({
  itens,
}: {
  itens: ContaDisponibilidadeItem[];
}) {
  const [ordem, setOrdem] = useState<Ordem>("disponibilidade");
  const { can } = useAuth();
  // O caixa exige `pagamento_cadastro`. Quem não tem veria um 403 ao clicar —
  // um link que leva a porta fechada é pior que nenhum link.
  const podeAbrirConta = can("pagamento_cadastro");

  const linhas = useMemo<Linha[]>(
    () =>
      itens.map((c) => {
        const disponivelReal = Number(c.disponivel);
        return {
          id_conta: c.id_conta,
          nome: c.nome,
          banco: c.banco,
          fonte_codigo: c.fonte_codigo ?? null,
          fonte_descricao: c.fonte_descricao ?? null,
          saldo_atual: Number(c.saldo_atual),
          disponivel: Math.max(disponivelReal, 0),
          disponivelReal,
          comprometido: Number(c.comprometido),
          bloqueado: Number(c.bloqueado),
          insuficiencia: Number(c.insuficiencia ?? 0),
        };
      }),
    [itens],
  );

  const ordenadas = useMemo(() => ordenar(linhas, ordem), [linhas, ordem]);

  const totais = useMemo(() => {
    const soma = (f: (l: Linha) => number) => linhas.reduce((acc, l) => acc + f(l), 0);
    const saldo = soma((l) => l.saldo_atual);
    return {
      saldo,
      disponivel: soma((l) => l.disponivel),
      comprometido: soma((l) => l.comprometido),
      bloqueado: soma((l) => l.bloqueado),
      insuficiencia: soma((l) => l.insuficiencia),
    };
  }, [linhas]);

  const fatias = [
    { name: "Disponível", value: totais.disponivel, cor: GRAFICO.positivo },
    { name: "Comprometido", value: totais.comprometido, cor: GRAFICO.alerta },
    { name: "Bloqueado", value: totais.bloqueado, cor: GRAFICO.neutro },
  ].filter((f) => f.value > 0);

  const emRisco = ordenadas.filter((l) => l.insuficiencia > 0);

  const semVinculacao = itens.filter((c) => !c.fonte_vinculacao).length;
  const insight = lerODado(ordenadas, totais, semVinculacao);

  if (linhas.length === 0) {
    return (
      <GraficoCard
        titulo="Disponibilidade por conta"
        vazio
        vazioTitulo="Nenhuma conta bancária"
        vazioDescricao="Cadastre uma conta para acompanhar a disponibilidade."
      />
    );
  }

  return (
    <GraficoCard
      titulo="Disponibilidade por conta"
      subtitulo={`${linhas.length === 1 ? "1 conta" : `${linhas.length} contas`} · disponível = saldo − comprometido − bloqueado`}
      insight={insight}
      acao={
        linhas.length > 1 ? (
          <Select
            value={ordem}
            onChange={(e) => setOrdem(e.target.value as Ordem)}
            aria-label="Ordenar contas por"
            className="w-auto"
          >
            {ORDENS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        ) : undefined
      }
    >
      <div className="space-y-5">
        {emRisco.length > 0 && (
          <p
            role="status"
            className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger-soft/40 px-3 py-2 text-xs text-danger-soft-foreground"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>
              {emRisco.length === 1
                ? `A conta "${emRisco[0].nome}" tem compromissos acima do saldo`
                : `${emRisco.length} contas têm compromissos acima do saldo`}
              , somando {fmtBRL(totais.insuficiencia)} sem lastro.
            </span>
          </p>
        )}

        {/* Consolidado: a rosca responde "quanto temos e quanto é nosso" num
            relance; o total vai no CENTRO porque é o número que o gestor
            procura primeiro, e no miolo ele não disputa com as fatias. */}
        <div className="grid items-center gap-6 sm:grid-cols-[minmax(0,210px)_minmax(0,1fr)]">
          <div className="relative mx-auto h-[210px] w-full max-w-[210px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={fatias}
                  dataKey="value"
                  nameKey="name"
                  innerRadius="68%"
                  outerRadius="100%"
                  paddingAngle={2}
                  stroke="none"
                  isAnimationActive={false}
                >
                  {fatias.map((f) => (
                    <Cell key={f.name} fill={f.cor} />
                  ))}
                </Pie>
                <Tooltip content={<TooltipRosca total={totais.saldo} />} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
              <Wallet className="mb-1 h-4 w-4 text-foreground-subtle" aria-hidden="true" />
              <span className="font-display text-xl font-bold leading-tight tabular-nums text-foreground">
                {fmtCompacto(totais.saldo)}
              </span>
              <span className="text-[11px] uppercase tracking-wide text-foreground-muted">
                Saldo total
              </span>
            </div>
          </div>

          <ul className="space-y-2.5">
            {fatias.map((f) => (
              <li key={f.name} className="flex items-center gap-3">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: f.cor }}
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1 text-sm text-foreground-muted">{f.name}</span>
                <span className="shrink-0 text-right">
                  <span className="block text-sm font-semibold tabular-nums text-foreground">
                    {fmtBRL(f.value)}
                  </span>
                  <span className="block text-xs tabular-nums text-foreground-subtle">
                    {fmtPct(pct(f.value, totais.saldo))} do saldo
                  </span>
                </span>
              </li>
            ))}
            <li className="flex items-center justify-between gap-3 border-t border-border pt-2.5 text-sm">
              <span className="text-foreground-muted">
                {linhas.length === 1 ? "1 conta" : `${linhas.length} contas`}
              </span>
              <span className="font-semibold tabular-nums text-foreground">
                {fmtBRL(totais.saldo)}
              </span>
            </li>
          </ul>
        </div>

        {/* Conta a conta: a barra mostra a proporção, o "% livre" dá a leitura
            rápida, e o valor fica escrito — gráfico sem número vira estimativa. */}
        <ul className="divide-y divide-border border-t border-border">
          {ordenadas.map((l) => {
            const livre = pct(Math.max(l.disponivelReal, 0), Math.max(l.saldo_atual, 1));
            const conteudo = (
              <>
                <div className="flex items-baseline justify-between gap-3">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-foreground">
                      {l.nome}
                    </span>
                    <span className="block truncate text-xs text-foreground-subtle">
                      {l.banco}
                      {l.fonte_codigo ? ` · fonte ${l.fonte_codigo}` : ""}
                      {l.fonte_descricao ? ` — ${l.fonte_descricao}` : ""}
                    </span>
                  </span>
                  <span className="shrink-0 text-right">
                    <span
                      className={
                        l.insuficiencia > 0
                          ? "block text-sm font-semibold tabular-nums text-danger-soft-foreground"
                          : "block text-sm font-semibold tabular-nums text-foreground"
                      }
                    >
                      {fmtBRL(l.disponivelReal)}
                    </span>
                    <span className="block text-xs tabular-nums text-foreground-subtle">
                      {l.insuficiencia > 0
                        ? `sem lastro: ${fmtBRL(l.insuficiencia)}`
                        : `${fmtPct(livre)} livre de ${fmtBRL(l.saldo_atual)}`}
                    </span>
                  </span>
                </div>
                <div className="mt-2">
                  <BarraDaConta l={l} />
                </div>
              </>
            );
            return (
              <li key={l.id_conta}>
                {podeAbrirConta ? (
                  <Link
                    href={`/m/pagamentos/caixa?conta=${l.id_conta}`}
                    className="block rounded-card px-1 py-3 transition-colors duration-fast hover:bg-surface-2"
                  >
                    {conteudo}
                  </Link>
                ) : (
                  <div className="px-1 py-3">{conteudo}</div>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </GraficoCard>
  );
}
