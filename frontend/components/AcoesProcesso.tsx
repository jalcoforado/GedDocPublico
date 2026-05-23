"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  api,
  type EncaminharInput,
  type ProcessoDetail,
} from "@/lib/api";

type ModalKind = null | "encaminhar" | "receber" | "cancelar";

export function AcoesProcesso({ processo }: { processo: ProcessoDetail }) {
  const qc = useQueryClient();
  const [modal, setModal] = useState<ModalKind>(null);
  const [err, setErr] = useState<string | null>(null);

  // Encaminhamento pendente: o último ativo, não recebido, não cancelado.
  const encaminhamentoPendente = useMemo(() => {
    const mov = processo.movimentacoes.find(
      (m) =>
        m.acao_flag === "ENCAMINHAMENTO" &&
        m.encaminhamento &&
        !m.encaminhamento.recebido &&
        !m.encaminhamento.cancelado
    );
    return mov?.encaminhamento ?? null;
  }, [processo.movimentacoes]);

  const podeEncaminhar = processo.ativo && !encaminhamentoPendente;
  const podeReceber = !!encaminhamentoPendente && processo.ativo;
  const podeCancelar = !!encaminhamentoPendente && processo.ativo;

  function invalidate() {
    qc.invalidateQueries({ queryKey: ["processo", processo.id] });
    qc.invalidateQueries({ queryKey: ["processos"] });
  }

  const receberM = useMutation({
    mutationFn: () => api.processos.receber(processo.id),
    onSuccess: () => {
      invalidate();
      setModal(null);
    },
    onError: (e: Error) => setErr(e.message),
  });

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          onClick={() => {
            setErr(null);
            setModal("encaminhar");
          }}
          disabled={!podeEncaminhar}
        >
          Encaminhar
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            setErr(null);
            setModal("receber");
          }}
          disabled={!podeReceber}
        >
          Receber
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            setErr(null);
            setModal("cancelar");
          }}
          disabled={!podeCancelar}
        >
          Cancelar encaminhamento
        </Button>

        {encaminhamentoPendente && (
          <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-warning-soft px-2 py-0.5 text-xs font-semibold text-warning-soft-foreground">
            Aguardando recebimento
          </span>
        )}
      </div>

      <EncaminharDialog
        open={modal === "encaminhar"}
        onClose={() => setModal(null)}
        processo={processo}
        err={err}
        setErr={setErr}
        onDone={invalidate}
      />

      <Dialog
        open={modal === "receber"}
        onClose={() => setModal(null)}
        title="Confirmar recebimento"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModal(null)}>
              Cancelar
            </Button>
            <Button
              onClick={() => receberM.mutate()}
              disabled={receberM.isPending}
            >
              {receberM.isPending ? "Recebendo..." : "Confirmar recebimento"}
            </Button>
          </>
        }
      >
        <p className="text-sm">
          Confirma o recebimento do processo{" "}
          <b className="font-mono">{processo.numero_processo}</b> na unidade{" "}
          <b>{encaminhamentoPendente?.unidade_destino}</b>?
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Após o recebimento, o processo passa a constar na unidade de destino.
        </p>
        {err && (
          <p
            role="alert"
            className="mt-3 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
          >
            {err}
          </p>
        )}
      </Dialog>

      <CancelarDialog
        open={modal === "cancelar"}
        onClose={() => setModal(null)}
        encaminhamentoId={encaminhamentoPendente?.id ?? 0}
        err={err}
        setErr={setErr}
        onDone={invalidate}
      />
    </>
  );
}

