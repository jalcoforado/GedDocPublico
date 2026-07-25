"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
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

type SituacaoFonte = "ATIVA" | "SUSPENSA" | "ENCERRADA";

interface FormState {
  codigo: string;
  descricao: string;
  grupos_despesa_permitidos: string[];
  exercicio: string;
  esfera_origem: string;
  tipo_vinculacao: string;
  situacao: SituacaoFonte;
  vigencia_inicio: string;
  vigencia_fim: string;
}

const EMPTY: FormState = {
  codigo: "", descricao: "", grupos_despesa_permitidos: [],
  exercicio: "", esfera_origem: "", tipo_vinculacao: "", situacao: "ATIVA",
  vigencia_inicio: "", vigencia_fim: "",
};

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
      exercicio: f.exercicio != null ? String(f.exercicio) : "",
      esfera_origem: f.esfera_origem ?? "",
      tipo_vinculacao: f.tipo_vinculacao ?? "",
      situacao: f.situacao ?? "ATIVA",
      vigencia_inicio: f.vigencia_inicio ?? "",
      vigencia_fim: f.vigencia_fim ?? "",
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
        exercicio: form.exercicio ? Number(form.exercicio) : null,
        esfera_origem: form.esfera_origem.trim() || null,
        tipo_vinculacao: form.tipo_vinculacao.trim() || null,
        situacao: form.situacao,
        vigencia_inicio: form.vigencia_inicio || null,
        vigencia_fim: form.vigencia_fim || null,
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
          <div>
            <Label htmlFor="fonte-exercicio">Exercício</Label>
            <Input
              id="fonte-exercicio"
              type="number"
              value={form.exercicio}
              onChange={(e) => setForm({ ...form, exercicio: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="fonte-situacao">Situação</Label>
            <Select
              id="fonte-situacao"
              value={form.situacao}
              onChange={(e) => setForm({ ...form, situacao: e.target.value as SituacaoFonte })}
            >
              <option value="ATIVA">Ativa</option>
              <option value="SUSPENSA">Suspensa</option>
              <option value="ENCERRADA">Encerrada</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="fonte-esfera">Esfera de origem</Label>
            <Input
              id="fonte-esfera"
              value={form.esfera_origem}
              onChange={(e) => setForm({ ...form, esfera_origem: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="fonte-vinculacao">Tipo de vinculação</Label>
            <Input
              id="fonte-vinculacao"
              value={form.tipo_vinculacao}
              onChange={(e) => setForm({ ...form, tipo_vinculacao: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="fonte-vig-inicio">Vigência (início)</Label>
            <Input
              id="fonte-vig-inicio"
              type="date"
              value={form.vigencia_inicio}
              onChange={(e) => setForm({ ...form, vigencia_inicio: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="fonte-vig-fim">Vigência (fim)</Label>
            <Input
              id="fonte-vig-fim"
              type="date"
              value={form.vigencia_fim}
              onChange={(e) => setForm({ ...form, vigencia_fim: e.target.value })}
            />
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
