"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Car,
  CheckCircle,
  FileText,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";

import { fmtData } from "@/components/pagamentos/format";
import {
  AtalhosPrazo,
  dicaVigencia,
  hojeISO,
  somarMeses,
  useValidacao,
} from "@/components/transporte/formulario";
import { rotuloTipoServico } from "@/components/transporte/rotulos";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada, type OpcaoEscolha } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SectionCard } from "@/components/ui/section-card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { TabList, TabPanel, Tabs } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type ResultadoAvaliacao,
  type StatusDocumento,
  type TipoDocumentoTR,
  type VeiculoAvaliacao,
  type VeiculoDocumentoTR,
  type VeiculoRegulado,
  type VeiculoVistoriaTR,
  type VeiculoVistoriaRenovarInput,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TIPOS_DOCUMENTO: { value: TipoDocumentoTR; label: string }[] = [
  { value: "crlv", label: "CRLV" },
  { value: "cnh_copia", label: "Cópia CNH" },
  { value: "inspecao", label: "Inspeção" },
  { value: "vistoria", label: "Vistoria" },
  { value: "seguro", label: "Seguro" },
  { value: "autorizacao_especial", label: "Autorização Especial" },
  { value: "adaptacao", label: "Adaptação Mobiliário" },
  { value: "outro", label: "Outro" },
];

const STATUS_DOCUMENTO: { value: StatusDocumento; label: string }[] = [
  { value: "pendente", label: "Pendente" },
  { value: "valido", label: "Válido" },
  { value: "vencido", label: "Vencido" },
  { value: "rejeitado", label: "Rejeitado" },
];

const RESULTADOS_AVALIACAO: { value: ResultadoAvaliacao; label: string }[] = [
  { value: "pendente", label: "Pendente" },
  { value: "aprovado", label: "Aprovado" },
  { value: "reprovado", label: "Reprovado" },
  { value: "condicional", label: "Condicional" },
];

const TIPO_LABEL: Record<string, string> = Object.fromEntries(
  TIPOS_DOCUMENTO.map((t) => [t.value, t.label])
);
const STATUS_INTENT: Record<string, "success" | "warning" | "danger" | "info" | "neutral"> = {
  valido: "success",
  pendente: "warning",
  // Vencido é `danger` como no alvará: a mesma situação, a mesma cor.
  vencido: "danger",
  rejeitado: "danger",
};
const RESULTADO_INTENT: Record<string, "success" | "warning" | "danger" | "info" | "neutral"> = {
  aprovado: "success",
  pendente: "warning",
  reprovado: "danger",
  condicional: "info",
};
const STATUS_LABEL: Record<string, string> = Object.fromEntries(
  STATUS_DOCUMENTO.map((s) => [s.value, s.label]),
);
const RESULTADO_LABEL: Record<string, string> = Object.fromEntries(
  RESULTADOS_AVALIACAO.map((r) => [r.value, r.label]),
);
// Mesmos rótulos e cores da lista de veículos regulados.
const SITUACAO_VEICULO: Record<
  string,
  { label: string; intent: "success" | "warning" | "info" | "danger" | "neutral" }
> = {
  ativo: { label: "Ativo", intent: "success" },
  pendente: { label: "Pendente", intent: "warning" },
  suspenso: { label: "Suspenso", intent: "info" },
  cassado: { label: "Cassado", intent: "danger" },
  inativo: { label: "Inativo", intent: "neutral" },
};

interface DocumentoForm {
  tipo_documento: TipoDocumentoTR;
  numero_documento: string;
  data_emissao: string;
  data_validade: string;
  observacoes: string;
}

interface AvaliacaoForm {
  resultado: ResultadoAvaliacao;
  parecer: string;
  observacoes: string;
  data_avaliacao: string;
}

interface VistoriaForm {
  resultado: ResultadoAvaliacao;
  parecer: string;
  observacoes: string;
  data_vistoria: string;
  data_validade: string;
}

interface RenovarForm {
  resultado: ResultadoAvaliacao;
  parecer: string;
  observacoes: string;
  data_validade: string;
}

// Resultado de avaliação e vistoria: quatro opções, todas à vista, com o que
// cada uma diz sobre o veículo.
const OPCOES_RESULTADO: OpcaoEscolha<ResultadoAvaliacao>[] = [
  { valor: "pendente", rotulo: "Pendente", descricao: "Ainda em análise: o veículo não foi liberado nem barrado." },
  { valor: "aprovado", rotulo: "Aprovado", descricao: "O veículo está apto para o serviço." },
  { valor: "reprovado", rotulo: "Reprovado", descricao: "O veículo não está apto: diga no parecer o que reprovou." },
  { valor: "condicional", rotulo: "Condicional", descricao: "Apto com ressalvas: diga no parecer quais e o prazo." },
];

