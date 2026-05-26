"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { UnidadePicker } from "@/components/UnidadePicker";
import { api, type UnidadeTrabalho } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type FormState = Omit<UnidadeTrabalho, "id">;
const EMPTY: FormState = {
  unidade_trabalho: "",
  sigla: "",
  id_unidade_pai: null,
  id_tipo_unidade_trabalho: null,
};

export default function UnidadesPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<UnidadeTrabalho | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const listQ = useQuery({
    queryKey: ["unidades", page, q],
    queryFn: () => api.unidades.list({ page, page_size: 20, q: q || undefined }),
  });
  const tiposQ = useQuery({ queryKey: ["tipos-unidade"], queryFn: api.tiposUnidade });
  const todasQ = useQuery({ queryKey: ["unidades-all"], queryFn: () => api.unidades.list({ page_size: 200 }) });

  const createM = useMutation({
    mutationFn: (d: FormState) => api.unidades.create(d),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["unidades"] });
      toast.success("Unidade criada.");
      close();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const updateM = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<FormState> }) =>
      api.unidades.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["unidades"] });
      toast.success("Alterações salvas.");
      close();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.unidades.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["unidades"] });
      toast.success("Unidade excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function close() {
    setOpen(false);
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
  }

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setOpen(true);
  }

  function openEdit(u: UnidadeTrabalho) {
    setEditing(u);
    setForm({
      unidade_trabalho: u.unidade_trabalho,
      sigla: u.sigla,
      id_unidade_pai: u.id_unidade_pai,
      id_tipo_unidade_trabalho: u.id_tipo_unidade_trabalho,
    });
    setErr(null);
    setOpen(true);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (editing) updateM.mutate({ id: editing.id, data: form });
    else createM.mutate(form);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-primary">Unidades de Trabalho</h1>
        {can("unidadeTrabalho", "inserir") && <Button onClick={openNew}>Nova unidade</Button>}
      </div>

      <Input
        placeholder="Buscar por nome ou sigla..."
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setPage(1);
        }}
        className="max-w-sm"
      />

      <Table>
        <THead>
          <TR>
            <TH>Nome</TH>
            <TH>Sigla</TH>
            <TH>Tipo</TH>
            <TH>Unidade Pai</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {listQ.isLoading && (
            <TR>
              <TD colSpan={5} className="text-center text-muted-foreground">
                Carregando...
              </TD>
            </TR>
          )}
          {listQ.data?.items.map((u) => (
            <TR key={u.id}>
              <TD className="font-medium">{u.unidade_trabalho}</TD>
              <TD>{u.sigla ?? "—"}</TD>
              <TD className="text-muted-foreground">
                {tiposQ.data?.find((t) => t.id === u.id_tipo_unidade_trabalho)?.tipo_unidade_trabalho ?? "—"}
              </TD>
              <TD className="text-muted-foreground">
                {todasQ.data?.items.find((x) => x.id === u.id_unidade_pai)?.unidade_trabalho ?? "—"}
              </TD>
              <TD className="text-right">
                <div className="inline-flex gap-2">
                  {can("unidadeTrabalho", "atualizar") && (
                    <Button variant="secondary" size="sm" onClick={() => openEdit(u)}>
                      Editar
                    </Button>
                  )}
                  {can("unidadeTrabalho", "excluir") && (
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={async () => {
                        const ok = await confirm({
                          title: "Excluir unidade",
                          message: `Excluir ${u.unidade_trabalho}? Esta ação não pode ser desfeita.`,
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

      {listQ.data && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {listQ.data.total} unidades — página {page}
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
              disabled={page * 20 >= listQ.data.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Próxima
            </Button>
          </div>
        </div>
      )}

      <Dialog
        open={open}
        onClose={close}
        title={editing ? `Editar — ${editing.unidade_trabalho}` : "Nova unidade"}
        footer={
          <>
            <Button variant="secondary" onClick={close}>
              Cancelar
            </Button>
            <Button onClick={submit} disabled={createM.isPending || updateM.isPending}>
              {createM.isPending || updateM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </>
        }
      >
        <form onSubmit={submit} className="space-y-3">
          <div>
            <Label htmlFor="ut-nome" required>Nome</Label>
            <Input
              id="ut-nome"
              value={form.unidade_trabalho}
              onChange={(e) => setForm({ ...form, unidade_trabalho: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="ut-sigla">Sigla</Label>
            <Input
              id="ut-sigla"
              value={form.sigla ?? ""}
              onChange={(e) => setForm({ ...form, sigla: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="ut-tipo">Tipo</Label>
            <Select
              id="ut-tipo"
              value={form.id_tipo_unidade_trabalho ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  id_tipo_unidade_trabalho: e.target.value ? Number(e.target.value) : null,
                })
              }
            >
              <option value="">—</option>
              {tiposQ.data?.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.tipo_unidade_trabalho}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Unidade Pai</Label>
            <UnidadePicker
              value={form.id_unidade_pai}
              onChange={(v) =>
                setForm({
                  ...form,
                  // Não permite escolher a própria unidade como pai —
                  // o picker não filtra, então fazemos a checagem aqui.
                  id_unidade_pai: v === editing?.id ? null : v,
                })
              }
              placeholder="Sem pai (raiz)"
            />
          </div>
          {err && (
            <div
              role="alert"
              className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              {err}
            </div>
          )}
        </form>
      </Dialog>
    </div>
  );
}
