"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, FileText, Pause, Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Carregando } from "@/components/ui/carregando";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { PageHeader } from "@/components/ui/page-header";
import { RichTextEditor } from "@/components/ui/rich-text-editor";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { api, protocoloApi, type TemplateDocumento } from "@/lib/api";

interface FormState {
  nome: string;
  id_especie_documental: number | null;
  id_unidade_trabalho: number | null;
  descricao: string;
  corpo_html: string;
  ativo: boolean;
}

const EMPTY: FormState = {
  nome: "",
  id_especie_documental: null,
  id_unidade_trabalho: null,
  descricao: "",
  corpo_html: "",
  ativo: true,
};

export default function TemplatesDocumentoPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);

  const listQ = useQuery({
    queryKey: ["templates-documento"],
    queryFn: () => api.templatesDocumento.list(),
  });
  const placeholdersQ = useQuery({
    queryKey: ["templates-documento", "placeholders"],
    queryFn: () => api.templatesDocumento.placeholders(),
    enabled: open,
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

  // Erro sob o campo só depois de tentar salvar; o botão não fica cinza.
  const [tentou, setTentou] = useState(false);
  const faltaNome = form.nome.trim().length === 0;
  const faltaCorpo = form.corpo_html.trim().length === 0;

  function salvar() {
    setTentou(true);
    if (faltaNome) {
      document.getElementById("tpl-nome")?.focus();
      return;
    }
    if (faltaCorpo) {
      document.querySelector<HTMLElement>('[aria-label="Conteúdo do template"]')?.focus();
      return;
    }
    saveM.mutate();
  }

  function abrirNovo() {
    setTentou(false);
    setEditId(null);
    setForm(EMPTY);
    setOpen(true);
  }

  async function abrirEdicao(id: number) {
    const t = await api.templatesDocumento.get(id);
    setTentou(false);
    setEditId(id);
    setForm({
      nome: t.nome,
      id_especie_documental: t.id_especie_documental,
      id_unidade_trabalho: t.id_unidade_trabalho,
      descricao: t.descricao ?? "",
      corpo_html: t.corpo_html,
      ativo: t.ativo,
    });
    setOpen(true);
  }

  const saveM = useMutation({
    mutationFn: () => {
      const payload = {
        nome: form.nome.trim(),
        id_especie_documental: form.id_especie_documental,
        id_unidade_trabalho: form.id_unidade_trabalho,
        descricao: form.descricao.trim() || null,
        corpo_html: form.corpo_html,
        ativo: form.ativo,
      };
      return editId === null
        ? api.templatesDocumento.create(payload)
        : api.templatesDocumento.update(editId, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["templates-documento"] });
      setOpen(false);
      toast.success(editId === null ? "Template criado." : "Template atualizado.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

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

  function inserirPlaceholder(chave: string) {
    setForm((f) => ({ ...f, corpo_html: `${f.corpo_html}<p>{{${chave}}}</p>` }));
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

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={editId === null ? "Novo modelo de documento" : "Editar modelo de documento"}
        size="xl"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={salvar} loading={saveM.isPending}>
              {saveM.isPending
                ? "Salvando…"
                : editId === null
                  ? "Criar modelo"
                  : "Salvar alterações"}
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <GradeCampos>
            <FormField
              label="Nome"
              required
              error={tentou && faltaNome ? "Dê um nome ao modelo, ex.: Despacho de encaminhamento." : undefined}
            >
              <Input
                id="tpl-nome"
                value={form.nome}
                onChange={(e) => setForm({ ...form, nome: e.target.value })}
                placeholder="Ex.: Despacho de encaminhamento"
              />
            </FormField>
            <FormField label="Espécie documental" opcional>
              <Select
                id="tpl-especie"
                value={form.id_especie_documental ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    id_especie_documental: e.target.value ? Number(e.target.value) : null,
                  })
                }
              >
                <option value="">Sem espécie</option>
                {(especiesQ.data ?? []).map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.nome}
                  </option>
                ))}
              </Select>
            </FormField>
          </GradeCampos>
          <FormField
            label="Setor administrador"
            opcional
            hint="Só define quem administra o modelo; todos continuam podendo usá-lo."
          >
            <Select
              id="tpl-unidade"
              value={form.id_unidade_trabalho ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  id_unidade_trabalho: e.target.value ? Number(e.target.value) : null,
                })
              }
            >
              <option value="">Nenhum setor específico</option>
              {(unidadesQ.data?.items ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.unidade_trabalho}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField
            label="Descrição"
            opcional
            hint="Aparece ao escolher o modelo, para ajudar a achar o certo."
          >
            <Input
              id="tpl-desc"
              value={form.descricao}
              onChange={(e) => setForm({ ...form, descricao: e.target.value })}
              placeholder="Ex.: Para encaminhar processos entre secretarias."
            />
          </FormField>

          <div className="space-y-1.5">
            <p className="text-sm font-medium text-foreground">Campos automáticos</p>
            <p className="text-xs text-foreground-muted">
              Clique para inserir no texto. Ao usar o modelo, cada campo vira o dado do processo.
            </p>
            <div className="flex flex-wrap gap-1.5">
              {(placeholdersQ.data ?? []).map((p) => (
                <button
                  key={p.chave}
                  type="button"
                  onClick={() => inserirPlaceholder(p.chave)}
                  title={p.descricao}
                  className="rounded border border-border bg-muted px-2 py-0.5 font-mono text-xs text-foreground transition-colors duration-fast hover:border-primary/40 hover:bg-primary/10"
                >
                  {`{{${p.chave}}}`}
                </button>
              ))}
            </div>
          </div>

          <FormField
            label="Conteúdo do modelo"
            required
            error={tentou && faltaCorpo ? "Escreva o texto do modelo." : undefined}
          >
            {/* O editor não aceita id: o rótulo aponta para o invólucro e o
                nome acessível vem do ariaLabel. */}
            <div>
              <RichTextEditor
                value={form.corpo_html}
                onChange={(html) => setForm({ ...form, corpo_html: html })}
                minHeight={280}
                ariaLabel="Conteúdo do template"
                onUploadImage={async (file) => {
                  const { url } = await api.editorImagens.upload(file);
                  return url;
                }}
              />
            </div>
          </FormField>

          <label className="flex cursor-pointer items-start gap-2.5 rounded-md border border-border bg-surface-1 px-3 py-2.5 transition-colors duration-fast hover:bg-surface-2">
            <Checkbox
              checked={form.ativo}
              onChange={(e) => setForm({ ...form, ativo: e.target.checked })}
              className="mt-0.5 h-4 w-4"
            />
            <span className="text-sm">
              <span className="block font-medium text-foreground">Ativo</span>
              <span className="block text-xs text-foreground-muted">
                Aparece na lista de modelos ao redigir um documento.
              </span>
            </span>
          </label>
        </div>
      </Dialog>
    </div>
  );
}
