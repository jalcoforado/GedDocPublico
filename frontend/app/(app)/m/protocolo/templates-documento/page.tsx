"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RichTextEditor } from "@/components/ui/rich-text-editor";
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

  function abrirNovo() {
    setEditId(null);
    setForm(EMPTY);
    setOpen(true);
  }

  async function abrirEdicao(id: number) {
    const t = await api.templatesDocumento.get(id);
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
  const podeSalvar = form.nome.trim().length > 0 && form.corpo_html.trim().length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">
            Templates de documento
          </h1>
          <p className="text-sm text-muted-foreground">
            Modelos com campos automáticos ({"{{"}placeholders{"}}"}) usados ao redigir
            documentos nos processos.
          </p>
        </div>
        <Button onClick={abrirNovo}>Novo template</Button>
      </div>

      {listQ.isLoading ? (
        <p className="text-sm text-muted-foreground">Carregando…</p>
      ) : templates.length === 0 ? (
        <p className="text-sm text-gray-500">
          Nenhum template cadastrado. Crie o primeiro modelo.
        </p>
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
                    <span className="ml-2 rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
                      inativo
                    </span>
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
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" onClick={() => abrirEdicao(t.id)}>
                  Editar
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => clonarM.mutate(t.id)}
                  disabled={clonarM.isPending}
                >
                  Clonar
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => excluir(t.id)}
                  disabled={removeM.isPending}
                >
                  Excluir
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={editId === null ? "Novo template" : "Editar template"}
        size="xl"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => saveM.mutate()} disabled={!podeSalvar || saveM.isPending}>
              {saveM.isPending ? "Salvando…" : "Salvar"}
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="tpl-nome">Nome</Label>
              <Input
                id="tpl-nome"
                value={form.nome}
                onChange={(e) => setForm({ ...form, nome: e.target.value })}
                placeholder="Ex.: Despacho de encaminhamento"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="tpl-especie">Espécie documental</Label>
              <select
                id="tpl-especie"
                value={form.id_especie_documental ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    id_especie_documental: e.target.value ? Number(e.target.value) : null,
                  })
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="">Sem espécie</option>
                {(especiesQ.data ?? []).map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.nome}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="tpl-unidade">Setor administrador</Label>
            <select
              id="tpl-unidade"
              value={form.id_unidade_trabalho ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  id_unidade_trabalho: e.target.value ? Number(e.target.value) : null,
                })
              }
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">Todo o tenant (sem setor específico)</option>
              {(unidadesQ.data?.items ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.unidade_trabalho}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              Só define quem administra o modelo — todos no tenant continuam podendo usá-lo.
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="tpl-desc">Descrição</Label>
            <Input
              id="tpl-desc"
              value={form.descricao}
              onChange={(e) => setForm({ ...form, descricao: e.target.value })}
              placeholder="Breve descrição do uso do modelo"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Campos automáticos (clique para inserir)</Label>
            <div className="flex flex-wrap gap-1.5">
              {(placeholdersQ.data ?? []).map((p) => (
                <button
                  key={p.chave}
                  type="button"
                  onClick={() => inserirPlaceholder(p.chave)}
                  title={p.descricao}
                  className="rounded border border-border bg-muted px-2 py-0.5 text-xs text-foreground hover:bg-accent"
                >
                  {`{{${p.chave}}}`}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Conteúdo do modelo</Label>
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

          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={form.ativo}
              onChange={(e) => setForm({ ...form, ativo: e.target.checked })}
            />
            Ativo (disponível para seleção ao redigir)
          </label>
        </div>
      </Dialog>
    </div>
  );
}
