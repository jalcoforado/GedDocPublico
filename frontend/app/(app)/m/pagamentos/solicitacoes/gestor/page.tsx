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

export default function GestorPage() {
  // Listar débitos aguardando gestor
  const listQ = useQuery({
    queryKey: ["pag-solicitacoes-gestor"],
    queryFn: async () => {
      const debitos = await api.pagamentos.debitos.list();
      return (debitos as DebitoOut[]).filter((d) =>
        ["AGUARDANDO_GESTOR", "AJUSTE_GESTOR"].includes(d.situacao_tramitacao)
      );
    },
  });

  const debitos = (listQ.data ?? []) as DebitoOut[];
  const aguardandoGestor = debitos.filter((d) => d.situacao_tramitacao === "AGUARDANDO_GESTOR");
  const ajusteGestor = debitos.filter((d) => d.situacao_tramitacao === "AJUSTE_GESTOR");

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Fila do Gestor</h1>
        <p className="text-sm text-muted-foreground">
          Solicitações aguardando sua decisão
        </p>
      </div>

      {/* Resumo */}
      <div className="grid grid-cols-2 gap-4">
        <div className="p-4 bg-surface-1 border rounded">
          <div className="text-sm font-medium text-muted-foreground">Aguardando Decisão</div>
          <div className="text-2xl font-bold">{aguardandoGestor.length}</div>
        </div>
        <div className="p-4 bg-surface-1 border rounded">
          <div className="text-sm font-medium text-muted-foreground">Aguardando Ajustes</div>
          <div className="text-2xl font-bold">{ajusteGestor.length}</div>
        </div>
      </div>

      {/* Aguardando Decisão */}
      {aguardandoGestor.length > 0 && (
        <div className="space-y-2">
          <h2 className="font-semibold">Aguardando Sua Decisão</h2>
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
                {aguardandoGestor.map((d) => (
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
                          Analisar
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

      {/* Aguardando Ajustes */}
      {ajusteGestor.length > 0 && (
        <div className="space-y-2">
          <h2 className="font-semibold">Aguardando Ajustes</h2>
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
                {ajusteGestor.map((d) => (
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
          Nenhuma solicitação aguardando sua ação
        </div>
      )}
    </div>
  );
}
