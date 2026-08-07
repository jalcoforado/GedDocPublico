"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, type DebitoOut, type SituacaoTramitacao } from "@/lib/api";
import { SITUACAO_TRAMITACAO_CONFIG, ETAPAS_FLUXO, getEtapaIndex, aguardandoDecisao } from "@/components/pagamentos/statusFluxo";
import { fmtData, fmtMoeda } from "@/components/pagamentos/format";

function StatusBadge({ situacao }: { situacao: SituacaoTramitacao }) {
  const cfg = SITUACAO_TRAMITACAO_CONFIG[situacao];
  return <Badge intent={cfg.intent}>{cfg.label}</Badge>;
}

function Stepper({ etapaAtual }: { etapaAtual: number }) {
  return (
    <div className="flex items-center justify-between">
      {ETAPAS_FLUXO.map((e, idx) => (
        <div key={idx} className="flex items-center flex-1">
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${
              idx <= etapaAtual
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {idx + 1}
          </div>
          <div className="text-xs font-medium text-muted-foreground ml-2 flex-1 max-w-24">
            {e.label}
          </div>
          {idx < ETAPAS_FLUXO.length - 1 && (
            <div
              className={`h-1 flex-1 mx-1 ${
                idx < etapaAtual ? "bg-primary" : "bg-muted"
              }`}
            />
          )}
        </div>
      ))}
    </div>
  );
}

export default function DetalheDebitosPage({ params }: { params: { id: string } }) {
  const qc = useQueryClient();
  const toast = useToast();
  const router = useRouter();
  const id = parseInt(params.id);

  const [openDialog, setOpenDialog] = useState(false);
  const [justificativa, setJustificativa] = useState("");
  const [acaoSelecionada, setAcaoSelecionada] = useState<string | null>(null);

  // Carregar débito
  const debitoQ = useQuery({
    queryKey: ["pag-debito", id],
    queryFn: () => api.pagamentos.debitos.get(id),
  });

  const debito = debitoQ.data as DebitoOut | undefined;
  const etapaAtual = debito ? getEtapaIndex(debito.situacao_tramitacao) : 0;
  const aguardaDecisao = debito && aguardandoDecisao(debito.situacao_tramitacao);

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

  if (debitoQ.isLoading) {
    return <div className="py-8 text-center">Carregando...</div>;
  }

  if (!debito) {
    return <div className="py-8 text-center text-danger">Solicitação não encontrada</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Solicitação #{debito.id}</h1>
          <p className="text-sm text-muted-foreground">{debito.nome_fornecedor}</p>
        </div>
        <StatusBadge situacao={debito.situacao_tramitacao} />
      </div>

      {/* Stepper */}
      <div className="p-4 bg-surface-1 rounded border">
        <Stepper etapaAtual={etapaAtual} />
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Coluna principal */}
        <div className="col-span-2 space-y-4">
          {/* Informações gerais */}
          <div className="p-4 bg-surface-1 border rounded">
            <h2 className="font-semibold mb-3">Informações</h2>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="font-medium text-muted-foreground">Fornecedor</div>
                <div>{debito.nome_fornecedor}</div>
              </div>
              <div>
                <div className="font-medium text-muted-foreground">Valor Total</div>
                <div>{fmtMoeda(debito.valor_total)}</div>
              </div>
              <div>
                <div className="font-medium text-muted-foreground">Descrição</div>
                <div className="col-span-1">{debito.descricao}</div>
              </div>
              <div>
                <div className="font-medium text-muted-foreground">Competência</div>
                <div>{debito.competencia}</div>
              </div>
              <div>
                <div className="font-medium text-muted-foreground">NE</div>
                <div className="font-mono">{debito.numero_ne || "-"}</div>
              </div>
              <div>
                <div className="font-medium text-muted-foreground">NF</div>
                <div className="font-mono">{debito.numero_nf || "-"}</div>
              </div>
            </div>
          </div>

          {/* Parcelas */}
          <div className="p-4 bg-surface-1 border rounded">
            <h2 className="font-semibold mb-3">Parcelas</h2>
            <div className="overflow-x-auto">
              <Table>
                <THead>
                  <TR>
                    <TH>Número</TH>
                    <TH>Valor</TH>
                    <TH>Vencimento</TH>
                    <TH>Status</TH>
                  </TR>
                </THead>
                <TBody>
                  {debitoQ.data?.parcelas?.map((p) => (
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
          </div>

          {/* Histórico */}
          <div className="p-4 bg-surface-1 border rounded">
            <h2 className="font-semibold mb-3">Histórico</h2>
            <div className="space-y-2">
              {debitoQ.data?.historico?.map((h) => (
                <div key={h.id} className="text-sm border-l-2 border-muted pl-3 py-2">
                  <div className="font-medium">{h.acao}</div>
                  <div className="text-xs text-muted-foreground">
                    {h.nome_usuario} · {fmtData(h.criado_em)}
                  </div>
                  {h.justificativa && (
                    <div className="text-xs mt-1 italic">{h.justificativa}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Coluna lateral — ações */}
        <div className="space-y-3">
          {debito.situacao_tramitacao === "RASCUNHO" && (
            <Button
              onClick={() => {
                setAcaoSelecionada("enviar");
                setOpenDialog(true);
              }}
              className="w-full"
            >
              Enviar para Gestor
            </Button>
          )}

          {debito.situacao_tramitacao === "AGUARDANDO_GESTOR" && (
            <>
              <Button
                onClick={() => {
                  setAcaoSelecionada("gestor-autorizar");
                  setOpenDialog(true);
                }}
                className="w-full"
              >
                Autorizar
              </Button>
              <Button
                onClick={() => {
                  setAcaoSelecionada("gestor-rejeitar");
                  setOpenDialog(true);
                }}
                className="w-full"
                variant="secondary"
              >
                Rejeitar
              </Button>
            </>
          )}

          {debito.situacao_tramitacao === "AGUARDANDO_VALIDACAO" && (
            <>
              <Button
                onClick={() => {
                  setAcaoSelecionada("validar");
                  setOpenDialog(true);
                }}
                className="w-full"
              >
                Validar
              </Button>
            </>
          )}

          {debito.situacao_tramitacao === "AGUARDANDO_AUTORIDADE" && (
            <>
              <Button
                onClick={() => {
                  setAcaoSelecionada("autoridade-aprovar");
                  setOpenDialog(true);
                }}
                className="w-full"
              >
                Aprovar
              </Button>
              <Button
                onClick={() => {
                  setAcaoSelecionada("autoridade-indeferir");
                  setOpenDialog(true);
                }}
                className="w-full"
                variant="secondary"
              >
                Indeferir
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Dialog para ações com justificativa */}
      <Dialog
        open={openDialog}
        onClose={() => setOpenDialog(false)}
        title={
          acaoSelecionada === "enviar"
            ? "Enviar para Gestor"
            : acaoSelecionada === "gestor-autorizar"
              ? "Autorizar"
              : acaoSelecionada === "gestor-rejeitar"
                ? "Rejeitar"
                : acaoSelecionada === "validar"
                  ? "Validar"
                  : acaoSelecionada === "autoridade-aprovar"
                    ? "Aprovar"
                    : "Indeferir"
        }
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpenDialog(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => {
                if (acaoSelecionada === "enviar") enviarGestorM.mutate();
                if (acaoSelecionada === "gestor-autorizar") gestorAutorizarM.mutate();
                if (acaoSelecionada === "gestor-rejeitar") gestorRejeitarM.mutate();
                if (acaoSelecionada === "validar") validarM.mutate();
                if (acaoSelecionada === "autoridade-aprovar") autoridadeAprovarM.mutate();
                if (acaoSelecionada === "autoridade-indeferir") autoridadeIndeferirM.mutate();
              }}
            >
              Confirmar
            </Button>
          </>
        }
      >
        {["gestor-rejeitar", "autoridade-indeferir"].includes(acaoSelecionada ?? "") && (
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
