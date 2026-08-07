"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api, type DebitoOut, type SituacaoTramitacao } from "@/lib/api";
import { SITUACAO_TRAMITACAO_CONFIG } from "@/components/pagamentos/statusFluxo";
import { fmtMoeda } from "@/components/pagamentos/format";

function StatusBadge({ situacao }: { situacao: SituacaoTramitacao }) {
  const cfg = SITUACAO_TRAMITACAO_CONFIG[situacao];
  return <Badge intent={cfg.intent}>{cfg.label}</Badge>;
}

export default function ConcluidasPage() {
  // Listar débitos concluídos
  const listQ = useQuery({
    queryKey: ["pag-solicitacoes-concluidas"],
    queryFn: async () => {
      const debitos = await api.pagamentos.debitos.list();
      return (debitos as DebitoOut[]).filter((d) =>
        ["AUTORIZADA", "REJEITADA_GESTOR", "INDEFERIDA_AUTORIDADE", "CANCELADA"].includes(
          d.situacao_tramitacao
        )
      );
    },
  });

  const debitos = (listQ.data ?? []) as DebitoOut[];
  const autorizadas = debitos.filter((d) => d.situacao_tramitacao === "AUTORIZADA");
  const rejeitadas = debitos.filter((d) => d.situacao_tramitacao === "REJEITADA_GESTOR");
  const indeferidas = debitos.filter(
    (d) => d.situacao_tramitacao === "INDEFERIDA_AUTORIDADE"
  );
  const canceladas = debitos.filter((d) => d.situacao_tramitacao === "CANCELADA");

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Solicitações Concluídas</h1>
        <p className="text-sm text-muted-foreground">
          Histórico de solicitações já finalizadas
        </p>
      </div>

      {/* Resumo */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-surface-1 border rounded">
          <div className="text-sm font-medium text-muted-foreground">Autorizadas</div>
          <div className="text-2xl font-bold text-success">{autorizadas.length}</div>
        </div>
        <div className="p-4 bg-surface-1 border rounded">
          <div className="text-sm font-medium text-muted-foreground">Rejeitadas</div>
          <div className="text-2xl font-bold text-danger">{rejeitadas.length}</div>
        </div>
        <div className="p-4 bg-surface-1 border rounded">
          <div className="text-sm font-medium text-muted-foreground">Indeferidas</div>
          <div className="text-2xl font-bold text-danger">{indeferidas.length}</div>
        </div>
        <div className="p-4 bg-surface-1 border rounded">
          <div className="text-sm font-medium text-muted-foreground">Canceladas</div>
          <div className="text-2xl font-bold text-muted-foreground">{canceladas.length}</div>
        </div>
      </div>

      {/* Autorizadas */}
      {autorizadas.length > 0 && (
        <div className="space-y-2">
          <h2 className="font-semibold text-success">Autorizadas</h2>
          <div className="border rounded-lg overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>ID</TH>
                  <TH>Fornecedor</TH>
                  <TH>Valor</TH>
                  <TH>Situação</TH>
                  <TH className="text-right">Ação</TH>
                </TR>
              </THead>
              <TBody>
                {autorizadas.map((d) => (
                  <TR key={d.id}>
                    <TD className="font-mono text-sm">#{d.id}</TD>
                    <TD>{d.nome_fornecedor}</TD>
                    <TD className="text-right tabular-nums">{fmtMoeda(d.valor_total)}</TD>
                    <TD>
                      <StatusBadge situacao={d.situacao_tramitacao} />
                    </TD>
                    <TD className="text-right">
                      <Link href={`/m/pagamentos/solicitacoes/${d.id}`}>
                        <Button size="sm" variant="secondary">
                          Ver
                        </Button>
                      </Link>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        </div>
      )}

      {/* Rejeitadas */}
      {rejeitadas.length > 0 && (
        <div className="space-y-2">
          <h2 className="font-semibold text-danger">Rejeitadas</h2>
          <div className="border rounded-lg overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>ID</TH>
                  <TH>Fornecedor</TH>
                  <TH>Valor</TH>
                  <TH>Situação</TH>
                  <TH className="text-right">Ação</TH>
                </TR>
              </THead>
              <TBody>
                {rejeitadas.map((d) => (
                  <TR key={d.id}>
                    <TD className="font-mono text-sm">#{d.id}</TD>
                    <TD>{d.nome_fornecedor}</TD>
                    <TD className="text-right tabular-nums">{fmtMoeda(d.valor_total)}</TD>
                    <TD>
                      <StatusBadge situacao={d.situacao_tramitacao} />
                    </TD>
                    <TD className="text-right">
                      <Link href={`/m/pagamentos/solicitacoes/${d.id}`}>
                        <Button size="sm" variant="secondary">
                          Ver
                        </Button>
                      </Link>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        </div>
      )}

      {/* Indeferidas */}
      {indeferidas.length > 0 && (
        <div className="space-y-2">
          <h2 className="font-semibold text-danger">Indeferidas</h2>
          <div className="border rounded-lg overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>ID</TH>
                  <TH>Fornecedor</TH>
                  <TH>Valor</TH>
                  <TH>Situação</TH>
                  <TH className="text-right">Ação</TH>
                </TR>
              </THead>
              <TBody>
                {indeferidas.map((d) => (
                  <TR key={d.id}>
                    <TD className="font-mono text-sm">#{d.id}</TD>
                    <TD>{d.nome_fornecedor}</TD>
                    <TD className="text-right tabular-nums">{fmtMoeda(d.valor_total)}</TD>
                    <TD>
                      <StatusBadge situacao={d.situacao_tramitacao} />
                    </TD>
                    <TD className="text-right">
                      <Link href={`/m/pagamentos/solicitacoes/${d.id}`}>
                        <Button size="sm" variant="secondary">
                          Ver
                        </Button>
                      </Link>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        </div>
      )}

      {/* Canceladas */}
      {canceladas.length > 0 && (
        <div className="space-y-2">
          <h2 className="font-semibold text-muted-foreground">Canceladas</h2>
          <div className="border rounded-lg overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>ID</TH>
                  <TH>Fornecedor</TH>
                  <TH>Valor</TH>
                  <TH>Situação</TH>
                  <TH className="text-right">Ação</TH>
                </TR>
              </THead>
              <TBody>
                {canceladas.map((d) => (
                  <TR key={d.id}>
                    <TD className="font-mono text-sm">#{d.id}</TD>
                    <TD>{d.nome_fornecedor}</TD>
                    <TD className="text-right tabular-nums">{fmtMoeda(d.valor_total)}</TD>
                    <TD>
                      <StatusBadge situacao={d.situacao_tramitacao} />
                    </TD>
                    <TD className="text-right">
                      <Link href={`/m/pagamentos/solicitacoes/${d.id}`}>
                        <Button size="sm" variant="secondary">
                          Ver
                        </Button>
                      </Link>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        </div>
      )}

      {debitos.length === 0 && (
        <div className="py-8 text-center text-muted-foreground">
          Nenhuma solicitação concluída
        </div>
      )}
    </div>
  );
}