function EncaminharDialog({
  open,
  onClose,
  processo,
  err,
  setErr,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  processo: ProcessoDetail;
  err: string | null;
  setErr: (e: string | null) => void;
  onDone: () => void;
}) {
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });
  const prioridadesQ = useQuery({
    queryKey: ["prioridades"],
    queryFn: () => api.prioridades(),
  });

  const [form, setForm] = useState<EncaminharInput>({
    id_unidade_destino: 0,
    id_prioridade: 0,
    quantidade_folhas: 0,
    data_prazo: null,
    despacho: "",
  });

  const m = useMutation({
    mutationFn: (data: EncaminharInput) =>
      api.processos.encaminhar(processo.id, data),
    onSuccess: () => {
      onDone();
      reset();
      onClose();
    },
    onError: (e: Error) => setErr(e.message),
  });

  function reset() {
    setForm({
      id_unidade_destino: 0,
      id_prioridade: 0,
      quantidade_folhas: 0,
      data_prazo: null,
      despacho: "",
    });
    setErr(null);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!form.id_unidade_destino || !form.id_prioridade) {
      setErr("Selecione unidade destino e prioridade.");
      return;
    }
    m.mutate({
      ...form,
      data_prazo: form.data_prazo || null,
      despacho: form.despacho || null,
    });
  }

  return (
    <Dialog
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title={`Encaminhar processo ${processo.numero_processo}`}
      size="md"
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
            {m.isPending ? "Encaminhando..." : "Encaminhar"}
          </Button>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-3">
        <div>
          <Label htmlFor="dest">Unidade destino *</Label>
          <Select
            id="dest"
            value={form.id_unidade_destino || ""}
            onChange={(e) =>
              setForm({ ...form, id_unidade_destino: Number(e.target.value) })
            }
            required
          >
            <option value="">—</option>
            {unidadesQ.data?.items.map((u) => (
              <option key={u.id} value={u.id}>
                {u.unidade_trabalho}
              </option>
            ))}
          </Select>
          <p className="mt-1 text-xs text-muted-foreground">
            Origem: {processo.local_atual ?? processo.unidade_proprietaria ?? "—"}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor="prio">Prioridade *</Label>
            <Select
              id="prio"
              value={form.id_prioridade || ""}
              onChange={(e) =>
                setForm({ ...form, id_prioridade: Number(e.target.value) })
              }
              required
            >
              <option value="">—</option>
              {prioridadesQ.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.prioridade}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="folhas">Quantidade de folhas</Label>
            <Input
              id="folhas"
              type="number"
              min={0}
              value={form.quantidade_folhas ?? 0}
              onChange={(e) =>
                setForm({ ...form, quantidade_folhas: Number(e.target.value) })
              }
            />
          </div>
        </div>
        <div>
          <Label htmlFor="prazo">Data prazo</Label>
          <Input
            id="prazo"
            type="date"
            value={form.data_prazo ?? ""}
            onChange={(e) => setForm({ ...form, data_prazo: e.target.value || null })}
          />
        </div>
        <div>
          <Label htmlFor="desp">Despacho (opcional)</Label>
          <Textarea
            id="desp"
            value={form.despacho ?? ""}
            onChange={(e) => setForm({ ...form, despacho: e.target.value })}
            rows={3}
            placeholder="Texto do despacho que acompanha o encaminhamento"
          />
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

function CancelarDialog({
  open,
  onClose,
  encaminhamentoId,
  err,
  setErr,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  encaminhamentoId: number;
  err: string | null;
  setErr: (e: string | null) => void;
  onDone: () => void;
}) {
  const [despacho, setDespacho] = useState("");

  const m = useMutation({
    mutationFn: () =>
      api.processos.cancelarEncaminhamento(encaminhamentoId, {
        despacho: despacho || null,
      }),
    onSuccess: () => {
      onDone();
      setDespacho("");
      onClose();
    },
    onError: (e: Error) => setErr(e.message),
  });

  return (
    <Dialog
      open={open}
      onClose={() => {
        setDespacho("");
        onClose();
      }}
      title="Cancelar encaminhamento pendente"
      footer={
        <>
          <Button
            variant="secondary"
            onClick={() => {
              setDespacho("");
              onClose();
            }}
          >
            Voltar
          </Button>
          <Button onClick={() => m.mutate()} disabled={m.isPending}>
            {m.isPending ? "Cancelando..." : "Confirmar cancelamento"}
          </Button>
        </>
      }
    >
      <p className="text-sm">
        O encaminhamento ainda não foi recebido. Ao cancelar, o processo permanece na
        unidade de origem e o cancelamento fica registrado no histórico.
      </p>
      <div className="mt-3">
        <Label htmlFor="cancdesp">Justificativa (opcional)</Label>
        <Textarea
          id="cancdesp"
          value={despacho}
          onChange={(e) => setDespacho(e.target.value)}
          rows={3}
        />
      </div>
      {err && (
        <div
          role="alert"
          className="mt-3 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
        >
          {err}
        </div>
      )}
    </Dialog>
  );
}
