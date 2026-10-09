"use client";

import { useQuery } from "@tanstack/react-query";
import { Inbox, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import {
  SituacaoContratoBadge,
  TRANSACAO_CONTRATO,
  VencimentoBadge,
  fmtPercentual,
} from "@/components/contratos/comum";
import { fmtData, fmtMoeda } from "@/components/pagamentos/format";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { SITUACAO_CONTRATO_LABEL, api, type SituacaoContrato } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const PAGE_SIZE = 20;
const SITUACOES = Object.keys(SITUACAO_CONTRATO_LABEL) as SituacaoContrato[];

export default function ContratosListaPage() {
  const { can } = useAuth();
  const podeCriar = can(TRANSACAO_CONTRATO, "inserir");

  const [situacao, setSituacao] = useState<SituacaoContrato | "">("");
  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [page, setPage] = useState(1);

  // Debounce: o termo vai para o servidor, então sem isto seria uma consulta
  // por tecla. Volta para a página 1 — a página 3 de outra busca não existe.
  useEffect(() => {
    const t = setTimeout(() => {
      setBuscaAplicada(busca.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [busca]);

  const listaQ = useQuery({
    queryKey: ["contratos-lista", situacao, buscaAplicada, page],
    queryFn: () =>
      api.contratos.list({ situacao, q: buscaAplicada, page, page_size: PAGE_SIZE }),
  });

  // Endpoint paginado: a tela consome `.items`. Tratar `data` como array
  // faria a lista dizer "nenhum contrato" com contratos no banco.
  const itens = listaQ.data?.items ?? [];
  const total = listaQ.data?.total ?? 0;
  const filtrando = situacao !== "" || buscaAplicada !== "";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Contratos"
        description="Do que vence primeiro para o que vence por último."
        breadcrumbs={[{ label: "Contratos e Convênios", href: "/m/contratos" }, { label: "Contratos" }]}
        actions={
          podeCriar ? (
            <Button asChild>
              <Link href="/m/contratos/contratos/novo">
                <Plus className="mr-1 h-4 w-4" />
                Novo contrato
              </Link>
            </Button>
          ) : undefined
        }
      />

      <div className="flex flex-wrap gap-3">
        <div>
          <Label htmlFor="f_situacao">Situação</Label>
          <Select
            id="f_situacao"
            value={situacao}
            onChange={(e) => {
              setSituacao(e.target.value as SituacaoContrato | "");
              setPage(1);
            }}
          >
            <option value="">Todas</option>
            {SITUACOES.map((s) => (
              <option key={s} value={s}>
                {SITUACAO_CONTRATO_LABEL[s]}
              </option>
            ))}
          </Select>
        </div>
        <div className="min-w-[220px] flex-1">
          <Label htmlFor="f_q">Busca por número ou objeto</Label>
          <Input
            id="f_q"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="012/2026, merenda, pavimentação..."
          />
        </div>
      </div>

      {listaQ.isError ? (
        <Alert intent="danger" title="Não foi possível carregar os contratos">
          {(listaQ.error as Error).message}
        </Alert>
      ) : listaQ.isLoading ? (
        <div className="py-8 text-center text-muted-foreground">Carregando...</div>
      ) : itens.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={filtrando ? "Nenhum contrato encontrado" : "Nenhum contrato"}
          description={
            filtrando
              ? "Nada corresponde ao filtro. A busca cobre todos os contratos do município, não só os desta página."
              : "Cadastre o primeiro contrato do município."
          }
        />
      ) : (
        <>
          <Table>
            <THead>
              <TR>
                <TH>Número</TH>
                <TH>Contratado</TH>
                <TH>Objeto</TH>
                <TH>Situação</TH>
                <TH>Vigência até</TH>
                <TH className="text-right">Valor atualizado</TH>
                <TH className="text-right">Aditivado</TH>
              </TR>
            </THead>
            <TBody>
              {itens.map((c) => (
                <TR key={c.id}>
                  <TD className="font-mono font-medium">
                    <Link
                      href={`/m/contratos/contratos/${c.id}`}
                      className="text-primary hover:underline"
                    >
                      {c.numero}
                    </Link>
                  </TD>
                  <TD>
                    <div>{c.fornecedor_nome ?? "—"}</div>
                    <div className="text-xs text-muted-foreground">{c.unidade_nome ?? "—"}</div>
                  </TD>
                  <TD className="max-w-xs truncate text-sm" title={c.objeto}>
                    {c.objeto}
                  </TD>
                  <TD>
                    <SituacaoContratoBadge situacao={c.situacao} />
                  </TD>
                  <TD>
                    <div className="flex flex-wrap items-center gap-2">
                      <span>{fmtData(c.vigencia_fim_atual)}</span>
                      <VencimentoBadge dias={c.dias_para_vencer} />
                    </div>
                  </TD>
                  <TD className="text-right tabular-nums">{fmtMoeda(c.valor_atualizado)}</TD>
                  <TD className="text-right tabular-nums">
                    <div className="flex items-center justify-end gap-2">
                      {c.acima_do_limite && <Badge intent="warning">Acima do limite</Badge>}
                      <span>{fmtPercentual(c.percentual_acrescimo)}</span>
                    </div>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
