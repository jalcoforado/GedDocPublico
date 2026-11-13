"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardCheck, Inbox, Pencil, Plus, SearchX, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { hojeLocal, rotuloVeiculo, useErrosDoFormulario } from "@/components/frota/formulario";
import { fmtData } from "@/components/pagamentos/format";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada, type OpcaoEscolha } from "@/components/ui/escolha-segmentada";
import { FilterBar } from "@/components/ui/filter-bar";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type VeiculoVistoria,
  type VistoriaResultado,
  type VistoriaTipo,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TIPOS: { value: VistoriaTipo; label: string }[] = [
  { value: "saida", label: "Saída" },
  { value: "retorno", label: "Retorno" },
  { value: "periodica", label: "Periódica" },
];
const RESULTADOS: { value: VistoriaResultado; label: string }[] = [
  { value: "aprovada", label: "Aprovada" },
  { value: "reprovada", label: "Reprovada" },
  { value: "com_ressalvas", label: "Com ressalvas" },
];
const TIPO_LABEL: Record<string, string> = Object.fromEntries(TIPOS.map((t) => [t.value, t.label]));
const RES_LABEL: Record<string, string> = Object.fromEntries(RESULTADOS.map((r) => [r.value, r.label]));
const RES_INTENT: Record<string, "success" | "danger" | "warning"> = {
  aprovada: "success",
  reprovada: "danger",
  com_ressalvas: "warning",
};

// No formulário, tipo e resultado ficam à vista (três opções cada), com o que
// cada um quer dizer.
const TIPOS_ESCOLHA: OpcaoEscolha<VistoriaTipo>[] = [
  { valor: "saida", rotulo: "Saída", descricao: "Antes de o veículo sair para uma viagem." },
  { valor: "retorno", rotulo: "Retorno", descricao: "Na volta de uma viagem." },
  { valor: "periodica", rotulo: "Periódica", descricao: "Conferência de rotina, fora de viagem." },
];
const RESULTADOS_ESCOLHA: OpcaoEscolha<VistoriaResultado>[] = [
  { valor: "aprovada", rotulo: "Aprovada", descricao: "Tudo em ordem: o veículo pode rodar." },
  {
    valor: "com_ressalvas",
    rotulo: "Com ressalvas",
    descricao: "Pode rodar, mas há algo a resolver — diga o quê nas observações.",
  },
  {
    valor: "reprovada",
    rotulo: "Reprovada",
    descricao: "Não deve rodar até resolver — diga o motivo nas observações.",
  },
];

const ITENS: { key: keyof VeiculoVistoria; label: string }[] = [
  { key: "pneus_ok", label: "Pneus" },
  { key: "luzes_ok", label: "Luzes" },
  { key: "freios_ok", label: "Freios" },
  { key: "documentacao_ok", label: "Documentação" },
  { key: "limpeza_ok", label: "Limpeza" },
  { key: "equipamentos_ok", label: "Equipamentos" },
];

interface VistForm {
  id_veiculo: number | null;
  data_vistoria: string;
  tipo: VistoriaTipo;
  resultado: VistoriaResultado;
  pneus_ok: boolean;
  luzes_ok: boolean;
  freios_ok: boolean;
  documentacao_ok: boolean;
  limpeza_ok: boolean;
  equipamentos_ok: boolean;
  observacoes: string;
}

