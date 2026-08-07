"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type DebitoOut, type SituacaoTramitacao } from "@/lib/api";
import { SITUACAO_TRAMITACAO_CONFIG, getEtapaIndex } from "@/components/pagamentos/statusFluxo";
import { fmtData, fmtMoeda } from "@/components/pagamentos/format";
import Link from "next/link";

function StatusBadge({ situacao }: { situacao: SituacaoTramitacao }) {
  const cfg = SITUACAO_TRAMITACAO_CONFIG[situacao];
  return <Badge intent={cfg.intent}>{cfg.label}</Badge>;
}

export default function SolicitacoesPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const router = useRouter();

  const [situacaoFiltro, setSituacaoFiltro] = useState<SituacaoTramitacao | "">("");
  const [fornecedorFiltro, setFornecedorFiltro] = useState("");
  const [search, setSearch] = useState("");

  // Listar solicitações (todas, ou filtradas por situação)
  const listQ = useQuery({
    queryKey: ["pag-solicitacoes-fluxo", situacaoFiltro, search],
    queryFn: async () => {
      // Lista todos os débitos com status EM_VALIDACAO ou superior (fluxo novo)
      const debitos = await api.pagamentos.debitos.list({
        status: situacaoFiltro || undefined,
      });

      // Filtra por fornecedor se necessário
      if (fornecedorFiltro) {
        return debitos.filter(d =>
          d.nome_fornecedor.toLowerCase().includes(fornecedorFiltro.toLowerCase())
        );
      }

      if (search) {
        return debitos.filter(d =>
          d.descricao.toLowerCase().includes(search.toLowerCase()) ||
          d.nome_fornecedor.toLowerCase().includes(search.toLowerCase()) ||
          d.numero_nf?.includes(search) ||
          d.numero_ne?.includes(search)
        );
      }

      return debitos;
    },
  });

  const debitos = useMemo(() => {
    return (listQ.data ?? []) as DebitoOut[];
  }, [listQ.data]);

  const etapas = useMemo(() => {
    const map: Record<number, DebitoOut[]> = {};
    debitos.forEach(d => {
      const idx = getEtapaIndex(d.situacao_tramitacao);
      if (!map[idx]) map[idx] = [];
      map[idx].push(d);
    });
    return map;
  }, [debitos]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Solicitações de Pagamento</h1>
          <p className="text-sm text-muted-foreground">
            Acompanhe as solicitações no fluxo de aprovação
          </p>
        </div>
        <Link href="/m/pagamentos/solicitacoes/novo">
          <Button>Nova Solicitação</Button>
        </Link>
      </div>

      {/* Filtros */}
      <div className="flex gap-3 flex-wrap">
        <Input
          placeholder="Pesquisar por fornecedor, descrição ou NF..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-64"
        />
        <Select
          value={situacaoFiltro}
          onChange={(e) => setSituacaoFiltro(e.target.value as SituacaoTramitacao | "")}
        >
          <option value="">Todas as situações</option>
          <option value="RASCUNHO">Rascunho</option>
          <option value="AGUARDANDO_GESTOR">Aguardando Gestor</option>
          <option value="AJUSTE_GESTOR">Ajuste (Gestor)</option>
          <option value="AGUARDANDO_VALIDACAO">Aguardando Validação</option>
          <option value="AJUSTE_VALIDACAO">Ajuste (Validação)</option>
          <option value="AGUARDANDO_AUTORIDADE">Aguardando Autoridade</option>
          <option value="AJUSTE_AUTORIDADE">Ajuste (Autoridade)</option>
          <option value="AUTORIZADA">Autorizada</option>
          <option value="REJEITADA_GESTOR">Rejeitada</option>
          <option value="INDEFERIDA_AUTORIDADE">Indeferida</option>
          <option value="CANCELADA">Cancelada</option>
        </Select>
      </div>

      {/* Tabela */}
      <div className="border rounded-lg overflow-x-auto">
        <Table>
          <THead>
            <TR>
              <TH>ID</TH>
              <TH>Fornecedor</TH>
              <TH>Descrição</TH>
              <TH>Valor</TH>
              <TH>Situação</TH>
              <TH>Etapa</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {listQ.isLoading && (
              <TR>
                <TD colSpan={7} className="py-8 text-center">
                  Carregando...
                </TD>
              </TR>
            )}
            {!listQ.isLoading && debitos.length === 0 && (
              <TR>
                <TD colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                  Nenhuma solicitação encontrada
                </TD>
              </TR>
            )}
            {debitos.map((d) => (
              <TR key={d.id}>
                <TD className="font-mono text-sm">#{d.id}</TD>
                <TD>{d.nome_fornecedor}</TD>
                <TD className="max-w-xs truncate">{d.descricao}</TD>
                <TD className="text-right tabular-nums">{fmtMoeda(d.valor_total)}</TD>
                <TD>
                  <StatusBadge situacao={d.situacao_tramitacao} />
                </TD>
                <TD className="text-sm text-muted-foreground">
                  {getEtapaIndex(d.situacao_tramitacao) === 0 && "Rascunho"}
                  {getEtapaIndex(d.situacao_tramitacao) === 1 && "Gestor"}
                  {getEtapaIndex(d.situacao_tramitacao) === 2 && "Validação"}
                  {getEtapaIndex(d.situacao_tramitacao) === 3 && "Autoridade"}
                  {getEtapaIndex(d.situacao_tramitacao) === 4 && "Concluído"}
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

      {/* Sumário por etapa */}
      {debitos.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          {[0, 1, 2, 3, 4].map((idx) => {
            const count = etapas[idx]?.length ?? 0;
            const labels = ["Rascunho", "Gestor", "Validação", "Autoridade", "Concluído"];
            return (
              <div key={idx} className="p-3 border rounded bg-surface-1">
                <div className="text-sm font-medium text-muted-foreground">{labels[idx]}</div>
                <div className="text-2xl font-bold">{count}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
