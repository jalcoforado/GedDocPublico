"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type Grupo, type GrupoTransacao } from "@/lib/api";

type FormState = Omit<Grupo, "id">;

export default function GruposPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState<Grupo | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<FormState>({ grupo: "", id_nivel: 0, id_sistema: 0 });
  const [permsState, setPermsState] = useState<Record<number, GrupoTransacao>>({});
  const [err, setErr] = useState<string | null>(null);

  const gruposQ = useQuery({ queryKey: ["grupos"], queryFn: api.grupos.list });
  const niveisQ = useQuery({ queryKey: ["niveis"], queryFn: api.niveis });
  const sistemasQ = useQuery({ queryKey: ["sistemas"], queryFn: api.sistemas });
  const transacoesQ = useQuery({ queryKey: ["transacoes"], queryFn: api.transacoes });

  const groupPermsQ = useQuery({
    enabled: !!editing,
    queryKey: ["grupo-transacoes", editing?.id],
    queryFn: () => api.grupos.transacoes(editing!.id),
  });

  const createM = useMutation({
    mutationFn: (d: FormState) => api.grupos.create(d),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["grupos"] });
      toast.success("Grupo criado.");
      setCreating(false);
      setForm({ grupo: "", id_nivel: 0, id_sistema: 0 });
    },
    onError: (e: Error) => setErr(e.message),
  });
  const updateM = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<FormState> }) =>
      api.grupos.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["grupos"] }),
    onError: (e: Error) => setErr(e.message),
  });
  const setPermsM = useMutation({
    mutationFn: (transacoes: GrupoTransacao[]) =>
      api.grupos.setTransacoes(editing!.id, transacoes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["grupo-transacoes", editing?.id] });
      toast.success("Permissões atualizadas.");
      setEditing(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function openEdit(g: Grupo) {
    setEditing(g);
    setErr(null);
  }

  function togglePerm(
    transId: number,
    field: "inserir" | "atualizar" | "excluir",
    value: boolean
  ) {
    setPermsState((s) => {
      const current = s[transId] ?? {
        id_transacao: transId,
        inserir: false,
        atualizar: false,
        excluir: false,
      };
      return { ...s, [transId]: { ...current, [field]: value } };
    });
  }

  // Inicializa permsState quando carrega
  if (groupPermsQ.data && Object.keys(permsState).length === 0 && editing) {
    const initial: Record<number, GrupoTransacao> = {};
    for (const gt of groupPermsQ.data) initial[gt.id_transacao] = gt;
    setPermsState(initial);
  }

  function saveGroupPerms() {
    const list: GrupoTransacao[] = (transacoesQ.data ?? [])
      .map((t) => permsState[t.id])
      .filter((x): x is GrupoTransacao => !!x && (x.inserir || x.atualizar || x.excluir));
    setPermsM.mutate(list);
  }

  function closePerms() {
    setEditing(null);
    setPermsState({});
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-primary">Grupos & Permissões</h1>
        <Button onClick={() => setCreating(true)}>Novo grupo</Button>
      </div>

      <Table>
        <THead>
          <TR>
            <TH>Grupo</TH>
            <TH>Nível</TH>
            <TH>Sistema</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {gruposQ.isLoading && (
            <TR>
              <TD colSpan={4} className="text-center text-muted-foreground">
                Carregando...
              </TD>
            </TR>
          )}
          {gruposQ.data?.map((g) => (
            <TR key={g.id}>
              <TD className="font-medium">{g.grupo}</TD>
              <TD>{niveisQ.data?.find((n) => n.id === g.id_nivel)?.nivel ?? g.id_nivel}</TD>
              <TD>{sistemasQ.data?.find((s) => s.id === g.id_sistema)?.sistema ?? g.id_sistema}</TD>
              <TD className="text-right">
                <Button variant="secondary" size="sm" onClick={() => openEdit(g)}>
                  Permissões
                </Button>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="Novo grupo"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreating(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => createM.mutate(form)}
              disabled={createM.isPending || !form.grupo || !form.id_nivel || !form.id_sistema}
            >
              Criar
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <Label required>Nome</Label>
            <Input
              value={form.grupo}
              onChange={(e) => setForm({ ...form, grupo: e.target.value })}
            />
          </div>
          <div>
            <Label required>Nível</Label>
            <Select
              value={form.id_nivel || ""}
              onChange={(e) => setForm({ ...form, id_nivel: Number(e.target.value) })}
            >
              <option value="">—</option>
              {niveisQ.data?.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.nivel} (valor {n.valor})
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label required>Sistema</Label>
            <Select
              value={form.id_sistema || ""}
              onChange={(e) => setForm({ ...form, id_sistema: Number(e.target.value) })}
            >
              <option value="">—</option>
              {sistemasQ.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.sistema} {s.app ? `(${s.app})` : ""}
                </option>
              ))}
            </Select>
          </div>
          {err && (
            <div
              role="alert"
              className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              {err}
            </div>
          )}
        </div>
      </Dialog>

      <Dialog
        open={!!editing}
        onClose={closePerms}
        title={editing ? `Permissões — ${editing.grupo}` : ""}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={closePerms}>
              Cancelar
            </Button>
            <Button onClick={saveGroupPerms} disabled={setPermsM.isPending}>
              {setPermsM.isPending ? "Salvando..." : "Salvar permissões"}
            </Button>
          </>
        }
      >
        {groupPermsQ.isLoading ? (
          <p className="text-sm text-muted-foreground">Carregando permissões...</p>
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Transação</TH>
                <TH>Inserir</TH>
                <TH>Atualizar</TH>
                <TH>Excluir</TH>
              </TR>
            </THead>
            <TBody>
              {transacoesQ.data?.map((t) => {
                const p = permsState[t.id];
                return (
                  <TR key={t.id}>
                    <TD>
                      <div className="font-medium">{t.transacao}</div>
                      <div className="font-mono text-xs text-muted-foreground">{t.codigo}</div>
                    </TD>
                    {(["inserir", "atualizar", "excluir"] as const).map((field) => (
                      <TD key={field}>
                        <Checkbox
                          checked={p?.[field] ?? false}
                          onChange={(e) => togglePerm(t.id, field, e.target.checked)}
                          aria-label={`${field} em ${t.transacao}`}
                        />
                      </TD>
                    ))}
                  </TR>
                );
              })}
            </TBody>
          </Table>
        )}
      </Dialog>
    </div>
  );
}
