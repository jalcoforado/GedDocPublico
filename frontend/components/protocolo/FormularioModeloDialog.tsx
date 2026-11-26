"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { EditorDeModelo, type ModoEdicao } from "@/components/protocolo/EditorDeModelo";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog } from "@/components/ui/dialog";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { api, protocoloApi, type TemplateDocumento } from "@/lib/api";
import { blocosParaHtml, htmlParaBlocos, type Bloco } from "@/lib/template-blocos";

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
  padrao: boolean;
}

const VAZIO: FormState = {
  nome: "",
  id_especie_documental: null,
  id_unidade_trabalho: null,
  descricao: "",
  corpo_html: "",
  ativo: true,
  padrao: false,
};

/**
 * Criar ou editar um modelo de documento — o formulário de Cadastros ›
 * Templates de documento, num diálogo que também abre de dentro do editor
 * ("Modelos de documentos" › "Criar novo modelo", SI-67), sem sair do
 * documento que se está redigindo.
 *
 * `modeloId` nulo = modelo novo. `onSalvo` recebe o modelo gravado.
 */
export function FormularioModeloDialog({
  open,
  onClose,
  modeloId = null,
  onSalvo,
}: {
  open: boolean;
  onClose: () => void;
  modeloId?: number | null;
  onSalvo?: (t: TemplateDocumento) => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();

  const [form, setForm] = useState<FormState>(VAZIO);
  const [modo, setModo] = useState<ModoEdicao>("blocos");
  const [blocos, setBlocos] = useState<Bloco[]>([]);
  // Erro sob o campo só depois de tentar salvar; o botão não fica cinza.
  const [tentou, setTentou] = useState(false);
  const [carregando, setCarregando] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTentou(false);
    setModo("blocos");
    if (modeloId === null) {
      setForm(VAZIO);
      setBlocos([]);
      return;
    }
    let vivo = true;
    setCarregando(true);
    api.templatesDocumento
      .get(modeloId)
      .then((t) => {
        if (!vivo) return;
        setForm({
          nome: t.nome,
          id_especie_documental: t.id_especie_documental,
          id_unidade_trabalho: t.id_unidade_trabalho,
          descricao: t.descricao ?? "",
          corpo_html: t.corpo_html,
          ativo: t.ativo,
          padrao: t.padrao,
        });
        // Modelo antigo (sem marca de bloco) abre como um bloco de Texto: nada se perde.
        setBlocos(htmlParaBlocos(t.corpo_html));
      })
      .catch((e: Error) => toast.error(e.message))
      .finally(() => vivo && setCarregando(false));
    return () => {
      vivo = false;
    };
  // Sem `toast` nas dependências: ele muda a cada render, e recarregar o
  // modelo apagaria o que foi digitado.
  }, [open, modeloId]);

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

  const placeholdersQ = useQuery({
    queryKey: ["templates-documento", "placeholders"],
    queryFn: () => api.templatesDocumento.placeholders(),
    enabled: open,
  });
  const especiesQ = useQuery({
    queryKey: ["especies-documentais"],
    queryFn: () => protocoloApi.listEspecies(),
    enabled: open,
  });
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
    enabled: open,
  });

  const faltaNome = form.nome.trim().length === 0;
  const faltaCorpo = form.corpo_html.trim().length === 0;

  const saveM = useMutation({
    mutationFn: () => {
      const payload = {
        nome: form.nome.trim(),
        id_especie_documental: form.id_especie_documental,
        id_unidade_trabalho: form.id_unidade_trabalho,
        descricao: form.descricao.trim() || null,
        corpo_html: form.corpo_html,
        ativo: form.ativo,
        // Inativo não pode ser padrão (o backend recusa): desativar desmarca.
        padrao: form.ativo && form.padrao,
      };
      return modeloId === null
        ? api.templatesDocumento.create(payload)
        : api.templatesDocumento.update(modeloId, payload);
    },
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: ["templates-documento"] });
      toast.success(modeloId === null ? "Modelo criado." : "Modelo atualizado.");
      onSalvo?.(t);
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

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

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={modeloId === null ? "Novo modelo de documento" : "Editar modelo de documento"}
      size="2xl"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={salvar} loading={saveM.isPending} disabled={carregando}>
            {saveM.isPending ? "Salvando…" : modeloId === null ? "Criar modelo" : "Salvar alterações"}
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

        <FormField
          label="Conteúdo do modelo"
          required
          error={tentou && faltaCorpo ? "Escreva o texto do modelo." : undefined}
        >
          <div>
            <EditorDeModelo
              modo={modo}
              onTrocarModo={trocarModo}
              blocos={blocos}
              onBlocos={mudarBlocos}
              corpoHtml={form.corpo_html}
              onCorpoHtml={(html) => setForm({ ...form, corpo_html: html })}
              campos={placeholdersQ.data ?? []}
              onUploadImage={enviarImagem}
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

        <label
          className={`flex items-start gap-2.5 rounded-md border border-border bg-surface-1 px-3 py-2.5 transition-colors duration-fast ${
            form.ativo ? "cursor-pointer hover:bg-surface-2" : "cursor-not-allowed opacity-60"
          }`}
        >
          <Checkbox
            checked={form.ativo && form.padrao}
            disabled={!form.ativo}
            onChange={(e) => setForm({ ...form, padrao: e.target.checked })}
            className="mt-0.5 h-4 w-4"
          />
          <span className="text-sm">
            <span className="block font-medium text-foreground">Usar como padrão</span>
            <span className="block text-xs text-foreground-muted">
              Já vem selecionado ao redigir um documento, para todos da prefeitura. Só um
              modelo pode ser o padrão: marcar este desmarca o anterior.
            </span>
          </span>
        </label>
      </div>
    </Dialog>
  );
}