const EMPTY: VistForm = {
  id_veiculo: null,
  data_vistoria: "",
  tipo: "periodica",
  resultado: "aprovada",
  pneus_ok: false,
  luzes_ok: false,
  freios_ok: false,
  documentacao_ok: false,
  limpeza_ok: false,
  equipamentos_ok: false,
  observacoes: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

export default function VistoriasPage() {
  const { can } = useAuth();
  const canCreate = can("frota", "inserir");
  const canEdit = can("frota", "atualizar");
  const canDelete = can("frota", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [resultadoFiltro, setResultadoFiltro] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<VeiculoVistoria | null>(null);
  const [form, setForm] = useState<VistForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);
  const campos = useErrosDoFormulario({
    veiculo: !editing && form.id_veiculo == null ? "Escolha o veículo." : undefined,
  });

  const veiculosQ = useQuery({ queryKey: ["frota-veiculos"], queryFn: () => api.frota.listAll() });
  const placaDe = useMemo(() => {
    const map = new Map<number, string>();
    (veiculosQ.data ?? []).forEach((v) => map.set(v.id, v.placa));
    return map;
  }, [veiculosQ.data]);

  const vistQ = useQuery({
    queryKey: ["frota-vistorias", resultadoFiltro],
    queryFn: () => api.vistorias.list(resultadoFiltro ? { resultado: resultadoFiltro } : undefined),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["frota-vistorias"] });

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing ? api.vistorias.update(editing.id, data) : api.vistorias.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Vistoria atualizada." : "Vistoria registrada.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.vistorias.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Vistoria excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof VistForm>(key: K, value: VistForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }
  function openNew() {
    setEditing(null);
    setForm({ ...EMPTY, data_vistoria: hojeLocal() });
    setErr(null);
    campos.limpar();
    setDialogOpen(true);
  }
  function openEdit(v: VeiculoVistoria) {
    setEditing(v);
    setForm({
      id_veiculo: v.id_veiculo,
      data_vistoria: v.data_vistoria,
      tipo: v.tipo,
      resultado: v.resultado,
      pneus_ok: v.pneus_ok,
      luzes_ok: v.luzes_ok,
      freios_ok: v.freios_ok,
      documentacao_ok: v.documentacao_ok,
      limpeza_ok: v.limpeza_ok,
      equipamentos_ok: v.equipamentos_ok,
      observacoes: v.observacoes ?? "",
    });
    setErr(null);
    campos.limpar();
    setDialogOpen(true);
  }
  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }
  function marcarTodos(marcar: boolean) {
    setForm((f) => ({ ...f, ...Object.fromEntries(ITENS.map((i) => [i.key, marcar])) }));
  }
  const itensOk = ITENS.filter((i) => form[i.key as keyof VistForm]).length;

  function salvar() {
    setErr(null);
    if (!campos.podeEnviar()) return;
    const comum = {
      data_vistoria: nullify(form.data_vistoria),
      tipo: form.tipo,
      resultado: form.resultado,
      pneus_ok: form.pneus_ok,
      luzes_ok: form.luzes_ok,
      freios_ok: form.freios_ok,
      documentacao_ok: form.documentacao_ok,
      limpeza_ok: form.limpeza_ok,
      equipamentos_ok: form.equipamentos_ok,
      observacoes: nullify(form.observacoes),
    };
    saveM.mutate(editing ? comum : { id_veiculo: form.id_veiculo, ...comum });
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={ClipboardCheck}
        title="Vistorias"
        description="Checklist interno de vistoria dos veículos da frota."
        breadcrumbs={[{ label: "Frota Pública", href: "/m/frota" }, { label: "Vistorias" }]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Nova vistoria
            </Button>
          ) : undefined
        }
      />

      <FilterBar>
        <FilterBar.Group label="Resultado">
          <Select
            aria-label="Resultado"
            value={resultadoFiltro}
            onChange={(e) => setResultadoFiltro(e.target.value)}
          >
            <option value="">Todos</option>
            {RESULTADOS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        {resultadoFiltro !== "" && (
          <FilterBar.Actions>
            <Button variant="ghost" onClick={() => setResultadoFiltro("")}>
              Limpar
            </Button>
          </FilterBar.Actions>
        )}
      </FilterBar>

      {!vistQ.isLoading && (vistQ.data?.length ?? 0) === 0 && resultadoFiltro !== "" ? (
        <EmptyState
          icon={SearchX}
          title="Nenhuma vistoria encontrada"
          description="Nenhuma vistoria tem o resultado escolhido."
          action={
            <Button variant="secondary" onClick={() => setResultadoFiltro("")}>
              Limpar filtros
            </Button>
          }
        />
      ) : !vistQ.isLoading && (vistQ.data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhuma vistoria"
          description="Registre a primeira vistoria de um veículo da frota."
          action={
            canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Nova vistoria
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Data</TH>
              <TH>Veículo</TH>
              <TH>Tipo</TH>
              <TH>Resultado</TH>
              <TH>Itens OK</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {vistQ.isLoading && (
              <TR>
                <TD colSpan={6} className="text-center text-muted-foreground">
                  Carregando...
                </TD>
              </TR>
            )}
            {vistQ.data?.map((v) => {
              const okCount = ITENS.filter((i) => v[i.key]).length;
              return (
                <TR key={v.id}>
                  <TD className="tabular-nums">{fmtData(v.data_vistoria)}</TD>
                  <TD className="font-mono">{placaDe.get(v.id_veiculo) ?? `#${v.id_veiculo}`}</TD>
                  <TD>{TIPO_LABEL[v.tipo] ?? v.tipo}</TD>
                  <TD>
                    <Badge intent={RES_INTENT[v.resultado] ?? "neutral"}>
                      {RES_LABEL[v.resultado] ?? v.resultado}
                    </Badge>
                  </TD>
                  <TD className="tabular-nums text-muted-foreground">
                    {okCount}/{ITENS.length}
                  </TD>
                  <TD className="text-right">
                    <AcoesDaLinha
                      acoes={[
                        {
                          label: "Editar",
                          icon: Pencil,
                          oculta: !canEdit,
                          onClick: () => openEdit(v),
                        },
                        {
                          label: "Excluir",
                          icon: Trash2,
                          perigo: true,
                          oculta: !canDelete,
                          disabled: deleteM.isPending,
                          onClick: async () => {
                            const ok = await confirm({
                              title: "Excluir vistoria",
                              message: "Excluir esta vistoria? Esta ação não pode ser desfeita.",
                              confirmLabel: "Excluir",
                              intent: "danger",
                            });
                            if (ok) deleteM.mutate(v.id);
                          },
                        },
                      ]}
                    />
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? "Editar vistoria" : "Nova vistoria"}
        description={
          editing
            ? `${placaDe.get(editing.id_veiculo) ?? `Veículo #${editing.id_veiculo}`} · ${fmtData(editing.data_vistoria)}`
            : "Confira item por item e dê o resultado no fim."
        }
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button type="submit" form="form-vistoria" loading={saveM.isPending}>
              {editing ? "Salvar alterações" : "Registrar vistoria"}
            </Button>
          </>
        }
      >
        <form
          id="form-vistoria"
          noValidate
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            salvar();
          }}
        >
          {!editing && (
            <FormField label="Veículo" required error={campos.erro("veiculo")}>
              <Select
                id="veiculo"
                value={form.id_veiculo ?? ""}
                onChange={(e) => set("id_veiculo", e.target.value ? Number(e.target.value) : null)}
                onBlur={campos.tocar("veiculo")}
              >
                <option value="">Selecione o veículo</option>
                {(veiculosQ.data ?? []).map((v) => (
                  <option key={v.id} value={v.id}>
                    {rotuloVeiculo(v)}
                  </option>
                ))}
              </Select>
            </FormField>
          )}
          <GradeCampos>
            <FormField
              label="Data"
              hint={!editing && form.data_vistoria === hojeLocal() ? "Já vem com a data de hoje." : undefined}
            >
              <Input
                id="data"
                type="date"
                value={form.data_vistoria}
                onChange={(e) => set("data_vistoria", e.target.value)}
              />
            </FormField>
            <EscolhaSegmentada
              nome="tipo_vistoria"
              titulo="Tipo de vistoria"
              moldura={false}
              valor={form.tipo}
              opcoes={TIPOS_ESCOLHA}
              onChange={(t) => set("tipo", t)}
            />
          </GradeCampos>

          {/* Checklist: um fieldset de verdade, com o total à vista — "4 de 6"
              diz na hora se falta conferir algo antes de dar o resultado. */}
          <fieldset className="rounded-lg border border-border bg-surface-1 p-3">
            <legend className="sr-only">Itens conferidos</legend>
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
              <div aria-hidden="true" className="text-sm font-medium text-foreground">
                Itens em ordem
              </div>
              <div className="flex items-center gap-3 text-xs">
                <span className="tabular-nums text-foreground-muted" aria-live="polite">
                  {itensOk} de {ITENS.length}
                </span>
                <button
                  type="button"
                  className="font-medium text-primary hover:underline"
                  onClick={() => marcarTodos(itensOk < ITENS.length)}
                >
                  {itensOk < ITENS.length ? "Marcar todos" : "Desmarcar todos"}
                </button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
              {ITENS.map((i) => (
                <label key={i.key} className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
                  <Checkbox
                    className="h-4 w-4"
                    checked={form[i.key as keyof VistForm] as boolean}
                    onChange={(e) => set(i.key as keyof VistForm, e.target.checked as never)}
                  />
                  {i.label}
                </label>
              ))}
            </div>
            <p className="mt-2 text-xs text-foreground-muted">Marque o que está em ordem; o que ficar sem marca conta como problema.</p>
          </fieldset>

          <EscolhaSegmentada
            nome="resultado_vistoria"
            titulo="Resultado"
            valor={form.resultado}
            opcoes={RESULTADOS_ESCOLHA}
            onChange={(r) => set("resultado", r)}
          />

          <FormField
            label="Observações"
            opcional={form.resultado === "aprovada"}
            hint={form.resultado !== "aprovada" ? "Diga o que precisa ser resolvido." : undefined}
          >
            <Textarea
              id="obs"
              rows={2}
              value={form.observacoes}
              onChange={(e) => set("observacoes", e.target.value)}
              placeholder="Ex.: pneu traseiro esquerdo careca; trocar antes da próxima viagem"
            />
          </FormField>

          {err && (
            <Alert intent="danger" title="Não foi possível salvar">
              {err}
            </Alert>
          )}
        </form>
      </Dialog>
    </div>
  );
}
