"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { IdCard, Inbox, Plus } from "lucide-react";
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
  type Permissionario,
  type PermissionarioSituacao,
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
const SITUACOES: { value: PermissionarioSituacao; label: string }[] = [
  { value: "pendente", label: "Pendente" },
  { value: "ativo", label: "Ativo" },
  { value: "suspenso", label: "Suspenso" },
  { value: "cassado", label: "Cassado" },
  { value: "inativo", label: "Inativo" },
];
const CNH_CATS = ["A", "B", "AB", "C", "D", "E", "AC", "AD", "AE"];
const TIPO_LABEL: Record<string, string> = Object.fromEntries(TIPOS.map((t) => [t.value, t.label]));
const SIT_LABEL: Record<string, string> = Object.fromEntries(SITUACOES.map((s) => [s.value, s.label]));
const SIT_INTENT: Record<string, "success" | "warning" | "info" | "danger" | "neutral"> = {
  ativo: "success",
  pendente: "warning",
  suspenso: "info",
  cassado: "danger",
  inativo: "neutral",
};

interface PermForm {
  nome: string;
  cpf: string;
  rg: string;
  data_nascimento: string;
  telefone: string;
  email: string;
  cnh_numero: string;
  cnh_categoria: string;
  cnh_validade: string;
  tipo_servico: TipoServico;
  numero_permissao: string;
  data_inicio_permissao: string;
  data_validade_permissao: string;
  situacao: PermissionarioSituacao;
  observacoes: string;
}

