"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { useValidacaoCampos } from "@/components/pagamentos/useValidacaoCampos";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonRow } from "@/components/ui/skeleton";
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
    v.reiniciar();
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
    v.reiniciar();
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
  const v = useValidacaoCampos(
    {
      codigo: !form.codigo.trim() && "Informe o código da fonte, como no orçamento.",
      descricao: !form.descricao.trim() && "Descreva a fonte em poucas palavras.",
      vigencia_fim:
        !!form.vigencia_inicio &&
        !!form.vigencia_fim &&
        form.vigencia_fim < form.vigencia_inicio &&
        "O fim da vigência tem de ser depois do início.",
    },
    { codigo: "fonte-codigo", descricao: "fonte-descricao", vigencia_fim: "fonte-vig-fim" },
  );

  function salvar() {
    if (v.conferir()) saveM.mutate();
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={BookOpen}
        title="Fontes de recursos"
        description="De onde vem o dinheiro de cada despesa e em quais grupos ele pode ser gasto."
        actions={
          <Button onClick={openNew}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Nova fonte de recursos
          </Button>
        }
      />

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
          {listQ.isLoading &&
            Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} cols={4} />)}
          {!listQ.isLoading && fontes.length === 0 && (
            <TR>
              <TD colSpan={4} className="p-0">
                <EmptyState
                  icon={BookOpen}
                  title="Nenhuma fonte de recursos cadastrada"
                  description="Cadastre as fontes antes das contas bancárias: toda conta pertence a uma."
                  action={
                    <Button onClick={openNew}>
                      <Plus className="h-4 w-4" aria-hidden="true" />
                      Nova fonte de recursos
                    </Button>
                  }
                  className="rounded-none border-0 bg-transparent"
                />
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
                <AcoesDaLinha
                  acoes={[
                    { label: "Editar", icon: Pencil, onClick: () => openEdit(f) },
                    { label: "Excluir", icon: Trash2, perigo: true, onClick: () => excluir(f) },
                  ]}
                />
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={editId === null ? "Nova fonte de recursos" : "Editar fonte de recursos"}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={salvar} loading={saveM.isPending}>
              {editId === null ? "Cadastrar fonte" : "Salvar alterações"}
            </Button>
          </>
        }
      >
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-[10rem_minmax(0,1fr)]">
            <FormField label="Código" required error={v.erro("codigo")}>
              <Input
                id="fonte-codigo"
                value={form.codigo}
                onChange={(e) => setForm({ ...form, codigo: e.target.value })}
                onBlur={v.tocar("codigo")}
                maxLength={20}
                placeholder="Ex.: 1.500.000"
              />
            </FormField>
            <FormField label="Descrição" required error={v.erro("descricao")}>
              <Input
                id="fonte-descricao"
                value={form.descricao}
                onChange={(e) => setForm({ ...form, descricao: e.target.value })}
                onBlur={v.tocar("descricao")}
                maxLength={200}
                placeholder="Ex.: Recursos não vinculados de impostos"
              />
            </FormField>
          </div>

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium text-foreground">Grupos de despesa permitidos</legend>
            <div className="flex flex-wrap gap-x-5 gap-y-2">
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
            <p className="text-xs text-foreground-muted">
              {form.grupos_despesa_permitidos.length === 0
                ? "Nenhum marcado: contas desta fonte podem ser de qualquer grupo."
                : "Contas bancárias desta fonte só podem ser dos grupos marcados."}
            </p>
          </fieldset>

          <EscolhaSegmentada
            nome="fonte-situacao"
            titulo="Situação"
            valor={form.situacao}
            onChange={(s) => setForm({ ...form, situacao: s })}
            opcoes={[
              { valor: "ATIVA", rotulo: "Ativa" },
              { valor: "SUSPENSA", rotulo: "Suspensa" },
              { valor: "ENCERRADA", rotulo: "Encerrada" },
            ]}
            moldura={false}
          />

          <div className="space-y-4 border-t border-border pt-4">
            <p className="text-sm font-semibold text-foreground">
              Detalhes{" "}
              <span className="text-xs font-normal text-foreground-subtle">opcionais</span>
            </p>
            <GradeCampos colunas={3}>
              <FormField label="Exercício">
                <Input
                  id="fonte-exercicio"
                  type="number"
                  inputMode="numeric"
                  value={form.exercicio}
                  onChange={(e) => setForm({ ...form, exercicio: e.target.value })}
                  placeholder={`Ex.: ${new Date().getFullYear()}`}
                />
              </FormField>
              <FormField label="Esfera de origem">
                <Input
                  id="fonte-esfera"
                  value={form.esfera_origem}
                  onChange={(e) => setForm({ ...form, esfera_origem: e.target.value })}
                  maxLength={20}
                  placeholder="Ex.: Federal"
                />
              </FormField>
              <FormField label="Tipo de vinculação">
                <Input
                  id="fonte-vinculacao"
                  value={form.tipo_vinculacao}
                  onChange={(e) => setForm({ ...form, tipo_vinculacao: e.target.value })}
                  maxLength={30}
                  placeholder="Ex.: Vinculada"
                />
              </FormField>
            </GradeCampos>
            <GradeCampos>
              <FormField label="Início da vigência">
                <Input
                  id="fonte-vig-inicio"
                  type="date"
                  value={form.vigencia_inicio}
                  onChange={(e) => setForm({ ...form, vigencia_inicio: e.target.value })}
                />
              </FormField>
              <FormField label="Fim da vigência" error={v.erro("vigencia_fim")}>
                <Input
                  id="fonte-vig-fim"
                  type="date"
                  value={form.vigencia_fim}
                  min={form.vigencia_inicio || undefined}
                  onChange={(e) => setForm({ ...form, vigencia_fim: e.target.value })}
                  onBlur={v.tocar("vigencia_fim")}
                />
              </FormField>
            </GradeCampos>
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
    </div>
  );
}
