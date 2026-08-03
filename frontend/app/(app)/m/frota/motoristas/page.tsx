"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { IdCard, FileText, Inbox, Plus, Settings2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type CnhCategoria,
  type Motorista,
  type MotoristaSituacao,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const SITUACOES: { value: MotoristaSituacao; label: string }[] = [
  { value: "ativo", label: "Ativo" },
  { value: "afastado", label: "Afastado" },
  { value: "inativo", label: "Inativo" },
];
const CATEGORIAS: CnhCategoria[] = ["A", "B", "AB", "C", "D", "E", "AC", "AD", "AE"];
const SITUACAO_LABEL: Record<string, string> = Object.fromEntries(
  SITUACOES.map((s) => [s.value, s.label]),
);

interface MotoristaForm {
  nome: string;
  cpf: string;
  matricula: string;
  cnh_numero: string;
  cnh_categoria: CnhCategoria;
  cnh_validade: string;
  telefone: string;
  email: string;
  id_unidade: number | null;
  id_usuario: number | null;
  situacao: MotoristaSituacao;
  observacoes: string;
}

const EMPTY: MotoristaForm = {
  nome: "",
  cpf: "",
  matricula: "",
  cnh_numero: "",
  cnh_categoria: "B",
  cnh_validade: "",
  telefone: "",
  email: "",
  id_unidade: null,
  id_usuario: null,
  situacao: "ativo",
  observacoes: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

function cnhVencida(validade: string): boolean {
  if (!validade) return false;
  return validade < new Date().toISOString().slice(0, 10);
}

export default function MotoristasPage() {
  const { can } = useAuth();
  const canCreate = can("frota", "inserir");
  const canEdit = can("frota", "atualizar");
  const canDelete = can("frota", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Motorista | null>(null);
  const [form, setForm] = useState<MotoristaForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const motoristasQ = useQuery({
    queryKey: ["frota-motoristas"],
    queryFn: () => api.motoristas.listAll(),
  });
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });
  const unidades = unidadesQ.data?.items ?? [];
  const unidadeNome = (id: number | null) =>
    unidades.find((u) => u.id === id)?.unidade_trabalho ?? "—";

  const invalidate = () => qc.invalidateQueries({ queryKey: ["frota-motoristas"] });

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing ? api.motoristas.update(editing.id, data) : api.motoristas.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Motorista atualizado." : "Motorista cadastrado.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const situacaoM = useMutation({
    mutationFn: ({ id, inativar }: { id: number; inativar: boolean }) =>
      inativar ? api.motoristas.inativar(id) : api.motoristas.reativar(id),
    onSuccess: () => {
      invalidate();
      toast.success("Situação atualizada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.motoristas.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Motorista excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof MotoristaForm>(key: K, value: MotoristaForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setDialogOpen(true);
  }

  function openEdit(m: Motorista) {
    setEditing(m);
    setForm({
      nome: m.nome,
      cpf: m.cpf,
      matricula: m.matricula ?? "",
      cnh_numero: m.cnh_numero,
      cnh_categoria: m.cnh_categoria,
      cnh_validade: m.cnh_validade ?? "",
      telefone: m.telefone ?? "",
      email: m.email ?? "",
      id_unidade: m.id_unidade,
      id_usuario: m.id_usuario,
      situacao: m.situacao,
      observacoes: m.observacoes ?? "",
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
    const payload = {
      nome: form.nome.trim(),
      cpf: form.cpf.trim(),
      matricula: nullify(form.matricula),
      cnh_numero: form.cnh_numero.trim(),
      cnh_categoria: form.cnh_categoria,
      cnh_validade: form.cnh_validade,
      telefone: nullify(form.telefone),
      email: nullify(form.email),
      id_unidade: form.id_unidade ?? null,
      id_usuario: form.id_usuario ?? null,
      situacao: form.situacao,
      observacoes: nullify(form.observacoes),
    };
    saveM.mutate(payload);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={IdCard}
        title="Motoristas"
        description="Cadastro de condutores da frota municipal."
        breadcrumbs={[{ label: "Frota Pública", href: "/m/frota" }, { label: "Motoristas" }]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Novo motorista
            </Button>
          ) : undefined
        }
      />

      {!motoristasQ.isLoading && (motoristasQ.data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhum motorista cadastrado"
          description="Cadastre o primeiro condutor da frota."
          action={
            canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Cadastrar motorista
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
              <TH>CNH</TH>
              <TH>Validade</TH>
              <TH>Unidade</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {motoristasQ.isLoading && (
              <TR>
                <TD colSpan={7} className="text-center text-muted-foreground">
                  Carregando motoristas...
                </TD>
              </TR>
            )}
            {motoristasQ.data?.map((m) => (
              <TR key={m.id}>
                <TD className="font-medium">{m.nome}</TD>
                <TD className="font-mono text-xs">{m.cpf}</TD>
                <TD>
                  <span className="font-mono text-xs">{m.cnh_numero}</span>
                  <Badge intent="neutral" className="ml-2">
                    {m.cnh_categoria}
                  </Badge>
                </TD>
                <TD>
                  {cnhVencida(m.cnh_validade) ? (
                    <Badge intent="danger">Vencida</Badge>
                  ) : (
                    <span className="tabular-nums">{m.cnh_validade}</span>
                  )}
                </TD>
                <TD className="text-muted-foreground">{unidadeNome(m.id_unidade)}</TD>
                <TD>
                  <Badge intent={m.situacao === "ativo" ? "success" : "neutral"}>
                    {SITUACAO_LABEL[m.situacao] ?? m.situacao}
                  </Badge>
                </TD>
                <TD className="text-right">
                  <div className="inline-flex gap-2">
                    {canEdit && (
                      <Button variant="secondary" size="sm" onClick={() => openEdit(m)}>
                        Editar
                      </Button>
                    )}
                    {canEdit && (
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={situacaoM.isPending}
                        onClick={async () => {
                          const inativar = m.situacao !== "inativo";
                          const ok = await confirm({
                            title: inativar ? "Inativar motorista" : "Reativar motorista",
                            message: inativar
                              ? `Inativar "${m.nome}"? Ele deixa de constar como condutor ativo.`
                              : `Reativar "${m.nome}"?`,
                            confirmLabel: inativar ? "Inativar" : "Reativar",
                          });
                          if (ok) situacaoM.mutate({ id: m.id, inativar });
                        }}
                      >
                        {m.situacao !== "inativo" ? "Inativar" : "Reativar"}
                      </Button>
                    )}
                    {canDelete && (
                      <Button
                        variant="danger"
                        size="sm"
                        disabled={deleteM.isPending}
                        onClick={async () => {
                          const ok = await confirm({
                            title: "Excluir motorista",
                            message: `Excluir "${m.nome}"? Esta ação não pode ser desfeita.`,
                            confirmLabel: "Excluir",
                            intent: "danger",
                          });
                          if (ok) deleteM.mutate(m.id);
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
        title={editing ? `Editar — ${editing.nome}` : "Novo motorista"}
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
          <SectionCard
            icon={FileText}
            title="Identificação"
            description="Dados pessoais e habilitação do condutor."
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
                <Input
                  id="cpf"
                  value={form.cpf}
                  onChange={(e) => set("cpf", e.target.value)}
                  className="font-mono"
                  placeholder="00000000000"
                />
              </div>
              <div>
                <Label htmlFor="matricula">Matrícula</Label>
                <Input
                  id="matricula"
                  value={form.matricula}
                  onChange={(e) => set("matricula", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="cnh_numero" required>
                  CNH (número)
                </Label>
                <Input
                  id="cnh_numero"
                  value={form.cnh_numero}
                  onChange={(e) => set("cnh_numero", e.target.value)}
                  className="font-mono"
                  placeholder="00000000000"
                />
              </div>
              <div>
                <Label htmlFor="cnh_categoria" required>
                  CNH (categoria)
                </Label>
                <Select
                  id="cnh_categoria"
                  value={form.cnh_categoria}
                  onChange={(e) => set("cnh_categoria", e.target.value as CnhCategoria)}
                >
                  {CATEGORIAS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="cnh_validade" required>
                  CNH (validade)
                </Label>
                <Input
                  id="cnh_validade"
                  type="date"
                  value={form.cnh_validade}
                  onChange={(e) => set("cnh_validade", e.target.value)}
                />
                {cnhVencida(form.cnh_validade) && (
                  <p className="mt-1 text-xs text-danger">CNH vencida nesta data.</p>
                )}
              </div>
            </div>
          </SectionCard>

          <SectionCard
            icon={Settings2}
            title="Contato, lotação e situação"
            description="Telefone/e-mail, unidade de lotação, vínculo com usuário e situação."
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="telefone">Telefone</Label>
                <Input
                  id="telefone"
                  value={form.telefone}
                  onChange={(e) => set("telefone", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="email">E-mail</Label>
                <Input
                  id="email"
                  type="email"
                  value={form.email}
                  onChange={(e) => set("email", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="unidade">Unidade (lotação)</Label>
                <Select
                  id="unidade"
                  value={form.id_unidade ?? ""}
                  onChange={(e) =>
                    set("id_unidade", e.target.value ? Number(e.target.value) : null)
                  }
                >
                  <option value="">—</option>
                  {unidades.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.unidade_trabalho}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="situacao">Situação</Label>
                <Select
                  id="situacao"
                  value={form.situacao}
                  onChange={(e) => set("situacao", e.target.value as MotoristaSituacao)}
                >
                  {SITUACOES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="sm:col-span-2">
                <Label htmlFor="obs">Observações</Label>
                <Textarea
                  id="obs"
                  rows={3}
                  value={form.observacoes}
                  onChange={(e) => set("observacoes", e.target.value)}
                />
              </div>
            </div>
          </SectionCard>

          {err && (
            <div role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
              {err}
            </div>
          )}
        </div>
      </Dialog>
    </div>
  );
}
