"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlarmClock, CheckCircle2, Send } from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface PageParams {
  params: Promise<{ id: string }>;
}

function formataData(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString("pt-BR");
}

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
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { rotulo: "Convocados", valor: kpis.convocados },
            { rotulo: "Atendidos", valor: kpis.atendidos },
            { rotulo: "Em atraso", valor: kpis.em_atraso },
            { rotulo: "Suspensos", valor: kpis.suspensos },
          ].map((k) => (
            <div key={k.rotulo} className="rounded-lg border p-3">
              <div className="text-xs text-muted-foreground">{k.rotulo}</div>
              <div className="text-2xl font-semibold">{k.valor}</div>
            </div>
          ))}
        </div>
      )}

      {q.isLoading ? (
        <div className="py-8 text-center text-muted-foreground">Carregando...</div>
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
                <TD className="text-sm text-muted-foreground">{f.documento}</TD>
                <TD className="text-sm">{formataData(f.prazo)}</TD>
                <TD>
                  <Badge intent="danger">{f.dias_atraso} dia(s)</Badge>
                </TD>
                <TD className="text-sm text-muted-foreground">
                  {formataData(f.ultima_notificacao)}
                </TD>
                <TD className="text-right">
                  <Link
                    href={`/m/transporte/recadastramento/${cicloId}/convocacao/${f.id}`}
                  >
                    <Button variant="secondary" size="sm">
                      Atender
                    </Button>
                  </Link>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </div>
  );
}
