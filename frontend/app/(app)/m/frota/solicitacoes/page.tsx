"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  Car,
  ClipboardList,
  Eraser,
  FileText,
  Inbox,
  LogIn,
  LogOut,
  MapPin,
  Pencil,
  Plus,
  ThumbsDown,
  ThumbsUp,
  Trash2,
} from "lucide-react";
import { type ReactNode, useState } from "react";

import { fmtKm, rotuloVeiculo, useErrosDoFormulario } from "@/components/frota/formulario";
import { fmtDataHora } from "@/components/frota/rotulos";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada, type OpcaoEscolha } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type DesignacaoInput,
  type RegistrarRetornoInput,
  type RegistrarSaidaInput,
  type SolicitacaoStatus,
  type SolicitacaoVeiculo,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const STATUS_LABEL: Record<SolicitacaoStatus, string> = {
  solicitada: "Solicitada",
  aprovada: "Aprovada",
  rejeitada: "Rejeitada",
  cancelada: "Cancelada",
  em_uso: "Em uso",
  concluida: "Concluída",
};
// Mesma régua de cor das demais telas da Frota (ver components/frota/rotulos.ts):
// aguardando decisão = warning; aprovada e em uso estão andando = info.
const STATUS_INTENT: Record<SolicitacaoStatus, "neutral" | "success" | "danger" | "warning" | "info"> = {
  solicitada: "warning",
  aprovada: "info",
  rejeitada: "danger",
  cancelada: "neutral",
  em_uso: "info",
  concluida: "success",
};

interface SolicitacaoForm {
  id_unidade_solicitante: number | null;
  finalidade: string;
  destino: string;
  data_saida_prevista: string;
  data_retorno_prevista: string;
  quantidade_passageiros: number;
  necessita_motorista: boolean;
  observacoes: string;
}

const EMPTY: SolicitacaoForm = {
  id_unidade_solicitante: null,
  finalidade: "",
  destino: "",
  data_saida_prevista: "",
  data_retorno_prevista: "",
  quantidade_passageiros: 1,
  necessita_motorista: false,
  observacoes: "",
};

interface DesignarForm {
  id_veiculo: number | null;
  id_motorista: number | null;
  observacoes_designacao: string;
}

const DESIGNAR_EMPTY: DesignarForm = {
  id_veiculo: null,
  id_motorista: null,
  observacoes_designacao: "",
};

interface SaidaForm {
  km_saida: string;
  observacoes_saida: string;
}
const SAIDA_EMPTY: SaidaForm = { km_saida: "", observacoes_saida: "" };

interface RetornoForm {
  km_retorno: string;
  observacoes_retorno: string;
}
const RETORNO_EMPTY: RetornoForm = { km_retorno: "", observacoes_retorno: "" };

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

/**
 * Erro do campo de quilometragem: vazio, não inteiro ou abaixo do piso. O
 * piso é a mesma regra do backend (saída ≥ km do veículo; retorno ≥ saída),
 * dita antes de enviar e com o número que vale.
 */
function erroKm(valor: string, minimo: number | null, piso: string): string | undefined {
  if (valor.trim() === "") return "Informe a quilometragem do painel.";
  const km = Number(valor);
  if (!Number.isInteger(km) || km < 0) return "Use só números inteiros, sem ponto nem vírgula.";
  if (minimo != null && km < minimo) return `O mínimo é ${fmtKm(minimo)} — ${piso}.`;
  return undefined;
}

const NECESSITA_MOTORISTA: OpcaoEscolha<"sim" | "nao">[] = [
  {
    valor: "nao",
    rotulo: "Não, só o veículo",
    descricao: "Alguém da própria unidade dirige.",
  },
  {
    valor: "sim",
    rotulo: "Sim, com motorista",
    descricao: "A frota designa um motorista junto com o veículo.",
  },
];

/** O pedido em uma linha, no topo dos diálogos do fluxo: quem decide vê o que está decidindo. */
function ResumoSolicitacao({
  s,
  extra,
}: {
  s: SolicitacaoVeiculo;
  extra?: ReactNode;
}) {
  return (
    <div className="rounded-md border border-border bg-surface-1 px-3 py-2 text-sm">
      <div className="font-medium text-foreground">{s.finalidade}</div>
      <div className="text-xs text-foreground-muted">
        {s.destino} · {fmtDataHora(s.data_saida_prevista)} até {fmtDataHora(s.data_retorno_prevista)} ·{" "}
        {s.quantidade_passageiros} {s.quantidade_passageiros === 1 ? "passageiro" : "passageiros"}
      </div>
      {extra && <div className="mt-1 text-xs text-foreground-muted">{extra}</div>}
    </div>
  );
}

