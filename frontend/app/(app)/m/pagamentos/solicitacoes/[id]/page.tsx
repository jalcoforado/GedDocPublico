"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, FileText, History, Receipt } from "lucide-react";
import { use, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Skeleton } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { EtapasFluxo } from "@/components/pagamentos/EtapasFluxo";
import { ProximaAcao } from "@/components/pagamentos/ProximaAcao";
import { SituacoesDebito } from "@/components/pagamentos/SituacoesDebito";
import { api, type DebitoOut } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { TRAMITACAO_ROTULO } from "@/components/pagamentos/situacoes";
import { fmtData, fmtMoeda } from "@/components/pagamentos/format";

export default function DetalheDebitosPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: idParam } = use(params);
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const id = parseInt(idParam);

  const [openDialog, setOpenDialog] = useState(false);
  const [justificativa, setJustificativa] = useState("");
  const [acaoSelecionada, setAcaoSelecionada] = useState<string | null>(null);
  const [etapaSelecionada, setEtapaSelecionada] = useState<"GESTOR" | "VALIDACAO" | "AUTORIDADE" | null>(null);

  // Carregar débito
  const debitoQ = useQuery({
    queryKey: ["pag-debito", id],
    queryFn: () => api.pagamentos.debitos.get(id),
  });

  const debito = debitoQ.data as DebitoOut | undefined;

  // Mutations para ações
  const enviarGestorM = useMutation({
    mutationFn: () =>
      api.pagamentos.debitos.enviarParaGestor(id, {
        lock_version: debito?.lock_version ?? 0,
      }),
    onSuccess: () => {
      toast.success("Enviado para o gestor");
      qc.invalidateQueries({ queryKey: ["pag-debito", id] });
      setOpenDialog(false);
    },
    onError: (err: any) => {
      toast.error(err.message || "Erro ao enviar");
    },
  });

  const gestorAutorizarM = useMutation({
    mutationFn: () =>
      api.pagamentos.debitos.gestorAutorizar(id, {
        lock_version: debito?.lock_version ?? 0,
      }),
    onSuccess: () => {
      toast.success("Autorizado pelo gestor");
      qc.invalidateQueries({ queryKey: ["pag-debito", id] });
      setOpenDialog(false);
    },
    onError: (err: any) => {
      toast.error(err.message || "Erro ao autorizar");
    },
  });

  const gestorRejeitarM = useMutation({
    mutationFn: () =>
      api.pagamentos.debitos.gestorRejeitar(id, {
        lock_version: debito?.lock_version ?? 0,
        justificativa,
      }),
    onSuccess: () => {
      toast.success("Rejeitado pelo gestor");
      qc.invalidateQueries({ queryKey: ["pag-debito", id] });
      setOpenDialog(false);
    },
    onError: (err: any) => {
      toast.error(err.message || "Erro ao rejeitar");
    },
  });

  const validarM = useMutation({
    mutationFn: () =>
      api.pagamentos.debitos.validar(id, {
        lock_version: debito?.lock_version ?? 0,
      }),
    onSuccess: () => {
      toast.success("Validado");
      qc.invalidateQueries({ queryKey: ["pag-debito", id] });
      setOpenDialog(false);
    },
    onError: (err: any) => {
      toast.error(err.message || "Erro ao validar");
    },
  });

  const autoridadeAprovarM = useMutation({
    mutationFn: () =>
      api.pagamentos.debitos.autoridadeAprovar(id, {
        lock_version: debito?.lock_version ?? 0,
      }),
    onSuccess: () => {
      toast.success("Aprovado pela autoridade");
      qc.invalidateQueries({ queryKey: ["pag-debito", id] });
      setOpenDialog(false);
    },
    onError: (err: any) => {
      toast.error(err.message || "Erro ao aprovar");
    },
  });

  const autoridadeIndeferirM = useMutation({
    mutationFn: () =>
      api.pagamentos.debitos.autoridadeIndeferir(id, {
        lock_version: debito?.lock_version ?? 0,
        justificativa,
      }),
    onSuccess: () => {
      toast.success("Indeferido pela autoridade");
      qc.invalidateQueries({ queryKey: ["pag-debito", id] });
      setOpenDialog(false);
    },
    onError: (err: any) => {
      toast.error(err.message || "Erro ao indeferir");
    },
  });

  const solicitarAjusteM = useMutation({
    mutationFn: () => {
      if (!etapaSelecionada) throw new Error("Etapa do ajuste não informada");
      return api.pagamentos.debitos.solicitarAjuste(id, {
        lock_version: debito?.lock_version ?? 0,
        etapa: etapaSelecionada,
        justificativa,
      });
    },
    onSuccess: () => {
      toast.success("Ajuste solicitado");
      qc.invalidateQueries({ queryKey: ["pag-debito", id] });
      setOpenDialog(false);
    },
    onError: (err: any) => toast.error(err.message || "Erro ao solicitar ajuste"),
  });

  const responderAjusteM = useMutation({
    mutationFn: () => api.pagamentos.debitos.responderAjuste(id, {
      lock_version: debito?.lock_version ?? 0,
    }),
    onSuccess: () => {
      toast.success("Ajuste respondido");
      qc.invalidateQueries({ queryKey: ["pag-debito", id] });
      setOpenDialog(false);
    },
    onError: (err: any) => toast.error(err.message || "Erro ao responder ajuste"),
  });

  const cancelarM = useMutation({
    mutationFn: () => api.pagamentos.debitos.cancelar(id, {
      lock_version: debito?.lock_version ?? 0,
      justificativa,
    }),
    onSuccess: () => {
      toast.success("Solicitação cancelada");
      qc.invalidateQueries({ queryKey: ["pag-debito", id] });
      setOpenDialog(false);
    },
    onError: (err: any) => toast.error(err.message || "Erro ao cancelar"),
  });

  const confirmarLiquidacaoM = useMutation({
    mutationFn: () => api.pagamentos.debitos.confirmarLiquidacao(id),
    onSuccess: () => {
      toast.success("Liquidação confirmada");
      qc.invalidateQueries({ queryKey: ["pag-debito", id] });
    },
    onError: (err: any) => toast.error(err.message || "Erro ao confirmar liquidação"),
  });

  const breadcrumbs = [
    { label: "Pagamentos", href: "/m/pagamentos" },
    { label: "Solicitações", href: "/m/pagamentos/solicitacoes" },
  ];

  if (debitoQ.isLoading) {
    return (
      <div className="space-y-4">
        <PageHeader breadcrumbs={breadcrumbs} title="Carregando…" icon={FileText} />
        <Skeleton className="h-16 w-full" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
          <Skeleton className="h-56 w-full" />
        </div>
      </div>
    );
  }

  if (!debito) {
    return (
      <div className="space-y-4">
        <PageHeader breadcrumbs={breadcrumbs} title="Solicitação" icon={FileText} />
        <EmptyState
          icon={FileText}
          title="Solicitação não encontrada"
          description="Ela pode ter sido removida, ou o número informado está incorreto."
        />
      </div>
    );
  }

  const perfis = [
    "pagamento_solicitar", "pagamento_gerir", "pagamento_validar", "pagamento_autorizar",
  ].filter((codigo) => can(codigo));

  const rotulo = TRAMITACAO_ROTULO[debito.situacao_tramitacao];

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={breadcrumbs}
        title={`Solicitação #${debito.id}`}
        description={debito.nome_fornecedor}
        icon={FileText}
        actions={<Badge intent={rotulo.intent} icon={rotulo.icon}>{rotulo.label}</Badge>}
      />

      {/* Stepper */}
      <SectionCard title="Progresso do fluxo" icon={ClipboardList}>
        <EtapasFluxo tramitacao={debito.situacao_tramitacao} />
      </SectionCard>

      {/* Três dimensões */}
      <SituacoesDebito
        tramitacao={debito.situacao_tramitacao}
        fila={debito.situacao_fila}
        pagamento={debito.situacao_pagamento}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Coluna principal */}
        <div className="space-y-4 lg:col-span-2">
          {/* Informações gerais */}
          <SectionCard title="Informações" icon={FileText}>
            <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
              <div>
                <div className="text-xs font-medium text-foreground-muted">Fornecedor</div>
                <div className="text-foreground">{debito.nome_fornecedor}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-foreground-muted">Valor Total</div>
                <div className="tabular-nums text-foreground">{fmtMoeda(debito.valor_total)}</div>
              </div>
              <div className="sm:col-span-2">
                <div className="text-xs font-medium text-foreground-muted">Descrição</div>
                <div className="text-foreground">{debito.descricao}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-foreground-muted">Competência</div>
                <div className="text-foreground">{debito.competencia}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-foreground-muted">NE</div>
                <div className="font-mono text-foreground">{debito.numero_ne || "—"}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-foreground-muted">NF</div>
                <div className="font-mono text-foreground">{debito.numero_nf || "—"}</div>
              </div>
            </div>
          </SectionCard>

          {/* Parcelas */}
          <SectionCard title="Parcelas" icon={Receipt}>
            {debitoQ.data?.parcelas && debitoQ.data.parcelas.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <THead>
                    <TR>
                      <TH>Número</TH>
                      <TH className="text-right">Valor</TH>
                      <TH>Vencimento</TH>
                      <TH>Status</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {debitoQ.data.parcelas.map((p) => (
                      <TR key={p.id}>
                        <TD>{p.numero}</TD>
                        <TD className="text-right tabular-nums">{fmtMoeda(p.valor)}</TD>
                        <TD>{fmtData(p.vencimento)}</TD>
                        <TD>
                          <Badge intent="neutral">{p.status}</Badge>
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </div>
            ) : (
              <p className="text-sm text-foreground-subtle">Nenhuma parcela cadastrada.</p>
            )}
          </SectionCard>

          {/* Histórico */}
          <SectionCard title="Histórico" icon={History}>
            {debitoQ.data?.historico && debitoQ.data.historico.length > 0 ? (
              <div className="space-y-3">
                {debitoQ.data.historico.map((h) => (
                  <div key={h.id} className="border-l-2 border-border pl-3 py-0.5 text-sm">
                    <div className="font-medium text-foreground">{h.acao}</div>
                    <div className="text-xs text-foreground-muted">
                      {h.nome_usuario} · {fmtData(h.criado_em)}
                    </div>
                    {h.justificativa && (
                      <div className="mt-1 text-xs italic text-foreground-subtle">{h.justificativa}</div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-foreground-subtle">Sem movimentações registradas.</p>
            )}
          </SectionCard>
        </div>

        {/* Coluna lateral — ações */}
        <div className="space-y-4">
          {debito.situacao_tramitacao === "AGUARDANDO_VALIDACAO" &&
            can("pagamento_validar") && !debito.liquidacao_confirmada && (
              <Button
                variant="secondary"
                className="w-full"
                onClick={() => confirmarLiquidacaoM.mutate()}
                disabled={confirmarLiquidacaoM.isPending}
              >
                Confirmar liquidação
              </Button>
            )}
          <ProximaAcao
            tramitacao={debito.situacao_tramitacao}
            perfis={perfis}
            onAction={(acao, etapa) => {
              setJustificativa("");
              setAcaoSelecionada(acao);
              setEtapaSelecionada(
                etapa === "GESTOR" || etapa === "VALIDACAO" || etapa === "AUTORIDADE"
                  ? etapa
                  : null,
              );
              setOpenDialog(true);
            }}
          />
        </div>
      </div>

      {/* Dialog para ações com justificativa */}
      <Dialog
        open={openDialog}
        onClose={() => setOpenDialog(false)}
        title={
          acaoSelecionada === "enviar"
            ? "Enviar para Gestor"
            : acaoSelecionada === "gestor/autorizar"
              ? "Autorizar"
              : acaoSelecionada === "gestor/rejeitar"
                ? "Rejeitar"
                : acaoSelecionada === "validar"
                  ? "Validar"
                  : acaoSelecionada === "autoridade/aprovar"
                    ? "Aprovar"
                    : acaoSelecionada === "autoridade/indeferir"
                      ? "Indeferir"
                      : acaoSelecionada === "ajuste/solicitar"
                        ? "Solicitar ajuste"
                        : acaoSelecionada === "ajuste/responder"
                          ? "Responder ajuste"
                          : "Cancelar solicitação"
        }
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpenDialog(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => {
                if (acaoSelecionada === "enviar") enviarGestorM.mutate();
                if (acaoSelecionada === "gestor/autorizar") gestorAutorizarM.mutate();
                if (acaoSelecionada === "gestor/rejeitar") gestorRejeitarM.mutate();
                if (acaoSelecionada === "validar") validarM.mutate();
                if (acaoSelecionada === "autoridade/aprovar") autoridadeAprovarM.mutate();
                if (acaoSelecionada === "autoridade/indeferir") autoridadeIndeferirM.mutate();
                if (acaoSelecionada === "ajuste/solicitar") solicitarAjusteM.mutate();
                if (acaoSelecionada === "ajuste/responder") responderAjusteM.mutate();
                if (acaoSelecionada === "cancelar") cancelarM.mutate();
              }}
              disabled={
                ["gestor/rejeitar", "autoridade/indeferir", "ajuste/solicitar", "cancelar"]
                  .includes(acaoSelecionada ?? "") && !justificativa.trim()
              }
            >
              Confirmar
            </Button>
          </>
        }
      >
        {["gestor/rejeitar", "autoridade/indeferir", "ajuste/solicitar", "cancelar"]
          .includes(acaoSelecionada ?? "") && (
          <div className="space-y-3">
            <Label>Justificativa</Label>
            <Textarea
              value={justificativa}
              onChange={(e) => setJustificativa(e.target.value)}
              placeholder="Explique o motivo..."
              className="min-h-24"
            />
          </div>
        )}
      </Dialog>
    </div>
  );
}
