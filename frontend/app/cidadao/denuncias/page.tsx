"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertOctagon } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api, type OcorrenciaSituacao } from "@/lib/api";
import { useRequireCidadao } from "@/lib/cidadao-auth";

// Mesmos rótulos e intents do admin (`app/(app)/m/transporte/ocorrencias/page.tsx`)
// — a situação de uma denúncia é a mesma linha do tempo dos dois lados.
const SITUACAO_LABEL: Record<OcorrenciaSituacao, string> = {
  registrada: "Registrada",
  em_apuracao: "Em apuração",
  procedente: "Procedente",
  improcedente: "Improcedente",
  arquivada: "Arquivada",
};

const SITUACAO_INTENT: Record<OcorrenciaSituacao, "neutral" | "warning" | "danger"> = {
  registrada: "neutral",
  em_apuracao: "warning",
  procedente: "danger",
  improcedente: "neutral",
  arquivada: "neutral",
};

function fmtData(s: string) {
  return new Date(s).toLocaleDateString("pt-BR");
}

export default function CidadaoDenunciasPage() {
  const { cidadao, loading } = useRequireCidadao();

  const q = useQuery({
    queryKey: ["cidadao-minhas-denuncias"],
    queryFn: () => api.cidadaoDenuncias.list(),
    enabled: !!cidadao,
  });

  if (loading) return <p className="text-sm text-muted-foreground">Carregando...</p>;
  if (!cidadao) return null;

  const itens = q.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold text-primary">Minhas denúncias</h1>
        <Link href="/cidadao/denuncias/nova">
          <Button>Nova denúncia</Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{itens.length} denúncia(s) registrada(s)</CardTitle>
        </CardHeader>
        <CardContent>
          {q.isLoading && (
            <p className="py-6 text-center text-sm text-muted-foreground">Carregando...</p>
          )}
          {!q.isLoading && itens.length === 0 && (
            <EmptyState
              icon={AlertOctagon}
              title="Você ainda não registrou nenhuma denúncia"
              description="Viu uma irregularidade no transporte regulado (táxi, mototáxi, escolar)? Registre aqui e acompanhe a apuração."
              action={
                <Link href="/cidadao/denuncias/nova">
                  <Button>Registrar denúncia</Button>
                </Link>
              }
            />
          )}
          {!q.isLoading && itens.length > 0 && (
            <>
              {/* Mobile: cards */}
              <ul className="space-y-3 md:hidden">
                {itens.map((d) => (
                  <li key={d.id} className="rounded-md border border-border bg-surface-1 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-sm font-medium">{d.tipo_nome ?? "—"}</span>
                      <Badge intent={SITUACAO_INTENT[d.situacao]}>
                        {SITUACAO_LABEL[d.situacao]}
                      </Badge>
                    </div>
                    <div className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                      {d.descricao}
                    </div>
                    <dl className="mt-2 space-y-1 text-xs">
                      <div className="flex justify-between gap-2">
                        <dt className="text-muted-foreground">Data do fato</dt>
                        <dd className="tabular-nums">{fmtData(d.data_fato)}</dd>
                      </div>
                      {d.referencia_alvo && (
                        <div className="flex justify-between gap-2">
                          <dt className="text-muted-foreground">Referência</dt>
                          <dd>{d.referencia_alvo}</dd>
                        </div>
                      )}
                    </dl>
                  </li>
                ))}
              </ul>

              {/* Desktop: tabela */}
              <div className="hidden md:block">
                <Table>
                  <THead>
                    <TR>
                      <TH>Tipo</TH>
                      <TH>Descrição</TH>
                      <TH>Referência</TH>
                      <TH>Data do fato</TH>
                      <TH>Registrada em</TH>
                      <TH>Situação</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {itens.map((d) => (
                      <TR key={d.id}>
                        <TD className="text-sm">{d.tipo_nome ?? "—"}</TD>
                        <TD className="max-w-xs truncate text-sm">{d.descricao}</TD>
                        <TD className="text-sm text-muted-foreground">
                          {d.referencia_alvo ?? "—"}
                        </TD>
                        <TD className="text-xs tabular-nums">{fmtData(d.data_fato)}</TD>
                        <TD className="text-xs tabular-nums">{fmtData(d.criado_em)}</TD>
                        <TD>
                          <Badge intent={SITUACAO_INTENT[d.situacao]}>
                            {SITUACAO_LABEL[d.situacao]}
                          </Badge>
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
