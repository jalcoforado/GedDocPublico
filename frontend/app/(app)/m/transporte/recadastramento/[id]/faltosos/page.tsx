"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlarmClock, Ban, CheckCircle2, ClipboardCheck, Send, Users } from "lucide-react";
import { use, useState } from "react";

import { fmtData } from "@/components/pagamentos/format";
import { documentoParaExibir } from "@/components/transporte/rotulos";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface PageParams {
  params: Promise<{ id: string }>;
}

// `new Date("2026-11-10")` é meia-noite UTC: em UTC-3 o prazo aparecia um
// dia antes. `fmtData` lê data sem hora como data local.
const formataData = fmtData;

export default function FaltososPage({ params }: PageParams) {
  const { id } = use(params);
  const cicloId = Number(id);

  const { can } = useAuth();
  const canNotificar = can("transporte_regulado", "atualizar");
  const qc = useQueryClient();
  const toast = useToast();

  const [selecionados, setSelecionados] = useState<number[]>([]);

  const q = useQuery({
    queryKey: ["tr-faltosos", cicloId],
    queryFn: () => api.recadastramento.faltosos.list(cicloId),
  });

  const notificarM = useMutation({
    mutationFn: (ids: number[]) =>
      api.recadastramento.faltosos.notificar(cicloId, ids),
    onSuccess: (resultados) => {
      const enviadas = resultados.filter((r) => r.resultado === "enviada").length;
      const sem = resultados.length - enviadas;
      // As duas contagens aparecem sempre, inclusive quando `sem` é zero: quem
      // dispara em lote precisa saber quantos NÃO foram alcançados, e um aviso
      // que só aparece às vezes é um aviso que ninguém procura.
      toast.success(
        `${enviadas} notificação(ões) enviada(s); ${sem} sem contato cadastrado.`,
      );
      setSelecionados([]);
      qc.invalidateQueries({ queryKey: ["tr-faltosos", cicloId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const itens = q.data?.itens ?? [];
  const kpis = q.data?.kpis;
  const todosMarcados = itens.length > 0 && selecionados.length === itens.length;

  function alternar(convId: number) {
    setSelecionados((atual) =>
      atual.includes(convId)
        ? atual.filter((x) => x !== convId)
        : [...atual, convId],
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={AlarmClock}
        title="Faltosos"
        description={
          q.data
            ? `Ciclo ${q.data.ciclo.nome} — quem perdeu o prazo e ainda não foi atendido.`
            : "Quem perdeu o prazo e ainda não foi atendido."
        }
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Recadastramento", href: "/m/transporte/recadastramento" },
          {
            label: "Ciclo",
            href: `/m/transporte/recadastramento/${cicloId}`,
          },
          { label: "Faltosos" },
        ]}
        actions={
          canNotificar && selecionados.length > 0 ? (
            <Button
              onClick={() => notificarM.mutate(selecionados)}
              disabled={notificarM.isPending}
            >
              <Send className="mr-1 h-4 w-4" />
              {notificarM.isPending
                ? "Enviando..."
                : `Notificar ${selecionados.length}`}
            </Button>
          ) : undefined
        }
      />

      {kpis && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <KpiCard label="Convocados" value={kpis.convocados} icon={Users} />
          <KpiCard
            label="Atendidos"
            value={kpis.atendidos}
            icon={CheckCircle2}
            intent="success"
          />
          <KpiCard label="Em atraso" value={kpis.em_atraso} icon={AlarmClock} intent="danger" />
          <KpiCard label="Suspensos" value={kpis.suspensos} icon={Ban} intent="warning" />
        </div>
      )}

      {q.isLoading ? (
        <Carregando className="py-8 text-center text-muted-foreground" />
      ) : itens.length === 0 ? (
        <EmptyState
          icon={CheckCircle2}
          title="Ninguém em atraso"
          description="Todo mundo que foi convocado está dentro do prazo ou já foi atendido."
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH className="w-8">
                <input
                  type="checkbox"
                  aria-label="Selecionar todos"
                  checked={todosMarcados}
                  onChange={(e) =>
                    setSelecionados(e.target.checked ? itens.map((i) => i.id) : [])
                  }
                />
              </TH>
              <TH>Regulado</TH>
              <TH>Documento</TH>
              <TH>Prazo</TH>
              <TH>Atraso</TH>
              <TH>Última notificação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {itens.map((f) => (
              <TR key={f.id}>
                <TD>
                  <input
                    type="checkbox"
                    aria-label={`Selecionar ${f.nome_regulado}`}
                    checked={selecionados.includes(f.id)}
                    onChange={() => alternar(f.id)}
                  />
                </TD>
                <TD className="font-medium">{f.nome_regulado}</TD>
                <TD className="whitespace-nowrap font-mono text-sm text-muted-foreground">
                  {documentoParaExibir(f.documento)}
                </TD>
                <TD className="text-sm tabular-nums">{formataData(f.prazo)}</TD>
                <TD>
                  <Badge intent="danger">
                    {f.dias_atraso} {f.dias_atraso === 1 ? "dia" : "dias"}
                  </Badge>
                </TD>
                <TD className="text-sm tabular-nums text-muted-foreground">
                  {formataData(f.ultima_notificacao)}
                </TD>
                <TD className="text-right">
                  <AcoesDaLinha
                    acoes={[
                      {
                        label: "Atender",
                        icon: ClipboardCheck,
                        href: `/m/transporte/recadastramento/${cicloId}/convocacao/${f.id}`,
                      },
                    ]}
                  />
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </div>
  );
}
