"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Inbox, Pencil, Plus, SearchX, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type AplicaA,
  type RecadastramentoItem,
  type RecadastramentoItemInput,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const APLICA_A: { value: AplicaA; label: string }[] = [
  { value: "ambos", label: "Permissionários e empresas" },
  { value: "permissionario", label: "Só permissionários" },
  { value: "empresa", label: "Só empresas" },
];
const APLICA_A_LABEL: Record<string, string> = Object.fromEntries(
  APLICA_A.map((a) => [a.value, a.label]),
);

interface ItemForm {
  descricao: string;
  aplica_a: AplicaA;
  obrigatorio: boolean;
  ordem: string;
  ativo: boolean;
}

const EMPTY: ItemForm = {
  descricao: "",
  aplica_a: "ambos",
  obrigatorio: true,
  ordem: "0",
  ativo: true,
};

export default function ItensRecadastramentoPage() {
  const { can } = useAuth();
  const canCreate = can("transporte_regulado", "inserir");
  const canEdit = can("transporte_regulado", "atualizar");
  const canDelete = can("transporte_regulado", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [busca, setBusca] = useState("");
  const [aplicaFiltro, setAplicaFiltro] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<RecadastramentoItem | null>(null);
  const [form, setForm] = useState<ItemForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const [buscaAplicada, setBuscaAplicada] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca.trim()), 300);
    return () => clearTimeout(t);
  }, [busca]);

  const listaQ = useQuery({
    queryKey: ["tr-recad-itens", aplicaFiltro, buscaAplicada],
    queryFn: () =>
      api.recadastramento.itens.list({
        aplica_a: aplicaFiltro || undefined,
        // Busca no servidor: a lista chega truncada em `page_size`, então
        // filtrar aqui faria a tela negar item que existe.
        q: buscaAplicada || undefined,
      }),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["tr-recad-itens"] });

  const saveM = useMutation({
    mutationFn: (data: RecadastramentoItemInput) =>
      editing
        ? api.recadastramento.itens.update(editing.id, data)
        : api.recadastramento.itens.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Item atualizado." : "Item criado.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });

  const deleteM = useMutation({
    mutationFn: (id: number) => api.recadastramento.itens.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Item excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setDialogOpen(true);
  }

  function openEdit(i: RecadastramentoItem) {
    setEditing(i);
    setForm({
      descricao: i.descricao,
      aplica_a: i.aplica_a as AplicaA,
      obrigatorio: i.obrigatorio,
      ordem: String(i.ordem),
      ativo: i.ativo,
    });
    setErr(null);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
  }

  function submit() {
    setErr(null);
    if (form.descricao.trim() === "") {
      setErr("Descrição é obrigatória.");
      return;
    }
    const ordem = Number(form.ordem);
    if (!Number.isFinite(ordem)) {
      setErr("Ordem tem de ser um número.");
      return;
    }
    saveM.mutate({
      descricao: form.descricao.trim(),
      aplica_a: form.aplica_a,
      obrigatorio: form.obrigatorio,
      ordem,
      ativo: form.ativo,
    });
  }

  const itens = listaQ.data?.items ?? [];
  const buscando = buscaAplicada.length > 0 || aplicaFiltro !== "";

  function limparFiltros() {
    setAplicaFiltro("");
    setBusca("");
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={ClipboardList}
        title="Itens do recadastramento"
        description="Documentos exigidos no recadastramento. O catálogo é do município e vale para todos os ciclos."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Recadastramento", href: "/m/transporte/recadastramento" },
          { label: "Itens" },
        ]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Novo item exigido
            </Button>
          ) : undefined
        }
      />

      <FilterBar ariaLabel="Filtros dos itens">
        <FilterBar.Group label="Aplica-se a" className="w-full sm:w-60">
          <Select
            id="f_aplica"
            aria-label="Aplica-se a"
            value={aplicaFiltro}
            onChange={(e) => setAplicaFiltro(e.target.value)}
          >
            <option value="">Todos</option>
            {APLICA_A.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        <FilterBar.Group label="Busca por descrição" className="min-w-[200px] flex-1">
          <Input
            id="f_q"
            aria-label="Busca por descrição"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="CNH, contrato social..."
          />
        </FilterBar.Group>
        {buscando && (
          <FilterBar.Actions>
            <Button variant="ghost" onClick={limparFiltros}>
              Limpar
            </Button>
          </FilterBar.Actions>
        )}
      </FilterBar>

      {listaQ.isLoading ? (
        <Carregando className="text-center text-muted-foreground py-8" />
      ) : itens.length === 0 ? (
        <EmptyState
          icon={buscando ? SearchX : Inbox}
          title={buscando ? "Nenhum item encontrado" : "Nenhum item cadastrado"}
          description={
            buscando
              ? "Nada corresponde ao filtro atual. A busca cobre todo o catálogo, não só esta página."
              : "Sem itens, o atendimento não tem o que conferir e toda convocação pode ser deferida direto."
          }
          action={
            buscando ? (
              <Button variant="secondary" onClick={limparFiltros}>
                Limpar filtros
              </Button>
            ) : canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Criar item
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Ordem</TH>
              <TH>Descrição</TH>
              <TH>Aplica-se a</TH>
              <TH>Exigência</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {itens.map((i) => (
              <TR key={i.id}>
                <TD className="text-muted-foreground">{i.ordem}</TD>
                <TD className="font-medium">
                  <div className="flex flex-wrap items-center gap-2">
                    {i.descricao}
                    {!i.ativo && <Badge intent="neutral">Inativo</Badge>}
                  </div>
                </TD>
                <TD className="text-sm text-muted-foreground">
                  {APLICA_A_LABEL[i.aplica_a] ?? i.aplica_a}
                </TD>
                <TD>
                  {i.obrigatorio ? (
                    <Badge intent="warning">Obrigatório</Badge>
                  ) : (
                    <Badge intent="neutral">Opcional</Badge>
                  )}
                </TD>
                <TD className="text-right">
                  <AcoesDaLinha
                    acoes={[
                      { label: "Editar", icon: Pencil, onClick: () => openEdit(i), oculta: !canEdit },
                      {
                        label: "Excluir",
                        icon: Trash2,
                        perigo: true,
                        oculta: !canDelete,
                        onClick: async () => {
                          const ok = await confirm({
                            title: "Excluir item",
                            message: `Excluir "${i.descricao}"? As marcações já feitas continuam registradas nos atendimentos.`,
                          });
                          if (ok) deleteM.mutate(i.id);
                        },
                      },
                    ]}
                  />
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? "Editar item" : "Novo item do recadastramento"}
        footer={
          <>
            <Button variant="secondary" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={submit} disabled={saveM.isPending}>
              {saveM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          {err && <div className="text-sm text-danger">{err}</div>}
          <div>
            <Label htmlFor="i_desc">Descrição</Label>
            <Input
              id="i_desc"
              value={form.descricao}
              onChange={(e) => setForm({ ...form, descricao: e.target.value })}
              placeholder="CNH válida"
            />
          </div>
          <div>
            <Label htmlFor="i_aplica">Aplica-se a</Label>
            <Select
              id="i_aplica"
              value={form.aplica_a}
              onChange={(e) =>
                setForm({ ...form, aplica_a: e.target.value as AplicaA })
              }
            >
              {APLICA_A.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </Select>
            <p className="mt-1 text-xs text-muted-foreground">
              CNH é de pessoa; contrato social é de empresa. Item que não se aplica
              não aparece na ficha.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="i_ordem">Ordem</Label>
              <Input
                id="i_ordem"
                type="number"
                value={form.ordem}
                onChange={(e) => setForm({ ...form, ordem: e.target.value })}
              />
            </div>
            <div className="space-y-2 pt-6">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.obrigatorio}
                  onChange={(e) =>
                    setForm({ ...form, obrigatorio: e.target.checked })
                  }
                />
                Obrigatório
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.ativo}
                  onChange={(e) => setForm({ ...form, ativo: e.target.checked })}
                />
                Ativo
              </label>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Só item <strong>obrigatório e ativo</strong> trava o deferimento. Desligar
            um item não apaga as marcações já feitas.
          </p>
        </div>
      </Dialog>
    </div>
  );
}
