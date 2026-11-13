"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Blocks, Type } from "lucide-react";
import { useState } from "react";

import { PreVisualizacaoDocumento } from "@/components/PreVisualizacaoDocumento";
import { MontadorTemplate } from "@/components/protocolo/MontadorTemplate";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RichTextEditor } from "@/components/ui/rich-text-editor";
import { useToast } from "@/components/ui/toast";
import { api, protocoloApi, type TemplateDocumento } from "@/lib/api";
import { blocosParaHtml, htmlParaBlocos, type Bloco } from "@/lib/template-blocos";
import { cn } from "@/lib/utils";

/** Montar com blocos (SI-31) ou editar o HTML corrido no editor de texto. */
type ModoEdicao = "blocos" | "livre";

async function enviarImagem(file: File): Promise<string> {
  const { url } = await api.editorImagens.upload(file);
  return url;
}

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
  const [modo, setModo] = useState<ModoEdicao>("blocos");
  const [blocos, setBlocos] = useState<Bloco[]>([]);

  // Em modo blocos o HTML gravado é sempre o dos blocos: uma fonte só.
  function mudarBlocos(nova: Bloco[]) {
    setBlocos(nova);
    setForm((f) => ({ ...f, corpo_html: blocosParaHtml(nova) }));
  }

  function trocarModo(novo: ModoEdicao) {
    if (novo === modo) return;
    // Voltar do editor livre relê o HTML: o que ainda tem marca de bloco volta
    // a ser bloco, o resto vira bloco de Texto.
    if (novo === "blocos") setBlocos(htmlParaBlocos(form.corpo_html));
    setModo(novo);
  }

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
    setBlocos([]);
    setModo("blocos");
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
    // Modelo antigo (sem marca de bloco) abre como um bloco de Texto: nada se perde.
    setBlocos(htmlParaBlocos(t.corpo_html));
    setModo("blocos");
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
        <Carregando className="text-sm text-muted-foreground" />
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
        size="2xl"
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

          <div className="space-y-2">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <Label>Conteúdo do modelo</Label>
                <p className="text-xs text-muted-foreground">
                  {modo === "blocos"
                    ? "Monte o documento com blocos; ao lado, como ele sai no PDF."
                    : "Texto corrido. Voltar para blocos junta o que não for bloco num bloco de Texto."}
                </p>
              </div>
              <div
                role="group"
                aria-label="Modo de edição do modelo"
                className="inline-flex rounded-md border border-border bg-surface-1 p-0.5"
              >
                {(
                  [
                    ["blocos", "Montar com blocos", Blocks],
                    ["livre", "Editor livre", Type],
                  ] as const
                ).map(([valor, nome, Icone]) => (
                  <button
                    key={valor}
                    type="button"
                    aria-pressed={modo === valor}
                    onClick={() => trocarModo(valor)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs font-medium transition-colors duration-fast",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      modo === valor
                        ? "bg-card text-foreground shadow-sm"
                        : "text-foreground-muted hover:text-foreground",
                    )}
                  >
                    <Icone className="h-3.5 w-3.5" aria-hidden="true" />
                    {nome}
                  </button>
                ))}
              </div>
            </div>

            {modo === "blocos" ? (
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
                <MontadorTemplate
                  blocos={blocos}
                  onChange={mudarBlocos}
                  campos={placeholdersQ.data ?? []}
                  onUploadImage={enviarImagem}
                />
                <div className="xl:sticky xl:top-0 xl:self-start">
                  <PreVisualizacaoDocumento
                    titulo=""
                    corpoHtml={form.corpo_html}
                    modelo
                    className="h-[40rem]"
                  />
                </div>
              </div>
            ) : (
              <RichTextEditor
                value={form.corpo_html}
                onChange={(html) => setForm({ ...form, corpo_html: html })}
                minHeight={280}
                ariaLabel="Conteúdo do template"
                campos={placeholdersQ.data ?? []}
                onUploadImage={enviarImagem}
              />
            )}
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
