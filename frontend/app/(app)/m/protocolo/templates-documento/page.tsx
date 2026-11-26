"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, FileText, Pause, Pencil, Plus, Star, Trash2 } from "lucide-react";
import { useState } from "react";

import { FormularioModeloDialog } from "@/components/protocolo/FormularioModeloDialog";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Carregando } from "@/components/ui/carregando";
import { useConfirm } from "@/components/ui/confirm";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { useToast } from "@/components/ui/toast";
import { api, protocoloApi, type TemplateDocumento } from "@/lib/api";

export default function TemplatesDocumentoPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  // Modelo aberto no formulário: `null` = novo; ausente = fechado.
  const [aberto, setAberto] = useState<{ id: number | null } | null>(null);

  const listQ = useQuery({
    queryKey: ["templates-documento"],
    queryFn: () => api.templatesDocumento.list(),
  });
  const especiesQ = useQuery({
    queryKey: ["especies-documentais"],
    queryFn: () => protocoloApi.listEspecies(),
  });
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });
  const especiePorId = new Map((especiesQ.data ?? []).map((e) => [e.id, e.nome]));
  const unidadePorId = new Map(
    (unidadesQ.data?.items ?? []).map((u) => [u.id, u.unidade_trabalho]),
  );

  function abrirNovo() {
    setAberto({ id: null });
  }

  function abrirEdicao(id: number) {
    setAberto({ id });
  }

  const removeM = useMutation({
    mutationFn: (id: number) => api.templatesDocumento.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["templates-documento"] });
      toast.success("Template excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const clonarM = useMutation({
    mutationFn: (id: number) => api.templatesDocumento.clonar(id),
    onSuccess: (clone) => {
      qc.invalidateQueries({ queryKey: ["templates-documento"] });
      toast.success(`Clonado como "${clone.nome}".`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function excluir(id: number) {
    if (
      await confirm({
        title: "Excluir template?",
        message: "O modelo será removido. Minutas já criadas não são afetadas.",
        confirmLabel: "Excluir",
      })
    ) {
      removeM.mutate(id);
    }
  }

  const templates = listQ.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        icon={FileText}
        title="Templates de documento"
        description={
          <>
            Modelos com campos automáticos ({"{{"}placeholders{"}}"}) usados ao redigir
            documentos nos processos.
          </>
        }
        actions={
          <Button onClick={abrirNovo}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Novo template
          </Button>
        }
      />

      {listQ.isLoading ? (
        <Carregando className="text-sm text-muted-foreground" />
      ) : templates.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="Nenhum template cadastrado"
          description="Crie o primeiro modelo para usar ao redigir documentos nos processos."
          action={
            <Button onClick={abrirNovo}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Novo template
            </Button>
          }
        />
      ) : (
        <ul className="divide-y divide-border rounded-md border border-border bg-card">
          {templates.map((t: TemplateDocumento) => (
            <li
              key={t.id}
              className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-foreground">
                  {t.nome}
                  {t.padrao && (
                    <Badge intent="brand" icon={Star} className="ml-2">
                      Padrão
                    </Badge>
                  )}
                  {!t.ativo && (
                    <Badge intent="neutral" icon={Pause} className="ml-2">
                      Inativo
                    </Badge>
                  )}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t.id_especie_documental !== null
                    ? especiePorId.get(t.id_especie_documental) ?? "espécie desconhecida"
                    : "sem espécie documental"}
                  {t.id_unidade_trabalho !== null &&
                    ` · ${unidadePorId.get(t.id_unidade_trabalho) ?? "unidade desconhecida"}`}
                  {t.placeholders_utilizados?.length
                    ? ` · ${t.placeholders_utilizados.length} campo(s) automático(s)`
                    : ""}
                </div>
              </div>
              <AcoesDaLinha
                acoes={[
                  { label: "Editar", icon: Pencil, onClick: () => abrirEdicao(t.id) },
                  {
                    label: "Clonar",
                    icon: Copy,
                    onClick: () => clonarM.mutate(t.id),
                    disabled: clonarM.isPending,
                  },
                  {
                    label: "Excluir",
                    icon: Trash2,
                    perigo: true,
                    onClick: () => excluir(t.id),
                    disabled: removeM.isPending,
                  },
                ]}
              />
            </li>
          ))}
        </ul>
      )}

      <FormularioModeloDialog
        open={aberto !== null}
        onClose={() => setAberto(null)}
        modeloId={aberto?.id ?? null}
      />
    </div>
  );
}
