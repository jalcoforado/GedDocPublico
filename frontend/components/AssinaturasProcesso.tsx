"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import {
  api,
  assinaturaComprovanteUrl,
  type AssinanteStatus,
  type ProcessoDetail,
  type SolicitacaoAssinatura,
} from "@/lib/api";
import {
  statusAssinante,
  statusSolicitacao,
  validacaoMensagem,
} from "@/lib/assinatura";

function fmtDt(s: string | null | undefined) {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export function AssinaturasProcesso({ processo }: { processo: ProcessoDetail }) {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const [openSolic, setOpenSolic] = useState(false);
  const listQ = useQuery({
    queryKey: ["assinaturas-processo", processo.id],
    queryFn: () => api.assinaturas.listarDoProcesso(processo.id),
  });

  const cancelarM = useMutation({
    mutationFn: (solicId: number) => api.assinaturas.cancelar(solicId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assinaturas-processo", processo.id] });
      toast.success("Solicitação cancelada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const podeSolicitar =
    processo.ativo &&
    processo.anexos.length > 0 &&
    processo.movimentacoes.length > 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-600">
          {listQ.data?.length ?? 0} solicitação(ões)
        </div>
        <Button onClick={() => setOpenSolic(true)} disabled={!podeSolicitar}>
          Solicitar assinatura
        </Button>
      </div>

      {listQ.isLoading && <p className="text-sm text-gray-500">Carregando...</p>}

      {(listQ.data ?? []).map((s) => (
        <SolicitacaoCard
          key={s.id}
          solic={s}
          onCancelar={async (id) => {
            const ok = await confirm({
              title: "Cancelar solicitação de assinatura",
              message:
                "A solicitação será marcada como cancelada e fica registrada no histórico. Continuar?",
              confirmLabel: "Cancelar solicitação",
              cancelLabel: "Voltar",
              intent: "danger",
            });
            if (ok) cancelarM.mutate(id);
          }}
        />
      ))}

      {listQ.data && listQ.data.length === 0 && (
        <p className="text-sm text-gray-500">Sem solicitações de assinatura.</p>
      )}

      <SolicitarDialog
        open={openSolic}
        onClose={() => setOpenSolic(false)}
        processo={processo}
        onDone={() =>
          qc.invalidateQueries({ queryKey: ["assinaturas-processo", processo.id] })
        }
      />
    </div>
  );
}

const INTENT_ICON = {
  success: CheckCircle2,
  danger: XCircle,
  warning: Clock,
} as const;

function statusBadge(s: SolicitacaoAssinatura) {
  const { label, intent } = statusSolicitacao(s);
  return <Badge intent={intent} icon={INTENT_ICON[intent]}>{label}</Badge>;
}

function assinanteBadge(a: AssinanteStatus) {
  const { label, intent } = statusAssinante(a);
  return <Badge intent={intent} icon={INTENT_ICON[intent]}>{label}</Badge>;
}

export function ValidarAcao({ aaId }: { aaId: number }) {
  const toast = useToast();
  const [res, setRes] = useState<{ texto: string; ok: boolean | null } | null>(null);
  const m = useMutation({
    mutationFn: () => api.assinaturas.validar(aaId),
    onSuccess: (v) => {
      const msg = validacaoMensagem(v);
      setRes(msg);
      if (msg.ok === true) toast.success(msg.texto);
      else if (msg.ok === false) toast.error(msg.texto);
    },
    onError: (e: Error) => toast.error(e.message),
  });
  return (
    <span className="ml-2 inline-flex flex-wrap items-center gap-2 text-xs">
      <button
        type="button"
        onClick={() => m.mutate()}
        disabled={m.isPending}
        className="text-primary hover:underline disabled:opacity-50"
      >
        {m.isPending ? "Validando..." : "Validar"}
      </button>
      <a
        href={assinaturaComprovanteUrl(aaId)}
        target="_blank"
        rel="noreferrer"
        className="text-primary hover:underline"
      >
        Comprovante
      </a>
      {res && (
        <span
          className={
            res.ok === false
              ? "text-danger-soft-foreground"
              : "text-muted-foreground"
          }
        >
          {res.texto}
        </span>
      )}
    </span>
  );
}

function SolicitacaoCard({
  solic,
  onCancelar,
}: {
  solic: SolicitacaoAssinatura;
  onCancelar: (id: number) => Promise<void> | void;
}) {
  return (
    <div className="rounded-md border border-border bg-card p-3 text-sm">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {statusBadge(solic)}
          <span className="text-xs text-muted-foreground">
            Solicitada em {fmtDt(solic.dt_inicio)} por {solic.nome_solicitante ?? "—"}
          </span>
        </div>
        {!solic.realizada && !solic.cancelada && (
          <Button
            variant="danger"
            size="sm"
            onClick={() => onCancelar(solic.id)}
          >
            Cancelar
          </Button>
        )}
      </div>
      <div className="space-y-2">
        {solic.assinantes.map((a) => (
          <div key={a.id_usuario_assinatura} className="rounded bg-muted p-2">
            <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
              <b className="text-foreground">{a.nome_assinante ?? `Usuário ${a.id_assinante}`}</b>
              {assinanteBadge(a)}
              <span className="text-muted-foreground">· ordem {a.ordem}</span>
              {a.status === "recusada" && a.motivo_recusa && (
                <span className="text-danger-soft-foreground">· motivo: {a.motivo_recusa}</span>
              )}
            </div>
            <ul className="ml-3 list-disc text-xs">
              {a.anexos.map((ax) => (
                <li
                  key={ax.id}
                  className={ax.assinado ? "text-success-soft-foreground" : "text-foreground"}
                >
                  {ax.anexo_descricao ?? `Anexo #${ax.id_anexo}`}
                  {ax.assinado && (
                    <>
                      <span className="ml-2 text-xs text-muted-foreground">
                        assinado em {fmtDt(ax.dt_assinatura)} · nível {ax.nivel}
                      </span>
                      <ValidarAcao aaId={ax.id} />
                    </>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function SolicitarDialog({
  open,
  onClose,
  processo,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  processo: ProcessoDetail;
  onDone: () => void;
}) {
  const usuariosQ = useQuery({
    queryKey: ["usuarios-page1"],
    queryFn: () => api.usuarios.list({ page_size: 100 }),
  });
  const [idsAssinantes, setIdsAssinantes] = useState<number[]>([]);
  const [idsAnexos, setIdsAnexos] = useState<number[]>([]);
  const [err, setErr] = useState<string | null>(null);

  // Anexos PDF ativos do processo
  const anexosCandidatos = processo.anexos.filter((a) => !!a.e_doc);

  const m = useMutation({
    mutationFn: () =>
      api.assinaturas.solicitar(processo.id, {
        id_assinantes: idsAssinantes,
        id_anexos: idsAnexos,
        id_tipo_assinatura: 1, // tipo "Interna"
      }),
    onSuccess: () => {
      onDone();
      reset();
      onClose();
    },
    onError: (e: Error) => setErr(e.message),
  });

  function reset() {
    setIdsAssinantes([]);
    setIdsAnexos([]);
    setErr(null);
  }

  function toggle<T>(set: T[], item: T): T[] {
    return set.includes(item) ? set.filter((x) => x !== item) : [...set, item];
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (idsAssinantes.length === 0) return setErr("Escolha pelo menos um assinante.");
    if (idsAnexos.length === 0) return setErr("Escolha pelo menos um anexo.");
    m.mutate();
  }

  return (
    <Dialog
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title="Solicitar assinatura"
      size="lg"
      footer={
        <>
          <Button
            variant="secondary"
            onClick={() => {
              reset();
              onClose();
            }}
          >
            Cancelar
          </Button>
          <Button onClick={submit} disabled={m.isPending}>
            {m.isPending ? "Enviando..." : "Solicitar"}
          </Button>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <div>
          <Label>Anexos a assinar</Label>
          {anexosCandidatos.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Este processo não tem anexos para assinar.
            </p>
          ) : (
            <div className="max-h-40 overflow-y-auto rounded-md border border-border p-2">
              {anexosCandidatos.map((a) => (
                <label
                  key={a.id}
                  className="flex items-center gap-2 py-1 text-sm"
                >
                  <Checkbox
                    checked={idsAnexos.includes(a.id)}
                    onChange={() => setIdsAnexos((s) => toggle(s, a.id))}
                  />
                  <span>
                    {a.descricao ?? `Anexo #${a.id}`}
                    <span className="ml-1 text-muted-foreground">({a.e_doc})</span>
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>

        <div>
          <Label>Destinatários (assinantes)</Label>
          <div className="max-h-48 overflow-y-auto rounded-md border border-border p-2">
            {usuariosQ.data?.items.map((u) => (
              <label key={u.id} className="flex items-center gap-2 py-1 text-sm">
                <Checkbox
                  checked={idsAssinantes.includes(u.id)}
                  onChange={() => setIdsAssinantes((s) => toggle(s, u.id))}
                />
                <span>
                  {u.nome} <span className="text-muted-foreground">· {u.email}</span>
                </span>
              </label>
            ))}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Cada destinatário precisará assinar TODOS os anexos selecionados.
          </p>
        </div>

        {err && (
          <div
            role="alert"
            className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
          >
            {err}
          </div>
        )}
      </form>
    </Dialog>
  );
}
