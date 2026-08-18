"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useRequireCidadao } from "@/lib/cidadao-auth";

function fmt(s: string) {
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

export default function CidadaoProcessosPage() {
  const { cidadao, loading } = useRequireCidadao();

  const q = useQuery({
    queryKey: ["cidadao-meus-processos"],
    queryFn: () => api.cidadao.listarProcessos(),
    enabled: !!cidadao,
  });

  if (loading) return <p className="text-sm text-muted-foreground">Carregando...</p>;
  if (!cidadao) return null;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold text-primary">Meus processos</h1>
        <Link href="/cidadao/abrir">
          <Button>Abrir novo processo</Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            {q.data?.length ?? 0} processo(s) em seu nome
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              (CPF/CNPJ {cidadao.cpf_cnpj})
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {q.isLoading && (
            <p className="py-6 text-center text-sm text-muted-foreground">Carregando...</p>
          )}
          {!q.isLoading && (q.data?.length ?? 0) === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Você ainda não tem processos abertos.
            </p>
          )}
          {!q.isLoading && (q.data?.length ?? 0) > 0 && (
            <>
              {/* Mobile: cards (a tabela não cabe em 360px sem scroll horizontal) */}
              <ul className="space-y-3 md:hidden">
                {q.data?.map((p) => (
                  <li
                    key={p.id}
                    className="rounded-md border border-border bg-surface-1 p-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="break-all font-mono text-xs tabular-nums">
                        {p.nup ?? p.numero_processo}
                      </span>
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
                    <div className="mt-2 text-sm font-medium">{p.assunto ?? "—"}</div>
                    {p.tipo_processo && (
                      <div className="text-xs text-muted-foreground">{p.tipo_processo}</div>
                    )}
                    <dl className="mt-2 space-y-1 text-xs">
                      <div className="flex justify-between gap-2">
                        <dt className="text-muted-foreground">Aberto em</dt>
                        <dd className="tabular-nums">{fmt(p.data_hora_abertura)}</dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt className="shrink-0 text-muted-foreground">Local atual</dt>
                        <dd className="text-right">{p.local_atual ?? "—"}</dd>
                      </div>
                    </dl>
                    <div className="mt-3 border-t border-border pt-2 text-right">
                      <Link
                        href={`/cidadao/processos/${p.id}`}
                        className="inline-flex h-9 items-center rounded-md border border-transparent px-3 text-xs font-medium text-primary transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        Acompanhar →
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>

              {/* Desktop: tabela */}
              <div className="hidden md:block">
                <Table>
                  <THead>
                    <TR>
                      <TH>Número</TH>
                      <TH>Aberto em</TH>
                      <TH>Assunto</TH>
                      <TH>Local atual</TH>
                      <TH>Status</TH>
                      <TH className="text-right">Ações</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {q.data?.map((p) => (
                      <TR key={p.id}>
                        <TD className="font-mono text-xs tabular-nums">
                          {p.nup ?? p.numero_processo}
                        </TD>
                        <TD className="text-xs tabular-nums">{fmt(p.data_hora_abertura)}</TD>
                        <TD>
                          <div className="text-sm">{p.assunto ?? "—"}</div>
                          <div className="text-xs text-muted-foreground">
                            {p.tipo_processo ?? ""}
                          </div>
                        </TD>
                        <TD className="text-sm">{p.local_atual ?? "—"}</TD>
                        <TD>
                          {p.ativo ? (
                            <Badge intent="success" icon={Clock}>
                              Em andamento
                            </Badge>
                          ) : (
                            <Badge intent="neutral" icon={CheckCircle2}>
                              Encerrado
                            </Badge>
                          )}
                        </TD>
                        <TD className="text-right">
                          <Link
                            href={`/cidadao/processos/${p.id}`}
                            className="inline-flex h-9 items-center rounded-md border border-transparent px-3 text-xs font-medium text-primary transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            Acompanhar →
                          </Link>
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
