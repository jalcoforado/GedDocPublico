"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FilePlus2, Pencil, Send, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { ArquivarDialog } from "@/components/ArquivarDialog";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { DESPACHO_PADRAO } from "@/lib/despacho";
import {
  api,
  type EncaminharInput,
  type ProcessoDetail,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

type ModalKind = null | "encaminhar" | "receber" | "recusar" | "cancelar" | "arquivar";

/** Como o processo aparece em título de diálogo: rascunho não tem número. */
function nomeDoProcesso(p: ProcessoDetail): string {
  return p.numero_processo ? `processo ${p.numero_processo}` : "rascunho";
}

/**
 * Barra de ações do processo, no topo da página (SI-16, modelo do SEI): o que
 * se faz com o processo fica ao lado do número, não embaixo das abas.
 *
 * Rascunho tem outra barra (`AcoesRascunho`): editar, abrir, encaminhar e
 * excluir. Receber, recusar e cancelar não se aplicam — rascunho nunca
 * tramitou —, e arquivar o servidor recusa.
 */
export function AcoesProcesso({ processo }: { processo: ProcessoDetail }) {
  if (processo.situacao === "rascunho") return <AcoesRascunho processo={processo} />;
  return <AcoesTramitacao processo={processo} />;
}

function AcoesTramitacao({ processo }: { processo: ProcessoDetail }) {
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

  // F4 — já arquivado não arquiva de novo. A fonte é a linha do tempo e não
  // `processo.ativo`: arquivar NÃO mexe naquele campo (decisão registrada em
  // `services/acoes_processo.py::arquivar`), então usá-lo aqui daria sempre
  // "pode arquivar".
  const jaArquivado = useMemo(
    () => processo.movimentacoes.some((m) => m.acao_flag === "ARQUIVAMENTO"),
    [processo.movimentacoes],
  );
  const podeArquivar = !jaArquivado && !encaminhamentoPendente;

  const podeEncaminhar = processo.ativo && !encaminhamentoPendente;
  // Receber/recusar são da unidade de destino e cancelar, da de origem. O
  // servidor diz se quem consulta pode; `false` explícito desabilita, ausente
  // não restringe (o servidor continua sendo a barreira).
  const doDestino = processo.pode_receber_encaminhamento !== false;
  const daOrigem = processo.pode_cancelar_encaminhamento !== false;
  const podeReceber = !!encaminhamentoPendente && processo.ativo && doDestino;
  const podeCancelar = !!encaminhamentoPendente && processo.ativo && daOrigem;

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
        {/* A outra decisão de quem está com o processo chegando. */}
        <Button
          variant="secondary"
          onClick={() => {
            setErr(null);
            setModal("recusar");
          }}
          disabled={!podeReceber}
        >
          Recusar
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
        <Button
          variant="secondary"
          onClick={() => {
            setErr(null);
            setModal("arquivar");
          }}
          disabled={!podeArquivar}
        >
          Arquivar
        </Button>

        {encaminhamentoPendente && (
          <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-warning-soft px-2 py-0.5 text-xs font-semibold text-warning-soft-foreground">
            Aguardando recebimento
          </span>
        )}
        {encaminhamentoPendente && !doDestino && (
          <span className="text-xs text-muted-foreground">
            Receber ou recusar cabe a quem é de {encaminhamentoPendente.unidade_destino}.
          </span>
        )}
      </div>

      <ArquivarDialog
        open={modal === "arquivar"}
        onClose={() => setModal(null)}
        processo={processo}
      />

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
            <Button variant="ghost" onClick={() => setModal(null)}>
              Cancelar
            </Button>
            <Button onClick={() => receberM.mutate()} loading={receberM.isPending}>
              {receberM.isPending ? "Recebendo…" : "Confirmar recebimento"}
            </Button>
          </>
        }
      >
        <p className="text-sm">
          Confirma o recebimento do processo{" "}
          <b className="font-mono">{processo.numero_processo ?? "(sem número)"}</b> na unidade{" "}
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

      <RecusarDialog
        open={modal === "recusar"}
        onClose={() => setModal(null)}
        processoId={processo.id}
        unidadeOrigem={encaminhamentoPendente?.unidade_origem ?? null}
        err={err}
        setErr={setErr}
        onDone={invalidate}
      />

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

/**
 * Ações do rascunho (SI-16). Só o autor chega a ver um rascunho — para os
 * outros o servidor responde 404 —, então aqui não se pergunta "é meu?".
 * As permissões seguem as do servidor: editar e encaminhar pedem `atualizar`,
 * abrir pede `inserir` (é o ato da abertura), excluir pede `excluir`.
 */
function AcoesRascunho({ processo }: { processo: ProcessoDetail }) {
  const qc = useQueryClient();
  const router = useRouter();
  const confirm = useConfirm();
  const toast = useToast();
  const { can } = useAuth();
  const [encaminhando, setEncaminhando] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function invalidate() {
    qc.invalidateQueries({ queryKey: ["processo", processo.id] });
    qc.invalidateQueries({ queryKey: ["processos"] });
  }

  async function abrir() {
    try {
      const ok = await confirm({
        title: "Abrir o processo?",
        message:
          "O processo ganha número agora e passa a valer. Ele fica na sua unidade, e depois disso não volta a ser rascunho.",
        confirmLabel: "Abrir processo",
        onConfirm: async () => {
          const p = await api.processos.abrirRascunho(processo.id);
          toast.success(`Processo ${p.numero_processo} aberto.`);
        },
      });
      if (ok) invalidate();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Não foi possível abrir o processo.");
    }
  }

  async function excluir() {
    try {
      const ok = await confirm({
        title: "Excluir o rascunho?",
        message: "O rascunho some das suas listas. Esta ação não pode ser desfeita pela tela.",
        confirmLabel: "Excluir rascunho",
        intent: "danger",
        onConfirm: () => api.processos.excluirRascunho(processo.id),
      });
      if (!ok) return;
      qc.invalidateQueries({ queryKey: ["processos"] });
      toast.success("Rascunho excluído.");
      router.push("/m/protocolo/processos?situacao=rascunho");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Não foi possível excluir o rascunho.");
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        {can("processo", "atualizar") && (
          <Button asChild variant="secondary">
            <Link href={`/m/protocolo/processos/${processo.id}/editar`}>
              <Pencil className="h-4 w-4" aria-hidden="true" />
              Editar
            </Link>
          </Button>
        )}
        {can("processo", "inserir") && (
          <Button onClick={abrir} title="Gera o número sem tramitar. O processo fica na sua unidade.">
            <FilePlus2 className="h-4 w-4" aria-hidden="true" />
            Abrir processo
          </Button>
        )}
        {can("processo", "atualizar") && (
          <Button
            variant="secondary"
            onClick={() => {
              setErr(null);
              setEncaminhando(true);
            }}
            disabled={!processo.ativo}
            title="Encaminhar também abre o processo: ele ganha número."
          >
            <Send className="h-4 w-4" aria-hidden="true" />
            Encaminhar
          </Button>
        )}
        {can("processo", "excluir") && (
          <Button variant="ghost" onClick={excluir}>
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            Excluir rascunho
          </Button>
        )}
        <span className="text-xs text-foreground-subtle">
          Rascunho: sem número, e só você o vê.
        </span>
      </div>

      <EncaminharDialog
        open={encaminhando}
        onClose={() => setEncaminhando(false)}
        processo={processo}
        err={err}
        setErr={setErr}
        onDone={invalidate}
      />
    </>
  );
}

/** Mensagem de erro do servidor dentro do diálogo. */
function ErroDialogo({ err }: { err: string | null }) {
  if (!err) return null;
  return (
    <p
      role="alert"
      className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
    >
      {err}
    </p>
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
  // F3 — quando o workflow ativo restringe o próximo destino, o combo só
  // oferece o que `encaminhar` vai aceitar (em vez de deixar escolher e
  // barrar depois, exigindo excluir o rascunho e recomeçar).
  const destinosQ = useQuery({
    queryKey: ["destinos-permitidos", processo.id],
    queryFn: () => api.processos.destinosPermitidos(processo.id),
  });
  const unidadesOptions =
    destinosQ.data?.restrito && destinosQ.data.ids_unidade
      ? (unidadesQ.data?.items ?? []).filter((u) =>
          destinosQ.data!.ids_unidade!.includes(u.id),
        )
      : (unidadesQ.data?.items ?? []);
  // Dezenas de unidades: combo com busca, não um <select> para rolar.
  const destinoOptions: ComboboxOption[] = unidadesOptions.map((u) => ({
    value: u.id,
    label: u.unidade_trabalho,
  }));
  const prioridades = prioridadesQ.data ?? [];

  const [form, setForm] = useState<EncaminharInput>({
    id_unidade_destino: 0,
    id_prioridade: 0,
    quantidade_folhas: 0,
    data_prazo: null,
    despacho: "",
  });
  // Erro sob o campo só depois de tentar encaminhar.
  const [tentou, setTentou] = useState(false);
  const faltaDestino = tentou && !form.id_unidade_destino;
  const faltaPrioridade = tentou && !form.id_prioridade;

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
    setTentou(false);
    setErr(null);
  }

  function fechar() {
    reset();
    onClose();
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setTentou(true);
    if (!form.id_unidade_destino || !form.id_prioridade) {
      const alvo = !form.id_unidade_destino
        ? document.getElementById("dest")
        : (document.getElementById("prio") ??
          document.querySelector<HTMLElement>('input[name="prio"]'));
      alvo?.focus();
      return;
    }
    m.mutate({
      ...form,
      data_prazo: form.data_prazo || null,
      despacho: form.despacho || null,
    });
  }

  const origem = processo.local_atual ?? processo.unidade_proprietaria ?? null;

  return (
    <Dialog
      open={open}
      onClose={fechar}
      title={`Encaminhar ${nomeDoProcesso(processo)}`}
      description={origem ? `Sai de ${origem}.` : undefined}
      size="md"
      footer={
        <>
          <Button variant="ghost" onClick={fechar}>
            Cancelar
          </Button>
          <Button onClick={submit} loading={m.isPending}>
            {m.isPending ? "Encaminhando…" : "Encaminhar"}
          </Button>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="space-y-4">
        {processo.situacao === "rascunho" && (
          <p className="rounded-md bg-warning-soft px-3 py-2 text-sm text-warning-soft-foreground">
            Encaminhar abre o processo: ele ganha número agora e deixa de ser rascunho.
          </p>
        )}
        <FormField
          label="Unidade de destino"
          required
          hint={
            destinosQ.data?.restrito ? (
              <span className="text-warning-soft-foreground">{destinosQ.data.motivo}</span>
            ) : (
              "Quem recebe o processo. Busque pelo nome."
            )
          }
          error={faltaDestino ? "Escolha para qual unidade o processo vai." : undefined}
        >
          <Combobox
            id="dest"
            options={destinoOptions}
            value={form.id_unidade_destino || null}
            onChange={(v) =>
              setForm({ ...form, id_unidade_destino: typeof v === "number" ? v : 0 })
            }
            placeholder="Buscar unidade…"
            searchPlaceholder="Nome da unidade…"
            emptyText="Nenhuma unidade com esse nome."
            loading={unidadesQ.isLoading || destinosQ.isLoading}
          />
        </FormField>

        {/* Poucas prioridades: todas à vista. Se o catálogo crescer, volta a
            ser lista. */}
        {prioridades.length >= 2 && prioridades.length <= 4 ? (
          <div>
            <EscolhaSegmentada
              nome="prio"
              titulo="Prioridade"
              moldura={false}
              valor={form.id_prioridade ? String(form.id_prioridade) : ""}
              onChange={(v) => setForm({ ...form, id_prioridade: Number(v) })}
              opcoes={prioridades.map((p) => ({ valor: String(p.id), rotulo: p.prioridade }))}
            />
            {faltaPrioridade && (
              <p className="mt-1 text-xs font-medium text-danger-soft-foreground">
                Escolha a prioridade.
              </p>
            )}
          </div>
        ) : (
          <FormField
            label="Prioridade"
            required
            error={faltaPrioridade ? "Escolha a prioridade." : undefined}
          >
            <Select
              id="prio"
              value={form.id_prioridade || ""}
              onChange={(e) =>
                setForm({ ...form, id_prioridade: Number(e.target.value) })
              }
            >
              <option value="">Escolha…</option>
              {prioridades.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.prioridade}
                </option>
              ))}
            </Select>
          </FormField>
        )}

        <GradeCampos>
          <FormField label="Quantidade de folhas" opcional hint="Do processo físico, se houver.">
            <CampoComUnidade
              id="folhas"
              type="number"
              min={0}
              sufixo="folhas"
              value={form.quantidade_folhas ?? 0}
              onChange={(e) =>
                setForm({ ...form, quantidade_folhas: Number(e.target.value) })
              }
            />
          </FormField>
          <FormField label="Prazo" opcional hint="Até quando o destino deve responder.">
            <Input
              id="prazo"
              type="date"
              value={form.data_prazo ?? ""}
              onChange={(e) => setForm({ ...form, data_prazo: e.target.value || null })}
            />
          </FormField>
        </GradeCampos>

        <FormField
          label="Despacho"
          opcional
          hint="Vai junto com o processo e fica no histórico."
          acao={
            !form.despacho ? (
              <button
                type="button"
                onClick={() => setForm({ ...form, despacho: DESPACHO_PADRAO })}
                className="font-medium text-primary underline-offset-2 hover:underline"
              >
                Usar texto padrão
              </button>
            ) : undefined
          }
        >
          <Textarea
            id="desp"
            value={form.despacho ?? ""}
            onChange={(e) => setForm({ ...form, despacho: e.target.value })}
            rows={3}
            placeholder="Ex.: Encaminho para análise e parecer."
          />
        </FormField>
        <ErroDialogo err={err} />
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

  function fechar() {
    setDespacho("");
    onClose();
  }

  return (
    <Dialog
      open={open}
      onClose={fechar}
      title="Cancelar encaminhamento"
      footer={
        <>
          <Button variant="ghost" onClick={fechar}>
            Voltar
          </Button>
          <Button onClick={() => m.mutate()} loading={m.isPending}>
            {m.isPending ? "Cancelando…" : "Confirmar cancelamento"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm">
          O encaminhamento ainda não foi recebido. Ao cancelar, o processo permanece na
          unidade de origem e o cancelamento fica registrado no histórico.
        </p>
        <FormField label="Justificativa" opcional hint="Fica registrada no histórico do processo.">
          <Textarea
            id="cancdesp"
            value={despacho}
            onChange={(e) => setDespacho(e.target.value)}
            rows={3}
            placeholder="Ex.: Encaminhado para a unidade errada."
          />
        </FormField>
        <ErroDialogo err={err} />
      </div>
    </Dialog>
  );
}

/** Mínimo do motivo — o mesmo do backend (`RecusarEncaminhamentoRequest`). */
const MOTIVO_MINIMO = 5;

function RecusarDialog({
  open,
  onClose,
  processoId,
  unidadeOrigem,
  err,
  setErr,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  processoId: number;
  unidadeOrigem: string | null;
  err: string | null;
  setErr: (e: string | null) => void;
  onDone: () => void;
}) {
  const [motivo, setMotivo] = useState("");
  const [tentou, setTentou] = useState(false);
  const motivoValido = motivo.trim().length >= MOTIVO_MINIMO;

  const m = useMutation({
    mutationFn: () => api.processos.recusarEncaminhamento(processoId, motivo.trim()),
    onSuccess: () => {
      onDone();
      setMotivo("");
      setTentou(false);
      onClose();
    },
    onError: (e: Error) => setErr(e.message),
  });

  function fechar() {
    setMotivo("");
    setTentou(false);
    onClose();
  }

  // O botão não fica desabilitado esperando o motivo: clicar sem ele mostra,
  // sob o campo, o que falta — um botão cinza sem explicação não diz nada.
  function confirmar() {
    setTentou(true);
    if (!motivoValido) {
      document.getElementById("recusamotivo")?.focus();
      return;
    }
    m.mutate();
  }

  return (
    <Dialog
      open={open}
      onClose={fechar}
      title="Recusar encaminhamento"
      footer={
        <>
          <Button variant="ghost" onClick={fechar}>
            Voltar
          </Button>
          <Button onClick={confirmar} loading={m.isPending}>
            {m.isPending ? "Recusando…" : "Confirmar recusa"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm">
          O processo não entra nesta unidade: volta para{" "}
          <b>{unidadeOrigem ?? "a unidade de origem"}</b>, que é avisada e vê o motivo.
        </p>
        <FormField
          label="Motivo da recusa"
          required
          hint="Diga por que o processo não é desta unidade ou o que falta."
          error={
            tentou && !motivoValido
              ? `Escreva o motivo, com pelo menos ${MOTIVO_MINIMO} letras.`
              : undefined
          }
        >
          <Textarea
            id="recusamotivo"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            rows={3}
            maxLength={2000}
            placeholder="Ex.: O assunto é da Secretaria de Saúde, não desta unidade."
          />
        </FormField>
        <ErroDialogo err={err} />
      </div>
    </Dialog>
  );
}
