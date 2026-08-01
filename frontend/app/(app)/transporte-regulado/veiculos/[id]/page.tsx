"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileText, CheckCircle, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SectionCard } from "@/components/ui/section-card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
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

const RESULTADOS_VISTORIA: { value: ResultadoAvaliacao; label: string }[] = [
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
  vencido: "info",
  rejeitado: "danger",
};
const RESULTADO_INTENT: Record<string, "success" | "warning" | "danger" | "info" | "neutral"> = {
  aprovado: "success",
  pendente: "warning",
  reprovado: "danger",
  condicional: "info",
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
  data_avaliacao: new Date().toISOString().split("T")[0],
};

const EMPTY_VIST: VistoriaForm = {
  resultado: "pendente",
  parecer: "",
  observacoes: "",
  data_vistoria: new Date().toISOString().split("T")[0],
  data_validade: "",
};

const EMPTY_RENOV: RenovarForm = {
  resultado: "pendente",
  parecer: "",
  observacoes: "",
  data_validade: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
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
      setAvalForm(EMPTY_AVAL);
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
      setAvalForm(EMPTY_AVAL);
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
      setVistForm(EMPTY_VIST);
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
      setVistForm(EMPTY_VIST);
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
      setRenovarForm(EMPTY_RENOV);
      toast.success("Vistoria renovada");
    },
    onError: (e: any) => toast.error(e.message || "Erro ao renovar vistoria"),
  });

  if (veiculoQ.isLoading) return <div>Carregando...</div>;
  if (veiculoQ.isError) return <div>Erro ao carregar veículo</div>;

  const veiculo = veiculoQ.data!;

  const handleSaveDoc = async () => {
    if (!docForm.numero_documento.trim()) {
      toast.error("Número do documento é obrigatório");
      return;
    }
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
    if (!avalForm.parecer.trim() || avalForm.parecer.length < 10) {
      toast.error("Parecer deve ter no mínimo 10 caracteres");
      return;
    }
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
    if (!vistForm.parecer.trim() || vistForm.parecer.length < 10) {
      toast.error("Parecer deve ter no mínimo 10 caracteres");
      return;
    }
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
    if (!renovarForm.parecer.trim() || renovarForm.parecer.length < 10) {
      toast.error("Parecer deve ter no mínimo 10 caracteres");
      return;
    }
    const payload: VeiculoVistoriaRenovarInput = {
      resultado: renovarForm.resultado,
      parecer: renovarForm.parecer,
      observacoes: renovarForm.observacoes || null,
      data_validade: renovarForm.data_validade || null,
    };
    await renovarVistM.mutateAsync(payload);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/transporte-regulado/veiculos">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Voltar
          </Button>
        </Link>
        <PageHeader title={veiculo.placa} description={`${veiculo.marca} ${veiculo.modelo}`} />
      </div>

      {/* Abas */}
      <div className="flex gap-2 border-b">
        {(["info", "documentos", "avaliacoes", "vistorias"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 border-b-2 transition ${
              tab === t
                ? "border-blue-500 text-blue-600 font-semibold"
                : "border-transparent text-gray-600 hover:text-gray-900"
            }`}
          >
            {t === "info" && "Informações"}
            {t === "documentos" && "Documentos"}
            {t === "avaliacoes" && "Avaliações"}
            {t === "vistorias" && "Vistorias"}
          </button>
        ))}
      </div>

      {/* Info Tab */}
      {tab === "info" && (
        <SectionCard title="Informações do Veículo">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Placa</Label>
              <p className="font-semibold">{veiculo.placa}</p>
            </div>
            <div>
              <Label>Marca/Modelo</Label>
              <p className="font-semibold">
                {veiculo.marca} {veiculo.modelo}
              </p>
            </div>
            <div>
              <Label>RENAVAM</Label>
              <p>{veiculo.renavam || "-"}</p>
            </div>
            <div>
              <Label>Chassi</Label>
              <p>{veiculo.chassi || "-"}</p>
            </div>
            <div>
              <Label>Situação</Label>
              <Badge intent={veiculo.situacao === "ativo" ? "success" : "warning"}>
                {veiculo.situacao}
              </Badge>
            </div>
            <div>
              <Label>Tipo de Serviço</Label>
              <p>{veiculo.tipo_servico}</p>
            </div>
          </div>
        </SectionCard>
      )}

      {/* Documentos Tab */}
      {tab === "documentos" && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Documentos do Veículo</h2>
            {can("transporte_regulado", "inserir") && (
              <Button
                size="sm"
                onClick={() => {
                  setEditingDoc(null);
                  setDocForm(EMPTY_DOC);
                  setDocDialogOpen(true);
                }}
              >
                <Plus className="h-4 w-4 mr-2" />
                Novo Documento
              </Button>
            )}
          </div>

          {docsQ.isLoading ? (
            <div>Carregando...</div>
          ) : docsQ.data && docsQ.data.items.length > 0 ? (
            <Table>
              <THead>
                <TR>
                  <TH>Tipo</TH>
                  <TH>Número</TH>
                  <TH>Emissão</TH>
                  <TH>Validade</TH>
                  <TH>Status</TH>
                  <TH>Ações</TH>
                </TR>
              </THead>
              <TBody>
                {docsQ.data.items.map((doc) => (
                  <TR key={doc.id}>
                    <TD>{TIPO_LABEL[doc.tipo_documento]}</TD>
                    <TD>{doc.numero_documento}</TD>
                    <TD>{doc.data_emissao || "-"}</TD>
                    <TD>{doc.data_validade || "-"}</TD>
                    <TD>
                      <Badge intent={STATUS_INTENT[doc.situacao] || "neutral"}>
                        {doc.situacao}
                      </Badge>
                    </TD>
                    <TD className="flex gap-2">
                      {can("transporte_regulado", "atualizar") && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setEditingDoc(doc);
                            setDocForm({
                              tipo_documento: doc.tipo_documento,
                              numero_documento: doc.numero_documento,
                              data_emissao: doc.data_emissao || "",
                              data_validade: doc.data_validade || "",
                              observacoes: doc.observacoes || "",
                            });
                            setDocDialogOpen(true);
                          }}
                        >
                          Editar
                        </Button>
                      )}
                      {can("transporte_regulado", "excluir") && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => removerDocM.mutate(doc.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          ) : (
            <EmptyState icon={FileText} title="Sem documentos" description="Nenhum documento registrado" />
          )}

          {/* Documento Dialog */}
          <Dialog
            open={docDialogOpen}
            onClose={() => setDocDialogOpen(false)}
            title={editingDoc ? "Editar Documento" : "Novo Documento"}
          >
            <div className="space-y-4">
              <div>
                <Label>Tipo de Documento</Label>
                <Select
                  value={docForm.tipo_documento}
                  onChange={(e) =>
                    setDocForm({ ...docForm, tipo_documento: e.target.value as TipoDocumentoTR })
                  }
                >
                  {TIPOS_DOCUMENTO.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Número do Documento *</Label>
                <Input
                  value={docForm.numero_documento}
                  onChange={(e) =>
                    setDocForm({ ...docForm, numero_documento: e.target.value })
                  }
                  placeholder="Ex: ABC123456"
                />
              </div>
              <div>
                <Label>Data de Emissão</Label>
                <Input
                  type="date"
                  value={docForm.data_emissao}
                  onChange={(e) => setDocForm({ ...docForm, data_emissao: e.target.value })}
                />
              </div>
              <div>
                <Label>Data de Validade</Label>
                <Input
                  type="date"
                  value={docForm.data_validade}
                  onChange={(e) => setDocForm({ ...docForm, data_validade: e.target.value })}
                />
              </div>
              <div>
                <Label>Observações</Label>
                <Textarea
                  value={docForm.observacoes}
                  onChange={(e) => setDocForm({ ...docForm, observacoes: e.target.value })}
                  placeholder="Observações adicionais..."
                />
              </div>
              <div className="flex gap-2 justify-end">
                <Button variant="secondary" onClick={() => setDocDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button onClick={handleSaveDoc} disabled={criarDocM.isPending || atualizarDocM.isPending}>
                  Salvar
                </Button>
              </div>
            </div>
          </Dialog>
        </div>
      )}

      {/* Avaliacoes Tab */}
      {tab === "avaliacoes" && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Avaliações do Veículo</h2>
            {can("transporte_regulado", "inserir") && (
              <Button
                size="sm"
                onClick={() => {
                  setEditingAval(null);
                  setAvalForm(EMPTY_AVAL);
                  setAvalDialogOpen(true);
                }}
              >
                <Plus className="h-4 w-4 mr-2" />
                Nova Avaliação
              </Button>
            )}
          </div>

          {avalsQ.isLoading ? (
            <div>Carregando...</div>
          ) : avalsQ.data && avalsQ.data.items.length > 0 ? (
            <Table>
              <THead>
                <TR>
                  <TH>Resultado</TH>
                  <TH>Data</TH>
                  <TH>Parecer</TH>
                  <TH>Ações</TH>
                </TR>
              </THead>
              <TBody>
                {avalsQ.data.items.map((aval) => (
                  <TR key={aval.id}>
                    <TD>
                      <Badge intent={RESULTADO_INTENT[aval.resultado] || "neutral"}>
                        {aval.resultado}
                      </Badge>
                    </TD>
                    <TD>{new Date(aval.data_avaliacao).toLocaleDateString()}</TD>
                    <TD className="max-w-sm truncate">{aval.parecer}</TD>
                    <TD className="flex gap-2">
                      {can("transporte_regulado", "atualizar") && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setEditingAval(aval);
                            setAvalForm({
                              resultado: aval.resultado,
                              parecer: aval.parecer,
                              observacoes: aval.observacoes || "",
                              data_avaliacao: aval.data_avaliacao.split("T")[0],
                            });
                            setAvalDialogOpen(true);
                          }}
                        >
                          Editar
                        </Button>
                      )}
                      {can("transporte_regulado", "excluir") && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => removerAvalM.mutate(aval.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          ) : (
            <EmptyState icon={CheckCircle} title="Sem avaliações" description="Nenhuma avaliação registrada" />
          )}

          {/* Avaliacao Dialog */}
          <Dialog
            open={avalDialogOpen}
            onClose={() => setAvalDialogOpen(false)}
            title={editingAval ? "Editar Avaliação" : "Nova Avaliação"}
          >
            <div className="space-y-4">
              <div>
                <Label>Resultado *</Label>
                <Select
                  value={avalForm.resultado}
                  onChange={(e) =>
                    setAvalForm({ ...avalForm, resultado: e.target.value as ResultadoAvaliacao })
                  }
                >
                  {RESULTADOS_AVALIACAO.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Data da Avaliação</Label>
                <Input
                  type="date"
                  value={avalForm.data_avaliacao}
                  onChange={(e) => setAvalForm({ ...avalForm, data_avaliacao: e.target.value })}
                />
              </div>
              <div>
                <Label>Parecer *</Label>
                <Textarea
                  value={avalForm.parecer}
                  onChange={(e) => setAvalForm({ ...avalForm, parecer: e.target.value })}
                  placeholder="Descreva o parecer técnico (mínimo 10 caracteres)..."
                  rows={5}
                />
              </div>
              <div>
                <Label>Observações</Label>
                <Textarea
                  value={avalForm.observacoes}
                  onChange={(e) => setAvalForm({ ...avalForm, observacoes: e.target.value })}
                  placeholder="Observações adicionais..."
                />
              </div>
              <div className="flex gap-2 justify-end">
                <Button variant="secondary" onClick={() => setAvalDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button onClick={handleSaveAval} disabled={criarAvalM.isPending || atualizarAvalM.isPending}>
                  Salvar
                </Button>
              </div>
            </div>
          </Dialog>
        </div>
      )}

      {/* Vistorias Tab */}
      {tab === "vistorias" && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Vistorias do Veículo</h2>
            {can("transporte_regulado", "inserir") && (
              <Button
                size="sm"
                onClick={() => {
                  setEditingVist(null);
                  setVistForm(EMPTY_VIST);
                  setVistDialogOpen(true);
                }}
              >
                <Plus className="h-4 w-4 mr-2" />
                Nova Vistoria
              </Button>
            )}
          </div>

          {vistQ.isLoading ? (
            <div>Carregando...</div>
          ) : vistQ.data && vistQ.data.items.length > 0 ? (
            <Table>
              <THead>
                <TR>
                  <TH>Resultado</TH>
                  <TH>Data</TH>
                  <TH>Parecer</TH>
                  <TH>Ações</TH>
                </TR>
              </THead>
              <TBody>
                {vistQ.data.items.map((vist) => {
                  const isVencida = vist.data_validade && new Date(vist.data_validade) <= new Date();
                  return (
                    <TR key={vist.id}>
                      <TD>
                        <div className="flex flex-col gap-1">
                          <Badge intent={RESULTADO_INTENT[vist.resultado] || "neutral"}>
                            {vist.resultado}
                          </Badge>
                          {isVencida && (
                            <Badge intent="danger">Vencida</Badge>
                          )}
                        </div>
                      </TD>
                      <TD>
                        <div className="flex flex-col gap-1">
                          <span>{new Date(vist.data_vistoria).toLocaleDateString()}</span>
                          {vist.data_validade && (
                            <span className="text-xs text-muted-foreground">
                              Válida até: {new Date(vist.data_validade).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </TD>
                      <TD className="max-w-sm truncate">{vist.parecer}</TD>
                      <TD className="flex gap-2">
                        {isVencida && can("transporte_regulado", "inserir") && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setSelectedVistToRenew(vist);
                              setRenovarForm(EMPTY_RENOV);
                              setRenovarDialogOpen(true);
                            }}
                          >
                            Renovar
                          </Button>
                        )}
                        {can("transporte_regulado", "atualizar") && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setEditingVist(vist);
                              setVistForm({
                                resultado: vist.resultado,
                                parecer: vist.parecer,
                                observacoes: vist.observacoes || "",
                                data_vistoria: vist.data_vistoria.split("T")[0],
                                data_validade: vist.data_validade ? vist.data_validade.split("T")[0] : "",
                              });
                              setVistDialogOpen(true);
                            }}
                          >
                            Editar
                          </Button>
                        )}
                        {can("transporte_regulado", "excluir") && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => removerVistM.mutate(vist.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          ) : (
            <EmptyState icon={CheckCircle} title="Sem vistorias" description="Nenhuma vistoria registrada" />
          )}

          {/* Vistoria Dialog */}
          <Dialog
            open={vistDialogOpen}
            onClose={() => setVistDialogOpen(false)}
            title={editingVist ? "Editar Vistoria" : "Nova Vistoria"}
          >
            <div className="space-y-4">
              <div>
                <Label>Resultado *</Label>
                <Select
                  value={vistForm.resultado}
                  onChange={(e) =>
                    setVistForm({ ...vistForm, resultado: e.target.value as ResultadoAvaliacao })
                  }
                >
                  {RESULTADOS_VISTORIA.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Data da Vistoria</Label>
                <Input
                  type="date"
                  value={vistForm.data_vistoria}
                  onChange={(e) => setVistForm({ ...vistForm, data_vistoria: e.target.value })}
                />
              </div>
              <div>
                <Label>Data de Validade</Label>
                <Input
                  type="date"
                  value={vistForm.data_validade}
                  onChange={(e) => setVistForm({ ...vistForm, data_validade: e.target.value })}
                />
              </div>
              <div>
                <Label>Parecer *</Label>
                <Textarea
                  value={vistForm.parecer}
                  onChange={(e) => setVistForm({ ...vistForm, parecer: e.target.value })}
                  placeholder="Descreva o parecer da vistoria (mínimo 10 caracteres)..."
                  rows={5}
                />
              </div>
              <div>
                <Label>Observações</Label>
                <Textarea
                  value={vistForm.observacoes}
                  onChange={(e) => setVistForm({ ...vistForm, observacoes: e.target.value })}
                  placeholder="Observações adicionais..."
                />
              </div>
              <div className="flex gap-2 justify-end">
                <Button variant="secondary" onClick={() => setVistDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button onClick={handleSaveVist} disabled={criarVistM.isPending || atualizarVistM.isPending}>
                  Salvar
                </Button>
              </div>
            </div>
          </Dialog>

          {/* Renovar Vistoria Dialog */}
          <Dialog
            open={renovarDialogOpen}
            onClose={() => setRenovarDialogOpen(false)}
            title="Renovar Vistoria"
          >
            <div className="space-y-4">
              {selectedVistToRenew && (
                <div className="p-3 bg-muted rounded-md">
                  <p className="text-sm font-medium">Renovando vistoria de {new Date(selectedVistToRenew.data_vistoria).toLocaleDateString()}</p>
                  <p className="text-xs text-muted-foreground mt-1">Válida até: {selectedVistToRenew.data_validade ? new Date(selectedVistToRenew.data_validade).toLocaleDateString() : "Sem validade"}</p>
                </div>
              )}
              <div>
                <Label>Resultado *</Label>
                <Select
                  value={renovarForm.resultado}
                  onChange={(e) =>
                    setRenovarForm({ ...renovarForm, resultado: e.target.value as ResultadoAvaliacao })
                  }
                >
                  {RESULTADOS_VISTORIA.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Data de Validade</Label>
                <Input
                  type="date"
                  value={renovarForm.data_validade}
                  onChange={(e) => setRenovarForm({ ...renovarForm, data_validade: e.target.value })}
                />
              </div>
              <div>
                <Label>Parecer *</Label>
                <Textarea
                  value={renovarForm.parecer}
                  onChange={(e) => setRenovarForm({ ...renovarForm, parecer: e.target.value })}
                  placeholder="Descreva o parecer da renovação (mínimo 10 caracteres)..."
                  rows={5}
                />
              </div>
              <div>
                <Label>Observações</Label>
                <Textarea
                  value={renovarForm.observacoes}
                  onChange={(e) => setRenovarForm({ ...renovarForm, observacoes: e.target.value })}
                  placeholder="Observações adicionais..."
                />
              </div>
              <div className="flex gap-2 justify-end">
                <Button variant="secondary" onClick={() => setRenovarDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button onClick={handleSaveRenov} disabled={renovarVistM.isPending}>
                  Renovar Vistoria
                </Button>
              </div>
            </div>
          </Dialog>
        </div>
      )}
    </div>
  );
}
