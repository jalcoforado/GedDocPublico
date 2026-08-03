"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, Plus } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
const STATUS: { value: DocumentoStatus; label: string }[] = [
  { value: "ativo", label: "Ativo" },
  { value: "vencido", label: "Vencido" },
  { value: "substituido", label: "Substituído" },
  { value: "cancelado", label: "Cancelado" },
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

function fmtData(d: string | null): string {
  if (!d) return "—";
  return new Date(`${d}T00:00:00`).toLocaleDateString("pt-BR");
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
    if (!form.data_vencimento) {
      setErr("Data de vencimento é obrigatória.");
      return;
    }
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

  const titulo = veiculo
    ? mode === "form"
      ? `${editing ? "Editar documento" : "Novo documento"} — ${veiculo.placa}`
      : `Documentos — ${veiculo.placa}`
    : "Documentos";

  return (
    <Dialog
      open={open}
      onClose={closeAll}
      title={titulo}
      size="lg"
      footer={
        mode === "form" ? (
          <>
            <Button variant="secondary" onClick={backToList}>
              Voltar
            </Button>
            <Button onClick={salvar} disabled={saveM.isPending}>
              {saveM.isPending ? "Salvando..." : "Salvar"}
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
                        <div className="inline-flex gap-2">
                          {canEdit && (
                            <Button variant="secondary" size="sm" onClick={() => openEdit(d)}>
                              Editar
                            </Button>
                          )}
                          {canDelete && (
                            <Button
                              variant="danger"
                              size="sm"
                              disabled={deleteM.isPending}
                              onClick={async () => {
                                const ok = await confirm({
                                  title: "Excluir documento",
                                  message: `Excluir o documento ${
                                    TIPO_LABEL[d.tipo_documento] ?? d.tipo_documento
                                  }? Esta ação não pode ser desfeita.`,
                                  confirmLabel: "Excluir",
                                  intent: "danger",
                                });
                                if (ok) deleteM.mutate(d.id);
                              }}
                            >
                              Excluir
                            </Button>
                          )}
                        </div>
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="tipo_documento" required>
                Tipo de documento
              </Label>
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
            </div>
            <div>
              <Label htmlFor="doc_status">Status</Label>
              <Select
                id="doc_status"
                value={form.status}
                onChange={(e) => set("status", e.target.value as DocumentoStatus)}
              >
                {STATUS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="numero">Número</Label>
              <Input id="numero" value={form.numero} onChange={(e) => set("numero", e.target.value)} />
            </div>
            <div>
              <Label htmlFor="orgao">Órgão emissor</Label>
              <Input
                id="orgao"
                value={form.orgao_emissor}
                onChange={(e) => set("orgao_emissor", e.target.value)}
                placeholder="ex.: DETRAN"
              />
            </div>
            <div>
              <Label htmlFor="data_emissao">Data de emissão</Label>
              <Input
                id="data_emissao"
                type="date"
                value={form.data_emissao}
                onChange={(e) => set("data_emissao", e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="data_vencimento" required>
                Data de vencimento
              </Label>
              <Input
                id="data_vencimento"
                type="date"
                value={form.data_vencimento}
                onChange={(e) => set("data_vencimento", e.target.value)}
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="doc_obs">Observações</Label>
              <Textarea
                id="doc_obs"
                rows={3}
                value={form.observacoes}
                onChange={(e) => set("observacoes", e.target.value)}
              />
            </div>
          </div>

          {err && (
            <div role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
              {err}
            </div>
          )}
        </div>
      )}
    </Dialog>
  );
}
