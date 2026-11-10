"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Clock, PenLine, XCircle } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { ValidacaoPublicaCard } from "@/components/ValidacaoPublicaCard";
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
        <div className="text-sm text-foreground-muted">
          {listQ.data?.length ?? 0} solicitação(ões)
        </div>
        <Button onClick={() => setOpenSolic(true)} disabled={!podeSolicitar}>
          Solicitar assinatura
        </Button>
      </div>

      {listQ.isLoading && <Carregando className="text-sm text-muted-foreground" />}

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
        <EmptyState
          icon={PenLine}
          title="Sem solicitações de assinatura"
          description="Peça a assinatura de um anexo com “Solicitar assinatura”."
          className="p-6"
        />
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
                      <ValidacaoPublicaCard aaId={ax.id} />
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

  // Erro sob o grupo só depois de tentar enviar; o botão não fica cinza.
  const [tentou, setTentou] = useState(false);
  const [filtro, setFiltro] = useState("");
  const faltaAnexo = idsAnexos.length === 0;
  const faltaAssinante = idsAssinantes.length === 0;

  // Até 100 servidores numa lista: o filtro poupa a rolagem.
  const termo = filtro.trim().toLowerCase();
  const usuariosVisiveis = (usuariosQ.data?.items ?? []).filter(
    (u) =>
      !termo ||
      u.nome.toLowerCase().includes(termo) ||
      (u.email ?? "").toLowerCase().includes(termo) ||
      idsAssinantes.includes(u.id),
  );

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setTentou(true);
    if (faltaAnexo || faltaAssinante) return;
    m.mutate();
  }

  function fechar() {
    reset();
    setTentou(false);
    setFiltro("");
    onClose();
  }

  const grupo = "max-h-48 overflow-y-auto rounded-md border border-border p-2";
  const erroGrupo = "mt-1.5 flex items-start gap-1 text-xs font-medium text-danger-soft-foreground";

  return (
    <Dialog
      open={open}
      onClose={fechar}
      title="Solicitar assinatura"
      description="Cada assinante precisa assinar todos os anexos marcados."
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={fechar}>
            Cancelar
          </Button>
          <Button onClick={submit} loading={m.isPending}>
            {m.isPending ? "Enviando…" : "Solicitar assinatura"}
          </Button>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="space-y-5">
        <fieldset>
          <legend className="mb-1 flex w-full items-baseline justify-between text-sm font-medium text-foreground">
            <span>
              Anexos a assinar
              <span className="ml-0.5 text-danger" aria-hidden="true">
                *
              </span>
            </span>
            {idsAnexos.length > 0 && (
              <span className="text-xs font-normal tabular-nums text-foreground-muted">
                {idsAnexos.length} marcado{idsAnexos.length === 1 ? "" : "s"}
              </span>
            )}
          </legend>
          {anexosCandidatos.length === 0 ? (
            <p className="text-xs text-foreground-muted">
              Este processo não tem anexos para assinar.
            </p>
          ) : (
            <div className={grupo}>
              {anexosCandidatos.map((a) => (
                <label
                  key={a.id}
                  className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-surface-2"
                >
                  <Checkbox
                    checked={idsAnexos.includes(a.id)}
                    onChange={() => setIdsAnexos((s) => toggle(s, a.id))}
                    className="h-4 w-4"
                  />
                  <span className="text-foreground">
                    {a.descricao ?? `Anexo ${a.id}`}
                    <span className="ml-1 text-foreground-muted">({a.e_doc})</span>
                  </span>
                </label>
              ))}
            </div>
          )}
          {tentou && faltaAnexo && (
            <p className={erroGrupo}>
              <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              Marque pelo menos um anexo.
            </p>
          )}
        </fieldset>

        <fieldset>
          <legend className="mb-1 flex w-full items-baseline justify-between text-sm font-medium text-foreground">
            <span>
              Assinantes
              <span className="ml-0.5 text-danger" aria-hidden="true">
                *
              </span>
            </span>
            {idsAssinantes.length > 0 && (
              <span className="text-xs font-normal tabular-nums text-foreground-muted">
                {idsAssinantes.length} marcado{idsAssinantes.length === 1 ? "" : "s"}
              </span>
            )}
          </legend>
          <Input
            type="search"
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
            placeholder="Filtrar por nome ou e-mail…"
            aria-label="Filtrar assinantes"
            className="mb-2"
          />
          <div className={grupo}>
            {usuariosVisiveis.length === 0 ? (
              <p className="px-1 py-1 text-xs text-foreground-muted">
                Ninguém com esse nome ou e-mail.
              </p>
            ) : (
              usuariosVisiveis.map((u) => (
                <label
                  key={u.id}
                  className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-surface-2"
                >
                  <Checkbox
                    checked={idsAssinantes.includes(u.id)}
                    onChange={() => setIdsAssinantes((s) => toggle(s, u.id))}
                    className="h-4 w-4"
                  />
                  <span className="text-foreground">
                    {u.nome} <span className="text-foreground-muted">· {u.email}</span>
                  </span>
                </label>
              ))
            )}
          </div>
          {tentou && faltaAssinante && (
            <p className={erroGrupo}>
              <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              Marque pelo menos um assinante.
            </p>
          )}
        </fieldset>

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
