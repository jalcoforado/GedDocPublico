"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { useErrosDoFormulario } from "@/components/frota/formulario";
import { fmtData } from "@/components/pagamentos/format";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada, type OpcaoEscolha } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type DocumentoStatus,
  type TipoDocumento,
  type Veiculo,
  type VeiculoDocumento,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TIPOS: { value: TipoDocumento; label: string }[] = [
  { value: "crlv", label: "CRLV" },
  { value: "seguro", label: "Seguro" },
  { value: "licenciamento", label: "Licenciamento" },
  { value: "autorizacao", label: "Autorização" },
  { value: "vistoria", label: "Vistoria" },
  { value: "outro", label: "Outro" },
];
// Quatro situações: à vista no formulário, com a consequência de cada uma
// (só ativo e vencido entram nos alertas — services/frota.py).
const STATUS_ESCOLHA: OpcaoEscolha<DocumentoStatus>[] = [
  { valor: "ativo", rotulo: "Ativo", descricao: "Em vigor. Entra nos alertas de vencimento." },
  { valor: "vencido", rotulo: "Vencido", descricao: "Passou da validade e segue nos alertas até ser renovado." },
  { valor: "substituido", rotulo: "Substituído", descricao: "Trocado por um mais novo. Sai dos alertas." },
  { valor: "cancelado", rotulo: "Cancelado", descricao: "Não vale mais. Sai dos alertas." },
];
const TIPO_LABEL: Record<string, string> = Object.fromEntries(
  TIPOS.map((t) => [t.value, t.label]),
);

interface DocForm {
  tipo_documento: TipoDocumento;
  numero: string;
  orgao_emissor: string;
  data_emissao: string;
  data_vencimento: string;
  status: DocumentoStatus;
  observacoes: string;
}

