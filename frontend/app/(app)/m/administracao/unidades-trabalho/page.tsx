"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useState } from "react";

import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { UnidadeEditDrawer, type DrawerMode } from "@/components/organograma/UnidadeEditDrawer";
import { api, organogramaApi, type UnidadeTrabalho } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function UnidadesPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  // O formulário é o mesmo do Organograma (UnidadeEditDrawer): a unidade se
  // cadastra de um jeito só nas duas telas, e daqui também não dá para pôr
  // uma unidade debaixo de uma subordinada dela.
  const [modo, setModo] = useState<DrawerMode | null>(null);

  const listQ = useQuery({
    queryKey: ["unidades", page, q],
    queryFn: () => api.unidades.list({ page, page_size: 20, q: q || undefined }),
  });
  const tiposQ = useQuery({ queryKey: ["tipos-unidade"], queryFn: api.tiposUnidade });
  const todasQ = useQuery({ queryKey: ["unidades-all"], queryFn: () => api.unidades.list({ page_size: 200 }) });
  // Árvore inteira: o formulário precisa dela para saber quem pode ser pai.
  const arvoreQ = useQuery({
    queryKey: ["organograma"],
    queryFn: () => organogramaApi.tree(),
    staleTime: 5 * 60_000,
  });

  const deleteM = useMutation({
    mutationFn: (id: number) => api.unidades.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["unidades"] });
      toast.success("Unidade excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function openNew() {
    setModo({ kind: "create", parentId: null });
  }

  function openEdit(u: UnidadeTrabalho) {
    setModo({ kind: "edit", unidade: u });
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Building2}
        title="Unidades de trabalho"
        description="Secretarias, setores e equipamentos onde os servidores trabalham e os processos tramitam."
        actions={
          can("unidadeTrabalho", "inserir") && (
            <Button onClick={openNew}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Nova unidade
            </Button>
          )
        }
      />

      <div className="relative w-full max-w-sm">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-subtle"
          aria-hidden="true"
        />
        <Input
          placeholder="Buscar por nome ou sigla…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          className="pl-9"
        />
      </div>

      <Table>
        <THead>
          <TR>
            <TH>Nome</TH>
            <TH>Sigla</TH>
            <TH>Tipo</TH>
            <TH>Unidade pai</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {listQ.isLoading &&
            Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={5} />)}
          {!listQ.isLoading && listQ.data?.items.length === 0 && (
            <TR>
              <TD colSpan={5} className="p-0">
                <EmptyState
                  icon={Building2}
                  title={q ? "Nenhuma unidade encontrada" : "Nenhuma unidade cadastrada"}
                  description={
                    q
                      ? "Confira o nome ou a sigla digitada na busca."
                      : "Use “Nova unidade” para cadastrar a primeira."
                  }
                  className="border-0 bg-transparent"
                />
              </TD>
            </TR>
          )}
          {listQ.data?.items.map((u) => (
            <TR key={u.id}>
              <TD className="font-medium">{u.unidade_trabalho}</TD>
              <TD>{u.sigla || "—"}</TD>
              <TD className="text-foreground-muted">
                {tiposQ.data?.find((t) => t.id === u.id_tipo_unidade_trabalho)?.tipo_unidade_trabalho ?? "—"}
              </TD>
              <TD className="text-foreground-muted">
                {todasQ.data?.items.find((x) => x.id === u.id_unidade_pai)?.unidade_trabalho ?? "—"}
              </TD>
              <TD className="text-right">
                <AcoesDaLinha
                  acoes={[
                    {
                      label: "Editar",
                      icon: Pencil,
                      oculta: !can("unidadeTrabalho", "atualizar"),
                      onClick: () => openEdit(u),
                    },
                    {
                      label: "Excluir",
                      icon: Trash2,
                      perigo: true,
                      oculta: !can("unidadeTrabalho", "excluir"),
                      onClick: async () => {
                        const ok = await confirm({
                          title: "Excluir unidade",
                          message: `Excluir ${u.unidade_trabalho}? Esta ação não pode ser desfeita.`,
                          confirmLabel: "Excluir",
                          intent: "danger",
                        });
                        if (ok) deleteM.mutate(u.id);
                      },
                    },
                  ]}
                />
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      {listQ.data && (
        <div className="flex items-center justify-between text-sm text-foreground-muted">
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

      <UnidadeEditDrawer
        open={modo !== null}
        mode={modo}
        allNos={arvoreQ.data ?? []}
        canDelete={can("unidadeTrabalho", "excluir")}
        onClose={() => setModo(null)}
      />
    </div>
  );
}
