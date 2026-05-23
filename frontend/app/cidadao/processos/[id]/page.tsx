"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useRequireCidadao } from "@/lib/cidadao-auth";

function fmt(s: string | null | undefined) {
  if (!s) return "—";
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

export default function CidadaoProcessoDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const idValido = Number.isInteger(id) && id > 0;
  const { cidadao, loading } = useRequireCidadao();

  const q = useQuery({
    queryKey: ["cidadao-processo", id],
    queryFn: () => api.cidadao.getProcesso(id),
    enabled: !!cidadao && idValido,
  });

  if (loading) return <p className="text-sm text-muted-foreground">Carregando...</p>;
  if (!cidadao) return null;

  if (!idValido) {
    return (
      <div className="space-y-3">
        <Link href="/cidadao/processos" className="text-sm text-primary hover:underline">
          ← Voltar
        </Link>
        <div
          role="alert"
          className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
        >
          ID de processo inválido.
        </div>
      </div>
    );
  }

  if (q.isLoading) return <p className="text-sm text-muted-foreground">Carregando processo...</p>;
  if (q.error || !q.data) {
    return (
      <div className="space-y-3">
        <Link href="/cidadao/processos" className="text-sm text-primary hover:underline">
          ← Voltar
        </Link>
        <div
          role="alert"
          className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
        >
          {q.error instanceof Error ? q.error.message : "Erro ao carregar"}
        </div>
      </div>
    );
  }

  const p = q.data;

  return (
    <div className="space-y-4">
      <Link href="/cidadao/processos" className="text-sm text-primary hover:underline">
        ← Voltar
      </Link>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <CardTitle className="font-mono">{p.numero_processo}</CardTitle>
            <span className="text-sm text-muted-foreground tabular-nums">
              aberto em {fmt(p.data_hora_abertura)}
            </span>
          </div>
          <div className="mt-2">
            {p.ativo ? (
              <Badge intent="success" icon={Clock}>
                Em andamento
              </Badge>
            ) : (
              <Badge intent="neutral" icon={CheckCircle2}>
                Encerrado
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Assunto</dt>
              <dd>{p.assunto ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Tipo de processo</dt>
              <dd>{p.tipo_processo ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Local atual</dt>
              <dd>{p.local_atual ?? "—"}</dd>
            </div>
            {p.corpo && (
              <div className="md:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Descrição</dt>
                <dd className="whitespace-pre-wrap">{p.corpo}</dd>
              </div>
            )}
            {p.observacao && (
              <div className="md:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Observação</dt>
                <dd className="whitespace-pre-wrap">{p.observacao}</dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Histórico ({p.movimentacoes.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {p.movimentacoes.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhuma movimentação ainda.</p>
          ) : (
            <ol className="space-y-3">
              {p.movimentacoes.map((m) => (
                <li key={m.id} className="border-l-2 border-primary pl-4">
                  <div className="text-xs text-muted-foreground tabular-nums">
                    {fmt(m.data_hora_movimentacao)}
                  </div>
                  <div className="text-sm">
                    <span className="font-medium text-foreground">{m.acao}</span>
                    {m.unidade_responsavel && (
                      <span className="text-muted-foreground">
                        {" "}
                        em {m.unidade_responsavel}
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
