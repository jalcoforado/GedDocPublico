"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardCheck, Inbox, Plus } from "lucide-react";
import { useMemo, useState } from "react";

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
function fmtData(d: string | null): string {
  if (!d) return "—";
  return new Date(`${d}T00:00:00`).toLocaleDateString("pt-BR");
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
    setForm(EMPTY);
    setErr(null);
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
    setDialogOpen(true);
  }
  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }
  function salvar() {
    setErr(null);
    if (!editing && form.id_veiculo == null) {
      setErr("Selecione o veículo.");
      return;
    }
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
        breadcrumbs={[{ label: "Frota Pública", href: "/frotas" }, { label: "Vistorias" }]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Nova vistoria
            </Button>
          ) : undefined
        }
      />

      <div>
        <Label htmlFor="f_res">Resultado</Label>
        <Select id="f_res" value={resultadoFiltro} onChange={(e) => setResultadoFiltro(e.target.value)}>
          <option value="">Todos</option>
          {RESULTADOS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </Select>
      </div>

      {!vistQ.isLoading && (vistQ.data?.length ?? 0) === 0 ? (
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
                    <div className="inline-flex gap-2">
                      {canEdit && (
                        <Button variant="secondary" size="sm" onClick={() => openEdit(v)}>
                          Editar
                        </Button>
                      )}
                      {canDelete && (
                        <Button
                          variant="danger"
                          size="sm"
                          disabled={deleteM.isPending}
                          onClick={async () => {
                            const ok = await confirm({
                              title: "Excluir vistoria",
                              message: "Excluir esta vistoria? Esta ação não pode ser desfeita.",
                              confirmLabel: "Excluir",
                              intent: "danger",
                            });
                            if (ok) deleteM.mutate(v.id);
                          }}
                        >
                          Excluir
                        </Button>
                      )}
                    </div>
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
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {!editing && (
              <div className="sm:col-span-3">
                <Label htmlFor="veiculo" required>
                  Veículo
                </Label>
                <Select
                  id="veiculo"
                  value={form.id_veiculo ?? ""}
                  onChange={(e) => set("id_veiculo", e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">Selecione...</option>
                  {(veiculosQ.data ?? []).map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.placa} {v.marca ? `— ${v.marca}` : ""}
                    </option>
                  ))}
                </Select>
              </div>
            )}
            <div>
              <Label htmlFor="data">Data</Label>
              <Input
                id="data"
                type="date"
                value={form.data_vistoria}
                onChange={(e) => set("data_vistoria", e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="tipo" required>
                Tipo
              </Label>
              <Select id="tipo" value={form.tipo} onChange={(e) => set("tipo", e.target.value as VistoriaTipo)}>
                {TIPOS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="resultado" required>
                Resultado
              </Label>
              <Select
                id="resultado"
                value={form.resultado}
                onChange={(e) => set("resultado", e.target.value as VistoriaResultado)}
              >
                {RESULTADOS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <fieldset className="rounded-md border border-border p-3">
            <legend className="px-1 text-sm font-medium text-foreground-muted">Checklist</legend>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {ITENS.map((i) => (
                <label key={i.key} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form[i.key as keyof VistForm] as boolean}
                    onChange={(e) => set(i.key as keyof VistForm, e.target.checked as never)}
                  />
                  {i.label}
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <Label htmlFor="obs">Observações</Label>
            <Textarea id="obs" rows={2} value={form.observacoes} onChange={(e) => set("observacoes", e.target.value)} />
          </div>

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
