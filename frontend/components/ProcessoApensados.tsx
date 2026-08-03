"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronRight,
  Files,
  Loader2,
  Paperclip,
  Plus,
  ScrollText,
  X,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import {
  api,
  apensamentoApi,
  termoApensamentoPdfUrl,
  type ApensamentoDetail,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

function fmtDateTime(s: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface Props {
  processoId: number;
  numeroProcesso: string;
  /** id_processo_pai vindo do detail (null se não está apensado) */
  idProcessoPai: number | null;
}

export function ProcessoApensados({ processoId, numeroProcesso, idProcessoPai }: Props) {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const { can } = useAuth();
  const canMutate = can("processo", "atualizar");

  const [openApensar, setOpenApensar] = useState(false);

  const apensadosQ = useQuery({
    queryKey: ["apensados", processoId],
    queryFn: () => apensamentoApi.listarApensados(processoId),
  });
  const historicoQ = useQuery({
    queryKey: ["apensamentos-historico", processoId],
    queryFn: () => apensamentoApi.listarHistorico(processoId, false),
  });

  const desapensarM = useMutation({
    mutationFn: ({ id, motivo }: { id: number; motivo: string }) =>
      apensamentoApi.desapensar(id, motivo),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["apensados", processoId] });
      qc.invalidateQueries({ queryKey: ["apensamentos-historico", processoId] });
      qc.invalidateQueries({ queryKey: ["processo", processoId] });
      toast.success("Processo desapensado.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function onDesapensarSelf() {
    const ok = await confirm({
      title: "Desapensar este processo",
      message: `${numeroProcesso} deixará de tramitar junto ao processo principal. O termo de desapensamento será gerado para registro formal.`,
      confirmLabel: "Desapensar",
      intent: "danger",
    });
    if (!ok) return;
    // Pega motivo via prompt simples
    const motivo = window.prompt("Motivo do desapensamento (mínimo 3 caracteres):");
    if (!motivo || motivo.trim().length < 3) {
      toast.error("Motivo obrigatório (≥3 chars).");
      return;
    }
    desapensarM.mutate({ id: processoId, motivo: motivo.trim() });
  }

  async function onDesapensarFilho(idFilho: number, numero: string) {
    const ok = await confirm({
      title: `Desapensar ${numero}`,
      message: `O processo ${numero} deixará de ser apensado a ${numeroProcesso}.`,
      confirmLabel: "Desapensar",
      intent: "danger",
    });
    if (!ok) return;
    const motivo = window.prompt("Motivo do desapensamento (mínimo 3 caracteres):");
    if (!motivo || motivo.trim().length < 3) {
      toast.error("Motivo obrigatório (≥3 chars).");
      return;
    }
    desapensarM.mutate({ id: idFilho, motivo: motivo.trim() });
  }

  const apensados = apensadosQ.data ?? [];
  const historico = historicoQ.data ?? [];
  const historicoEncerrado = historico.filter((h) => !h.ativo);
  const apensamentoAtivoComoPai = idProcessoPai != null;

  return (
    <section className="rounded-xl border border-border bg-card shadow-xs">
      <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div className="flex items-start gap-3">
          <span
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand/8 text-brand"
            aria-hidden="true"
          >
            <Files className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold tracking-tight">
              Apensados
            </h2>
            <p className="mt-0.5 text-xs text-foreground-muted">
              Processos vinculados a este para tramitarem juntos.
            </p>
          </div>
        </div>
        {canMutate && !apensamentoAtivoComoPai && (
          <Button size="sm" variant="secondary" onClick={() => setOpenApensar(true)}>
            <Plus className="mr-1 h-4 w-4" aria-hidden="true" />
            Apensar outro
          </Button>
        )}
      </header>

      <div className="p-5">
        {apensamentoAtivoComoPai && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-warning/30 bg-warning-soft/30 px-3 py-2 text-xs">
            <div>
              Este processo está <strong>apensado</strong> ao processo{" "}
              <Link
                href={`/m/protocolo/processos/${idProcessoPai}`}
                className="font-mono font-semibold underline-offset-2 hover:underline"
              >
                #{idProcessoPai}
              </Link>
              . Tramita junto com ele.
            </div>
            {canMutate && (
              <Button
                size="sm"
                variant="secondary"
                onClick={onDesapensarSelf}
                disabled={desapensarM.isPending}
              >
                Desapensar
              </Button>
            )}
          </div>
        )}

        {apensadosQ.isLoading && (
          <p className="text-sm text-foreground-muted">
            <Loader2 className="mr-1 inline h-4 w-4 animate-spin" /> Carregando…
          </p>
        )}

        {!apensadosQ.isLoading && apensados.length === 0 && !apensamentoAtivoComoPai && (
          <p className="text-sm text-foreground-muted">
            Nenhum processo apensado.
          </p>
        )}

        {apensados.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
              Processos apensados a este ({apensados.length})
            </p>
            {/* Tree visual com linhas de conexão verticais + ramo horizontal */}
            <ol className="relative space-y-2 pl-8">
              {/* Linha vertical do "tronco" */}
              <span
                aria-hidden="true"
                className="absolute left-3 top-0 bottom-2 w-px bg-border"
              />
              {apensados.map((a, idx) => {
                const isLast = idx === apensados.length - 1;
                return (
                  <li
                    key={a.id_apensamento}
                    className="relative rounded-lg border border-border bg-surface-1 px-3 py-2.5 transition-colors hover:bg-surface-2"
                  >
                    {/* Ramo horizontal saindo da linha vertical para o card */}
                    <span
                      aria-hidden="true"
                      className="absolute -left-5 top-5 h-px w-5 bg-border"
                    />
                    {/* Nó (círculo) no encontro do ramo com a linha vertical */}
                    <span
                      aria-hidden="true"
                      className="absolute -left-[1.4rem] top-[1.05rem] h-1.5 w-1.5 rounded-full bg-brand"
                    />
                    {/* Esconde o trecho final da linha vertical se for o último item */}
                    {isLast && (
                      <span
                        aria-hidden="true"
                        className="absolute -left-5 top-5 -ml-0.5 h-full w-0.5 bg-card"
                      />
                    )}

                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <Link
                          href={`/m/protocolo/processos/${a.id_processo}`}
                          className="font-mono text-sm font-semibold text-primary hover:underline"
                        >
                          {a.nup ?? a.numero_processo}
                        </Link>
                        {a.nup && (
                          <span className="ml-2 font-mono text-[10px] text-foreground-muted">
                            (legado: {a.numero_processo})
                          </span>
                        )}
                        <p className="mt-0.5 text-xs text-foreground-muted">
                          {a.manifestante ?? "—"}
                        </p>
                        <p className="mt-1 text-xs italic text-foreground-muted">
                          {a.motivo}
                        </p>
                        <p className="mt-0.5 text-[10px] text-foreground-subtle">
                          Apensado em {fmtDateTime(a.apensado_em)}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col gap-1.5">
                        <a
                          href={termoApensamentoPdfUrl(a.id_apensamento)}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <Button size="sm" variant="ghost">
                            <ScrollText className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                            Termo
                          </Button>
                        </a>
                        {canMutate && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => onDesapensarFilho(a.id_processo, a.numero_processo)}
                            disabled={desapensarM.isPending}
                            className="text-danger hover:bg-danger/5"
                          >
                            <X className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                            Desapensar
                          </Button>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        )}

        {historicoEncerrado.length > 0 && (
          <details className="mt-5 text-xs text-foreground-muted">
            <summary className="cursor-pointer font-semibold uppercase tracking-wider text-foreground-subtle">
              Histórico de apensamentos encerrados ({historicoEncerrado.length})
            </summary>
            <ul className="mt-2 space-y-1.5">
              {historicoEncerrado.map((h) => (
                <HistoricoItem key={h.id} a={h} contextoProcessoId={processoId} />
              ))}
            </ul>
          </details>
        )}
      </div>

      {openApensar && (
        <ApensarDialog
          processoId={processoId}
          numeroProcesso={numeroProcesso}
          onClose={() => setOpenApensar(false)}
          onSuccess={() => {
            qc.invalidateQueries({ queryKey: ["apensados", processoId] });
            qc.invalidateQueries({ queryKey: ["processo", processoId] });
            qc.invalidateQueries({
              queryKey: ["apensamentos-historico", processoId],
            });
            setOpenApensar(false);
          }}
        />
      )}
    </section>
  );
}

function HistoricoItem({
  a,
  contextoProcessoId,
}: {
  a: ApensamentoDetail;
  contextoProcessoId: number;
}) {
  // Determina papel deste processo (filho ou pai) no apensamento
  const ehFilho = a.id_processo_apensado === contextoProcessoId;
  const outroId = ehFilho ? a.id_processo_principal : a.id_processo_apensado;
  const outroNum = ehFilho ? a.numero_processo_principal : a.numero_processo_apensado;
  const rotulo = ehFilho ? "Foi apensado a" : "Recebeu apensamento de";

  return (
    <li className="rounded border border-border bg-surface-1 px-2 py-1.5">
      <div className="flex items-center gap-1 text-foreground-muted">
        <span>{rotulo}</span>
        <Link
          href={`/m/protocolo/processos/${outroId}`}
          className="font-mono text-primary hover:underline"
        >
          {outroNum ?? `#${outroId}`}
        </Link>
        <ChevronRight className="h-3 w-3" aria-hidden="true" />
        <a
          href={termoApensamentoPdfUrl(a.id)}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:underline"
        >
          termo
        </a>
      </div>
      <p className="text-[10px] text-foreground-subtle">
        {fmtDateTime(a.criado_em)} → desapensado {fmtDateTime(a.desapensado_em)}
        {a.motivo_desapensamento && ` · "${a.motivo_desapensamento}"`}
      </p>
    </li>
  );
}

function ApensarDialog({
  processoId,
  numeroProcesso,
  onClose,
  onSuccess,
}: {
  processoId: number;
  numeroProcesso: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const toast = useToast();
  const [idPrincipal, setIdPrincipal] = useState<number | null>(null);
  const [motivo, setMotivo] = useState("");

  const processosQ = useQuery({
    queryKey: ["processos-todos-apensar"],
    queryFn: () => api.processos.list({ page_size: 200 }),
  });

  const opts = useMemo<ComboboxOption[]>(() => {
    return (processosQ.data?.items ?? [])
      .filter((p) => p.id !== processoId)
      .map((p) => ({
        value: p.id,
        label: p.nup ?? p.numero_processo,
        hint: p.manifestante ?? undefined,
      }));
  }, [processosQ.data, processoId]);

  const apensarM = useMutation({
    mutationFn: () => {
      if (idPrincipal == null || motivo.trim().length < 3) {
        return Promise.reject(
          new Error("Escolha o processo principal e informe motivo (≥3 chars)."),
        );
      }
      return apensamentoApi.apensar(processoId, {
        id_processo_principal: idPrincipal,
        motivo: motivo.trim(),
      });
    },
    onSuccess: () => {
      toast.success("Processo apensado.");
      onSuccess();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          apensarM.mutate();
        }}
        className="w-full max-w-lg space-y-3 rounded-xl border border-border bg-card p-5 shadow-xl animate-scale-in"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Apensar {numeroProcesso}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-foreground-muted hover:bg-surface-2"
            aria-label="Fechar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="text-xs text-foreground-muted">
          Este processo ({numeroProcesso}) passará a ser apensado (filho) do
          processo escolhido abaixo. Termo de apensamento é gerado automaticamente.
        </p>

        <div>
          <Label>Processo principal (pai) <span className="text-danger">*</span></Label>
          <Combobox
            options={opts}
            value={idPrincipal}
            onChange={(v) => setIdPrincipal(typeof v === "number" ? v : null)}
            placeholder="Buscar por número ou manifestante…"
            loading={processosQ.isLoading}
          />
        </div>

        <div>
          <Label htmlFor="motivo-apensar">
            Motivo <span className="text-danger">*</span>
          </Label>
          <Textarea
            id="motivo-apensar"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            rows={3}
            maxLength={1000}
            placeholder="Ex: documentos do mesmo objeto, mesmo manifestante, mesma licitação…"
          />
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            type="submit"
            disabled={
              idPrincipal == null || motivo.trim().length < 3 || apensarM.isPending
            }
          >
            {apensarM.isPending && (
              <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />
            )}
            <Paperclip className="mr-1 h-4 w-4" aria-hidden="true" />
            Apensar
          </Button>
        </div>
      </form>
    </div>
  );
}
