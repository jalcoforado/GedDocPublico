"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import {
  api,
  NIVEL_SIGILO_LABEL,
  type NivelSigilo,
  type ResetSenhaResponse,
  type UsuarioDetail,
  type UsuarioInput,
} from "@/lib/api";

const NIVEIS_SIGILO: NivelSigilo[] = [
  "ostensivo",
  "interno",
  "reservado",
  "secreto",
  "ultrassecreto",
];
import { useAuth } from "@/lib/auth";

const EMPTY_FORM: UsuarioInput = {
  nome: "",
  email: "",
  cpf: "",
  id_unidade_trabalho: null,
  cargo: "",
  ativo: true,
  senha: "",
  grupos: [],
};

export default function UsuariosPage() {
  const { can, perms } = useAuth();
  const isSuper = perms?.is_super_usuario ?? false;
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<UsuarioDetail | null>(null);
  const [form, setForm] = useState<UsuarioInput>(EMPTY_FORM);
  const [err, setErr] = useState<string | null>(null);
  const [resetResult, setResetResult] = useState<ResetSenhaResponse | null>(null);
  const [senhaCopiada, setSenhaCopiada] = useState(false);

  const usuariosQ = useQuery({
    queryKey: ["usuarios", page, q],
    queryFn: () => api.usuarios.list({ page, page_size: 20, q: q || undefined }),
  });
  const unidadesQ = useQuery({ queryKey: ["unidades-all"], queryFn: () => api.unidades.list({ page_size: 200 }) });
  const gruposQ = useQuery({ queryKey: ["grupos"], queryFn: api.grupos.list });

  const createM = useMutation({
    mutationFn: (data: UsuarioInput) => api.usuarios.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["usuarios"] });
      toast.success("Usuário criado.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const updateM = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<UsuarioInput> }) =>
      api.usuarios.update(id, data),
    onSuccess: async (_updated, { id, data }) => {
      if (data.grupos) await api.usuarios.setGrupos(id, data.grupos);
      qc.invalidateQueries({ queryKey: ["usuarios"] });
      toast.success("Alterações salvas.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.usuarios.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["usuarios"] });
      toast.success("Usuário excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const resetM = useMutation({
    mutationFn: (id: number) => api.usuarios.resetarSenha(id),
    onSuccess: (res) => {
      setSenhaCopiada(false);
      setResetResult(res);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function openNew() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setErr(null);
    setDialogOpen(true);
  }

  async function openEdit(id: number) {
    setErr(null);
    const detail = await api.usuarios.get(id);
    setEditing(detail);
    setForm({
      nome: detail.nome,
      email: detail.email,
      cpf: detail.cpf,
      id_unidade_trabalho: detail.id_unidade_trabalho,
      cargo: detail.cargo ?? "",
      ativo: detail.ativo,
      senha: "",
      grupos: detail.grupos,
      nivel_acesso_sigilo: detail.nivel_acesso_sigilo,
    });
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY_FORM);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (editing) {
      const payload: Partial<UsuarioInput> = { ...form };
      if (!payload.senha) delete payload.senha;
      // Só super-usuário altera credencial de sigilo (backend bloqueia com 403).
      if (!isSuper) delete payload.nivel_acesso_sigilo;
      updateM.mutate({ id: editing.id, data: payload });
    } else {
      createM.mutate(form);
    }
  }

  function toggleGrupo(id: number) {
    setForm((f) => {
      const has = f.grupos?.includes(id);
      return {
        ...f,
        grupos: has ? f.grupos!.filter((x) => x !== id) : [...(f.grupos ?? []), id],
      };
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-primary">Usuários</h1>
        {can("usuario", "inserir") && <Button onClick={openNew}>Novo usuário</Button>}
      </div>

      <div className="flex gap-2">
        <Input
          placeholder="Buscar por nome ou e-mail..."
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          className="max-w-sm"
        />
      </div>

      <Table>
        <THead>
          <TR>
            <TH>Nome</TH>
            <TH>E-mail</TH>
            <TH>CPF</TH>
            <TH>Ativo</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {usuariosQ.isLoading && (
            <TR>
              <TD colSpan={5} className="text-center text-muted-foreground">
                Carregando...
              </TD>
            </TR>
          )}
          {usuariosQ.data?.items.map((u) => (
            <TR key={u.id}>
              <TD className="font-medium">{u.nome}</TD>
              <TD className="text-muted-foreground">{u.email}</TD>
              <TD className="font-mono text-xs tabular-nums">{u.cpf}</TD>
              <TD>{u.ativo ? "Sim" : "Não"}</TD>
              <TD className="text-right">
                <div className="inline-flex gap-2">
                  {can("usuario", "atualizar") && (
                    <Button variant="secondary" size="sm" onClick={() => openEdit(u.id)}>
                      Editar
                    </Button>
                  )}
                  {can("usuario", "atualizar") && (
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={resetM.isPending}
                      onClick={async () => {
                        const ok = await confirm({
                          title: "Resetar senha",
                          message: `Gerar uma senha temporária para ${u.nome}? A senha atual deixará de funcionar e a nova será exibida uma única vez.`,
                          confirmLabel: "Gerar senha",
                        });
                        if (ok) resetM.mutate(u.id);
                      }}
                    >
                      Resetar senha
                    </Button>
                  )}
                  {can("usuario", "excluir") && (
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={async () => {
                        const ok = await confirm({
                          title: "Excluir usuário",
                          message: `Excluir ${u.nome}? Esta ação não pode ser desfeita.`,
                          confirmLabel: "Excluir",
                          intent: "danger",
                        });
                        if (ok) deleteM.mutate(u.id);
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

      {usuariosQ.data && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {usuariosQ.data.total} usuários — página {page}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Anterior
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={page * 20 >= usuariosQ.data.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Próxima
            </Button>
          </div>
        </div>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? `Editar — ${editing.nome}` : "Novo usuário"}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={submit} disabled={createM.isPending || updateM.isPending}>
              {createM.isPending || updateM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </>
        }
      >
        <form onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Label htmlFor="nome" required>Nome</Label>
            <Input
              id="nome"
              value={form.nome}
              onChange={(e) => setForm({ ...form, nome: e.target.value })}
              autoComplete="name"
              required
            />
          </div>
          <div>
            <Label htmlFor="email" required>E-mail</Label>
            <Input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              autoComplete="email"
              inputMode="email"
              required
            />
          </div>
          <div>
            <Label htmlFor="cpf" required>CPF (11 dígitos)</Label>
            <Input
              id="cpf"
              maxLength={11}
              inputMode="numeric"
              value={form.cpf}
              onChange={(e) => setForm({ ...form, cpf: e.target.value.replace(/\D/g, "") })}
              required
            />
          </div>
          <div>
            <Label htmlFor="cargo">Cargo</Label>
            <Input
              id="cargo"
              value={form.cargo ?? ""}
              onChange={(e) => setForm({ ...form, cargo: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="unidade">Unidade primária</Label>
            <Select
              id="unidade"
              value={form.id_unidade_trabalho ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  id_unidade_trabalho: e.target.value ? Number(e.target.value) : null,
                })
              }
            >
              <option value="">—</option>
              {unidadesQ.data?.items.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.unidade_trabalho}
                </option>
              ))}
            </Select>
          </div>
          {editing && isSuper && (
            <div>
              <Label htmlFor="nivel-acesso">Credencial de sigilo</Label>
              <Select
                id="nivel-acesso"
                value={form.nivel_acesso_sigilo ?? "interno"}
                onChange={(e) =>
                  setForm({
                    ...form,
                    nivel_acesso_sigilo: e.target.value as NivelSigilo,
                  })
                }
              >
                {NIVEIS_SIGILO.map((n) => (
                  <option key={n} value={n}>
                    {NIVEL_SIGILO_LABEL[n]}
                  </option>
                ))}
              </Select>
              <p className="mt-1 text-xs text-foreground-muted">
                Define até qual grau de sigilo este servidor pode ver.
              </p>
            </div>
          )}
          <div>
            <Label htmlFor="senha" required={!editing}>
              {editing ? "Nova senha (vazio = manter)" : "Senha"}
            </Label>
            <PasswordInput
              id="senha"
              value={form.senha ?? ""}
              onChange={(e) => setForm({ ...form, senha: e.target.value })}
              autoComplete={editing ? "new-password" : "new-password"}
              required={!editing}
            />
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="ativo"
              checked={form.ativo}
              onChange={(e) => setForm({ ...form, ativo: e.target.checked })}
            />
            <Label htmlFor="ativo" className="!mb-0">
              Ativo
            </Label>
          </div>
          <div className="sm:col-span-2">
            <Label>Grupos</Label>
            <div className="grid max-h-40 grid-cols-1 gap-1 overflow-y-auto rounded-md border border-border p-2 sm:grid-cols-2">
              {gruposQ.data?.map((g) => (
                <label key={g.id} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={form.grupos?.includes(g.id) ?? false}
                    onChange={() => toggleGrupo(g.id)}
                  />
                  {g.grupo}
                </label>
              ))}
            </div>
          </div>
          {err && (
            <div
              role="alert"
              className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground sm:col-span-2"
            >
              {err}
            </div>
          )}
        </form>
      </Dialog>

      <Dialog
        open={resetResult !== null}
        onClose={() => setResetResult(null)}
        title="Senha temporária gerada"
        footer={
          <Button onClick={() => setResetResult(null)}>Fechar</Button>
        }
      >
        {resetResult && (
          <div className="space-y-3">
            <p className="text-sm text-foreground-muted">{resetResult.aviso}</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 break-all rounded-md border border-border bg-surface-1 px-3 py-2 font-mono text-base">
                {resetResult.senha_temporaria}
              </code>
              <Button
                variant="secondary"
                size="sm"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(resetResult.senha_temporaria);
                    setSenhaCopiada(true);
                    toast.success("Senha copiada.");
                  } catch {
                    toast.error("Não foi possível copiar — selecione e copie manualmente.");
                  }
                }}
              >
                {senhaCopiada ? "Copiada" : "Copiar"}
              </Button>
            </div>
            <p
              role="alert"
              className="rounded-md bg-warning-soft px-3 py-2 text-xs text-warning-soft-foreground"
            >
              Anote ou copie agora: esta senha não será exibida novamente.
            </p>
          </div>
        )}
      </Dialog>
    </div>
  );
}
