"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type FonteRecursos } from "@/lib/api";

const GRUPO_LABELS: Record<string, string> = {
  PESSOAL: "Pessoal",
  CUSTEIO: "Custeio",
  INVESTIMENTO: "Investimento",
  DIVIDA: "Dívida",
  OUTRAS: "Outras",
};

interface FormState {
  codigo: string;
  descricao: string;
  grupos_despesa_permitidos: string[];
}

const EMPTY: FormState = { codigo: "", descricao: "", grupos_despesa_permitidos: [] };

export default function FontesPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const listQ = useQuery({
    queryKey: ["pag-fontes"],
    queryFn: () => api.pagamentos.cadastros.fontes.list(),
  });
  const enumsQ = useQuery({
    queryKey: ["pag-enums"],
    queryFn: () => api.pagamentos.cadastros.enums(),
  });

  function openNew() {
    setEditId(null);
    setForm(EMPTY);
    setErr(null);
    setOpen(true);
  }

  function openEdit(f: FonteRecursos) {
    setEditId(f.id);
    setForm({
      codigo: f.codigo,
      descricao: f.descricao,
      grupos_despesa_permitidos: f.grupos_despesa_permitidos,
    });
    setErr(null);
    setOpen(true);
  }

  function toggleGrupo(g: string) {
    setForm((prev) => ({
      ...prev,
      grupos_despesa_permitidos: prev.grupos_despesa_permitidos.includes(g)
        ? prev.grupos_despesa_permitidos.filter((x) => x !== g)
        : [...prev.grupos_despesa_permitidos, g],
    }));
  }

  const saveM = useMutation({
    mutationFn: () => {
      const payload = {
        codigo: form.codigo.trim(),
        descricao: form.descricao.trim(),
        grupos_despesa_permitidos: form.grupos_despesa_permitidos,
      };
      return editId === null
        ? api.pagamentos.cadastros.fontes.create(payload)
        : api.pagamentos.cadastros.fontes.update(editId, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-fontes"] });
      toast.success(editId === null ? "Fonte criada." : "Fonte atualizada.");
      setOpen(false);
    },
    onError: (e: Error) => setErr(e.message),
  });

  const removeM = useMutation({
    mutationFn: (id: number) => api.pagamentos.cadastros.fontes.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-fontes"] });
      toast.success("Fonte excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function excluir(f: FonteRecursos) {
    const ok = await confirm({
      title: "Excluir fonte de recursos",
      message: "Esta ação não pode ser desfeita. Deseja realmente excluir esta fonte?",
      confirmLabel: "Excluir",
      intent: "danger",
    });
    if (ok) removeM.mutate(f.id);
  }

  const fontes = listQ.data ?? [];
  const grupoOptions = enumsQ.data?.grupo_despesa ?? Object.keys(GRUPO_LABELS);
  const podeSalvar = form.codigo.trim().length > 0 && form.descricao.trim().length > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-aprimora">Fontes de recursos</h1>
        <Button onClick={openNew}>Novo</Button>
      </div>

      <Table>
        <THead>
          <TR>
            <TH>Código</TH>
            <TH>Descrição</TH>
            <TH>Grupos permitidos</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {!listQ.isLoading && fontes.length === 0 && (
            <TR>
              <TD colSpan={4} className="py-6 text-center text-sm text-muted-foreground">
                Nenhuma fonte cadastrada.
              </TD>
            </TR>
          )}
          {fontes.map((f) => (
            <TR key={f.id}>
              <TD>{f.codigo}</TD>
              <TD>{f.descricao}</TD>
              <TD>
                {f.grupos_despesa_permitidos.map((g) => GRUPO_LABELS[g] ?? g).join(", ") || "—"}
              </TD>
              <TD className="text-right">
                <div className="inline-flex gap-2">
                  <Button variant="secondary" size="sm" onClick={() => openEdit(f)}>
                    Editar
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => excluir(f)}>
                    Excluir
                  </Button>
                </div>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={editId === null ? "Nova fonte de recursos" : "Editar fonte de recursos"}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => saveM.mutate()} disabled={!podeSalvar || saveM.isPending}>
              {saveM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </>
        }
      >
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor="fonte-codigo" required>
              Código
            </Label>
            <Input
              id="fonte-codigo"
              value={form.codigo}
              onChange={(e) => setForm({ ...form, codigo: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="fonte-descricao" required>
              Descrição
            </Label>
            <Input
              id="fonte-descricao"
              value={form.descricao}
              onChange={(e) => setForm({ ...form, descricao: e.target.value })}
              required
            />
          </div>
          <div className="col-span-2">
            <Label>Grupos de despesa permitidos</Label>
            <div className="flex flex-wrap gap-4 pt-1">
              {grupoOptions.map((g) => (
                <label key={g} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={form.grupos_despesa_permitidos.includes(g)}
                    onChange={() => toggleGrupo(g)}
                  />
                  {GRUPO_LABELS[g] ?? g}
                </label>
              ))}
            </div>
          </div>
          {err && (
            <div
              role="alert"
              className="col-span-2 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              {err}
            </div>
          )}
        </div>
      </Dialog>
    </div>
  );
}
