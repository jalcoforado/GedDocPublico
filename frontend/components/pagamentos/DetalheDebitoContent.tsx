"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ClipboardList,
  Download,
  FileEdit,
  FileText,
  History,
  Layers,
  Paperclip,
  Receipt,
  Trash2,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SectionCard } from "@/components/ui/section-card";
import { Skeleton } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { EtapasFluxo } from "@/components/pagamentos/EtapasFluxo";
import { ProximaAcao } from "@/components/pagamentos/ProximaAcao";
import { SituacoesDebito } from "@/components/pagamentos/SituacoesDebito";
import {
  PEDIDO_AJUSTE_ROTULO,
  TRAMITACAO_ROTULO,
  TRANSACAO_PAGAMENTOS,
  TRANSACAO_PAGAMENTOS_ROTULO,
} from "@/components/pagamentos/situacoes";
import { fmtData, fmtDataHora, fmtMoeda, fmtTamanho } from "@/components/pagamentos/format";
import {
  ApiError,
  api,
  type AnexoDebitoOut,
  type DebitoOut,
  type EtapaAjuste,
  type TipoAjuste,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

// Etapa que ABRIU o ajuste, a partir da situação atual — espelha
// `ajustes.ETAPA_POR_SITUACAO` (backend). Não confundir com "de quem é a vez
// agora" (sempre UNIDADE nesses estados): aqui é quem PODE abrir um pedido
// adicional ou cancelar o pedido que abriu.
const ETAPA_ABERTURA_POR_TRAMITACAO: Partial<Record<string, EtapaAjuste>> = {
  AJUSTE_GESTOR: "GESTOR",
  AJUSTE_VALIDACAO: "VALIDACAO",
  AJUSTE_AUTORIDADE: "AUTORIDADE",
};

const TRANSACAO_POR_ETAPA: Record<EtapaAjuste, string> = {
  GESTOR: "pagamento_gerir",
  VALIDACAO: "pagamento_validar",
  AUTORIDADE: "pagamento_autorizar",
};

/**
 * Conteúdo do detalhe de uma solicitação de pagamento — extraído de
 * `app/(app)/m/pagamentos/solicitacoes/[id]/page.tsx` para ser testável sem
 * o `use(params)` da rota (Suspense de parâmetro assíncrono não se
 * resolve de forma confiável em teste isolado; ver AdminTenantModulos.test.tsx
 * para o mesmo padrão de extração).
 */
export function DetalheDebitoContent({ id }: { id: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();

  const [openDialog, setOpenDialog] = useState(false);
  const [justificativa, setJustificativa] = useState("");
  const [acaoSelecionada, setAcaoSelecionada] = useState<string | null>(null);
  const [etapaSelecionada, setEtapaSelecionada] = useState<EtapaAjuste | null>(null);

  // Form rico de "Solicitar ajustes" / "Novo pedido de ajuste" (F2)
  const [ajusteMotivo, setAjusteMotivo] = useState("");
  const [ajusteDescricao, setAjusteDescricao] = useState("");
  const [ajusteTransacao, setAjusteTransacao] = useState("");
  const [ajusteTipo, setAjusteTipo] = useState<TipoAjuste>("NAO_MATERIAL");
  const [ajustePrazo, setAjustePrazo] = useState("");
  const [ajusteCampos, setAjusteCampos] = useState("");

  // Resposta a um pedido de ajuste específico
  const [respostaPorPedido, setRespostaPorPedido] = useState<Record<number, string>>({});

  // Documentos do débito (F2, Task 8)
  const [anexoArquivo, setAnexoArquivo] = useState<File | null>(null);
  const [anexoDescricao, setAnexoDescricao] = useState("");
  const [anexoPedidoId, setAnexoPedidoId] = useState<number | "">("");
  const [confirmRemoverAnexo, setConfirmRemoverAnexo] = useState<AnexoDebitoOut | null>(null);

  // Carregar débito
  const debitoQ = useQuery({
    queryKey: ["pag-debito", id],
    queryFn: () => api.pagamentos.debitos.get(id),
  });

  const debito = debitoQ.data as DebitoOut | undefined;

  const pedidosQ = useQuery({
    queryKey: ["pag-pedidos-ajuste", id],
    queryFn: () => api.pagamentos.debitos.listarPedidosAjuste(id),
  });

  const versoesQ = useQuery({
    queryKey: ["pag-versoes", id],
    queryFn: () => api.pagamentos.debitos.listarVersoes(id),
    enabled: !!debito && debito.versao > 1,
  });

  const anexosQ = useQuery({
    queryKey: ["pag-anexos", id],
    queryFn: () => api.pagamentos.debitos.listarAnexos(id),
  });
  const anexos = anexosQ.data ?? [];

  const pedidos = pedidosQ.data ?? [];
  const pedidosAbertos = pedidos.filter((p) => p.situacao === "ABERTO");
  // Pedidos abertos que ESTE usuário pode responder — "o form de responder
  // está aberto" para eles (seção "Pendências de ajuste" mais abaixo). O
  // upload de documento associado carrega o id_pedido_ajuste de um deles.
  const pedidosRespondiveisPorMim = pedidosAbertos.filter((p) => can(p.transacao_responsavel));
  const anexoPedidoSelecionado =
    anexoPedidoId !== ""
      ? anexoPedidoId
      : pedidosRespondiveisPorMim.length === 1
        ? pedidosRespondiveisPorMim[0].id
        : "";

  function resetFormAjuste() {
    setAjusteMotivo("");
    setAjusteDescricao("");
    setAjusteTransacao("");
    setAjusteTipo("NAO_MATERIAL");
    setAjustePrazo("");
    setAjusteCampos("");
  }

  function invalidarTudo() {
    qc.invalidateQueries({ queryKey: ["pag-debito", id] });
    qc.invalidateQueries({ queryKey: ["pag-pedidos-ajuste", id] });
    qc.invalidateQueries({ queryKey: ["pag-versoes", id] });
    qc.invalidateQueries({ queryKey: ["pag-anexos", id] });
  }

  // Mutations para ações
  const enviarGestorM = useMutation({
    mutationFn: () =>
      api.pagamentos.debitos.enviarParaGestor(id, {
        lock_version: debito?.lock_version ?? 0,
      }),
    onSuccess: () => {
      toast.success("Enviado para o gestor");
      invalidarTudo();
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
      invalidarTudo();
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
      invalidarTudo();
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
      invalidarTudo();
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
      invalidarTudo();
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
      invalidarTudo();
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
        motivo: ajusteMotivo,
        descricao: ajusteDescricao,
        transacao_responsavel: ajusteTransacao,
        tipo: ajusteTipo,
        prazo: ajustePrazo || null,
        campos_relacionados: ajusteCampos.trim()
          ? ajusteCampos.split(",").map((c) => c.trim()).filter(Boolean)
          : null,
      });
    },
    onSuccess: () => {
      toast.success("Ajuste solicitado");
      invalidarTudo();
      setOpenDialog(false);
      resetFormAjuste();
    },
    onError: (err: any) => toast.error(err.message || "Erro ao solicitar ajuste"),
  });

  // Pedido adicional sobre um débito já em ajuste — não transiciona o débito.
  const criarPedidoAjusteM = useMutation({
    mutationFn: () =>
      api.pagamentos.debitos.criarPedidoAjuste(id, {
        motivo: ajusteMotivo,
        descricao: ajusteDescricao,
        transacao_responsavel: ajusteTransacao,
        tipo: ajusteTipo,
        prazo: ajustePrazo || null,
        campos_relacionados: ajusteCampos.trim()
          ? ajusteCampos.split(",").map((c) => c.trim()).filter(Boolean)
          : null,
      }),
    onSuccess: () => {
      toast.success("Pedido de ajuste adicional criado");
      invalidarTudo();
      setOpenDialog(false);
      resetFormAjuste();
    },
    onError: (err: any) => toast.error(err.message || "Erro ao criar pedido de ajuste"),
  });

  // Reenvio: 409 quando ainda há pedido ABERTO — a tela recarrega e mostra o
  // estado real, sem repetir a ação (spec Task 7).
  const responderAjusteM = useMutation({
    mutationFn: () => api.pagamentos.debitos.responderAjuste(id, {
      lock_version: debito?.lock_version ?? 0,
    }),
    onSuccess: () => {
      toast.success("Ajuste respondido");
      invalidarTudo();
      setOpenDialog(false);
    },
    onError: (err: any) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error("Ainda há pedido de ajuste em aberto — a tela foi atualizada.");
        invalidarTudo();
        return;
      }
      toast.error(err.message || "Erro ao responder ajuste");
    },
  });

  const responderPedidoM = useMutation({
    mutationFn: ({ pedidoId, resposta }: { pedidoId: number; resposta: string }) =>
      api.pagamentos.debitos.responderPedidoAjuste(id, pedidoId, { resposta }),
    onSuccess: (_data, vars) => {
      toast.success("Pedido de ajuste respondido");
      setRespostaPorPedido((r) => ({ ...r, [vars.pedidoId]: "" }));
      invalidarTudo();
    },
    onError: (err: any) => toast.error(err.message || "Erro ao responder pedido"),
  });

  const cancelarPedidoM = useMutation({
    mutationFn: (pedidoId: number) => api.pagamentos.debitos.cancelarPedidoAjuste(id, pedidoId),
    onSuccess: () => {
      toast.success("Pedido de ajuste cancelado");
      invalidarTudo();
    },
    onError: (err: any) => toast.error(err.message || "Erro ao cancelar pedido"),
  });

  const cancelarM = useMutation({
    mutationFn: () => api.pagamentos.debitos.cancelar(id, {
      lock_version: debito?.lock_version ?? 0,
      justificativa,
    }),
    onSuccess: () => {
      toast.success("Solicitação cancelada");
      invalidarTudo();
      setOpenDialog(false);
    },
    onError: (err: any) => toast.error(err.message || "Erro ao cancelar"),
  });

  const confirmarLiquidacaoM = useMutation({
    mutationFn: () => api.pagamentos.debitos.confirmarLiquidacao(id),
    onSuccess: () => {
      toast.success("Liquidação confirmada");
      invalidarTudo();
    },
    onError: (err: any) => toast.error(err.message || "Erro ao confirmar liquidação"),
  });

  const uploadAnexoM = useMutation({
    mutationFn: () => {
      if (!anexoArquivo) throw new Error("Selecione um arquivo");
      return api.pagamentos.debitos.uploadAnexo(
        id,
        anexoArquivo,
        anexoDescricao || undefined,
        anexoPedidoSelecionado || null,
      );
    },
    onSuccess: () => {
      toast.success("Documento anexado");
      setAnexoArquivo(null);
      setAnexoDescricao("");
      setAnexoPedidoId("");
      qc.invalidateQueries({ queryKey: ["pag-anexos", id] });
    },
    onError: (err: any) => toast.error(err.message || "Erro ao anexar documento"),
  });

  const removerAnexoM = useMutation({
    mutationFn: (anexoDebitoId: number) => api.pagamentos.debitos.removerAnexo(id, anexoDebitoId),
    onSuccess: () => {
      toast.success("Documento removido");
      setConfirmRemoverAnexo(null);
      qc.invalidateQueries({ queryKey: ["pag-anexos", id] });
    },
    onError: (err: any) => toast.error(err.message || "Erro ao remover documento"),
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

  // Etapa que abriu o ajuste atual (se o débito está em AJUSTE_*) — decide
  // quem pode abrir pedido adicional e quem pode cancelar o pedido que abriu.
  const etapaAbertura = ETAPA_ABERTURA_POR_TRAMITACAO[debito.situacao_tramitacao];
  const podeAdicionarPedido =
    !!etapaAbertura && can(TRANSACAO_POR_ETAPA[etapaAbertura]);
  const podeReenviar = !!etapaAbertura && can("pagamento_solicitar");

  const formularioAjusteValido =
    ajusteMotivo.trim().length > 0 &&
    ajusteDescricao.trim().length > 0 &&
    ajusteTransacao.length > 0 &&
    !!ajusteTipo;

  const dialogEhFormularioRico =
    acaoSelecionada === "ajuste/solicitar" || acaoSelecionada === "ajuste/adicional";
  const dialogEhJustificativa =
    ["gestor/rejeitar", "autoridade/indeferir", "cancelar"].includes(acaoSelecionada ?? "");

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

          {/* Pendências de ajuste (F2) */}
          <SectionCard title="Pendências de ajuste" icon={FileEdit}>
            {pedidosQ.isLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : pedidos.length === 0 ? (
              <p className="text-sm text-foreground-subtle">Nenhum pedido de ajuste nesta solicitação.</p>
            ) : (
              <div className="space-y-4">
                {pedidos.map((p) => {
                  const situacaoRotulo = PEDIDO_AJUSTE_ROTULO[p.situacao];
                  const podeResponder = p.situacao === "ABERTO" && can(p.transacao_responsavel);
                  const podeCancelar =
                    p.situacao === "ABERTO" && can(TRANSACAO_POR_ETAPA[p.etapa_solicitante]);
                  return (
                    <div key={p.id} className="rounded-lg border border-border p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Badge intent={situacaoRotulo.intent} icon={situacaoRotulo.icon}>
                          {situacaoRotulo.label}
                        </Badge>
                        <span className="text-xs text-foreground-muted">
                          {fmtDataHora(p.criado_em)}
                        </span>
                      </div>
                      <div className="mt-2 text-sm font-medium text-foreground">{p.motivo}</div>
                      <p className="mt-1 text-sm text-foreground-muted">{p.descricao}</p>
                      <div className="mt-2 grid grid-cols-1 gap-2 text-xs text-foreground-muted sm:grid-cols-3">
                        <div>
                          Responsável:{" "}
                          <span className="text-foreground">
                            {TRANSACAO_PAGAMENTOS_ROTULO[p.transacao_responsavel] ?? p.transacao_responsavel}
                          </span>
                        </div>
                        <div>
                          Tipo:{" "}
                          <span className="text-foreground">
                            {p.tipo === "MATERIAL" ? "Alteração material" : "Não material"}
                          </span>
                        </div>
                        {p.prazo && (
                          <div>
                            Prazo: <span className="text-foreground">{fmtData(p.prazo)}</span>
                          </div>
                        )}
                      </div>
                      {p.resposta && (
                        <div className="mt-2 rounded-md bg-muted p-2 text-sm text-foreground">
                          <span className="font-medium">Resposta: </span>
                          {p.resposta}
                        </div>
                      )}
                      {podeResponder && (
                        <div className="mt-3 space-y-2">
                          <Textarea
                            value={respostaPorPedido[p.id] ?? ""}
                            onChange={(e) =>
                              setRespostaPorPedido((r) => ({ ...r, [p.id]: e.target.value }))
                            }
                            placeholder="Escreva a resposta ao pedido de ajuste..."
                            className="min-h-20"
                          />
                          <Button
                            size="sm"
                            onClick={() =>
                              responderPedidoM.mutate({
                                pedidoId: p.id,
                                resposta: respostaPorPedido[p.id] ?? "",
                              })
                            }
                            disabled={
                              !(respostaPorPedido[p.id] ?? "").trim() || responderPedidoM.isPending
                            }
                          >
                            Responder pedido
                          </Button>
                        </div>
                      )}
                      {podeCancelar && (
                        <div className="mt-2">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => cancelarPedidoM.mutate(p.id)}
                            disabled={cancelarPedidoM.isPending}
                          >
                            Cancelar pedido
                          </Button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {(podeAdicionarPedido || podeReenviar) && (
              <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-3">
                {podeAdicionarPedido && (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      resetFormAjuste();
                      setAcaoSelecionada("ajuste/adicional");
                      setOpenDialog(true);
                    }}
                  >
                    Novo pedido de ajuste
                  </Button>
                )}
                {podeReenviar && (
                  <Button
                    onClick={() => responderAjusteM.mutate()}
                    disabled={pedidosAbertos.length > 0 || responderAjusteM.isPending}
                    title={
                      pedidosAbertos.length > 0
                        ? "Ainda há pedido de ajuste em aberto — responda todos antes de reenviar."
                        : undefined
                    }
                  >
                    Reenviar para análise
                  </Button>
                )}
              </div>
            )}
          </SectionCard>

          {/* Documentos (F2, Task 8) */}
          <SectionCard title="Documentos" icon={Paperclip}>
            <div className="space-y-4">
              {can("pagamento_solicitar") && (
                <div className="space-y-3 rounded-lg border border-border p-3">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <FormField label="Arquivo">
                      <input
                        type="file"
                        onChange={(e) => setAnexoArquivo(e.target.files?.[0] ?? null)}
                        className="block w-full text-sm text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-muted file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-foreground hover:file:bg-muted/80"
                      />
                    </FormField>
                    <FormField label="Descrição" hint="Opcional">
                      <Input
                        value={anexoDescricao}
                        onChange={(e) => setAnexoDescricao(e.target.value)}
                        placeholder="ex.: Nota fiscal corrigida"
                      />
                    </FormField>
                  </div>
                  {pedidosRespondiveisPorMim.length > 0 && (
                    <FormField label="Vincular a pedido de ajuste" hint="Opcional — resposta a um pedido aberto">
                      <Select
                        value={anexoPedidoSelecionado === "" ? "" : String(anexoPedidoSelecionado)}
                        onChange={(e) =>
                          setAnexoPedidoId(e.target.value ? Number(e.target.value) : "")
                        }
                      >
                        <option value="">Nenhum</option>
                        {pedidosRespondiveisPorMim.map((p) => (
                          <option key={p.id} value={p.id}>
                            #{p.id} — {p.motivo}
                          </option>
                        ))}
                      </Select>
                    </FormField>
                  )}
                  <Button
                    size="sm"
                    onClick={() => uploadAnexoM.mutate()}
                    disabled={!anexoArquivo || uploadAnexoM.isPending}
                  >
                    Enviar documento
                  </Button>
                </div>
              )}

              {anexosQ.isLoading ? (
                <Skeleton className="h-16 w-full" />
              ) : anexos.length === 0 ? (
                <p className="text-sm text-foreground-subtle">Nenhum documento anexado.</p>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <THead>
                      <TR>
                        <TH>Nome</TH>
                        <TH>Tamanho</TH>
                        <TH>Quem</TH>
                        <TH>Quando</TH>
                        <TH>Versão</TH>
                        <TH className="text-right">Ações</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {anexos.map((a) => (
                        <TR key={a.id}>
                          <TD>{a.nome ?? `Anexo #${a.id_anexo}`}</TD>
                          <TD>{fmtTamanho(a.tamanho)}</TD>
                          <TD>{a.id_usuario ? `Usuário #${a.id_usuario}` : "—"}</TD>
                          <TD>{fmtDataHora(a.criado_em)}</TD>
                          <TD>{a.versao_debito}</TD>
                          <TD className="text-right">
                            <div className="flex justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                asChild
                              >
                                <a
                                  href={api.pagamentos.debitos.anexoDownloadUrl(a.id)}
                                  target="_blank"
                                  rel="noreferrer"
                                  aria-label={`Baixar ${a.nome ?? `anexo #${a.id_anexo}`}`}
                                >
                                  <Download className="h-4 w-4" />
                                </a>
                              </Button>
                              {can("pagamento_solicitar") && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  aria-label={`Remover ${a.nome ?? `anexo #${a.id_anexo}`}`}
                                  onClick={() => setConfirmRemoverAnexo(a)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              )}
                            </div>
                          </TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                </div>
              )}
            </div>
          </SectionCard>

          {/* Versões (F2) — só quando o débito já sofreu alteração material */}
          {debito.versao > 1 && (
            <SectionCard title="Versões anteriores" icon={Layers}>
              {versoesQ.isLoading ? (
                <Skeleton className="h-16 w-full" />
              ) : (versoesQ.data ?? []).length === 0 ? (
                <p className="text-sm text-foreground-subtle">Nenhuma versão congelada registrada.</p>
              ) : (
                <div className="space-y-3">
                  {(versoesQ.data ?? []).map((v) => (
                    <div key={v.id} className="rounded-lg border border-border p-3 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Badge intent="neutral">Versão {v.versao}</Badge>
                        <span className="text-xs text-foreground-muted">{fmtDataHora(v.criado_em)}</span>
                      </div>
                      <div className="mt-1 text-foreground-muted">{v.motivo}</div>
                      <dl className="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-2">
                        {Object.entries(v.dados).map(([campo, valor]) => (
                          <div key={campo} className="flex justify-between gap-2 text-xs">
                            <dt className="text-foreground-muted">{campo.replace(/_/g, " ")}</dt>
                            <dd className="font-medium text-foreground">{String(valor ?? "—")}</dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
          )}

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
              resetFormAjuste();
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

      {/* Dialog para ações */}
      <Dialog
        open={openDialog}
        onClose={() => setOpenDialog(false)}
        size={dialogEhFormularioRico ? "lg" : "md"}
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
                        : acaoSelecionada === "ajuste/adicional"
                          ? "Novo pedido de ajuste"
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
                if (acaoSelecionada === "ajuste/adicional") criarPedidoAjusteM.mutate();
                if (acaoSelecionada === "ajuste/responder") responderAjusteM.mutate();
                if (acaoSelecionada === "cancelar") cancelarM.mutate();
              }}
              disabled={
                (dialogEhJustificativa && !justificativa.trim()) ||
                (dialogEhFormularioRico && !formularioAjusteValido)
              }
            >
              Confirmar
            </Button>
          </>
        }
      >
        {dialogEhJustificativa && (
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

        {dialogEhFormularioRico && (
          <div className="space-y-4">
            <FormField label="Motivo" required>
              <Input
                value={ajusteMotivo}
                onChange={(e) => setAjusteMotivo(e.target.value)}
                placeholder="Resumo curto do que precisa ser ajustado"
                maxLength={255}
              />
            </FormField>
            <FormField label="Descrição" required>
              <Textarea
                value={ajusteDescricao}
                onChange={(e) => setAjusteDescricao(e.target.value)}
                placeholder="Detalhe o que precisa ser corrigido..."
                className="min-h-24"
              />
            </FormField>
            <FormField label="Transação responsável" required>
              <Select
                value={ajusteTransacao}
                onChange={(e) => setAjusteTransacao(e.target.value)}
              >
                <option value="">Selecione…</option>
                {TRANSACAO_PAGAMENTOS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </FormField>
            <div className="space-y-1">
              <Label required>Tipo</Label>
              <div className="flex gap-4 text-sm">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="ajuste-tipo"
                    value="NAO_MATERIAL"
                    checked={ajusteTipo === "NAO_MATERIAL"}
                    onChange={() => setAjusteTipo("NAO_MATERIAL")}
                  />
                  Não material
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="ajuste-tipo"
                    value="MATERIAL"
                    checked={ajusteTipo === "MATERIAL"}
                    onChange={() => setAjusteTipo("MATERIAL")}
                  />
                  Alteração material
                </label>
              </div>
              {ajusteTipo === "MATERIAL" && (
                <p className="text-xs text-foreground-muted">
                  Alteração material invalida aprovações já dadas e volta o débito ao gestor.
                </p>
              )}
            </div>
            <FormField label="Prazo" hint="Opcional">
              <Input
                type="date"
                value={ajustePrazo}
                onChange={(e) => setAjustePrazo(e.target.value)}
              />
            </FormField>
            <FormField label="Campos relacionados" hint="Opcional — separe por vírgula">
              <Input
                value={ajusteCampos}
                onChange={(e) => setAjusteCampos(e.target.value)}
                placeholder="ex.: valor_total, numero_nf"
              />
            </FormField>
          </div>
        )}
      </Dialog>

      {/* Remoção de documento — resumo de impacto, não "tem certeza?" (F2, Task 8) */}
      <Dialog
        open={!!confirmRemoverAnexo}
        onClose={() => setConfirmRemoverAnexo(null)}
        size="sm"
        title="Remover documento"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmRemoverAnexo(null)}>
              Cancelar
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                if (confirmRemoverAnexo) removerAnexoM.mutate(confirmRemoverAnexo.id);
              }}
              disabled={removerAnexoM.isPending}
            >
              Remover documento
            </Button>
          </>
        }
      >
        {confirmRemoverAnexo && (
          <p className="text-sm text-foreground">
            <strong>{confirmRemoverAnexo.nome ?? `Anexo #${confirmRemoverAnexo.id_anexo}`}</strong>{" "}
            será removido desta solicitação e deixará de aparecer na lista de documentos e no
            download — inclusive para quem está aguardando essa resposta a um pedido de ajuste.
            Esta ação não pode ser desfeita pela tela.
          </p>
        )}
      </Dialog>
    </div>
  );
}
