"use client";

/**
 * Painel de workflow (P8 D3, Task 6) — leitura só, entidade polimórfica
 * (ocorrência/alvará/convocação). Busca `GET /transporte-regulado/workflow/
 * {entidadeTipo}/{entidadeId}` no mount e mostra o estado atual, dias no
 * estado (+ SLA quando configurado no DSL) e a timeline do log de
 * transições. Erro de rede não some com o painel — mostra mensagem
 * discreta, não bloqueia a tela hospedeira (tela de ocorrência/alvará/
 * recadastramento continua utilizável mesmo se o workflow falhar).
 */
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type WorkflowTransicaoOut } from "@/lib/api";

export interface WorkflowTimelineProps {
  entidadeTipo: "ocorrencia" | "alvara" | "convocacao";
  entidadeId: number;
}

function humanizarSlug(slug: string): string {
  return slug
    .split("_")
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}

function formatarData(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pt-BR");
}

export function WorkflowTimeline({ entidadeTipo, entidadeId }: WorkflowTimelineProps) {
  const q = useQuery({
    queryKey: ["/transporte-regulado/workflow", entidadeTipo, entidadeId],
    queryFn: () => api.transporteWorkflow.getWorkflow(entidadeTipo, entidadeId),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Fluxo de trabalho</CardTitle>
      </CardHeader>
      <CardContent>
        {q.isLoading ? (
          <p className="text-sm text-muted-foreground">Carregando fluxo de trabalho...</p>
        ) : q.isError ? (
          <p className="text-sm text-muted-foreground">
            Não foi possível carregar o fluxo de trabalho no momento.
          </p>
        ) : !q.data || q.data.estado_atual === null ? (
          <p className="text-sm text-muted-foreground">Fluxo ainda não iniciado.</p>
        ) : (
          <WorkflowConteudo dados={q.data} />
        )}
      </CardContent>
    </Card>
  );
}

function WorkflowConteudo({
  dados,
}: {
  dados: NonNullable<ReturnType<typeof useQuery<Awaited<ReturnType<typeof api.transporteWorkflow.getWorkflow>>>>["data"]>;
}) {
  const slaExcedido =
    dados.sla_dias !== null &&
    dados.dias_no_estado !== null &&
    dados.dias_no_estado > dados.sla_dias;

  const intent = dados.ativa === false ? "neutral" : slaExcedido ? "danger" : "info";

  const log = [...dados.log].sort(
    (a, b) => new Date(a.executada_em).getTime() - new Date(b.executada_em).getTime(),
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge intent={intent}>{humanizarSlug(dados.estado_atual as string)}</Badge>
        {dados.ativa === false && (
          <span className="text-xs text-muted-foreground">Encerrado</span>
        )}
      </div>

      {dados.dias_no_estado !== null && (
        <p className="text-sm text-muted-foreground">
          {dados.dias_no_estado} {dados.dias_no_estado === 1 ? "dia" : "dias"} neste estado
          {dados.sla_dias !== null && (
            <>
              {" "}
              — SLA de {dados.sla_dias} {dados.sla_dias === 1 ? "dia" : "dias"}
              {slaExcedido && (
                <span className="font-semibold text-danger"> (excedido)</span>
              )}
            </>
          )}
        </p>
      )}

      {log.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sem transições registradas ainda.</p>
      ) : (
        <ol className="space-y-2">
          {log.map((t: WorkflowTransicaoOut, i: number) => (
            <li
              key={`${t.executada_em}-${i}`}
              className="rounded-md border border-border bg-surface-1 px-3 py-2 text-sm"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">{humanizarSlug(t.transicao_label)}</span>
                <span className="text-xs text-muted-foreground">
                  {formatarData(t.executada_em)}
                </span>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {humanizarSlug(t.estado_de)} → {humanizarSlug(t.estado_para)}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
