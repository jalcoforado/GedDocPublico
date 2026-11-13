"use client";

import { Carregando } from "@/components/ui/carregando";

import { useQuery } from "@tanstack/react-query";
import { AlertOctagon, Plus } from "lucide-react";
import Link from "next/link";

import { DenunciaRegistrada } from "@/components/cidadao/DenunciaRegistrada";
import { fmtDia } from "@/components/cidadao/formato";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
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

export default function CidadaoDenunciasPage() {
  const { cidadao, loading } = useRequireCidadao();

  const q = useQuery({
    queryKey: ["cidadao-minhas-denuncias"],
    queryFn: () => api.cidadaoDenuncias.list(),
    enabled: !!cidadao,
  });

  if (loading) return <Carregando className="text-sm text-foreground-muted" />;
  if (!cidadao) return null;

  const itens = q.data ?? [];
  const nova = (
    <Button asChild>
      <Link href="/cidadao/denuncias/nova">
        <Plus className="h-4 w-4" aria-hidden="true" />
        Nova denúncia
      </Link>
    </Button>
  );

  return (
    <div className="space-y-4">
      <PageHeader
        icon={AlertOctagon}
        title="Minhas denúncias"
        description="Irregularidades no transporte que você avisou à prefeitura e a situação de cada uma."
        actions={nova}
      />

      <DenunciaRegistrada />

      {q.isLoading && <Carregando className="py-6 text-center text-sm text-foreground-muted" />}

      {!q.isLoading && itens.length === 0 && (
        <EmptyState
          icon={AlertOctagon}
          title="Você ainda não registrou nenhuma denúncia"
          description="Viu uma irregularidade no transporte (táxi, mototáxi, escolar)? Registre aqui e acompanhe a apuração."
          action={nova}
        />
      )}

      {!q.isLoading && itens.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>
              {itens.length} {itens.length === 1 ? "denúncia registrada" : "denúncias registradas"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Celular: cartões */}
            <ul className="space-y-3 md:hidden">
              {itens.map((d) => (
                <li key={d.id} className="rounded-lg border border-border bg-surface-1 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-sm font-medium text-foreground">{d.tipo_nome ?? "—"}</span>
                    <Badge intent={SITUACAO_INTENT[d.situacao]}>{SITUACAO_LABEL[d.situacao]}</Badge>
                  </div>
                  <p className="mt-2 line-clamp-3 text-sm text-foreground-muted">{d.descricao}</p>
                  <dl className="mt-3 space-y-1 text-xs">
                    <div className="flex justify-between gap-2">
                      <dt className="text-foreground-muted">Quando aconteceu</dt>
                      <dd className="tabular-nums">{fmtDia(d.data_fato)}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-foreground-muted">Enviada em</dt>
                      <dd className="tabular-nums">{fmtDia(d.criado_em)}</dd>
                    </div>
                    {d.referencia_alvo && (
                      <div className="flex justify-between gap-2">
                        <dt className="text-foreground-muted">Placa, ponto ou linha</dt>
                        <dd className="text-right">{d.referencia_alvo}</dd>
                      </div>
                    )}
                  </dl>
                </li>
              ))}
            </ul>

            {/* Computador: tabela */}
            <div className="hidden md:block">
              <Table>
                <THead>
                  <TR>
                    <TH>O que aconteceu</TH>
                    <TH>Descrição</TH>
                    <TH>Placa, ponto ou linha</TH>
                    <TH>Quando</TH>
                    <TH>Enviada em</TH>
                    <TH>Situação</TH>
                  </TR>
                </THead>
                <TBody>
                  {itens.map((d) => (
                    <TR key={d.id}>
                      <TD className="text-sm">{d.tipo_nome ?? "—"}</TD>
                      <TD className="max-w-xs truncate text-sm" title={d.descricao}>
                        {d.descricao}
                      </TD>
                      <TD className="text-sm text-foreground-muted">{d.referencia_alvo ?? "—"}</TD>
                      <TD className="text-xs tabular-nums">{fmtDia(d.data_fato)}</TD>
                      <TD className="text-xs tabular-nums">{fmtDia(d.criado_em)}</TD>
                      <TD>
                        <Badge intent={SITUACAO_INTENT[d.situacao]}>{SITUACAO_LABEL[d.situacao]}</Badge>
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