// O backend exige parecer com 10 caracteres ou mais (`min_length=10`).
const PARECER_MIN = 10;
function erroParecer(p: string): string | undefined {
  if (p.trim() === "") return "Escreva o parecer.";
  const n = p.length;
  return n < PARECER_MIN ? `O parecer precisa de pelo menos ${PARECER_MIN} caracteres (faltam ${PARECER_MIN - n}).` : undefined;
}
function dicaParecer(p: string): string {
  const n = p.trim() === "" ? 0 : p.length;
  return n === 0 || n >= PARECER_MIN ? "O que foi conferido e a conclusão." : `Faltam ${PARECER_MIN - n} caracteres.`;
}
function erroDataPassada(d: string, rotulo: string): string | undefined {
  if (!d) return `Informe a data ${rotulo}.`;
  return d > hojeISO() ? `A data ${rotulo} não pode ser futura.` : undefined;
}

const EMPTY_DOC: DocumentoForm = {
  tipo_documento: "crlv" as TipoDocumentoTR,
  numero_documento: "",
  data_emissao: "",
  data_validade: "",
  observacoes: "",
};

const EMPTY_AVAL: AvaliacaoForm = {
  resultado: "pendente",
  parecer: "",
  observacoes: "",
  // `toISOString` dava o dia de amanhã depois das 21h em UTC-3.
  data_avaliacao: hojeISO(),
};

const EMPTY_VIST: VistoriaForm = {
  resultado: "pendente",
  parecer: "",
  observacoes: "",
  data_vistoria: hojeISO(),
  data_validade: "",
};

const EMPTY_RENOV: RenovarForm = {
  resultado: "pendente",
  parecer: "",
  observacoes: "",
  data_validade: somarMeses(hojeISO(), 12),
};