const EMPTY: DocForm = {
  tipo_documento: "crlv",
  numero: "",
  orgao_emissor: "",
  data_emissao: "",
  data_vencimento: "",
  status: "ativo",
  observacoes: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

/** Badge de vencimento calculado a partir de data_vencimento (cliente). */
function badgeVencimento(venc: string): { intent: "danger" | "warning" | "success"; label: string } {
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  const d = new Date(`${venc}T00:00:00`);
  const em30 = new Date(hoje);
  em30.setDate(em30.getDate() + 30);
  if (d < hoje) return { intent: "danger", label: "Vencido" };
  if (d <= em30) return { intent: "warning", label: "Vence em breve" };
  return { intent: "success", label: "Válido" };
}

/** Dica sob o vencimento: o que a data escolhida significa hoje. */
function dicaVencimento(venc: string): { texto: string; className: string } {
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  const dias = Math.round((new Date(`${venc}T00:00:00`).getTime() - hoje.getTime()) / 86_400_000);
  if (Number.isNaN(dias)) return { texto: "", className: "" };
  if (dias < 0) return { texto: "Esta data já passou: o documento está vencido.", className: "font-medium text-danger-soft-foreground" };
  if (dias === 0) return { texto: "Vence hoje.", className: "font-medium text-warning-soft-foreground" };
  if (dias <= 30)
    return {
      texto: `Vence em ${dias} ${dias === 1 ? "dia" : "dias"} — já aparece nos alertas.`,
      className: "font-medium text-warning-soft-foreground",
    };
  return { texto: `Vence em ${dias} dias.`, className: "" };
}

interface Props {
  veiculo: Veiculo | null;
  open: boolean;
  onClose: () => void;
}

export function DocumentosDialog({ veiculo, open, onClose }: Props) {
  const { can } = useAuth();
  const canCreate = can("frota", "inserir");
  const canEdit = can("frota", "atualizar");
  const canDelete = can("frota", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [mode, setMode] = useState<"list" | "form">("list");
  const [editing, setEditing] = useState<VeiculoDocumento | null>(null);
  const [form, setForm] = useState<DocForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);
  // Mesmas regras do backend: vencimento obrigatório; emissão, se houver, não
  // depois dele (schemas/frota.py::VeiculoDocumentoBase).
  const campos = useErrosDoFormulario({
    data_emissao:
      form.data_emissao && form.data_vencimento && form.data_emissao > form.data_vencimento
        ? "A emissão não pode ser depois do vencimento."
        : undefined,
    data_vencimento: form.data_vencimento ? undefined : "Informe a data de vencimento.",
  });
  // A situação da data escolhida, já no campo: a mesma régua do selo da lista.
  const vencimento = form.data_vencimento ? dicaVencimento(form.data_vencimento) : null;

  const docsQ = useQuery({
    queryKey: ["frota-documentos", veiculo?.id],
    queryFn: () => api.documentosVeiculo.listByVeiculo(veiculo!.id),
    enabled: open && veiculo != null,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["frota-documentos", veiculo?.id] });
    qc.invalidateQueries({ queryKey: ["frota-documentos-alertas"] });
  };

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing
        ? api.documentosVeiculo.update(editing.id, data)
        : api.documentosVeiculo.create(veiculo!.id, data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Documento atualizado." : "Documento cadastrado.");
      backToList();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.documentosVeiculo.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Documento excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof DocForm>(key: K, value: DocForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    campos.limpar();
    setMode("form");
  }

  function openEdit(d: VeiculoDocumento) {
    setEditing(d);
    setForm({
      tipo_documento: d.tipo_documento,
      numero: d.numero ?? "",
      orgao_emissor: d.orgao_emissor ?? "",
      data_emissao: d.data_emissao ?? "",
      data_vencimento: d.data_vencimento,
      status: d.status,
      observacoes: d.observacoes ?? "",
    });
    setErr(null);
    campos.limpar();
    setMode("form");
  }

  function backToList() {
    setMode("list");
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
  }

  function closeAll() {
    backToList();
    onClose();
  }

  function salvar() {
    setErr(null);
    if (!campos.podeEnviar()) return;
    const payload = {
      tipo_documento: form.tipo_documento,
      numero: nullify(form.numero),
      orgao_emissor: nullify(form.orgao_emissor),
      data_emissao: nullify(form.data_emissao),
      data_vencimento: form.data_vencimento,
      status: form.status,
      observacoes: nullify(form.observacoes),
    };
    saveM.mutate(payload);
  }

  const titulo =
    mode === "form" ? (editing ? "Editar documento" : "Novo documento") : "Documentos do veículo";

  return (
    <Dialog
      open={open}
      onClose={closeAll}
      title={titulo}
      description={veiculo ? `Placa ${veiculo.placa}` : undefined}
      size="lg"
      footer={
        mode === "form" ? (
          <>
            <Button variant="ghost" onClick={backToList}>
              Voltar à lista
            </Button>
            <Button type="submit" form="form-documento" loading={saveM.isPending}>
              {editing ? "Salvar alterações" : "Cadastrar documento"}
            </Button>
          </>
        ) : (
          <Button variant="secondary" onClick={closeAll}>
            Fechar
          </Button>
        )
      }
    >
      {mode === "list" ? (
        <div className="space-y-3">
          {canCreate && (
            <div className="flex justify-end">
              <Button size="sm" onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Novo documento
              </Button>
            </div>
          )}

          {!docsQ.isLoading && (docsQ.data?.length ?? 0) === 0 ? (
            <EmptyState
              icon={Inbox}
              title="Nenhum documento cadastrado"
              description="Cadastre CRLV, seguro, licenciamento e outros documentos do veículo."
            />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Tipo</TH>
                  <TH>Número</TH>
                  <TH>Vencimento</TH>
                  <TH>Situação</TH>
                  <TH className="text-right">Ações</TH>
                </TR>
              </THead>
              <TBody>
                {docsQ.isLoading && (
                  <TR>
                    <TD colSpan={5} className="text-center text-muted-foreground">
                      Carregando documentos...
                    </TD>
                  </TR>
                )}
                {docsQ.data?.map((d) => {
                  const b = badgeVencimento(d.data_vencimento);
                  return (
                    <TR key={d.id}>
                      <TD>{TIPO_LABEL[d.tipo_documento] ?? d.tipo_documento}</TD>
                      <TD className="text-muted-foreground">{d.numero ?? "—"}</TD>
                      <TD className="tabular-nums">{fmtData(d.data_vencimento)}</TD>
                      <TD>
                        <Badge intent={b.intent}>{b.label}</Badge>
                      </TD>
                      <TD className="text-right">
                        <AcoesDaLinha
                          acoes={[
                            {
                              label: "Editar",
                              icon: Pencil,
                              oculta: !canEdit,
                              onClick: () => openEdit(d),
                            },
                            {
                              label: "Excluir",
                              icon: Trash2,
                              perigo: true,
                              oculta: !canDelete,
                              disabled: deleteM.isPending,
                              onClick: async () => {
                                const ok = await confirm({
                                  title: "Excluir documento",
                                  message: `Excluir o documento ${
                                    TIPO_LABEL[d.tipo_documento] ?? d.tipo_documento
                                  }? Esta ação não pode ser desfeita.`,
                                  confirmLabel: "Excluir",
                                  intent: "danger",
                                });
                                if (ok) deleteM.mutate(d.id);
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
        </div>
      ) : (
        <form
          id="form-documento"
          noValidate
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            salvar();
          }}
        >
          <GradeCampos>
            <FormField label="Tipo de documento" required>
              <Select
                id="tipo_documento"
                value={form.tipo_documento}
                onChange={(e) => set("tipo_documento", e.target.value as TipoDocumento)}
              >
                {TIPOS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Número" opcional>
              <Input
                id="numero"
                value={form.numero}
                onChange={(e) => set("numero", e.target.value)}
                placeholder="Ex.: 012345678901"
                maxLength={60}
              />
            </FormField>
          </GradeCampos>
          <FormField label="Órgão emissor" opcional>
            <Input
              id="orgao"
              value={form.orgao_emissor}
              onChange={(e) => set("orgao_emissor", e.target.value)}
              placeholder="Ex.: DETRAN-CE"
              maxLength={120}
            />
          </FormField>
          <GradeCampos>
            <FormField label="Emissão" opcional error={campos.erro("data_emissao")}>
              <Input
                id="data_emissao"
                type="date"
                max={form.data_vencimento || undefined}
                value={form.data_emissao}
                onChange={(e) => set("data_emissao", e.target.value)}
                onBlur={campos.tocar("data_emissao")}
              />
            </FormField>
            <FormField
              label="Vencimento"
              required
              hint={
                vencimento?.texto ? (
                  <span className={vencimento.className}>{vencimento.texto}</span>
                ) : (
                  "É por ela que o sistema avisa o que vai vencer."
                )
              }
              error={campos.erro("data_vencimento")}
            >
              <Input
                id="data_vencimento"
                type="date"
                value={form.data_vencimento}
                onChange={(e) => set("data_vencimento", e.target.value)}
                onBlur={campos.tocar("data_vencimento")}
              />
            </FormField>
          </GradeCampos>
          <EscolhaSegmentada
            nome="status_documento"
            titulo="Situação"
            moldura={false}
            valor={form.status}
            opcoes={STATUS_ESCOLHA}
            onChange={(s) => set("status", s)}
          />
          <FormField label="Observações" opcional>
            <Textarea
              id="doc_obs"
              rows={3}
              value={form.observacoes}
              onChange={(e) => set("observacoes", e.target.value)}
              placeholder="Ex.: apólice nº 77.123, cobertura total"
            />
          </FormField>

          {err && (
            <Alert intent="danger" title="Não foi possível salvar">
              {err}
            </Alert>
          )}
        </form>
      )}
    </Dialog>
  );
}
