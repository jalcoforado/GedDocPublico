"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Inbox, Pencil, Plus, SearchX, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { useValidacao } from "@/components/transporte/formulario";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FilterBar } from "@/components/ui/filter-bar";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
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
    val.reiniciar();
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
    val.reiniciar();
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
  }

  // Antes o primeiro erro ia para o topo e escondia o resto; agora cada
  // um aparece no seu campo, depois de sair dele ou de tentar salvar.
  const val = useValidacao<"descricao" | "ordem">({
    descricao: form.descricao.trim() === "" ? "Informe o que o regulado precisa apresentar." : undefined,
    ordem: !Number.isFinite(Number(form.ordem)) ? "Use um número inteiro (ex.: 10)." : undefined,
  });

  function submit() {
    setErr(null);
    if (!val.conferir()) return;
    const ordem = Number(form.ordem);
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
        title={editing ? `Editar item — ${editing.descricao}` : "Novo item do recadastramento"}
        description={editing ? undefined : "O que o regulado precisa apresentar. Vira uma linha do checklist do atendimento."}
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={submit} loading={saveM.isPending}>
              {editing ? "Salvar alterações" : "Criar item"}
            </Button>
          </>
        }
      >
        <div ref={val.ref} className="space-y-5">
          <FormField label="Descrição" required error={val.erro("descricao")}>
            <Input
              id="i_desc"
              value={form.descricao}
              onChange={(e) => setForm({ ...form, descricao: e.target.value })}
              onBlur={val.sair("descricao")}
              placeholder="Ex.: CNH válida"
            />
          </FormField>
          <EscolhaSegmentada<AplicaA>
            nome="i_aplica"
            titulo="Vale para"
            valor={form.aplica_a}
            onChange={(a) => setForm({ ...form, aplica_a: a })}
            opcoes={[
              { valor: "ambos", rotulo: "Os dois", descricao: "Entra na ficha de permissionários e de empresas." },
              { valor: "permissionario", rotulo: "Permissionários", descricao: "Documento de pessoa, como a CNH. Não aparece na ficha de empresa." },
              { valor: "empresa", rotulo: "Empresas", descricao: "Documento de empresa, como o contrato social. Não aparece na ficha de permissionário." },
            ]}
          />
          <div className="space-y-3 rounded-lg border border-border bg-surface-1 p-3">
            <label className="flex items-start gap-2 text-sm text-foreground">
              <Checkbox
                checked={form.obrigatorio}
                onChange={(e) => setForm({ ...form, obrigatorio: e.target.checked })}
                className="mt-0.5"
              />
              <span>
                Obrigatório
                <span className="block text-xs text-foreground-muted">
                  Enquanto ativo, sem ele marcado o atendimento não pode ser deferido.
                </span>
              </span>
            </label>
            <label className="flex items-start gap-2 text-sm text-foreground">
              <Checkbox
                checked={form.ativo}
                onChange={(e) => setForm({ ...form, ativo: e.target.checked })}
                className="mt-0.5"
              />
              <span>
                Ativo
                <span className="block text-xs text-foreground-muted">
                  Desligar tira o item das fichas novas; as marcações já feitas ficam.
                </span>
              </span>
            </label>
          </div>
          <FormField
            label="Ordem"
            opcional
            error={val.erro("ordem")}
            hint="Posição no checklist: menor vem primeiro."
            className="max-w-40"
          >
            <Input
              id="i_ordem"
              type="number"
              inputMode="numeric"
              value={form.ordem}
              onChange={(e) => setForm({ ...form, ordem: e.target.value })}
              onBlur={val.sair("ordem")}
            />
          </FormField>
          {err && <Alert intent="danger">{err}</Alert>}
        </div>
      </Dialog>
    </div>
  );
}