export default function VeiculoDetailPage() {
  const params = useParams();
  const veiculoId = Number(params.id);
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [tab, setTab] = useState<"info" | "documentos" | "avaliacoes" | "vistorias">("info");
  const [docDialogOpen, setDocDialogOpen] = useState(false);
  const [avalDialogOpen, setAvalDialogOpen] = useState(false);
  const [vistDialogOpen, setVistDialogOpen] = useState(false);
  const [renovarDialogOpen, setRenovarDialogOpen] = useState(false);
  const [docForm, setDocForm] = useState<DocumentoForm>(EMPTY_DOC);
  const [avalForm, setAvalForm] = useState<AvaliacaoForm>(EMPTY_AVAL);
  const [vistForm, setVistForm] = useState<VistoriaForm>(EMPTY_VIST);
  const [renovarForm, setRenovarForm] = useState<RenovarForm>(EMPTY_RENOV);
  const [editingDoc, setEditingDoc] = useState<VeiculoDocumentoTR | null>(null);
  const [editingAval, setEditingAval] = useState<VeiculoAvaliacao | null>(null);
  const [editingVist, setEditingVist] = useState<VeiculoVistoriaTR | null>(null);
  const [selectedVistToRenew, setSelectedVistToRenew] = useState<VeiculoVistoriaTR | null>(null);

  const veiculoQ = useQuery({
    queryKey: ["tr-veiculo", veiculoId],
    queryFn: () => api.veiculosRegulados.get(veiculoId),
  });

  const docsQ = useQuery({
    queryKey: ["tr-documentos", veiculoId],
    queryFn: () => api.veiculosRegulados.documentos.list(veiculoId),
  });

  const avalsQ = useQuery({
    queryKey: ["tr-avaliacoes", veiculoId],
    queryFn: () => api.veiculosRegulados.avaliacoes.list(veiculoId),
  });

  const vistQ = useQuery({
    queryKey: ["tr-vistorias", veiculoId],
    queryFn: () => api.veiculosRegulados.vistorias.list(veiculoId),
  });

  const vistVencidasQ = useQuery({
    queryKey: ["tr-vistorias-vencidas", veiculoId],
    queryFn: () => api.veiculosRegulados.vistorias.listarVencidas(veiculoId),
  });

  const criarDocM = useMutation({
    mutationFn: (data: any) => api.veiculosRegulados.documentos.create(veiculoId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-documentos"] });
      setDocDialogOpen(false);
      setDocForm(EMPTY_DOC);
      toast.success("Documento criado");
    },
    onError: (e: any) => toast.error(e.message || "Erro ao criar documento"),
  });

  const atualizarDocM = useMutation({
    mutationFn: (data: any) =>
      api.veiculosRegulados.documentos.update(veiculoId, editingDoc!.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-documentos"] });
      setDocDialogOpen(false);
      setEditingDoc(null);
      setDocForm(EMPTY_DOC);
      toast.success("Documento atualizado");
    },
    onError: (e: any) => toast.error(e.message || "Erro ao atualizar documento"),
  });

  const removerDocM = useMutation({
    mutationFn: (docId: number) => api.veiculosRegulados.documentos.remove(veiculoId, docId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-documentos"] });
      toast.success("Documento removido");
    },
    onError: (e: any) => toast.error(e.message || "Erro ao remover documento"),
  });

  const criarAvalM = useMutation({
    mutationFn: (data: any) => api.veiculosRegulados.avaliacoes.create(veiculoId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-avaliacoes"] });
      setAvalDialogOpen(false);
      setAvalForm({ ...EMPTY_AVAL, data_avaliacao: hojeISO() });
      toast.success("Avaliação criada");
    },
    onError: (e: any) => toast.error(e.message || "Erro ao criar avaliação"),
  });

  const atualizarAvalM = useMutation({
    mutationFn: (data: any) =>
      api.veiculosRegulados.avaliacoes.update(veiculoId, editingAval!.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-avaliacoes"] });
      setAvalDialogOpen(false);
      setEditingAval(null);
      setAvalForm({ ...EMPTY_AVAL, data_avaliacao: hojeISO() });
      toast.success("Avaliação atualizada");
    },
    onError: (e: any) => toast.error(e.message || "Erro ao atualizar avaliação"),
  });

  const removerAvalM = useMutation({
    mutationFn: (avalId: number) => api.veiculosRegulados.avaliacoes.remove(veiculoId, avalId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-avaliacoes"] });
      toast.success("Avaliação removida");
    },
    onError: (e: any) => toast.error(e.message || "Erro ao remover avaliação"),
  });

  const criarVistM = useMutation({
    mutationFn: (data: any) => api.veiculosRegulados.vistorias.create(veiculoId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-vistorias"] });
      setVistDialogOpen(false);
      setVistForm({ ...EMPTY_VIST, data_vistoria: hojeISO() });
      toast.success("Vistoria criada");
    },
    onError: (e: any) => toast.error(e.message || "Erro ao criar vistoria"),
  });

  const atualizarVistM = useMutation({
    mutationFn: (data: any) =>
      api.veiculosRegulados.vistorias.update(veiculoId, editingVist!.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-vistorias"] });
      setVistDialogOpen(false);
      setEditingVist(null);
      setVistForm({ ...EMPTY_VIST, data_vistoria: hojeISO() });
      toast.success("Vistoria atualizada");
    },
    onError: (e: any) => toast.error(e.message || "Erro ao atualizar vistoria"),
  });

  const removerVistM = useMutation({
    mutationFn: (vistId: number) => api.veiculosRegulados.vistorias.remove(veiculoId, vistId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-vistorias"] });
      toast.success("Vistoria removida");
    },
    onError: (e: any) => toast.error(e.message || "Erro ao remover vistoria"),
  });

  const renovarVistM = useMutation({
    mutationFn: (data: VeiculoVistoriaRenovarInput) =>
      api.veiculosRegulados.vistorias.renovar(veiculoId, selectedVistToRenew!.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-vistorias"] });
      qc.invalidateQueries({ queryKey: ["tr-vistorias-vencidas"] });
      setRenovarDialogOpen(false);
      setSelectedVistToRenew(null);
      setRenovarForm({ ...EMPTY_RENOV, data_validade: somarMeses(hojeISO(), 12) });
      toast.success("Vistoria renovada");
    },
    onError: (e: any) => toast.error(e.message || "Erro ao renovar vistoria"),
  });

  // Regras do backend (parecer ≥ 10 caracteres, data não futura) ditas no
  // campo — antes eram um toast que sumia e não dizia onde. Antes do `return`
  // antecipado: são hooks.
  const valDoc = useValidacao<"numero_documento">({
    numero_documento: docForm.numero_documento.trim() === "" ? "Informe o número do documento." : undefined,
  });
  const valAval = useValidacao<"parecer" | "data_avaliacao">({
    parecer: erroParecer(avalForm.parecer),
    data_avaliacao: erroDataPassada(avalForm.data_avaliacao, "da avaliação"),
  });
  const valVist = useValidacao<"parecer" | "data_vistoria">({
    parecer: erroParecer(vistForm.parecer),
    data_vistoria: erroDataPassada(vistForm.data_vistoria, "da vistoria"),
  });
  const valRenov = useValidacao<"parecer">({ parecer: erroParecer(renovarForm.parecer) });

  if (veiculoQ.isLoading) return <Carregando />;
  if (veiculoQ.isError)
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Não foi possível carregar o veículo"
        description="Confira o endereço ou volte para a lista de veículos regulados."
      />
    );

  const veiculo = veiculoQ.data!;

  const handleSaveDoc = async () => {
    if (!valDoc.conferir()) return;
    const payload = {
      tipo_documento: docForm.tipo_documento,
      numero_documento: docForm.numero_documento,
      data_emissao: docForm.data_emissao || null,
      data_validade: docForm.data_validade || null,
      observacoes: docForm.observacoes || null,
    };
    if (editingDoc) {
      await atualizarDocM.mutateAsync(payload);
    } else {
      await criarDocM.mutateAsync(payload);
    }
  };

  const handleSaveAval = async () => {
    if (!valAval.conferir()) return;
    const payload = {
      resultado: avalForm.resultado,
      parecer: avalForm.parecer,
      observacoes: avalForm.observacoes || null,
      data_avaliacao: avalForm.data_avaliacao,
    };
    if (editingAval) {
      await atualizarAvalM.mutateAsync(payload);
    } else {
      await criarAvalM.mutateAsync(payload);
    }
  };

  const handleSaveVist = async () => {
    if (!valVist.conferir()) return;
    const payload = {
      resultado: vistForm.resultado,
      parecer: vistForm.parecer,
      observacoes: vistForm.observacoes || null,
      data_vistoria: vistForm.data_vistoria,
      data_validade: vistForm.data_validade || null,
    };
    if (editingVist) {
      await atualizarVistM.mutateAsync(payload);
    } else {
      await criarVistM.mutateAsync(payload);
    }
  };

  const handleSaveRenov = async () => {
    if (!valRenov.conferir()) return;
    const payload: VeiculoVistoriaRenovarInput = {
      resultado: renovarForm.resultado,
      parecer: renovarForm.parecer,
      observacoes: renovarForm.observacoes || null,
      data_validade: renovarForm.data_validade || null,
    };
    await renovarVistM.mutateAsync(payload);
  };

  return (
    // A seta de voltar vem do PageHeader (trilha com a lista de veículos); o
    // botão "Voltar" solto e as abas com azul/cinza fixos saíram.
    <Tabs value={tab} onChange={(v) => setTab(v as typeof tab)} className="space-y-6">
      <PageHeader
        icon={Car}
        title={veiculo.placa}
        description={`${veiculo.marca} ${veiculo.modelo} — ${rotuloTipoServico(veiculo.tipo_servico)}`}
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Veículos regulados", href: "/m/transporte/veiculos" },
          { label: veiculo.placa },
        ]}
        tabs={
          <TabList
            aria-label="Seção do veículo"
            tabs={[
              { value: "info", label: "Informações" },
              { value: "documentos", label: "Documentos" },
              { value: "avaliacoes", label: "Avaliações" },
              { value: "vistorias", label: "Vistorias" },
            ]}
          />
        }
      />

      <TabPanel value="info">
        <SectionCard title="Informações do veículo" icon={Car}>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-foreground-muted">Placa</dt>
              <dd className="font-mono font-semibold text-foreground">{veiculo.placa}</dd>
            </div>
            <div>
              <dt className="text-xs text-foreground-muted">Marca / modelo</dt>
              <dd className="font-semibold text-foreground">
                {veiculo.marca} {veiculo.modelo}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-foreground-muted">RENAVAM</dt>
              <dd className="text-foreground">{veiculo.renavam || "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-foreground-muted">Chassi</dt>
              <dd className="text-foreground">{veiculo.chassi || "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-foreground-muted">Situação</dt>
              <dd>
                <Badge intent={SITUACAO_VEICULO[veiculo.situacao]?.intent ?? "neutral"}>
                  {SITUACAO_VEICULO[veiculo.situacao]?.label ?? veiculo.situacao}
                </Badge>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-foreground-muted">Tipo de serviço</dt>
              <dd className="text-foreground">{rotuloTipoServico(veiculo.tipo_servico)}</dd>
            </div>
          </dl>
        </SectionCard>
      </TabPanel>

      <TabPanel value="documentos">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">Documentos do veículo</h2>
            {can("transporte_regulado", "inserir") && (
              <Button
                size="sm"
                onClick={() => {
                  setEditingDoc(null);
                  setDocForm(EMPTY_DOC);
                  valDoc.reiniciar();
                  setDocDialogOpen(true);
                }}
              >
                <Plus className="mr-1 h-4 w-4" />
                Novo documento
              </Button>
            )}
          </div>

          {docsQ.isLoading ? (
            <Carregando />
          ) : docsQ.data && docsQ.data.items.length > 0 ? (
            <Table>
              <THead>
                <TR>
                  <TH>Tipo</TH>
                  <TH>Número</TH>
                  <TH>Emissão</TH>
                  <TH>Validade</TH>
                  <TH>Situação</TH>
                  <TH className="text-right">Ações</TH>
                </TR>
              </THead>
              <TBody>
                {docsQ.data.items.map((doc) => (
                  <TR key={doc.id}>
                    <TD>{TIPO_LABEL[doc.tipo_documento] ?? doc.tipo_documento}</TD>
                    <TD>{doc.numero_documento}</TD>
                    <TD className="tabular-nums">{fmtData(doc.data_emissao)}</TD>
                    <TD className="tabular-nums">{fmtData(doc.data_validade)}</TD>
                    <TD>
                      <Badge intent={STATUS_INTENT[doc.situacao] || "neutral"}>
                        {STATUS_LABEL[doc.situacao] ?? doc.situacao}
                      </Badge>
                    </TD>
                    <TD className="text-right">
                      <AcoesDaLinha
                        acoes={[
                          {
                            label: "Editar",
                            icon: Pencil,
                            oculta: !can("transporte_regulado", "atualizar"),
                            onClick: () => {
                              setEditingDoc(doc);
                              setDocForm({
                                tipo_documento: doc.tipo_documento,
                                numero_documento: doc.numero_documento,
                                data_emissao: doc.data_emissao || "",
                                data_validade: doc.data_validade || "",
                                observacoes: doc.observacoes || "",
                              });
                              valDoc.reiniciar();
                              setDocDialogOpen(true);
                            },
                          },
                          {
                            label: "Excluir",
                            icon: Trash2,
                            perigo: true,
                            oculta: !can("transporte_regulado", "excluir"),
                            onClick: async () => {
                              const ok = await confirm({
                                title: "Excluir documento",
                                message: `Excluir o documento "${doc.numero_documento}"? Esta ação não pode ser desfeita.`,
                                confirmLabel: "Excluir",
                                intent: "danger",
                              });
                              if (ok) removerDocM.mutate(doc.id);
                            },
                          },
                        ]}
                      />
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          ) : (
            <EmptyState
              icon={FileText}
              title="Nenhum documento"
              description="CRLV, seguro, inspeção e demais documentos do veículo aparecem aqui."
            />
          )}

          {/* Documento Dialog */}
          <Dialog
            open={docDialogOpen}
            onClose={() => setDocDialogOpen(false)}
            title={editingDoc ? "Editar documento" : "Novo documento"}
            description={`Documento do veículo ${veiculo.placa}.`}
            footer={
              <>
                <Button variant="ghost" onClick={() => setDocDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button onClick={handleSaveDoc} loading={criarDocM.isPending || atualizarDocM.isPending}>
                  {editingDoc ? "Salvar alterações" : "Adicionar documento"}
                </Button>
              </>
            }
          >
            <div ref={valDoc.ref} className="space-y-4">
              <GradeCampos>
                <FormField label="Tipo de documento" required>
                  <Select
                    id="doc_tipo"
                    value={docForm.tipo_documento}
                    onChange={(e) =>
                      setDocForm({ ...docForm, tipo_documento: e.target.value as TipoDocumentoTR })
                    }
                  >
                    {TIPOS_DOCUMENTO.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </Select>
                </FormField>
                <FormField label="Número do documento" required error={valDoc.erro("numero_documento")}>
                  <Input
                    id="doc_numero"
                    value={docForm.numero_documento}
                    onChange={(e) => setDocForm({ ...docForm, numero_documento: e.target.value })}
                    onBlur={valDoc.sair("numero_documento")}
                    placeholder="Ex.: ABC123456"
                  />
                </FormField>
              </GradeCampos>
              <GradeCampos>
                <FormField label="Emissão" opcional>
                  <Input
                    id="doc_emissao"
                    type="date"
                    value={docForm.data_emissao}
                    onChange={(e) => setDocForm({ ...docForm, data_emissao: e.target.value })}
                  />
                </FormField>
                <FormField
                  label="Validade"
                  opcional
                  hint={dicaVigencia(docForm.data_emissao, docForm.data_validade, "Deixe vazio se o documento não tem validade.")}
                >
                  <Input
                    id="doc_validade"
                    type="date"
                    value={docForm.data_validade}
                    onChange={(e) => setDocForm({ ...docForm, data_validade: e.target.value })}
                  />
                </FormField>
              </GradeCampos>
              <FormField label="Observações" opcional>
                <Textarea
                  id="doc_obs"
                  value={docForm.observacoes}
                  onChange={(e) => setDocForm({ ...docForm, observacoes: e.target.value })}
                  placeholder="Ex.: apólice renovada pela seguradora em outubro"
                />
              </FormField>
            </div>
          </Dialog>
        </div>
      </TabPanel>

      <TabPanel value="avaliacoes">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">Avaliações do veículo</h2>
            {can("transporte_regulado", "inserir") && (
              <Button
                size="sm"
                onClick={() => {
                  setEditingAval(null);
                  setAvalForm({ ...EMPTY_AVAL, data_avaliacao: hojeISO() });
                  valAval.reiniciar();
                  setAvalDialogOpen(true);
                }}
              >
                <Plus className="mr-1 h-4 w-4" />
                Nova avaliação
              </Button>
            )}
          </div>

          {avalsQ.isLoading ? (
            <Carregando />
          ) : avalsQ.data && avalsQ.data.items.length > 0 ? (
            <Table>
              <THead>
                <TR>
                  <TH>Resultado</TH>
                  <TH>Data</TH>
                  <TH>Parecer</TH>
                  <TH className="text-right">Ações</TH>
                </TR>
              </THead>
              <TBody>
                {avalsQ.data.items.map((aval) => (
                  <TR key={aval.id}>
                    <TD>
                      <Badge intent={RESULTADO_INTENT[aval.resultado] || "neutral"}>
                        {RESULTADO_LABEL[aval.resultado] ?? aval.resultado}
                      </Badge>
                    </TD>
                    <TD className="tabular-nums">{fmtData(aval.data_avaliacao)}</TD>
                    <TD className="max-w-sm truncate">{aval.parecer}</TD>
                    <TD className="text-right">
                      <AcoesDaLinha
                        acoes={[
                          {
                            label: "Editar",
                            icon: Pencil,
                            oculta: !can("transporte_regulado", "atualizar"),
                            onClick: () => {
                              setEditingAval(aval);
                              setAvalForm({
                                resultado: aval.resultado,
                                parecer: aval.parecer,
                                observacoes: aval.observacoes || "",
                                data_avaliacao: aval.data_avaliacao.split("T")[0],
                              });
                              valAval.reiniciar();
                              setAvalDialogOpen(true);
                            },
                          },
                          {
                            label: "Excluir",
                            icon: Trash2,
                            perigo: true,
                            oculta: !can("transporte_regulado", "excluir"),
                            onClick: async () => {
                              const ok = await confirm({
                                title: "Excluir avaliação",
                                message: "Excluir esta avaliação? Esta ação não pode ser desfeita.",
                                confirmLabel: "Excluir",
                                intent: "danger",
                              });
                              if (ok) removerAvalM.mutate(aval.id);
                            },
                          },
                        ]}
                      />
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          ) : (
            <EmptyState
              icon={CheckCircle}
              title="Nenhuma avaliação"
              description="As avaliações técnicas do veículo aparecem aqui, com o resultado e o parecer."
            />
          )}

          {/* Avaliacao Dialog */}
          <Dialog
            open={avalDialogOpen}
            onClose={() => setAvalDialogOpen(false)}
            title={editingAval ? "Editar avaliação" : "Nova avaliação"}
            description={`Avaliação técnica do veículo ${veiculo.placa}.`}
            footer={
              <>
                <Button variant="ghost" onClick={() => setAvalDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button onClick={handleSaveAval} loading={criarAvalM.isPending || atualizarAvalM.isPending}>
                  {editingAval ? "Salvar alterações" : "Registrar avaliação"}
                </Button>
              </>
            }
          >
            <div ref={valAval.ref} className="space-y-4">
              <EscolhaSegmentada<ResultadoAvaliacao>
                nome="aval-resultado"
                titulo="Resultado"
                valor={avalForm.resultado}
                onChange={(r) => setAvalForm({ ...avalForm, resultado: r })}
                opcoes={OPCOES_RESULTADO}
              />
              <FormField
                label="Data da avaliação"
                required
                error={valAval.erro("data_avaliacao")}
                hint={editingAval ? "Não pode ser data futura." : "Hoje, por padrão. Não pode ser data futura."}
              >
                <Input
                  id="aval_data"
                  type="date"
                  max={hojeISO()}
                  onBlur={valAval.sair("data_avaliacao")}
                  value={avalForm.data_avaliacao}
                  onChange={(e) => setAvalForm({ ...avalForm, data_avaliacao: e.target.value })}
                />
              </FormField>
              <FormField
                label="Parecer"
                required
                error={valAval.erro("parecer")}
                hint={dicaParecer(avalForm.parecer)}
              >
                <Textarea
                  id="aval_parecer"
                  value={avalForm.parecer}
                  onChange={(e) => setAvalForm({ ...avalForm, parecer: e.target.value })}
                  onBlur={valAval.sair("parecer")}
                  placeholder="Ex.: freios, pneus e iluminação em ordem; cinto traseiro com desgaste."
                  rows={5}
                />
              </FormField>
              <FormField label="Observações" opcional>
                <Textarea
                  id="aval_obs"
                  value={avalForm.observacoes}
                  onChange={(e) => setAvalForm({ ...avalForm, observacoes: e.target.value })}
                />
              </FormField>
            </div>
          </Dialog>
        </div>
      </TabPanel>

      <TabPanel value="vistorias">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">Vistorias do veículo</h2>
            {can("transporte_regulado", "inserir") && (
              <Button
                size="sm"
                onClick={() => {
                  setEditingVist(null);
                  setVistForm({ ...EMPTY_VIST, data_vistoria: hojeISO() });
                  valVist.reiniciar();
                  setVistDialogOpen(true);
                }}
              >
                <Plus className="mr-1 h-4 w-4" />
                Nova vistoria
              </Button>
            )}
          </div>

          {vistQ.isLoading ? (
            <Carregando />
          ) : vistQ.data && vistQ.data.items.length > 0 ? (
            <Table>
              <THead>
                <TR>
                  <TH>Resultado</TH>
                  <TH>Data</TH>
                  <TH>Parecer</TH>
                  <TH className="text-right">Ações</TH>
                </TR>
              </THead>
              <TBody>
                {vistQ.data.items.map((vist) => {
                  const isVencida = vist.data_validade && new Date(vist.data_validade) <= new Date();
                  return (
                    <TR key={vist.id}>
                      <TD>
                        <div className="flex flex-col items-start gap-1">
                          <Badge intent={RESULTADO_INTENT[vist.resultado] || "neutral"}>
                            {RESULTADO_LABEL[vist.resultado] ?? vist.resultado}
                          </Badge>
                          {isVencida && (
                            <Badge intent="danger">Vencida</Badge>
                          )}
                        </div>
                      </TD>
                      <TD>
                        <div className="flex flex-col gap-1 tabular-nums">
                          <span>{fmtData(vist.data_vistoria)}</span>
                          {vist.data_validade && (
                            <span className="text-xs text-muted-foreground">
                              Válida até {fmtData(vist.data_validade)}
                            </span>
                          )}
                        </div>
                      </TD>
                      <TD className="max-w-sm truncate">{vist.parecer}</TD>
                      <TD className="text-right">
                        <AcoesDaLinha
                          acoes={[
                            {
                              label: "Renovar",
                              icon: RefreshCw,
                              oculta: !(isVencida && can("transporte_regulado", "inserir")),
                              onClick: () => {
                                setSelectedVistToRenew(vist);
                                setRenovarForm({ ...EMPTY_RENOV, data_validade: somarMeses(hojeISO(), 12) });
                                valRenov.reiniciar();
                                setRenovarDialogOpen(true);
                              },
                            },
                            {
                              label: "Editar",
                              icon: Pencil,
                              oculta: !can("transporte_regulado", "atualizar"),
                              onClick: () => {
                                setEditingVist(vist);
                                setVistForm({
                                  resultado: vist.resultado,
                                  parecer: vist.parecer,
                                  observacoes: vist.observacoes || "",
                                  data_vistoria: vist.data_vistoria.split("T")[0],
                                  data_validade: vist.data_validade
                                    ? vist.data_validade.split("T")[0]
                                    : "",
                                });
                                valVist.reiniciar();
                                setVistDialogOpen(true);
                              },
                            },
                            {
                              label: "Excluir",
                              icon: Trash2,
                              perigo: true,
                              oculta: !can("transporte_regulado", "excluir"),
                              onClick: async () => {
                                const ok = await confirm({
                                  title: "Excluir vistoria",
                                  message: "Excluir esta vistoria? Esta ação não pode ser desfeita.",
                                  confirmLabel: "Excluir",
                                  intent: "danger",
                                });
                                if (ok) removerVistM.mutate(vist.id);
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
          ) : (
            <EmptyState
              icon={CheckCircle}
              title="Nenhuma vistoria"
              description="As vistorias do veículo aparecem aqui, com a validade de cada uma."
            />
          )}

          {/* Vistoria Dialog */}
          <Dialog
            open={vistDialogOpen}
            onClose={() => setVistDialogOpen(false)}
            title={editingVist ? "Editar vistoria" : "Nova vistoria"}
            description={`Vistoria do veículo ${veiculo.placa}.`}
            footer={
              <>
                <Button variant="ghost" onClick={() => setVistDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button onClick={handleSaveVist} loading={criarVistM.isPending || atualizarVistM.isPending}>
                  {editingVist ? "Salvar alterações" : "Registrar vistoria"}
                </Button>
              </>
            }
          >
            <div ref={valVist.ref} className="space-y-4">
              <EscolhaSegmentada<ResultadoAvaliacao>
                nome="vist-resultado"
                titulo="Resultado"
                valor={vistForm.resultado}
                onChange={(r) => setVistForm({ ...vistForm, resultado: r })}
                opcoes={OPCOES_RESULTADO}
              />
              <GradeCampos>
                <FormField
                  label="Data da vistoria"
                  required
                  error={valVist.erro("data_vistoria")}
                  hint={editingVist ? "Não pode ser data futura." : "Hoje, por padrão. Não pode ser data futura."}
                >
                  <Input
                    id="vist_data"
                    type="date"
                    max={hojeISO()}
                    onBlur={valVist.sair("data_vistoria")}
                    value={vistForm.data_vistoria}
                    onChange={(e) => setVistForm({ ...vistForm, data_vistoria: e.target.value })}
                  />
                </FormField>
                <FormField
                  label="Validade"
                  opcional
                  acao={
                    <AtalhosPrazo
                      inicio={vistForm.data_vistoria}
                      meses={[6, 12]}
                      onEscolher={(d) => setVistForm({ ...vistForm, data_validade: d })}
                    />
                  }
                  hint={dicaVigencia(vistForm.data_vistoria, vistForm.data_validade, "Até quando a vistoria vale.")}
                >
                  <Input
                    id="vist_validade"
                    type="date"
                    value={vistForm.data_validade}
                    onChange={(e) => setVistForm({ ...vistForm, data_validade: e.target.value })}
                  />
                </FormField>
              </GradeCampos>
              <FormField
                label="Parecer"
                required
                error={valVist.erro("parecer")}
                hint={dicaParecer(vistForm.parecer)}
              >
                <Textarea
                  id="vist_parecer"
                  value={vistForm.parecer}
                  onChange={(e) => setVistForm({ ...vistForm, parecer: e.target.value })}
                  onBlur={valVist.sair("parecer")}
                  placeholder="Ex.: itens de segurança conferidos; extintor dentro da validade."
                  rows={5}
                />
              </FormField>
              <FormField label="Observações" opcional>
                <Textarea
                  id="vist_obs"
                  value={vistForm.observacoes}
                  onChange={(e) => setVistForm({ ...vistForm, observacoes: e.target.value })}
                />
              </FormField>
            </div>
          </Dialog>

          {/* Renovar Vistoria Dialog */}
          <Dialog
            open={renovarDialogOpen}
            onClose={() => setRenovarDialogOpen(false)}
            title="Renovar vistoria"
            description="A renovação registra uma vistoria nova, ligada à vencida."
            footer={
              <>
                <Button variant="ghost" onClick={() => setRenovarDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button onClick={handleSaveRenov} loading={renovarVistM.isPending}>
                  Renovar vistoria
                </Button>
              </>
            }
          >
            <div ref={valRenov.ref} className="space-y-4">
              {selectedVistToRenew && (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-border bg-surface-1 p-4 text-sm">
                  <div>
                    <dt className="text-xs text-foreground-muted">Vistoria atual</dt>
                    <dd className="tabular-nums text-foreground">{fmtData(selectedVistToRenew.data_vistoria)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-foreground-muted">Validade atual</dt>
                    <dd className="flex items-center gap-2 tabular-nums text-foreground">
                      {selectedVistToRenew.data_validade ? fmtData(selectedVistToRenew.data_validade) : "Sem validade"}
                      <Badge intent="danger">Vencida</Badge>
                    </dd>
                  </div>
                </dl>
              )}
              <EscolhaSegmentada<ResultadoAvaliacao>
                nome="renov-resultado"
                titulo="Resultado"
                valor={renovarForm.resultado}
                onChange={(r) => setRenovarForm({ ...renovarForm, resultado: r })}
                opcoes={OPCOES_RESULTADO}
              />
              <FormField
                label="Nova validade"
                opcional
                acao={
                  <AtalhosPrazo
                    inicio=""
                    meses={[6, 12]}
                    onEscolher={(d) => setRenovarForm({ ...renovarForm, data_validade: d })}
                  />
                }
                hint={dicaVigencia(hojeISO(), renovarForm.data_validade, "Até quando a vistoria renovada vale.")}
              >
                <Input
                  id="renov_validade"
                  type="date"
                  value={renovarForm.data_validade}
                  onChange={(e) => setRenovarForm({ ...renovarForm, data_validade: e.target.value })}
                />
              </FormField>
              <FormField
                label="Parecer"
                required
                error={valRenov.erro("parecer")}
                hint={dicaParecer(renovarForm.parecer)}
              >
                <Textarea
                  id="renov_parecer"
                  value={renovarForm.parecer}
                  onChange={(e) => setRenovarForm({ ...renovarForm, parecer: e.target.value })}
                  onBlur={valRenov.sair("parecer")}
                  placeholder="Ex.: nova vistoria aprovada sem ressalvas."
                  rows={5}
                />
              </FormField>
              <FormField label="Observações" opcional>
                <Textarea
                  id="renov_obs"
                  value={renovarForm.observacoes}
                  onChange={(e) => setRenovarForm({ ...renovarForm, observacoes: e.target.value })}
                />
              </FormField>
            </div>
          </Dialog>
        </div>
      </TabPanel>
    </Tabs>
  );
}
