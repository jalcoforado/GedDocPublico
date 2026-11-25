"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Landmark, PiggyBank, Target, Wallet } from "lucide-react";

import { NavVisaoFinanceiro } from "@/components/pagamentos/NavVisaoFinanceiro";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { GraficoCard } from "@/components/ui/grafico-card";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import type { ExecucaoOrcamentaria, PosicaoDotacaoItem } from "@/lib/api";
import { api } from "@/lib/api";
import { GRAFICO } from "@/lib/chart-theme";

const fmtBRL = (v: number | string) =>
  Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const fmtPct = (v: number) =>
  `${v.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;

export default function OrcamentoPage() {
  const q = useQuery({
    queryKey: ["pag-orcamento"],
    queryFn: () => api.pagamentos.orcamento.execucao(),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Target}
        title="Execução orçamentária"
        description="Quanto da dotação já foi comprometida por empenho, dotação a dotação."
      />
      <NavVisaoFinanceiro />

      {q.isLoading && <div className="h-64 animate-pulse rounded-card bg-surface-2/40" />}
      {q.isError && (
        <EmptyState
          icon={Target}
          title="Não foi possível carregar a execução"
          description="Tente de novo em instantes."
        />
      )}
      {q.data && <Conteudo d={q.data} />}
    </div>
  );
}

function Conteudo({ d }: { d: ExecucaoOrcamentaria }) {
  if (d.qtd_dotacoes === 0) {
    return (
      <EmptyState
        icon={Target}
        title="Nenhuma dotação cadastrada"
        description="Cadastre as dotações do exercício para acompanhar a execução. Enquanto não houver dotação, a despesa continua sendo controlada só pelo lado financeiro."
      />
    );
  }

  const insight =
    d.dotacoes_estouradas > 0 ? (
      <>
        <strong className="font-semibold text-foreground">
          {d.dotacoes_estouradas}{" "}
          {d.dotacoes_estouradas === 1 ? "dotação está" : "dotações estão"} com empenho acima da
          dotação atualizada.
        </strong>{" "}
        Empenhar além do crédito depende de suplementação — sem ela, a despesa fica sem cobertura
        orçamentária.
      </>
    ) : d.despesas_sem_retorno > 0 ? (
      <>
        {d.despesas_sem_retorno}{" "}
        {d.despesas_sem_retorno === 1 ? "despesa vinculada ainda não teve" : "despesas vinculadas ainda não tiveram"}{" "}
        o empenho devolvido pelo sistema financeiro, então a execução de{" "}
        <strong className="font-semibold text-foreground">{fmtPct(d.execucao_pct)}</strong> é um
        piso, não o número final.
      </>
    ) : (
      <>
        Execução em <strong className="font-semibold text-foreground">{fmtPct(d.execucao_pct)}</strong>{" "}
        da dotação atualizada, com {fmtBRL(d.disponivel)} ainda disponíveis.
      </>
    );

  return (
    <>
      {d.despesas_sem_dotacao_qtd > 0 && (
        <Alert intent="warning">
          <strong className="font-semibold">
            {d.despesas_sem_dotacao_qtd}{" "}
            {d.despesas_sem_dotacao_qtd === 1 ? "despesa não está" : "despesas não estão"} vinculadas
            a dotação
          </strong>{" "}
          ({fmtBRL(d.despesas_sem_dotacao_valor)}). Elas não entram em nenhum número desta tela.
          Isso é proposital: ratear despesa sem dotação entre as dotações existentes inventaria
          execução que não aconteceu. É também a diferença entre o que o município gastou e o que o
          orçamento registra.
        </Alert>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Dotação atualizada"
          value={fmtBRL(d.dotacao_atualizada)}
          hint={`inicial ${fmtBRL(d.dotacao_inicial)}`}
          icon={PiggyBank}
          definicao="Dotação inicial mais créditos adicionais, menos anulações. É derivada dos créditos lançados, não uma coluna guardada."
        />
        <KpiCard
          label="Créditos adicionais"
          value={fmtBRL(d.creditos)}
          icon={Landmark}
          definicao="Suplementações, créditos especiais e extraordinários, menos as anulações. Todo crédito exige o ato (lei ou decreto) que o autorizou."
        />
        <KpiCard
          label="Empenhado"
          value={fmtBRL(d.empenhado)}
          hint={fmtPct(d.execucao_pct) + " da dotação"}
          icon={Target}
          definicao="Soma do valor empenhado devolvido pelo sistema financeiro. O Aprimora não empenha: registra o que foi empenhado e confere."
        />
        <KpiCard
          label="Disponível orçamentário"
          value={fmtBRL(d.disponivel)}
          icon={Wallet}
          intent={Number(d.disponivel) < 0 ? "danger" : "default"}
          definicao="Dotação atualizada menos empenhado. Não é dinheiro em conta: ter dotação não é ter saldo, e ter saldo não autoriza gasto sem dotação."
        />
      </div>

      <GraficoCard
        titulo={`Dotações do exercício ${d.exercicio ?? ""}`}
        subtitulo={`${d.qtd_dotacoes} ${d.qtd_dotacoes === 1 ? "dotação" : "dotações"} · as estouradas aparecem primeiro`}
        insight={insight}
      >
        <ul className="divide-y divide-border">
          {d.itens.map((i) => (
            <LinhaDotacao key={i.id_dotacao} i={i} />
          ))}
        </ul>
      </GraficoCard>
    </>
  );
}

function LinhaDotacao({ i }: { i: PosicaoDotacaoItem }) {
  const atualizada = Number(i.dotacao_atualizada);
  const empenhado = Number(i.empenhado);
  const base = Math.max(atualizada, empenhado, 1);
  const pctEmpenhado = (Math.min(empenhado, atualizada) / base) * 100;
  const pctEstouro = empenhado > atualizada ? ((empenhado - atualizada) / base) * 100 : 0;
  const pctLivre = atualizada > empenhado ? ((atualizada - empenhado) / base) * 100 : 0;

  return (
    <li className="py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-foreground">{i.descricao}</span>
          <span className="block truncate text-xs text-foreground-subtle">
            {i.nome_unidade} · função {i.funcao} · programa {i.programa} · {i.natureza_codigo} ·
            fonte {i.codigo_fonte}
          </span>
        </span>
        <span className="shrink-0 text-right">
          <span
            className={
              i.estourada
                ? "block text-sm font-semibold tabular-nums text-danger-soft-foreground"
                : "block text-sm font-semibold tabular-nums text-foreground"
            }
          >
            {fmtPct(i.execucao_pct)}
          </span>
          <span className="block text-xs text-foreground-subtle">
            {fmtBRL(i.empenhado)} de {fmtBRL(i.dotacao_atualizada)}
          </span>
        </span>
      </div>

      <div
        className="mt-2 flex h-2 w-full overflow-hidden rounded-full bg-surface-2"
        role="img"
        aria-label={`${i.descricao}: ${fmtPct(i.execucao_pct)} executado`}
      >
        <span style={{ width: `${pctEmpenhado}%`, backgroundColor: GRAFICO.alerta }} />
        {pctEstouro > 0 && (
          <span
            className="animate-pulse motion-reduce:animate-none"
            style={{ width: `${pctEstouro}%`, backgroundColor: GRAFICO.negativo }}
          />
        )}
        {pctLivre > 0 && (
          <span style={{ width: `${pctLivre}%`, backgroundColor: GRAFICO.positivo }} />
        )}
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-foreground-subtle">
        {Number(i.creditos) !== 0 && (
          <span>
            créditos: <span className="tabular-nums text-foreground">{fmtBRL(i.creditos)}</span>
          </span>
        )}
        <span>
          disponível:{" "}
          <span className="tabular-nums text-foreground">{fmtBRL(i.disponivel)}</span>
        </span>
        {i.despesas_sem_retorno > 0 && (
          <span className="flex items-center gap-1 text-warning-soft-foreground">
            <AlertTriangle className="h-3 w-3" aria-hidden="true" />
            {i.despesas_sem_retorno} sem retorno de empenho
          </span>
        )}
      </div>
    </li>
  );
}