export default function SolicitacoesPage() {
  const { can } = useAuth();
  const canCreate = can("frota", "inserir");
  const canEdit = can("frota", "atualizar");
  const canDelete = can("frota", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<SolicitacaoVeiculo | null>(null);
  const [form, setForm] = useState<SolicitacaoForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const [designarOpen, setDesignarOpen] = useState(false);
  const [designarSol, setDesignarSol] = useState<SolicitacaoVeiculo | null>(null);
  const [designarForm, setDesignarForm] = useState<DesignarForm>(DESIGNAR_EMPTY);
  const [designarErr, setDesignarErr] = useState<string | null>(null);

  const [saidaOpen, setSaidaOpen] = useState(false);
  const [saidaSol, setSaidaSol] = useState<SolicitacaoVeiculo | null>(null);
  const [saidaForm, setSaidaForm] = useState<SaidaForm>(SAIDA_EMPTY);
  const [saidaErr, setSaidaErr] = useState<string | null>(null);

  const [retornoOpen, setRetornoOpen] = useState(false);
  const [retornoSol, setRetornoSol] = useState<SolicitacaoVeiculo | null>(null);
  const [retornoForm, setRetornoForm] = useState<RetornoForm>(RETORNO_EMPTY);
  const [retornoErr, setRetornoErr] = useState<string | null>(null);

  // Rejeição: era um window.prompt — sem rótulo, sem dizer como corrigir, e o
  // "obrigatório" só aparecia num toast depois que a caixa já tinha fechado.
  const [rejeitarSol, setRejeitarSol] = useState<SolicitacaoVeiculo | null>(null);
  const [motivo, setMotivo] = useState("");
  const [rejeitarErr, setRejeitarErr] = useState<string | null>(null);

  const listQ = useQuery({
    queryKey: ["frota-solicitacoes"],
    queryFn: () => api.solicitacoes.listAll(),
  });
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });
  const veiculosQ = useQuery({ queryKey: ["frota-veiculos"], queryFn: () => api.frota.listAll() });
  const motoristasQ = useQuery({
    queryKey: ["frota-motoristas"],
    queryFn: () => api.motoristas.listAll(),
  });
  const unidades = unidadesQ.data?.items ?? [];
  const veiculos = veiculosQ.data ?? [];
  const motoristas = motoristasQ.data ?? [];
  const unidadeNome = (id: number | null) =>
    unidades.find((u) => u.id === id)?.unidade_trabalho ?? "—";
  const veiculoLabel = (id: number | null) => {
    const v = veiculos.find((x) => x.id === id);
    return v ? [v.placa, v.marca, v.modelo].filter(Boolean).join(" ") : null;
  };
  const motoristaNome = (id: number | null) =>
    motoristas.find((x) => x.id === id)?.nome ?? null;

  // Última quilometragem conhecida do veículo designado: o piso da saída (o
  // backend recusa abaixo dela) e a dica do campo.
  const kmDoVeiculo = (id: number | null) =>
    veiculos.find((x) => x.id === id)?.quilometragem_atual ?? null;
  const kmMinimoSaida = saidaSol ? kmDoVeiculo(saidaSol.id_veiculo_designado) : null;

  const campos = useErrosDoFormulario({
    finalidade: form.finalidade.trim() ? undefined : "Diga para que o veículo vai ser usado.",
    destino: form.destino.trim() ? undefined : "Informe o destino.",
    passageiros:
      Number.isInteger(form.quantidade_passageiros) && form.quantidade_passageiros >= 1
        ? undefined
        : "Informe ao menos 1 passageiro.",
    saida: form.data_saida_prevista ? undefined : "Informe quando o veículo sai.",
    retorno: !form.data_retorno_prevista
      ? "Informe quando o veículo volta."
      : form.data_saida_prevista && form.data_retorno_prevista < form.data_saida_prevista
        ? "O retorno não pode ser antes da saída."
        : undefined,
  });
  const camposRejeitar = useErrosDoFormulario({
    motivo: motivo.trim() ? undefined : "Escreva o motivo da rejeição.",
  });
  const camposDesignar = useErrosDoFormulario({
    d_veiculo: designarForm.id_veiculo ? undefined : "Escolha o veículo.",
    d_motorista:
      designarSol?.necessita_motorista && !designarForm.id_motorista
        ? "Esta solicitação pede motorista — escolha um."
        : undefined,
  });
  const camposSaida = useErrosDoFormulario({
    km_saida: erroKm(saidaForm.km_saida, kmMinimoSaida, "a última quilometragem do veículo"),
  });
  // Quanto o veículo rodou, à medida que se digita o km de chegada — confere
  // na hora um dígito a mais ou a menos.
  const kmRetorno = Number(retornoForm.km_retorno);
  const percorrido =
    retornoSol?.km_saida != null &&
    retornoForm.km_retorno.trim() !== "" &&
    Number.isInteger(kmRetorno) &&
    kmRetorno >= retornoSol.km_saida
      ? kmRetorno - retornoSol.km_saida
      : null;
  const camposRetorno = useErrosDoFormulario({
    km_retorno: erroKm(retornoForm.km_retorno, retornoSol?.km_saida ?? null, "a quilometragem da saída"),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["frota-solicitacoes"] });

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing ? api.solicitacoes.update(editing.id, data) : api.solicitacoes.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Solicitação atualizada." : "Solicitação registrada.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const aprovarM = useMutation({
    mutationFn: (id: number) => api.solicitacoes.aprovar(id),
    onSuccess: () => {
      invalidate();
      toast.success("Solicitação aprovada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const cancelarM = useMutation({
    mutationFn: (id: number) => api.solicitacoes.cancelar(id),
    onSuccess: () => {
      invalidate();
      toast.success("Solicitação cancelada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const rejeitarM = useMutation({
    mutationFn: ({ id, justificativa }: { id: number; justificativa: string }) =>
      api.solicitacoes.rejeitar(id, justificativa),
    onSuccess: () => {
      invalidate();
      toast.success("Solicitação rejeitada.");
      closeRejeitar();
    },
    onError: (e: Error) => setRejeitarErr(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.solicitacoes.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Solicitação excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const designarM = useMutation({
    mutationFn: ({ id, data }: { id: number; data: DesignacaoInput }) =>
      api.solicitacoes.designar(id, data),
    onSuccess: () => {
      invalidate();
      toast.success("Designação registrada.");
      closeDesignar();
    },
    onError: (e: Error) => setDesignarErr(e.message),
  });
  const limparDesignacaoM = useMutation({
    mutationFn: (id: number) => api.solicitacoes.limparDesignacao(id),
    onSuccess: () => {
      invalidate();
      toast.success("Designação removida.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const registrarSaidaM = useMutation({
    mutationFn: ({ id, data }: { id: number; data: RegistrarSaidaInput }) =>
      api.solicitacoes.registrarSaida(id, data),
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ["frota-veiculos"] });
      toast.success("Saída registrada.");
      closeSaida();
    },
    onError: (e: Error) => setSaidaErr(e.message),
  });
  const registrarRetornoM = useMutation({
    mutationFn: ({ id, data }: { id: number; data: RegistrarRetornoInput }) =>
      api.solicitacoes.registrarRetorno(id, data),
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ["frota-veiculos"] });
      toast.success("Retorno registrado.");
      closeRetorno();
    },
    onError: (e: Error) => setRetornoErr(e.message),
  });

  function set<K extends keyof SolicitacaoForm>(key: K, value: SolicitacaoForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    campos.limpar();
    setDialogOpen(true);
  }

  function openEdit(s: SolicitacaoVeiculo) {
    setEditing(s);
    setForm({
      id_unidade_solicitante: s.id_unidade_solicitante,
      finalidade: s.finalidade,
      destino: s.destino,
      data_saida_prevista: s.data_saida_prevista?.slice(0, 16) ?? "",
      data_retorno_prevista: s.data_retorno_prevista?.slice(0, 16) ?? "",
      quantidade_passageiros: s.quantidade_passageiros,
      necessita_motorista: s.necessita_motorista,
      observacoes: s.observacoes ?? "",
    });
    setErr(null);
    campos.limpar();
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }

  function salvar() {
    setErr(null);
    if (!campos.podeEnviar()) return;
    const payload = {
      id_unidade_solicitante: form.id_unidade_solicitante ?? null,
      finalidade: form.finalidade.trim(),
      destino: form.destino.trim(),
      data_saida_prevista: form.data_saida_prevista,
      data_retorno_prevista: form.data_retorno_prevista,
      quantidade_passageiros: form.quantidade_passageiros,
      necessita_motorista: form.necessita_motorista,
      observacoes: nullify(form.observacoes),
    };
    saveM.mutate(payload);
  }

  function openRejeitar(s: SolicitacaoVeiculo) {
    setRejeitarSol(s);
    setMotivo("");
    setRejeitarErr(null);
    camposRejeitar.limpar();
  }

  function closeRejeitar() {
    setRejeitarSol(null);
    setMotivo("");
    setRejeitarErr(null);
  }

  function confirmarRejeicao() {
    setRejeitarErr(null);
    if (!rejeitarSol || !camposRejeitar.podeEnviar()) return;
    rejeitarM.mutate({ id: rejeitarSol.id, justificativa: motivo.trim() });
  }

  function openDesignar(s: SolicitacaoVeiculo) {
    setDesignarSol(s);
    setDesignarForm({
      id_veiculo: s.id_veiculo_designado,
      id_motorista: s.id_motorista_designado,
      observacoes_designacao: s.observacoes_designacao ?? "",
    });
    camposDesignar.limpar();
    setDesignarErr(null);
    setDesignarOpen(true);
  }

  function closeDesignar() {
    setDesignarOpen(false);
    setDesignarSol(null);
    setDesignarForm(DESIGNAR_EMPTY);
    setDesignarErr(null);
  }

  function salvarDesignar() {
    setDesignarErr(null);
    if (!designarSol || !camposDesignar.podeEnviar()) return;
    const data: DesignacaoInput = {
      id_veiculo: designarForm.id_veiculo!,
      id_motorista: designarForm.id_motorista ?? null,
      observacoes_designacao: nullify(designarForm.observacoes_designacao),
    };
    designarM.mutate({ id: designarSol.id, data });
  }

  function openSaida(s: SolicitacaoVeiculo) {
    setSaidaSol(s);
    setSaidaForm(SAIDA_EMPTY);
    camposSaida.limpar();
    setSaidaErr(null);
    setSaidaOpen(true);
  }

  function closeSaida() {
    setSaidaOpen(false);
    setSaidaSol(null);
    setSaidaForm(SAIDA_EMPTY);
    setSaidaErr(null);
  }

  function salvarSaida() {
    setSaidaErr(null);
    if (!saidaSol || !camposSaida.podeEnviar()) return;
    const km = Number(saidaForm.km_saida);
    registrarSaidaM.mutate({
      id: saidaSol.id,
      data: { km_saida: km, observacoes_saida: nullify(saidaForm.observacoes_saida) },
    });
  }

  function openRetorno(s: SolicitacaoVeiculo) {
    setRetornoSol(s);
    setRetornoForm(RETORNO_EMPTY);
    camposRetorno.limpar();
    setRetornoErr(null);
    setRetornoOpen(true);
  }

  function closeRetorno() {
    setRetornoOpen(false);
    setRetornoSol(null);
    setRetornoForm(RETORNO_EMPTY);
    setRetornoErr(null);
  }

  function salvarRetorno() {
    setRetornoErr(null);
    if (!retornoSol || !camposRetorno.podeEnviar()) return;
    const km = Number(retornoForm.km_retorno);
    registrarRetornoM.mutate({
      id: retornoSol.id,
      data: { km_retorno: km, observacoes_retorno: nullify(retornoForm.observacoes_retorno) },
    });
  }

  const veiculosDisponiveis = veiculos.filter((v) => v.situacao === "disponivel");
  const motoristasAtivos = motoristas.filter((m) => m.situacao === "ativo");

  return (
    <div className="space-y-4">
      <PageHeader
        icon={ClipboardList}
        title="Solicitações de veículo"
        description="Pedidos de uso de veículo da frota, com finalidade, destino e datas previstas."
        breadcrumbs={[{ label: "Frota Pública", href: "/m/frota" }, { label: "Solicitações" }]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Nova solicitação
            </Button>
          ) : undefined
        }
      />

      {!listQ.isLoading && (listQ.data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhuma solicitação registrada"
          description="Registre a primeira solicitação de uso de veículo."
          action={
            canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Nova solicitação
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              {/* Dez colunas não cabiam em 1440px: Status e Ações ficavam
                  fora da tela, atrás da rolagem lateral. Agora são pares que
                  se leem juntos (o quê + para onde; saída + retorno; veículo +
                  motorista + o que aconteceu) numa célula de duas linhas. */}
              <TH>Solicitação</TH>
              <TH>Previsto</TH>
              <TH>Execução</TH>
              <TH>Status</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {listQ.isLoading && (
              <TR>
                <TD colSpan={6} className="text-center text-muted-foreground">
                  Carregando solicitações...
                </TD>
              </TR>
            )}
            {listQ.data?.map((s) => {
              const isSolicitada = s.status === "solicitada";
              const isAprovada = s.status === "aprovada";
              const isEmUso = s.status === "em_uso";
              return (
                <TR key={s.id}>
                  {/* Finalidade e destino são texto livre: cortados numa linha,
                      com o texto inteiro no title. Quebrando, cada linha virava
                      um bloco de cinco linhas. */}
                  <TD className="max-w-[20rem]">
                    <div className="truncate font-medium" title={s.finalidade}>
                      {s.finalidade}
                    </div>
                    {/* Destino, passageiros e unidade: o "para onde, quantos e
                        quem pede" — eram três colunas, duas quase sempre "—". */}
                    <div
                      className="truncate text-xs text-muted-foreground"
                      title={[s.destino, unidadeNome(s.id_unidade_solicitante)].filter((x) => x && x !== "—").join(" · ")}
                    >
                      {s.destino}
                      {" · "}
                      {s.quantidade_passageiros} {s.quantidade_passageiros === 1 ? "passageiro" : "passageiros"}
                      {unidadeNome(s.id_unidade_solicitante) !== "—" && ` · ${unidadeNome(s.id_unidade_solicitante)}`}
                    </div>
                  </TD>
                  <TD className="whitespace-nowrap tabular-nums">
                    <div>{fmtDataHora(s.data_saida_prevista)}</div>
                    <div className="text-xs text-muted-foreground">
                      até {fmtDataHora(s.data_retorno_prevista)}
                    </div>
                  </TD>
                  <TD className="max-w-[16rem]">
                    {s.id_veiculo_designado ? (
                      <>
                        <div className="truncate font-medium">
                          {veiculoLabel(s.id_veiculo_designado) ?? `#${s.id_veiculo_designado}`}
                        </div>
                        <div className="truncate text-xs text-muted-foreground">
                          {s.id_motorista_designado
                            ? (motoristaNome(s.id_motorista_designado) ?? `#${s.id_motorista_designado}`)
                            : "Sem motorista"}
                        </div>
                        {/* O último fato da viagem numa linha; os dois no title. */}
                        {(s.data_saida_real || s.data_retorno_real) && (
                          <div
                            className="truncate text-xs tabular-nums text-muted-foreground"
                            title={[
                              s.data_saida_real &&
                                `Saída: ${fmtDataHora(s.data_saida_real)}${s.km_saida != null ? ` · ${s.km_saida} km` : ""}`,
                              s.data_retorno_real &&
                                `Retorno: ${fmtDataHora(s.data_retorno_real)}${s.km_retorno != null ? ` · ${s.km_retorno} km` : ""}`,
                            ]
                              .filter(Boolean)
                              .join("\n")}
                          >
                            {s.data_retorno_real
                              ? `Voltou ${fmtDataHora(s.data_retorno_real)}${s.km_retorno != null ? ` · ${s.km_retorno} km` : ""}`
                              : `Saiu ${fmtDataHora(s.data_saida_real!)}${s.km_saida != null ? ` · ${s.km_saida} km` : ""}`}
                          </div>
                        )}
                      </>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TD>
                  <TD>
                    <Badge intent={STATUS_INTENT[s.status]}>{STATUS_LABEL[s.status]}</Badge>
                  </TD>
                  <TD className="text-right">
                    {/* Só o próximo passo do fluxo fica à vista (Aprovar →
                        Designar → Registrar saída → Registrar retorno); o resto
                        vai para o ⋯. Antes eram até cinco botões empilhados. */}
                    <AcoesDaLinha
                      visiveis={1}
                      acoes={[
                        {
                          label: "Aprovar",
                          icon: ThumbsUp,
                          oculta: !(canEdit && isSolicitada),
                          disabled: aprovarM.isPending,
                          onClick: () => aprovarM.mutate(s.id),
                        },
                        {
                          label: "Registrar saída",
                          icon: LogOut,
                          oculta: !(canEdit && isAprovada && s.id_veiculo_designado),
                          onClick: () => openSaida(s),
                        },
                        {
                          label: s.id_veiculo_designado ? "Trocar designação" : "Designar",
                          icon: Car,
                          oculta: !(canEdit && isAprovada),
                          onClick: () => openDesignar(s),
                        },
                        {
                          label: "Registrar retorno",
                          icon: LogIn,
                          oculta: !(canEdit && isEmUso),
                          onClick: () => openRetorno(s),
                        },
                        {
                          label: "Rejeitar",
                          icon: ThumbsDown,
                          oculta: !(canEdit && isSolicitada),
                          disabled: rejeitarM.isPending,
                          onClick: () => openRejeitar(s),
                        },
                        {
                          label: "Editar",
                          icon: Pencil,
                          oculta: !(canEdit && isSolicitada),
                          onClick: () => openEdit(s),
                        },
                        {
                          label: "Limpar designação",
                          icon: Eraser,
                          oculta: !(canEdit && isAprovada && s.id_veiculo_designado),
                          disabled: limparDesignacaoM.isPending,
                          onClick: async () => {
                            const ok = await confirm({
                              title: "Limpar designação",
                              message: "Remover o veículo/motorista designados desta solicitação?",
                              confirmLabel: "Limpar",
                            });
                            if (ok) limparDesignacaoM.mutate(s.id);
                          },
                        },
                        {
                          label: "Cancelar",
                          icon: Ban,
                          perigo: true,
                          oculta: !(canEdit && (isSolicitada || isAprovada)),
                          disabled: cancelarM.isPending,
                          onClick: async () => {
                            const ok = await confirm({
                              title: "Cancelar solicitação",
                              message: `Cancelar a solicitação "${s.finalidade}"?`,
                              confirmLabel: "Cancelar solicitação",
                            });
                            if (ok) cancelarM.mutate(s.id);
                          },
                        },
                        {
                          label: "Excluir",
                          icon: Trash2,
                          perigo: true,
                          oculta: !canDelete,
                          disabled: deleteM.isPending,
                          onClick: async () => {
                            const ok = await confirm({
                              title: "Excluir solicitação",
                              message: "Esta ação não pode ser desfeita. Excluir a solicitação?",
                              confirmLabel: "Excluir",
                              intent: "danger",
                            });
                            if (ok) deleteM.mutate(s.id);
                          },
                        },
                      ]}
                    />
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? "Editar solicitação" : "Nova solicitação de veículo"}
        description={
          editing
            ? editing.finalidade
            : "Depois de criada, a solicitação espera aprovação; o veículo é designado em seguida."
        }
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button type="submit" form="form-solicitacao" loading={saveM.isPending}>
              {editing ? "Salvar alterações" : "Criar solicitação"}
            </Button>
          </>
        }
      >
        <form
          id="form-solicitacao"
          noValidate
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            salvar();
          }}
        >
          <SectionCard icon={FileText} title="Para que e para onde" description="O motivo da viagem e quem vai.">
            <div className="space-y-4">
              <FormField label="Finalidade" required error={campos.erro("finalidade")}>
                <Input
                  id="finalidade"
                  value={form.finalidade}
                  onChange={(e) => set("finalidade", e.target.value)}
                  onBlur={campos.tocar("finalidade")}
                  placeholder="Ex.: Visita técnica às escolas da zona rural"
                  maxLength={255}
                />
              </FormField>
              <FormField label="Destino" required error={campos.erro("destino")}>
                <Input
                  id="destino"
                  value={form.destino}
                  onChange={(e) => set("destino", e.target.value)}
                  onBlur={campos.tocar("destino")}
                  placeholder="Ex.: Secretaria de Saúde — Centro"
                  maxLength={255}
                />
              </FormField>
              <GradeCampos>
                <FormField label="Unidade solicitante" opcional hint="Quem está pedindo o veículo.">
                  <Select
                    id="unidade"
                    value={form.id_unidade_solicitante ?? ""}
                    onChange={(e) =>
                      set("id_unidade_solicitante", e.target.value ? Number(e.target.value) : null)
                    }
                  >
                    <option value="">Nenhuma</option>
                    {unidades.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.unidade_trabalho}
                      </option>
                    ))}
                  </Select>
                </FormField>
                <FormField
                  label="Passageiros"
                  required

                  error={campos.erro("passageiros")}
                >
                  <Input
                    id="passageiros"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    value={form.quantidade_passageiros}
                    onChange={(e) =>
                      set("quantidade_passageiros", e.target.value ? Number(e.target.value) : 1)
                    }
                    onBlur={campos.tocar("passageiros")}
                  />
                </FormField>
              </GradeCampos>
            </div>
          </SectionCard>

          <SectionCard icon={MapPin} title="Quando" description="Saída e retorno previstos, com a hora.">
            <div className="space-y-4">
              <GradeCampos>
                <FormField label="Saída prevista" required error={campos.erro("saida")}>
                  <Input
                    id="saida"
                    type="datetime-local"
                    value={form.data_saida_prevista}
                    onChange={(e) => set("data_saida_prevista", e.target.value)}
                    onBlur={campos.tocar("saida")}
                  />
                </FormField>
                <FormField label="Retorno previsto" required error={campos.erro("retorno")}>
                  <Input
                    id="retorno"
                    type="datetime-local"
                    min={form.data_saida_prevista || undefined}
                    value={form.data_retorno_prevista}
                    onChange={(e) => set("data_retorno_prevista", e.target.value)}
                    onBlur={campos.tocar("retorno")}
                  />
                </FormField>
              </GradeCampos>
              <EscolhaSegmentada
                nome="necessita_motorista"
                titulo="Precisa de motorista?"
                moldura={false}
                valor={form.necessita_motorista ? "sim" : "nao"}
                opcoes={NECESSITA_MOTORISTA}
                onChange={(o) => set("necessita_motorista", o === "sim")}
              />
              <FormField label="Observações" opcional>
                <Textarea
                  id="obs"
                  rows={3}
                  value={form.observacoes}
                  onChange={(e) => set("observacoes", e.target.value)}
                  placeholder="Ex.: levar material de apoio; precisa de bagageiro"
                />
              </FormField>
            </div>
          </SectionCard>

          {err && (
            <Alert intent="danger" title="Não foi possível salvar">
              {err}
            </Alert>
          )}
        </form>
      </Dialog>

      <Dialog
        open={rejeitarSol != null}
        onClose={closeRejeitar}
        title="Rejeitar solicitação"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={closeRejeitar}>
              Cancelar
            </Button>
            <Button type="submit" form="form-rejeitar" variant="danger" loading={rejeitarM.isPending}>
              Rejeitar solicitação
            </Button>
          </>
        }
      >
        <form
          id="form-rejeitar"
          noValidate
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            confirmarRejeicao();
          }}
        >
          {rejeitarSol && <ResumoSolicitacao s={rejeitarSol} />}
          <FormField
            label="Motivo da rejeição"
            required
            hint="Fica registrado na solicitação, para quem pediu saber por quê."
            error={camposRejeitar.erro("motivo")}
          >
            <Textarea
              id="motivo"
              rows={3}
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              onBlur={camposRejeitar.tocar("motivo")}
              placeholder="Ex.: Não há veículo disponível na data; remarcar para a semana seguinte"
              maxLength={2000}
            />
          </FormField>
          {rejeitarErr && (
            <Alert intent="danger" title="Não foi possível rejeitar">
              {rejeitarErr}
            </Alert>
          )}
        </form>
      </Dialog>

      <Dialog
        open={designarOpen}
        onClose={closeDesignar}
        title="Designar veículo e motorista"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={closeDesignar}>
              Cancelar
            </Button>
            <Button type="submit" form="form-designar" loading={designarM.isPending}>
              {designarSol?.id_veiculo_designado ? "Trocar designação" : "Designar"}
            </Button>
          </>
        }
      >
        <form
          id="form-designar"
          noValidate
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            salvarDesignar();
          }}
        >
          {designarSol && <ResumoSolicitacao s={designarSol} />}
          <FormField
            label="Veículo"
            required
            hint={
              veiculosDisponiveis.length === 0
                ? "Nenhum veículo disponível agora — os em uso ou em manutenção não aparecem."
                : "Só aparecem os veículos disponíveis."
            }
            error={camposDesignar.erro("d_veiculo")}
          >
            <Select
              id="d_veiculo"
              value={designarForm.id_veiculo ?? ""}
              onChange={(e) =>
                setDesignarForm((f) => ({
                  ...f,
                  id_veiculo: e.target.value ? Number(e.target.value) : null,
                }))
              }
              onBlur={camposDesignar.tocar("d_veiculo")}
            >
              <option value="">Selecione o veículo</option>
              {veiculosDisponiveis.map((v) => (
                <option key={v.id} value={v.id}>
                  {rotuloVeiculo(v)}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField
            label="Motorista"
            required={designarSol?.necessita_motorista}
            opcional={!designarSol?.necessita_motorista}
            hint={
              designarSol?.necessita_motorista
                ? "Esta solicitação pede motorista. Só aparecem os ativos."
                : "Em branco, quem pediu dirige. Só aparecem os ativos."
            }
            error={camposDesignar.erro("d_motorista")}
          >
            <Select
              id="d_motorista"
              value={designarForm.id_motorista ?? ""}
              onChange={(e) =>
                setDesignarForm((f) => ({
                  ...f,
                  id_motorista: e.target.value ? Number(e.target.value) : null,
                }))
              }
              onBlur={camposDesignar.tocar("d_motorista")}
            >
              <option value="">{designarSol?.necessita_motorista ? "Selecione o motorista" : "Sem motorista"}</option>
              {motoristasAtivos.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nome}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label="Observações" opcional>
            <Textarea
              id="d_obs"
              rows={2}
              value={designarForm.observacoes_designacao}
              onChange={(e) =>
                setDesignarForm((f) => ({ ...f, observacoes_designacao: e.target.value }))
              }
              placeholder="Ex.: retirar a chave na portaria às 7h"
              maxLength={2000}
            />
          </FormField>
          {designarErr && (
            <Alert intent="danger" title="Não foi possível designar">
              {designarErr}
            </Alert>
          )}
        </form>
      </Dialog>

      <Dialog
        open={saidaOpen}
        onClose={closeSaida}
        title="Registrar saída"
        description="A data e a hora da saída são registradas agora, automaticamente."
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={closeSaida}>
              Cancelar
            </Button>
            <Button type="submit" form="form-saida" loading={registrarSaidaM.isPending}>
              Registrar saída
            </Button>
          </>
        }
      >
        <form
          id="form-saida"
          noValidate
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            salvarSaida();
          }}
        >
          {saidaSol && (
            <ResumoSolicitacao
              s={saidaSol}
              extra={[
                veiculoLabel(saidaSol.id_veiculo_designado),
                saidaSol.id_motorista_designado ? motoristaNome(saidaSol.id_motorista_designado) : "Sem motorista",
              ]
                .filter(Boolean)
                .join(" · ")}
            />
          )}
          <FormField
            label="Quilometragem na saída"
            required
            hint={
              kmMinimoSaida != null
                ? `O que marca o painel agora. Último registro do veículo: ${fmtKm(kmMinimoSaida)}.`
                : "O que marca o painel agora."
            }
            error={camposSaida.erro("km_saida")}
          >
            <CampoComUnidade
              id="km_saida"
              type="number"
              inputMode="numeric"
              min={kmMinimoSaida ?? 0}
              sufixo="km"
              value={saidaForm.km_saida}
              onChange={(e) => setSaidaForm((f) => ({ ...f, km_saida: e.target.value }))}
              onBlur={camposSaida.tocar("km_saida")}
              placeholder={kmMinimoSaida != null ? `Ex.: ${kmMinimoSaida}` : undefined}
            />
          </FormField>
          <FormField label="Observações" opcional>
            <Textarea
              id="obs_saida"
              rows={2}
              value={saidaForm.observacoes_saida}
              onChange={(e) => setSaidaForm((f) => ({ ...f, observacoes_saida: e.target.value }))}
              placeholder="Ex.: tanque cheio; arranhão na porta traseira já existente"
              maxLength={2000}
            />
          </FormField>
          {saidaErr && (
            <Alert intent="danger" title="Não foi possível registrar a saída">
              {saidaErr}
            </Alert>
          )}
        </form>
      </Dialog>

      <Dialog
        open={retornoOpen}
        onClose={closeRetorno}
        title="Registrar retorno"
        description="A data e a hora do retorno são registradas agora. A quilometragem informada passa a ser a do veículo."
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={closeRetorno}>
              Cancelar
            </Button>
            <Button type="submit" form="form-retorno" loading={registrarRetornoM.isPending}>
              Registrar retorno
            </Button>
          </>
        }
      >
        <form
          id="form-retorno"
          noValidate
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            salvarRetorno();
          }}
        >
          {retornoSol && (
            <ResumoSolicitacao
              s={retornoSol}
              extra={[
                veiculoLabel(retornoSol.id_veiculo_designado),
                retornoSol.data_saida_real &&
                  `saiu ${fmtDataHora(retornoSol.data_saida_real)}${retornoSol.km_saida != null ? ` com ${fmtKm(retornoSol.km_saida)}` : ""}`,
              ]
                .filter(Boolean)
                .join(" · ")}
            />
          )}
          <FormField
            label="Quilometragem no retorno"
            required
            hint={
              percorrido != null
                ? `Percorridos nesta viagem: ${fmtKm(percorrido)}.`
                : retornoSol?.km_saida != null
                  ? `Saiu com ${fmtKm(retornoSol.km_saida)}; o retorno não pode ser menor.`
                  : "O que marca o painel na chegada."
            }
            error={camposRetorno.erro("km_retorno")}
          >
            <CampoComUnidade
              id="km_retorno"
              type="number"
              inputMode="numeric"
              min={retornoSol?.km_saida ?? 0}
              sufixo="km"
              value={retornoForm.km_retorno}
              onChange={(e) => setRetornoForm((f) => ({ ...f, km_retorno: e.target.value }))}
              onBlur={camposRetorno.tocar("km_retorno")}
            />
          </FormField>
          <FormField label="Observações" opcional>
            <Textarea
              id="obs_retorno"
              rows={2}
              value={retornoForm.observacoes_retorno}
              onChange={(e) =>
                setRetornoForm((f) => ({ ...f, observacoes_retorno: e.target.value }))
              }
              placeholder="Ex.: pneu dianteiro calibrado na volta"
              maxLength={2000}
            />
          </FormField>
          {retornoErr && (
            <Alert intent="danger" title="Não foi possível registrar o retorno">
              {retornoErr}
            </Alert>
          )}
        </form>
      </Dialog>
    </div>
  );
}
