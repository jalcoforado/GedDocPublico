"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Inbox, Plus } from "lucide-react";
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
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type Alvara,
  type AlvaraInput,
  type Empresa,
  type Permissionario,
  type TipoServico,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TIPOS: { value: TipoServico; label: string }[] = [
  { value: "taxi", label: "Táxi" },
  { value: "mototaxi", label: "Mototáxi" },
  { value: "transporte_escolar", label: "Transporte escolar" },
  { value: "motofrete", label: "Motofrete" },
  { value: "transporte_distrital", label: "Transporte distrital" },
  { value: "aplicativo", label: "Aplicativo" },
  { value: "outro", label: "Outro" },
];
const TIPO_LABEL: Record<string, string> = Object.fromEntries(TIPOS.map((t) => [t.value, t.label]));

interface AlvaraForm {
  numero_alvara: string;
  data_inicio: string;
  data_validade: string;
  tipo_servico: TipoServico;
  observacoes: string;
  id_empresa: string;
  id_permissionario: string;
}

const EMPTY: AlvaraForm = {
  numero_alvara: "",
  data_inicio: "",
  data_validade: "",
  tipo_servico: "taxi",
  observacoes: "",
  id_empresa: "",
  id_permissionario: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

function isExpired(dataValidade: string | null | undefined): boolean {
  if (!dataValidade) return false;
  const today = new Date().toISOString().split("T")[0];
  return dataValidade <= today;
}

export default function AlvarasPage() {
  const { can } = useAuth();
  const canCreate = can("transporte_regulado", "inserir");
  const canEdit = can("transporte_regulado", "atualizar");
  const canDelete = can("transporte_regulado", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [empresaFiltro, setEmpresaFiltro] = useState("");
  const [permFiltro, setPermFiltro] = useState("");
  const [busca, setBusca] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Alvara | null>(null);
  const [form, setForm] = useState<AlvaraForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const listaQ = useQuery({
    queryKey: ["tr-alvaras", empresaFiltro, permFiltro, busca],
    queryFn: () =>
      api.alvaras.list({
        empresa_id: empresaFiltro ? Number(empresaFiltro) : undefined,
        permissionario_id: permFiltro ? Number(permFiltro) : undefined,
      }),
  });

  const empresasQ = useQuery({
    queryKey: ["tr-empresas-list"],
    queryFn: () => api.empresas.list(),
    enabled: dialogOpen,
  });

  const permsQ = useQuery({
    queryKey: ["tr-permissionarios-list"],
    queryFn: () => api.permissionarios.list(),
    enabled: dialogOpen,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["tr-alvaras"] });

  const saveM = useMutation({
    mutationFn: (data: AlvaraInput) =>
      editing ? api.alvaras.update(editing.id, data) : api.alvaras.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Alvará atualizado." : "Alvará cadastrado.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });

  const deleteM = useMutation({
    mutationFn: (id: number) => api.alvaras.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Alvará excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof AlvaraForm>(key: K, value: AlvaraForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setDialogOpen(true);
  }

  function openEdit(a: Alvara) {
    setEditing(a);
    setForm({
      numero_alvara: a.numero_alvara,
      data_inicio: a.data_inicio ?? "",
      data_validade: a.data_validade ?? "",
      tipo_servico: a.tipo_servico as TipoServico,
      observacoes: a.observacoes ?? "",
      id_empresa: a.id_empresa != null ? String(a.id_empresa) : "",
      id_permissionario: a.id_permissionario != null ? String(a.id_permissionario) : "",
    });
    setErr(null);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
  }

  function salvar() {
    setErr(null);
    if (form.numero_alvara.trim() === "") {
      setErr("Número do alvará é obrigatório.");
      return;
    }
    if (form.tipo_servico.trim() === "") {
      setErr("Tipo de serviço é obrigatório.");
      return;
    }
    if (form.id_empresa === "" && form.id_permissionario === "") {
      setErr("Informe ao menos uma empresa ou permissionário.");
      return;
    }
    if (form.data_inicio && form.data_validade && form.data_inicio > form.data_validade) {
      setErr("Data de início não pode ser posterior à data de validade.");
      return;
    }
    const payload: AlvaraInput = {
      numero_alvara: form.numero_alvara.trim(),
      data_inicio: nullify(form.data_inicio),
      data_validade: nullify(form.data_validade),
      tipo_servico: form.tipo_servico,
      observacoes: nullify(form.observacoes),
      id_empresa: form.id_empresa === "" ? null : Number(form.id_empresa),
      id_permissionario: form.id_permissionario === "" ? null : Number(form.id_permissionario),
    };
    saveM.mutate(payload);
  }

  const filteredData = listaQ.data?.filter((a) =>
    a.numero_alvara.toLowerCase().includes(busca.toLowerCase())
  ) ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        icon={FileText}
        title="Alvarás"
        description="Autorizações e permissões de operação para permissionários e empresas."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/transporte-regulado" },
          { label: "Alvarás" },
        ]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Novo alvará
            </Button>
          ) : undefined
        }
      />

      <div className="flex flex-wrap gap-3">
        <div>
          <Label htmlFor="f_emp">Empresa</Label>
          <Select id="f_emp" value={empresaFiltro} onChange={(e) => setEmpresaFiltro(e.target.value)}>
            <option value="">Todas</option>
            {empresasQ.data?.map((e: Empresa) => (
              <option key={e.id} value={String(e.id)}>
                {e.razao_social}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="f_perm">Permissionário</Label>
          <Select id="f_perm" value={permFiltro} onChange={(e) => setPermFiltro(e.target.value)}>
            <option value="">Todos</option>
            {permsQ.data?.map((p: Permissionario) => (
              <option key={p.id} value={String(p.id)}>
                {p.nome}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex-1 min-w-[200px]">
          <Label htmlFor="f_q">Busca por número</Label>
          <Input
            id="f_q"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="ALV-001, ALV-002..."
          />
        </div>
      </div>

      {listaQ.isLoading ? (
        <div className="text-center text-muted-foreground py-8">Carregando...</div>
      ) : filteredData.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhum alvará"
          description="Cadastre o primeiro alvará do transporte regulado."
          action={
            canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Cadastrar alvará
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Número</TH>
              <TH>Tipo de serviço</TH>
              <TH>Vinculação</TH>
              <TH>Validade</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {filteredData.map((a) => (
              <TR key={a.id}>
                <TD className="font-mono font-medium">{a.numero_alvara}</TD>
                <TD>{TIPO_LABEL[a.tipo_servico] ?? a.tipo_servico}</TD>
                <TD className="text-sm text-muted-foreground">
                  {a.id_empresa && a.id_permissionario
                    ? "Empresa + Permissionário"
                    : a.id_empresa
                      ? "Empresa"
                      : "Permissionário"}
                </TD>
                <TD>
                  {a.data_validade ? (
                    <div className="flex items-center gap-2">
                      {isExpired(a.data_validade) && (
                        <Badge intent="danger">Expirado</Badge>
                      )}
                      <span className={isExpired(a.data_validade) ? "line-through text-muted-foreground" : ""}>
                        {a.data_validade}
                      </span>
                    </div>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TD>
                <TD className="text-right">
                  <div className="inline-flex flex-wrap justify-end gap-2">
                    {canEdit && (
                      <Button variant="secondary" size="sm" onClick={() => openEdit(a)}>
                        Editar
                      </Button>
                    )}
                    {canDelete && (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={async () => {
                          const ok = await confirm({
                            title: "Excluir alvará",
                            message: `Excluir o alvará "${a.numero_alvara}"? Esta ação não pode ser desfeita.`,
                          });
                          if (ok) deleteM.mutate(a.id);
                        }}
                      >
                        Excluir
                      </Button>
                    )}
                  </div>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? `Editar — ${editing.numero_alvara}` : "Novo alvará"}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={salvar} disabled={saveM.isPending}>
              {saveM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {err && (
            <div className="rounded bg-red-50 p-3 text-sm text-red-700 border border-red-200">
              {err}
            </div>
          )}

          <div>
            <Label htmlFor="numero" required>
              Número do alvará
            </Label>
            <Input
              id="numero"
              value={form.numero_alvara}
              onChange={(e) => set("numero_alvara", e.target.value)}
              placeholder="ALV-001"
            />
          </div>

          <div>
            <Label htmlFor="tipo" required>
              Tipo de serviço
            </Label>
            <Select value={form.tipo_servico} onChange={(e) => set("tipo_servico", e.target.value as TipoServico)}>
              {TIPOS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="emp">Empresa</Label>
              <Select value={form.id_empresa} onChange={(e) => set("id_empresa", e.target.value)}>
                <option value="">Nenhuma</option>
                {empresasQ.data?.map((e: Empresa) => (
                  <option key={e.id} value={String(e.id)}>
                    {e.razao_social}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="perm">Permissionário</Label>
              <Select value={form.id_permissionario} onChange={(e) => set("id_permissionario", e.target.value)}>
                <option value="">Nenhum</option>
                {permsQ.data?.map((p: Permissionario) => (
                  <option key={p.id} value={String(p.id)}>
                    {p.nome}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="data_inicio">Data de início</Label>
              <Input
                id="data_inicio"
                type="date"
                value={form.data_inicio}
                onChange={(e) => set("data_inicio", e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="data_validade">Data de validade</Label>
              <Input
                id="data_validade"
                type="date"
                value={form.data_validade}
                onChange={(e) => set("data_validade", e.target.value)}
              />
            </div>
          </div>

          <div>
            <Label htmlFor="obs">Observações</Label>
            <Textarea
              id="obs"
              value={form.observacoes}
              onChange={(e) => set("observacoes", e.target.value)}
              placeholder="Notas adicionais sobre o alvará"
              rows={3}
            />
          </div>
        </div>
      </Dialog>
    </div>
  );
}
