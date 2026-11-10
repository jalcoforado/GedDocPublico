"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Banknote,
  ClipboardList,
  Download,
  FileEdit,
  FileText,
  Flag,
  History,
  Layers,
  ListOrdered,
  Paperclip,
  Percent,
  Receipt,
  Trash2,
  Undo2,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SectionCard } from "@/components/ui/section-card";
import { Skeleton } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  AcaoParcelaDialog,
  PagarParcelaDialog,
  RecolherRetencaoDialog,
  type AcaoParcela,
} from "@/components/pagamentos/AcoesFinanceirasDialogs";
import {
  ChecklistDebito,
  chaveChecklist,
  pendentesDoChecklist,
} from "@/components/pagamentos/ChecklistDebito";
import { TRAMITACOES_EDITAVEIS } from "@/components/pagamentos/EditarDebitoContent";
import { EtapasFluxo } from "@/components/pagamentos/EtapasFluxo";
import { CATEGORIAS_DEBITO } from "@/components/pagamentos/FormularioDebito";
import { ProximaAcao } from "@/components/pagamentos/ProximaAcao";
import { SituacoesDebito } from "@/components/pagamentos/SituacoesDebito";
import {
  FILA_ROTULO,
  PARCELA_ROTULO,
  PEDIDO_AJUSTE_ROTULO,
  TRAMITACAO_ROTULO,
  TRANSACAO_PAGAMENTOS,
  TRANSACAO_PAGAMENTOS_ROTULO,
} from "@/components/pagamentos/situacoes";
import { fmtCompetencia, fmtData, fmtDataHora, fmtMoeda, fmtTamanho } from "@/components/pagamentos/format";
import { useValidacaoCampos } from "@/components/pagamentos/useValidacaoCampos";
import {
  ApiError,
  api,
  type AnexoDebitoOut,
  type DebitoOut,
  type EtapaAjuste,
  type Parcela,
  type Retencao,
  type RetencaoInput,
  type SituacaoFila,
  type TipoAjuste,
  type TipoRetencao,
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
 * Texto do diálogo de cada ação do fluxo: título, uma frase do que acontece
 * e o verbo do botão principal (era "Confirmar" para tudo — quem clicava não
 * lia ali o que estava fazendo). `perigo` = botão vermelho.
 */
const ACAO_DIALOGO: Record<string, { titulo: string; descricao?: string; verbo: string; perigo?: boolean }> = {
  enviar: {
    titulo: "Enviar para o gestor",
    descricao: "A solicitação sai do rascunho e vai para a análise do gestor da pasta.",
    verbo: "Enviar para o gestor",
  },
  "gestor/autorizar": {
    titulo: "Autorizar",
    descricao: "A solicitação segue para a validação financeira.",
    verbo: "Autorizar",
  },
  "gestor/rejeitar": {
    titulo: "Rejeitar",
    descricao: "A solicitação é encerrada sem pagamento.",
    verbo: "Rejeitar solicitação",
    perigo: true,
  },
  validar: {
    titulo: "Validar",
    descricao: "Confirma a conformidade dos documentos e envia para a autoridade.",
    verbo: "Confirmar validação",
  },
  "autoridade/aprovar": {
    titulo: "Aprovar e ordenar pagamento",
    verbo: "Aprovar e ordenar",
  },
  "autoridade/indeferir": {
    titulo: "Indeferir",
    descricao: "A solicitação é encerrada sem pagamento.",
    verbo: "Indeferir solicitação",
    perigo: true,
  },
  "ajuste/solicitar": {
    titulo: "Solicitar ajuste",
    descricao: "A solicitação volta para quem precisa corrigir, com o pedido abaixo.",
    verbo: "Pedir ajuste",
  },
  "ajuste/adicional": {
    titulo: "Novo pedido de ajuste",
    descricao: "Soma um pedido aos que já estão abertos nesta solicitação.",
    verbo: "Abrir pedido de ajuste",
  },
  "ajuste/responder": {
    titulo: "Responder ajuste",
    descricao: "A solicitação volta para análise.",
    verbo: "Enviar resposta",
  },
  cancelar: {
    titulo: "Cancelar solicitação",
    descricao: "A solicitação sai do fluxo e não pode ser retomada.",
    verbo: "Cancelar solicitação",
    perigo: true,
  },
};

/** "aaaa-mm-dd" de hoje no horário local (o toISOString() é UTC). */
function hojeLocal(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

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

  // Aprovação pela autoridade: conta pagadora e, se faltar saldo, a exceção.
  const [contaPagadora, setContaPagadora] = useState("");
  const [semSaldoAutorizado, setSemSaldoAutorizado] = useState(false);
  const [justificativaExcecao, setJustificativaExcecao] = useState("");

  // Estorno / revogação de liberação de uma parcela, e recolhimento de retenção.
  const [acaoParcela, setAcaoParcela] = useState<{ acao: AcaoParcela; parcela: Parcela } | null>(
    null,
  );
  const [retencaoARecolher, setRetencaoARecolher] = useState<Retencao | null>(null);
  const [parcelaAPagar, setParcelaAPagar] = useState<Parcela | null>(null);

  // Resposta a um pedido de ajuste específico
  const [respostaPorPedido, setRespostaPorPedido] = useState<Record<number, string>>({});

  // Documentos do débito (F2, Task 8)
  const [anexoArquivo, setAnexoArquivo] = useState<File | null>(null);
  const [anexoDescricao, setAnexoDescricao] = useState("");
  const [anexoPedidoId, setAnexoPedidoId] = useState<number | "">("");
  const [confirmRemoverAnexo, setConfirmRemoverAnexo] = useState<AnexoDebitoOut | null>(null);

  // Exceção formal à ordem cronológica (F3, Task 5/6)
  const [excecaoOpen, setExcecaoOpen] = useState(false);
  const [excecaoJustificativa, setExcecaoJustificativa] = useState("");
  const [excecaoFundamento, setExcecaoFundamento] = useState("");
  const [excecaoData, setExcecaoData] = useState("");

  // Retenções (F4) — CRUD travado pelo backend (409) enquanto a parcela
  // estiver engajada num lote de pagamento.
  const [retencaoOpen, setRetencaoOpen] = useState(false);
  const [retencaoTipo, setRetencaoTipo] = useState<TipoRetencao>("IRRF");
  const [retencaoDescricao, setRetencaoDescricao] = useState("");
  const [retencaoBase, setRetencaoBase] = useState("");
  const [retencaoAliquota, setRetencaoAliquota] = useState("");
  const [retencaoValor, setRetencaoValor] = useState("");
  // Valor retido calculado de base × alíquota até a pessoa digitar outro.
  const [valorRetencaoCalculado, setValorRetencaoCalculado] = useState(false);

  function mudarBaseOuAliquota(base: string, aliquota: string) {
    setRetencaoBase(base);
    setRetencaoAliquota(aliquota);
    const b = Number(base);
    const a = Number(aliquota);
    if ((valorRetencaoCalculado || !retencaoValor) && b > 0 && a > 0) {
      setRetencaoValor(((b * a) / 100).toFixed(2));
      setValorRetencaoCalculado(true);
    }
  }

  const vRetencao = useValidacaoCampos(
    {
      base: !(Number(retencaoBase) > 0) && "Informe a base de cálculo, ex.: 1000,00.",
      valor: !(Number(retencaoValor) > 0) && "Informe o valor retido, ou a alíquota para calcular.",
    },
    { base: "ret-base", valor: "ret-valor" },
  );
  const vExcecao = useValidacaoCampos(
    {
      fundamento: !excecaoFundamento.trim() && "Cite o dispositivo legal que permite a exceção.",
      justificativa:
        !excecaoJustificativa.trim() && "Explique por que esta solicitação passa à frente.",
      data: !excecaoData && "Informe a data da autorização.",
    },
    { fundamento: "exc-fundamento", justificativa: "exc-justificativa", data: "exc-data" },
  );

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

  // Retenções (F4)
  const retencoesQ = useQuery({
    queryKey: ["pag-retencoes", id],
    queryFn: () => api.pagamentos.retencoes.listarDoDebito(id),
  });
  const retencoes = retencoesQ.data?.retencoes ?? [];

  // Posição na fila cronológica (F3) — 404 é esperado para débito legado que
  // ainda não passou pela fase de liquidação (não vira erro na tela).
  const posicaoFilaQ = useQuery({
    queryKey: ["pag-posicao-fila", id],
    queryFn: async () => {
      try {
        return await api.pagamentos.debitos.posicaoDebito(id);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
  });

  const excecoesQ = useQuery({
    queryKey: ["pag-excecoes", id],
    queryFn: () => api.pagamentos.debitos.listarExcecoes(id),
  });
  const excecoes = excecoesQ.data ?? [];

  // Mesma chave da seção "Conferência de documentos": uma requisição só, e o
  // diálogo de validação enxerga a marcação assim que ela é feita.
  const checklistQ = useQuery({
    queryKey: chaveChecklist(id),
    queryFn: () => api.pagamentos.debitos.checklist(id),
  });
  const checklistPendente = pendentesDoChecklist(checklistQ.data);

  // Contas que podem pagar este débito: as da fonte dele. Só interessa a quem
  // está com o diálogo de aprovação aberto.
  const aprovando = openDialog && acaoSelecionada === "autoridade/aprovar";
  const contasQ = useQuery({
    queryKey: ["pag-contas-elegiveis", debito?.id_fonte_recursos],
    queryFn: () => api.pagamentos.contasElegiveis(debito!.id_fonte_recursos),
    enabled: aprovando && !!debito,
  });
  const contasElegiveis = contasQ.data ?? [];
  const contaEscolhida = contasElegiveis.find((c) => String(c.id_conta) === contaPagadora);
  const faltaSaldo =
    !!contaEscolhida && !!debito && Number(contaEscolhida.disponivel) < Number(debito.valor_total);
  // Sem conta para escolher, não há o que preencher: o botão fica travado
  // (é um impedimento, não um campo faltando) e o diálogo diz por quê.
  const semContaParaEscolher =
    aprovando && (contasQ.isLoading || contasQ.isError || contasElegiveis.length === 0);

  // Erros do diálogo de ação — aparecem só depois de sair do campo ou de
  // clicar no botão principal, que não fica mais desabilitado por isso.
  const acaoPedeJustificativa = ["gestor/rejeitar", "autoridade/indeferir", "cancelar"].includes(
    acaoSelecionada ?? "",
  );
  const acaoEhPedidoAjuste =
    acaoSelecionada === "ajuste/solicitar" || acaoSelecionada === "ajuste/adicional";
  const vAcao = useValidacaoCampos(
    {
      conta:
        acaoSelecionada === "autoridade/aprovar" &&
        !semContaParaEscolher &&
        !contaEscolhida &&
        "Escolha a conta de onde sai o pagamento.",
      excecao:
        acaoSelecionada === "autoridade/aprovar" &&
        faltaSaldo &&
        !semSaldoAutorizado &&
        "Esta conta não cobre o valor. Escolha outra ou autorize como exceção.",
      justificativaExcecao:
        acaoSelecionada === "autoridade/aprovar" &&
        faltaSaldo &&
        semSaldoAutorizado &&
        !justificativaExcecao.trim() &&
        "Explique por que autorizar sem saldo — fica registrado na exceção.",
      justificativa:
        acaoPedeJustificativa &&
        !justificativa.trim() &&
        "Explique o motivo — fica no histórico da solicitação.",
      ajusteMotivo:
        acaoEhPedidoAjuste && !ajusteMotivo.trim() && "Resuma em uma linha o que precisa mudar.",
      ajusteDescricao:
        acaoEhPedidoAjuste &&
        !ajusteDescricao.trim() &&
        "Detalhe o que precisa ser corrigido, para quem ajusta não ter de perguntar.",
      ajusteTransacao: acaoEhPedidoAjuste && !ajusteTransacao && "Escolha quem deve fazer o ajuste.",
    },
    {
      conta: "acao-conta",
      excecao: "acao-excecao",
      justificativaExcecao: "acao-excecao-justificativa",
      justificativa: "acao-justificativa",
      ajusteMotivo: "ajuste-motivo",
      ajusteDescricao: "ajuste-descricao",
      ajusteTransacao: "ajuste-transacao",
    },
  );

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
    qc.invalidateQueries({ queryKey: ["pag-posicao-fila", id] });
    qc.invalidateQueries({ queryKey: ["pag-excecoes", id] });
    qc.invalidateQueries({ queryKey: chaveChecklist(id) });
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
        id_conta_pagadora: Number(contaPagadora),
        permitir_saldo_insuficiente: faltaSaldo && semSaldoAutorizado,
        justificativa_excecao:
          faltaSaldo && semSaldoAutorizado ? justificativaExcecao.trim() : null,
      }),
    onSuccess: () => {
      toast.success("Pagamento autorizado e ordem de pagamento gerada");
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

  // Etapa opcional da tesouraria: o pagamento foi despachado ao banco e
  // aguarda confirmação. Só existe a partir de "programada".
  const emProcessamentoM = useMutation({
    mutationFn: () => api.pagamentos.debitos.emProcessamento(id),
    onSuccess: () => {
      toast.success("Marcado como enviado ao banco");
      invalidarTudo();
    },
    onError: (err: any) => toast.error(err.message || "Erro ao marcar como enviado ao banco"),
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

  const criarRetencaoM = useMutation({
    mutationFn: () => {
      const payload: RetencaoInput = {
        tipo: retencaoTipo,
        descricao: retencaoDescricao || undefined,
        base_calculo: retencaoBase,
        aliquota: retencaoAliquota || undefined,
        valor: retencaoValor,
      };
      return api.pagamentos.retencoes.criar(id, payload);
    },
    onSuccess: () => {
      toast.success("Retenção lançada");
      setRetencaoOpen(false);
      setRetencaoDescricao(""); setRetencaoBase(""); setRetencaoAliquota(""); setRetencaoValor("");
      qc.invalidateQueries({ queryKey: ["pag-retencoes", id] });
    },
    onError: (err: any) => toast.error(err.message || "Erro ao lançar retenção"),
  });

  const excluirRetencaoM = useMutation({
    mutationFn: (retencaoId: number) => api.pagamentos.retencoes.excluir(retencaoId),
    onSuccess: () => {
      toast.success("Retenção removida");
      qc.invalidateQueries({ queryKey: ["pag-retencoes", id] });
    },
    onError: (err: any) => toast.error(err.message || "Erro ao remover retenção"),
  });

  const registrarExcecaoM = useMutation({
    mutationFn: () =>
      api.pagamentos.debitos.registrarExcecao(id, {
        justificativa: excecaoJustificativa,
        fundamento: excecaoFundamento,
        data_autorizacao: excecaoData,
      }),
    onSuccess: () => {
      toast.success("Exceção cronológica autorizada");
      setExcecaoOpen(false);
      setExcecaoJustificativa("");
      setExcecaoFundamento("");
      setExcecaoData("");
      qc.invalidateQueries({ queryKey: ["pag-posicao-fila", id] });
      qc.invalidateQueries({ queryKey: ["pag-excecoes", id] });
    },
    onError: (err: any) => toast.error(err.message || "Erro ao autorizar exceção"),
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

  const dialogEhFormularioRico =
    acaoSelecionada === "ajuste/solicitar" || acaoSelecionada === "ajuste/adicional";
  const acaoEmAndamento = [
    enviarGestorM, gestorAutorizarM, gestorRejeitarM, validarM, autoridadeAprovarM,
    autoridadeIndeferirM, solicitarAjusteM, criarPedidoAjusteM, responderAjusteM, cancelarM,
  ].some((m) => m.isPending);
  const dialogEhJustificativa =
    ["gestor/rejeitar", "autoridade/indeferir", "cancelar"].includes(acaoSelecionada ?? "");
  // O backend recusa a validação com item obrigatório pendente (422). Avisar
  // antes poupa o clique e diz exatamente o que falta.
  const validacaoTravadaPeloChecklist =
    acaoSelecionada === "validar" && checklistPendente.length > 0;
  const podeEditar =
    TRAMITACOES_EDITAVEIS.includes(debito.situacao_tramitacao) && can("pagamento_solicitar");
  const podeConferirDocumentos =
    debito.situacao_tramitacao === "AGUARDANDO_VALIDACAO" && can("pagamento_validar");

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={breadcrumbs}
        title={`Solicitação #${debito.id}`}
        description={debito.nome_fornecedor}
        icon={FileText}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Badge intent={rotulo.intent} icon={rotulo.icon}>{rotulo.label}</Badge>
            {podeEditar && (
              <Button asChild variant="secondary" size="sm">
                <Link href={`/m/pagamentos/solicitacoes/${debito.id}/editar`}>
                  <FileEdit className="h-4 w-4" aria-hidden="true" />
                  Editar solicitação
                </Link>
              </Button>
            )}
          </div>
        }
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
                <div className="text-xs font-medium text-foreground-muted">Valor total</div>
                <div className="tabular-nums text-foreground">{fmtMoeda(debito.valor_total)}</div>
              </div>
              <div className="sm:col-span-2">
                <div className="text-xs font-medium text-foreground-muted">Descrição</div>
                <div className="text-foreground">{debito.descricao}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-foreground-muted">Competência</div>
                <div className="text-foreground">{fmtCompetencia(debito.competencia)}</div>
              </div>
              {!debito.id_contrato && (
                <div>
                  <div className="text-xs font-medium text-foreground-muted">Categoria</div>
                  <div className="text-foreground">
                    {CATEGORIAS_DEBITO.find((c) => c.value === debito.categoria)?.label ?? "—"}
                  </div>
                </div>
              )}
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
                      <TH>Situação</TH>
                      <TH className="text-right">Ações</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {debitoQ.data.parcelas.map((p) => (
                      <TR key={p.id}>
                        <TD>{p.numero}</TD>
                        <TD className="text-right tabular-nums">{fmtMoeda(p.valor)}</TD>
                        <TD>{fmtData(p.vencimento)}</TD>
                        <TD>
                          <Badge
                            intent={PARCELA_ROTULO[p.status]?.intent ?? "neutral"}
                            icon={PARCELA_ROTULO[p.status]?.icon}
                          >
                            {PARCELA_ROTULO[p.status]?.label ?? p.status}
                          </Badge>
                        </TD>
                        <TD className="text-right">
                          {/* Estornar só vale para PAGA; Pagar e Revogar, para
                              LIBERADA — no máximo duas por linha, todas à vista
                              (os testes e o leitor de tela as acham pelo nome). */}
                          <AcoesDaLinha
                            acoes={[
                              {
                                label: "Pagar",
                                icon: Banknote,
                                ariaLabel: `Registrar pagamento da parcela ${p.numero}`,
                                oculta: !(p.status === "LIBERADA" && can("pagamento_pagar")),
                                onClick: () => setParcelaAPagar(p),
                              },
                              {
                                label: "Revogar liberação",
                                icon: Undo2,
                                perigo: true,
                                ariaLabel: `Revogar liberação da parcela ${p.numero}`,
                                oculta: !(p.status === "LIBERADA" && can("pagamento_autorizar")),
                                onClick: () => setAcaoParcela({ acao: "revogar", parcela: p }),
                              },
                              {
                                label: "Estornar",
                                icon: Undo2,
                                perigo: true,
                                ariaLabel: `Estornar pagamento da parcela ${p.numero}`,
                                oculta: !(p.status === "PAGA" && can("pagamento_pagar")),
                                onClick: () => setAcaoParcela({ acao: "estornar", parcela: p }),
                              },
                            ]}
                          />
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

          {/* Retenções (F4) */}
          <SectionCard title="Retenções" icon={Percent}>
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm text-foreground-subtle">
                  Bruto <span className="font-semibold tabular-nums text-foreground">
                    {fmtMoeda(retencoesQ.data?.valor_bruto ?? debito?.valor_total ?? "0")}
                  </span>
                  {" · "}Líquido <span className="font-semibold tabular-nums text-foreground">
                    {fmtMoeda(retencoesQ.data?.valor_liquido ?? debito?.valor_total ?? "0")}
                  </span>
                </p>
                {can("pagamento_pagar") && (
                  <Button size="sm" variant="secondary" onClick={() => {
                      setValorRetencaoCalculado(false);
                      vRetencao.reiniciar();
                      setRetencaoOpen(true);
                    }}>
                    Lançar retenção
                  </Button>
                )}
              </div>

              {retencoesQ.isLoading ? (
                <Skeleton className="h-16 w-full" />
              ) : retencoes.length === 0 ? (
                <p className="text-sm text-foreground-subtle">Nenhuma retenção lançada.</p>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <THead>
                      <TR>
                        <TH>Tipo</TH>
                        <TH>Descrição</TH>
                        <TH className="text-right">Base</TH>
                        <TH className="text-right">Alíquota</TH>
                        <TH className="text-right">Valor</TH>
                        <TH>Recolhimento</TH>
                        <TH className="text-right">Ações</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {retencoes.map((r) => (
                        <TR key={r.id}>
                          <TD>{r.tipo}</TD>
                          <TD className="max-w-[16rem] truncate">{r.descricao ?? "—"}</TD>
                          <TD className="text-right tabular-nums">{fmtMoeda(r.base_calculo)}</TD>
                          <TD className="text-right tabular-nums">{r.aliquota ? `${r.aliquota}%` : "—"}</TD>
                          <TD className="text-right tabular-nums">{fmtMoeda(r.valor)}</TD>
                          <TD>
                            {r.recolhido ? (
                              <Badge intent="success">Recolhida em {fmtData(r.data_recolhimento)}</Badge>
                            ) : (
                              <Badge intent="neutral">Pendente</Badge>
                            )}
                          </TD>
                          <TD className="text-right">
                            <AcoesDaLinha
                              acoes={[
                                {
                                  label: "Recolher",
                                  ariaLabel: `Registrar recolhimento da retenção ${r.tipo}`,
                                  oculta: !(can("pagamento_pagar") && !r.recolhido),
                                  onClick: () => setRetencaoARecolher(r),
                                },
                                {
                                  label: "Remover",
                                  icon: Trash2,
                                  perigo: true,
                                  ariaLabel: `Remover retenção ${r.tipo}`,
                                  oculta: !(can("pagamento_pagar") && !r.recolhido),
                                  disabled: excluirRetencaoM.isPending,
                                  onClick: () => excluirRetencaoM.mutate(r.id),
                                },
                              ]}
                            />
                          </TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                </div>
              )}
            </div>
          </SectionCard>

          {/* Fila cronológica (F3, Task 3/5) */}
          <SectionCard title="Fila cronológica" icon={ListOrdered}>
            {posicaoFilaQ.isLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : !posicaoFilaQ.data ? (
              <p className="text-sm text-foreground-subtle">
                Não registrado na fila cronológica — a posição só existe a partir da
                liquidação da despesa.
              </p>
            ) : (
              <div className="space-y-3">
                {(() => {
                  const posicaoFila = posicaoFilaQ.data;
                  const rotuloFila =
                    FILA_ROTULO[posicaoFila.situacao as SituacaoFila] ??
                    ({ label: posicaoFila.situacao, intent: "neutral", icon: ListOrdered } as const);
                  return (
                    <>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-foreground">
                          Posição {posicaoFila.posicao} de {posicaoFila.total_grupo} na fila
                        </span>
                        <Badge intent={rotuloFila.intent} icon={rotuloFila.icon}>
                          {rotuloFila.label}
                        </Badge>
                      </div>
                      {posicaoFila.motivo_bloqueio && (
                        <p className="text-sm text-foreground-muted">
                          Motivo: {posicaoFila.motivo_bloqueio}
                        </p>
                      )}
                      <p className="text-xs text-foreground-muted">
                        Marco na fila: {fmtDataHora(posicaoFila.marco_em)}
                      </p>
                    </>
                  );
                })()}

                {excecoes.length > 0 && (
                  <div className="space-y-2 border-t border-border pt-3">
                    <div className="flex items-center gap-1.5 text-sm font-medium text-foreground">
                      <Flag className="h-4 w-4 text-warning-soft-foreground" aria-hidden="true" />
                      Exceções cronológicas autorizadas
                    </div>
                    {excecoes.map((e) => (
                      <div key={e.id} className="rounded-lg border border-border p-3 text-sm">
                        <p className="font-medium text-foreground">
                          {e.fundamento} — autorizada em {fmtData(e.data_autorizacao)}
                        </p>
                        <p className="mt-1 text-foreground-muted">{e.justificativa}</p>
                      </div>
                    ))}
                  </div>
                )}

                {can("pagamento_autorizar") && (
                  <div className="border-t border-border pt-3">
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setExcecaoJustificativa("");
                        setExcecaoFundamento("");
                        // A autorização costuma ser registrada no dia em que é dada.
                        setExcecaoData(hojeLocal());
                        vExcecao.reiniciar();
                        setExcecaoOpen(true);
                      }}
                    >
                      Autorizar exceção cronológica
                    </Button>
                  </div>
                )}
              </div>
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
                      setAjusteTransacao("pagamento_solicitar");
                      vAcao.reiniciar();
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

          <ChecklistDebito id={id} editavel={podeConferirDocumentos} />

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
                          <TD>{a.nome_usuario ?? (a.id_usuario ? `Usuário #${a.id_usuario}` : "—")}</TD>
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
          {debito.situacao_pagamento === "PROGRAMADA" && can("pagamento_pagar") && (
            <Button
              variant="secondary"
              className="w-full"
              onClick={() => emProcessamentoM.mutate()}
              disabled={emProcessamentoM.isPending}
            >
              Marcar como enviado ao banco
            </Button>
          )}
          <ProximaAcao
            tramitacao={debito.situacao_tramitacao}
            perfis={perfis}
            onAction={(acao, etapa) => {
              setJustificativa("");
              resetFormAjuste();
              setContaPagadora("");
              setSemSaldoAutorizado(false);
              setJustificativaExcecao("");
              // Quem ajusta: quase sempre a unidade que pediu — vem preenchido.
              setAjusteTransacao("pagamento_solicitar");
              vAcao.reiniciar();
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

      {/* Dialog para ações. O botão principal diz o verbo da ação (não
          "Confirmar"); só trava quando há um impedimento que o formulário não
          resolve (checklist pendente, nenhuma conta para escolher). Campo
          faltando não trava: clicar é o que mostra o que falta. */}
      <Dialog
        open={openDialog}
        onClose={() => setOpenDialog(false)}
        size={dialogEhFormularioRico ? "lg" : "md"}
        title={ACAO_DIALOGO[acaoSelecionada ?? "cancelar"]?.titulo ?? "Cancelar solicitação"}
        description={ACAO_DIALOGO[acaoSelecionada ?? "cancelar"]?.descricao}
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpenDialog(false)}>
              {acaoSelecionada === "cancelar" ? "Voltar" : "Cancelar"}
            </Button>
            <Button
              variant={ACAO_DIALOGO[acaoSelecionada ?? "cancelar"]?.perigo ? "danger" : "primary"}
              onClick={() => {
                if (!vAcao.conferir()) return;
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
              disabled={validacaoTravadaPeloChecklist || semContaParaEscolher}
              loading={acaoEmAndamento}
            >
              {ACAO_DIALOGO[acaoSelecionada ?? "cancelar"]?.verbo ?? "Confirmar"}
            </Button>
          </>
        }
      >
        {validacaoTravadaPeloChecklist && (
          <div role="alert" className="space-y-2 text-sm text-foreground">
            <p>Antes de validar, confira na seção &ldquo;Conferência de documentos&rdquo;:</p>
            <ul className="list-disc space-y-1 pl-5 text-foreground-muted">
              {checklistPendente.map((i) => (
                <li key={i.id_checklist_item}>{i.descricao}</li>
              ))}
            </ul>
          </div>
        )}

        {acaoSelecionada === "autoridade/aprovar" && (
          <div className="space-y-4">
            <p className="text-sm text-foreground-muted">
              Aprovar reserva {fmtMoeda(debito.valor_total)} na conta escolhida e gera a ordem de
              pagamento. A conta não pode ser trocada depois.
            </p>
            {contasQ.isLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : contasQ.isError ? (
              <p role="alert" className="text-sm text-danger-soft-foreground">
                Não foi possível carregar as contas desta fonte de recursos.
              </p>
            ) : contasElegiveis.length === 0 ? (
              <p role="alert" className="text-sm text-foreground">
                Nenhuma conta pagadora ativa na fonte de recursos desta solicitação. Cadastre ou
                ative uma conta em Cadastros antes de aprovar.
              </p>
            ) : (
              <FormField
                label="Conta pagadora"
                required
                error={vAcao.erro("conta")}
                hint="Só aparecem as contas ativas da fonte desta solicitação que podem pagar."
              >
                <Select
                  id="acao-conta"
                  value={contaPagadora}
                  onChange={(e) => setContaPagadora(e.target.value)}
                >
                  <option value="">Escolha a conta</option>
                  {contasElegiveis.map((c) => (
                    <option key={c.id_conta} value={c.id_conta}>
                      {c.nome} — disponível {fmtMoeda(c.disponivel)}
                    </option>
                  ))}
                </Select>
              </FormField>
            )}
            {faltaSaldo && contaEscolhida && (
              <div
                role="alert"
                className="space-y-3 rounded-lg border border-warning/40 bg-warning-soft p-3 text-sm text-warning-soft-foreground"
              >
                <p>
                  O disponível desta conta ({fmtMoeda(contaEscolhida.disponivel)}) não cobre o valor
                  da solicitação ({fmtMoeda(debito.valor_total)}).
                </p>
                <label className="flex items-start gap-2">
                  <input
                    id="acao-excecao"
                    type="checkbox"
                    checked={semSaldoAutorizado}
                    onChange={(e) => setSemSaldoAutorizado(e.target.checked)}
                    aria-invalid={vAcao.erro("excecao") ? true : undefined}
                    aria-describedby={vAcao.erro("excecao") ? "acao-excecao-erro" : undefined}
                    className="mt-0.5 h-4 w-4 shrink-0"
                  />
                  Autorizar mesmo assim, como exceção registrada
                </label>
                {vAcao.erro("excecao") && (
                  <p id="acao-excecao-erro" className="text-xs font-medium">
                    {vAcao.erro("excecao")}
                  </p>
                )}
                {semSaldoAutorizado && (
                  <FormField
                    label="Justificativa da exceção"
                    required
                    error={vAcao.erro("justificativaExcecao")}
                    hint="Fica registrada junto da exceção de saldo. Até 255 caracteres."
                  >
                    <Textarea
                      id="acao-excecao-justificativa"
                      value={justificativaExcecao}
                      onChange={(e) => setJustificativaExcecao(e.target.value)}
                      onBlur={vAcao.tocar("justificativaExcecao")}
                      maxLength={255}
                      placeholder="Ex.: Decisão judicial com prazo de cumprimento até sexta."
                      className="min-h-20"
                    />
                  </FormField>
                )}
              </div>
            )}
          </div>
        )}

        {dialogEhJustificativa && (
          <FormField
            label="Justificativa"
            required
            error={vAcao.erro("justificativa")}
            hint={
              acaoSelecionada === "cancelar"
                ? "Fica no histórico. A solicitação cancelada não volta ao fluxo."
                : "Quem pediu vai ler isto no histórico da solicitação."
            }
          >
            <Textarea
              id="acao-justificativa"
              value={justificativa}
              onChange={(e) => setJustificativa(e.target.value)}
              onBlur={vAcao.tocar("justificativa")}
              placeholder={
                acaoSelecionada === "cancelar"
                  ? "Ex.: Despesa lançada em duplicidade com a solicitação 123."
                  : "Ex.: Valor diverge da nota fiscal anexada."
              }
              className="min-h-24"
            />
          </FormField>
        )}

        {dialogEhFormularioRico && (
          <div className="space-y-4">
            <FormField label="Motivo" required error={vAcao.erro("ajusteMotivo")}>
              <Input
                id="ajuste-motivo"
                value={ajusteMotivo}
                onChange={(e) => setAjusteMotivo(e.target.value)}
                onBlur={vAcao.tocar("ajusteMotivo")}
                placeholder="Ex.: Nota fiscal com valor diferente"
                maxLength={255}
              />
            </FormField>
            <FormField label="O que corrigir" required error={vAcao.erro("ajusteDescricao")}>
              <Textarea
                id="ajuste-descricao"
                value={ajusteDescricao}
                onChange={(e) => setAjusteDescricao(e.target.value)}
                onBlur={vAcao.tocar("ajusteDescricao")}
                placeholder="Ex.: A NF 4587 é de R$ 1.200,00 e a solicitação está com R$ 1.250,00. Corrija o valor ou anexe a nota certa."
                className="min-h-24"
              />
            </FormField>
            <FormField
              label="Quem ajusta"
              required
              error={vAcao.erro("ajusteTransacao")}
              hint="Recebe o pedido na caixa de trabalho. Vem preenchido com a unidade que pediu, o caso mais comum."
            >
              <Select
                id="ajuste-transacao"
                value={ajusteTransacao}
                onChange={(e) => setAjusteTransacao(e.target.value)}
              >
                <option value="">Escolha quem ajusta</option>
                {TRANSACAO_PAGAMENTOS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </FormField>
            <EscolhaSegmentada
              nome="ajuste-tipo"
              titulo="Tipo de ajuste"
              valor={ajusteTipo}
              onChange={setAjusteTipo}
              opcoes={[
                {
                  valor: "NAO_MATERIAL",
                  rotulo: "Não material",
                  descricao: "Não mexe em fornecedor, valor, fonte nem notas: as aprovações continuam valendo.",
                },
                {
                  valor: "MATERIAL",
                  rotulo: "Alteração material",
                  descricao: "Alteração material invalida aprovações já dadas e volta o débito ao gestor.",
                },
              ]}
              moldura={false}
            />
            <GradeCampos>
              <FormField label="Prazo" opcional hint="Até quando o ajuste deve ser feito.">
                <Input
                  id="ajuste-prazo"
                  type="date"
                  value={ajustePrazo}
                  onChange={(e) => setAjustePrazo(e.target.value)}
                />
              </FormField>
              <FormField label="Campos relacionados" opcional hint="Separe por vírgula.">
                <Input
                  id="ajuste-campos"
                  value={ajusteCampos}
                  onChange={(e) => setAjusteCampos(e.target.value)}
                  placeholder="Ex.: valor_total, numero_nf"
                />
              </FormField>
            </GradeCampos>
          </div>
        )}
      </Dialog>

      <AcaoParcelaDialog
        alvo={acaoParcela}
        onClose={() => setAcaoParcela(null)}
        onFeito={invalidarTudo}
      />
      <PagarParcelaDialog
        parcela={parcelaAPagar}
        onClose={() => setParcelaAPagar(null)}
        onFeito={invalidarTudo}
      />
      <RecolherRetencaoDialog
        retencao={retencaoARecolher}
        onClose={() => setRetencaoARecolher(null)}
        onFeito={() => qc.invalidateQueries({ queryKey: ["pag-retencoes", id] })}
      />

      {/* Lançar retenção (F4) — trava (409) enquanto a parcela estiver
          engajada num lote de pagamento; a mensagem do backend vira o toast. */}
      <Dialog
        open={retencaoOpen}
        onClose={() => setRetencaoOpen(false)}
        title="Lançar retenção"
        description="O valor retido sai do líquido a pagar ao fornecedor."
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setRetencaoOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => {
                if (vRetencao.conferir()) criarRetencaoM.mutate();
              }}
              loading={criarRetencaoM.isPending}
            >
              Lançar retenção
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <FormField label="Tipo" required>
            <Select
              id="ret-tipo"
              value={retencaoTipo}
              onChange={(e) => setRetencaoTipo(e.target.value as TipoRetencao)}
            >
              <option value="IRRF">IRRF</option>
              <option value="INSS">INSS</option>
              <option value="ISS">ISS</option>
              <option value="PIS_COFINS_CSLL">PIS/COFINS/CSLL</option>
              <option value="OUTRAS">Outras</option>
            </Select>
          </FormField>
          <GradeCampos>
            <FormField label="Base de cálculo" required error={vRetencao.erro("base")}>
              <CampoComUnidade
                id="ret-base"
                prefixo="R$"
                type="number"
                inputMode="decimal"
                step="0.01"
                min="0"
                value={retencaoBase}
                onChange={(e) => mudarBaseOuAliquota(e.target.value, retencaoAliquota)}
                onBlur={vRetencao.tocar("base")}
                placeholder="0,00"
              />
            </FormField>
            <FormField label="Alíquota" opcional>
              <CampoComUnidade
                id="ret-aliquota"
                sufixo="%"
                type="number"
                inputMode="decimal"
                step="0.01"
                min="0"
                value={retencaoAliquota}
                onChange={(e) => mudarBaseOuAliquota(retencaoBase, e.target.value)}
                placeholder="Ex.: 1,5"
              />
            </FormField>
          </GradeCampos>
          <FormField
            label="Valor retido"
            required
            error={vRetencao.erro("valor")}
            hint={
              valorRetencaoCalculado
                ? "Calculado: base × alíquota. Pode corrigir."
                : "Preencha a alíquota para calcular, ou digite o valor."
            }
          >
            <CampoComUnidade
              id="ret-valor"
              prefixo="R$"
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={retencaoValor}
              onChange={(e) => {
                setValorRetencaoCalculado(false);
                setRetencaoValor(e.target.value);
              }}
              onBlur={vRetencao.tocar("valor")}
              placeholder="0,00"
            />
          </FormField>
          <FormField label="Descrição" opcional>
            <Input
              id="ret-descricao"
              value={retencaoDescricao}
              onChange={(e) => setRetencaoDescricao(e.target.value)}
              maxLength={150}
              placeholder="Ex.: ISS retido na fonte — NF 4587"
            />
          </FormField>
        </div>
      </Dialog>

      {/* Exceção cronológica (F3, Task 5/6) — furo formal de ordem, com
          justificativa, fundamento legal e data de autorização. */}
      <Dialog
        open={excecaoOpen}
        onClose={() => setExcecaoOpen(false)}
        title="Autorizar exceção cronológica"
        description="Registra o furo formal à ordem de pagamento — exigido pela LRF e pela lei de licitações."
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setExcecaoOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => {
                if (vExcecao.conferir()) registrarExcecaoM.mutate();
              }}
              loading={registrarExcecaoM.isPending}
            >
              Autorizar exceção
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <FormField
            label="Fundamento legal"
            required
            error={vExcecao.erro("fundamento")}
            hint="O dispositivo que permite pagar fora da ordem."
          >
            <Input
              id="exc-fundamento"
              value={excecaoFundamento}
              onChange={(e) => setExcecaoFundamento(e.target.value)}
              onBlur={vExcecao.tocar("fundamento")}
              placeholder="Ex.: art. 141, § 1º, da Lei 14.133/2021"
              maxLength={255}
            />
          </FormField>
          <FormField
            label="Justificativa"
            required
            error={vExcecao.erro("justificativa")}
            hint="Por que esta solicitação passa à frente das que estão antes dela na fila."
          >
            <Textarea
              id="exc-justificativa"
              value={excecaoJustificativa}
              onChange={(e) => setExcecaoJustificativa(e.target.value)}
              onBlur={vExcecao.tocar("justificativa")}
              placeholder="Ex.: Fornecedor único de medicamento, com risco de desabastecimento."
              className="min-h-24"
            />
          </FormField>
          <FormField
            label="Data da autorização"
            required
            error={vExcecao.erro("data")}
            hint="Hoje, por padrão."
          >
            <Input
              id="exc-data"
              type="date"
              value={excecaoData}
              onChange={(e) => setExcecaoData(e.target.value)}
              onBlur={vExcecao.tocar("data")}
            />
          </FormField>
        </div>
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
