"use client";

import { Carregando } from "@/components/ui/carregando";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, FileText, Plus } from "lucide-react";
import Link from "next/link";

import { mascararDocumento } from "@/components/cidadao/documento";
import { fmtDia } from "@/components/cidadao/formato";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api } from "@/lib/api";
import { statusProcessoBadge } from "@/lib/badges";
import { useRequireCidadao } from "@/lib/cidadao-auth";

function StatusProcesso({ ativo }: { ativo: boolean }) {
  // Mesmo rótulo e cor do detalhe ("Em andamento" / "Concluído").
  const s = statusProcessoBadge({ ativo }, "cidadao");
  return (
    <Badge intent={s.intent} icon={s.icon}>
      {s.label}
    </Badge>
  );
}

export default function CidadaoProcessosPage() {
  const { cidadao, loading } = useRequireCidadao();

  const q = useQuery({
    queryKey: ["cidadao-meus-processos"],
    queryFn: () => api.cidadao.listarProcessos(),
    enabled: !!cidadao,
  });

  if (loading) return <Carregando className="text-sm text-foreground-muted" />;
  if (!cidadao) return null;

  const itens = q.data ?? [];
  const novo = (
    <Button asChild>
      <Link href="/cidadao/abrir">
        <Plus className="h-4 w-4" aria-hidden="true" />
        Abrir processo
      </Link>
    </Button>
  );

  return (
    <div className="space-y-4">
      <PageHeader
        icon={FileText}
        title="Meus processos"
        description="Os pedidos que você fez à prefeitura. Abra um para ver onde ele está e se falta algo seu."
        actions={novo}
      />

      {q.isLoading && <Carregando className="py-6 text-center text-sm text-foreground-muted" />}

      {!q.isLoading && itens.length === 0 && (
        <EmptyState
          icon={FileText}
          title="Você ainda não fez nenhum pedido"
          description="Quando abrir um processo, ele aparece aqui com o número do protocolo e o andamento."
          action={novo}
        />
      )}

      {!q.isLoading && itens.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>
              {itens.length} {itens.length === 1 ? "processo" : "processos"} em seu nome
            </CardTitle>
            {cidadao.cpf_cnpj && (
              <p className="text-xs text-foreground-muted tabular-nums">
                {cidadao.cpf_cnpj.length > 11 ? "CNPJ" : "CPF"} {mascararDocumento(cidadao.cpf_cnpj)}
              </p>
            )}
          </CardHeader>
          <CardContent>
            {/* Celular: o cartão inteiro é o alvo de toque (a tabela não cabe em 360px). */}
            <ul className="space-y-3 md:hidden">
              {itens.map((p) => (
                <li key={p.id}>
                  <Link
                    href={`/cidadao/processos/${p.id}`}
                    className="flex items-center gap-3 rounded-lg border border-border bg-surface-1 p-4 transition-colors duration-fast hover:border-border-strong hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="break-all font-mono text-sm font-medium tabular-nums text-primary">
                          {p.nup ?? p.numero_processo}
                        </span>
                        <StatusProcesso ativo={p.ativo} />
                      </div>
                      <div className="text-sm font-medium text-foreground">{p.assunto ?? "—"}</div>
                      <div className="text-xs text-foreground-muted">
                        Aberto em <span className="tabular-nums">{fmtDia(p.data_hora_abertura)}</span>
                        {" · "}
                        Está em: {p.local_atual ?? "aguardando triagem"}
                      </div>
                    </div>
                    <ChevronRight className="h-5 w-5 shrink-0 text-foreground-subtle" aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>

            {/* Computador: tabela */}
            <div className="hidden md:block">
              <Table>
                <THead>
                  <TR>
                    <TH>Protocolo</TH>
                    <TH>Aberto em</TH>
                    <TH>Sobre o quê</TH>
                    <TH>Onde está</TH>
                    <TH>Situação</TH>
                    <TH className="text-right">
                      <span className="sr-only">Ações</span>
                    </TH>
                  </TR>
                </THead>
                <TBody>
                  {itens.map((p) => (
                    <TR key={p.id}>
                      <TD className="font-mono text-xs tabular-nums">
                        <Link
                          href={`/cidadao/processos/${p.id}`}
                          className="font-medium text-primary underline-offset-2 hover:underline"
                        >
                          {p.nup ?? p.numero_processo}
                        </Link>
                      </TD>
                      <TD className="text-xs tabular-nums">{fmtDia(p.data_hora_abertura)}</TD>
                      <TD>
                        <div className="text-sm">{p.assunto ?? "—"}</div>
                        {p.tipo_processo && (
                          <div className="text-xs text-foreground-muted">{p.tipo_processo}</div>
                        )}
                      </TD>
                      <TD className="text-sm">{p.local_atual ?? "Aguardando triagem"}</TD>
                      <TD>
                        <StatusProcesso ativo={p.ativo} />
                      </TD>
                      <TD className="text-right">
                        <Button asChild variant="ghost" size="sm">
                          <Link href={`/cidadao/processos/${p.id}`}>
                            Acompanhar
                            <ChevronRight className="h-4 w-4" aria-hidden="true" />
                          </Link>
                        </Button>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