const EMPTY: PermForm = {
  nome: "",
  cpf: "",
  rg: "",
  data_nascimento: "",
  telefone: "",
  email: "",
  cnh_numero: "",
  cnh_categoria: "",
  cnh_validade: "",
  tipo_servico: "taxi",
  numero_permissao: "",
  data_inicio_permissao: "",
  data_validade_permissao: "",
  situacao: "pendente",
  observacoes: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

export default function PermissionariosPage() {
  const { can } = useAuth();
  const canCreate = can("transporte_regulado", "inserir");
  const canEdit = can("transporte_regulado", "atualizar");
  const canDelete = can("transporte_regulado", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [situacaoFiltro, setSituacaoFiltro] = useState("");
  const [tipoFiltro, setTipoFiltro] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Permissionario | null>(null);
  const [form, setForm] = useState<PermForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const listaQ = useQuery({
    queryKey: ["tr-permissionarios", situacaoFiltro, tipoFiltro],
    queryFn: () =>
      api.permissionarios.list({
        situacao: situacaoFiltro || undefined,
        tipo_servico: tipoFiltro || undefined,
      }),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["tr-permissionarios"] });

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing ? api.permissionarios.update(editing.id, data) : api.permissionarios.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Permissionário atualizado." : "Permissionário cadastrado.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const actionM = useMutation({
    mutationFn: ({ id, acao }: { id: number; acao: "inativar" | "reativar" | "suspender" }) =>
      acao === "inativar"
        ? api.permissionarios.inativar(id)
        : acao === "reativar"
          ? api.permissionarios.reativar(id)
          : api.permissionarios.suspender(id),
    onSuccess: () => {
      invalidate();
      toast.success("Situação atualizada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.permissionarios.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Permissionário excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof PermForm>(key: K, value: PermForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }
  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setDialogOpen(true);
  }
  function openEdit(p: Permissionario) {
    setEditing(p);
    setForm({
      nome: p.nome,
      cpf: p.cpf,
      rg: p.rg ?? "",
      data_nascimento: p.data_nascimento ?? "",
      telefone: p.telefone ?? "",
      email: p.email ?? "",
      cnh_numero: p.cnh_numero ?? "",
      cnh_categoria: p.cnh_categoria ?? "",
      cnh_validade: p.cnh_validade ?? "",
      tipo_servico: p.tipo_servico,
      numero_permissao: p.numero_permissao ?? "",
      data_inicio_permissao: p.data_inicio_permissao ?? "",
      data_validade_permissao: p.data_validade_permissao ?? "",
      situacao: p.situacao,
      observacoes: p.observacoes ?? "",
    });
    setErr(null);
    setDialogOpen(true);
  }
  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }
  function salvar() {
    setErr(null);
    if (form.nome.trim() === "") {
      setErr("Nome é obrigatório.");
      return;
    }
    if (form.cpf.trim() === "") {
      setErr("CPF é obrigatório.");
      return;
    }
    const payload = {
      nome: form.nome.trim(),
      cpf: form.cpf.trim(),
      rg: nullify(form.rg),
      data_nascimento: nullify(form.data_nascimento),
      telefone: nullify(form.telefone),
      email: nullify(form.email),
      cnh_numero: nullify(form.cnh_numero),
      cnh_categoria: nullify(form.cnh_categoria),
      cnh_validade: nullify(form.cnh_validade),
      tipo_servico: form.tipo_servico,
      numero_permissao: nullify(form.numero_permissao),
      data_inicio_permissao: nullify(form.data_inicio_permissao),
      data_validade_permissao: nullify(form.data_validade_permissao),
      situacao: form.situacao,
      observacoes: nullify(form.observacoes),
    };
    saveM.mutate(payload);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={IdCard}
        title="Permissionários"
        description="Cadastro de permissionários do transporte regulado."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/transporte-regulado" },
          { label: "Permissionários" },
        ]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Novo permissionário
            </Button>
          ) : undefined
        }
      />

      <div className="flex flex-wrap gap-3">
        <div>
          <Label htmlFor="f_sit">Situação</Label>
          <Select id="f_sit" value={situacaoFiltro} onChange={(e) => setSituacaoFiltro(e.target.value)}>
            <option value="">Todas</option>
            {SITUACOES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="f_tipo">Tipo de serviço</Label>
          <Select id="f_tipo" value={tipoFiltro} onChange={(e) => setTipoFiltro(e.target.value)}>
            <option value="">Todos</option>
            {TIPOS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {!listaQ.isLoading && (listaQ.data?.items.length ?? 0) === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhum permissionário"
          description="Cadastre o primeiro permissionário do transporte regulado."
          action={
            canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Cadastrar permissionário
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Nome</TH>
              <TH>CPF</TH>
              <TH>Tipo de serviço</TH>
              <TH>Permissão</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {listaQ.isLoading && (
              <TR>
                <TD colSpan={6} className="text-center text-muted-foreground">
                  Carregando...
                </TD>
              </TR>
            )}
            {listaQ.data?.items.map((p) => (
              <TR key={p.id}>
                <TD>{p.nome}</TD>
                <TD className="font-mono">{p.cpf}</TD>
                <TD>{TIPO_LABEL[p.tipo_servico] ?? p.tipo_servico}</TD>
                <TD className="text-muted-foreground">{p.numero_permissao ?? "—"}</TD>
                <TD>
                  <Badge intent={SIT_INTENT[p.situacao] ?? "neutral"}>
                    {SIT_LABEL[p.situacao] ?? p.situacao}
                  </Badge>
                </TD>
                <TD className="text-right">
                  <div className="inline-flex flex-wrap justify-end gap-2">
                    {canEdit && (
                      <Button variant="secondary" size="sm" onClick={() => openEdit(p)}>
                        Editar
                      </Button>
                    )}
                    {canEdit && p.situacao !== "ativo" && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => actionM.mutate({ id: p.id, acao: "reativar" })}
                      >
                        Reativar
                      </Button>
                    )}
                    {canEdit && p.situacao !== "suspenso" && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => actionM.mutate({ id: p.id, acao: "suspender" })}
                      >
                        Suspender
                      </Button>
                    )}
                    {canEdit && p.situacao !== "inativo" && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => actionM.mutate({ id: p.id, acao: "inativar" })}
                      >
                        Inativar
                      </Button>
                    )}
                    {canDelete && (
                      <Button
                        variant="danger"
                        size="sm"
                        disabled={deleteM.isPending}
                        onClick={async () => {
                          const ok = await confirm({
                            title: "Excluir permissionário",
                            message: `Excluir o permissionário "${p.nome}"? Esta ação não pode ser desfeita.`,
                            confirmLabel: "Excluir",
                            intent: "danger",
                          });
                          if (ok) deleteM.mutate(p.id);
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
        title={editing ? `Editar — ${editing.nome}` : "Novo permissionário"}
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
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Label htmlFor="nome" required>
              Nome
            </Label>
            <Input id="nome" value={form.nome} onChange={(e) => set("nome", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="cpf" required>
              CPF
            </Label>
            <Input id="cpf" value={form.cpf} onChange={(e) => set("cpf", e.target.value)} placeholder="000.000.000-00" />
          </div>
          <div>
            <Label htmlFor="rg">RG</Label>
            <Input id="rg" value={form.rg} onChange={(e) => set("rg", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="nasc">Data de nascimento</Label>
            <Input id="nasc" type="date" value={form.data_nascimento} onChange={(e) => set("data_nascimento", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="tel">Telefone</Label>
            <Input id="tel" value={form.telefone} onChange={(e) => set("telefone", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="email">E-mail</Label>
            <Input id="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="tipo" required>
              Tipo de serviço
            </Label>
            <Select id="tipo" value={form.tipo_servico} onChange={(e) => set("tipo_servico", e.target.value as TipoServico)}>
              {TIPOS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="cnh">CNH (número)</Label>
            <Input id="cnh" value={form.cnh_numero} onChange={(e) => set("cnh_numero", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="cnhcat">CNH categoria</Label>
            <Select id="cnhcat" value={form.cnh_categoria} onChange={(e) => set("cnh_categoria", e.target.value)}>
              <option value="">—</option>
              {CNH_CATS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="cnhval">CNH validade</Label>
            <Input id="cnhval" type="date" value={form.cnh_validade} onChange={(e) => set("cnh_validade", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="numperm">Número da permissão</Label>
            <Input id="numperm" value={form.numero_permissao} onChange={(e) => set("numero_permissao", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="sit">Situação</Label>
            <Select id="sit" value={form.situacao} onChange={(e) => set("situacao", e.target.value as PermissionarioSituacao)}>
              {SITUACOES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="ini">Início da permissão</Label>
            <Input id="ini" type="date" value={form.data_inicio_permissao} onChange={(e) => set("data_inicio_permissao", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="val">Validade da permissão</Label>
            <Input id="val" type="date" value={form.data_validade_permissao} onChange={(e) => set("data_validade_permissao", e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="obs">Observações</Label>
            <Textarea id="obs" rows={2} value={form.observacoes} onChange={(e) => set("observacoes", e.target.value)} />
          </div>
          {err && (
            <div role="alert" className="sm:col-span-2 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
              {err}
            </div>
          )}
        </div>
      </Dialog>
    </div>
  );
}
