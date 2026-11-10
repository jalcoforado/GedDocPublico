"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ClipboardList,
  FileText,
  Inbox,
  MessageSquareText,
  Pause,
  Pencil,
  Play,
  Plus,
  Settings2,
  Trash2,
} from "lucide-react";
import { useState } from "react";

import { BadgeAtivo } from "@/components/protocolo/BadgeAtivo";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { Input } from "@/components/ui/input";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  NIVEL_SIGILO_LABEL,
  protocoloApi,
  servicosApi,
  type NivelSigilo,
  type Servico,
  type ServicoDocumento,
  type ServicoInput,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAssuntosAll } from "@/lib/assuntos";

const NIVEIS_SIGILO = ["ostensivo", "interno", "reservado", "secreto", "ultrassecreto"];

const EMPTY: ServicoInput = {
  nome: "",
  slug: "",
  descricao_curta: "",
  descricao_detalhada: "",
  publico_alvo: "",
  instrucoes_cidadao: "",
  documentos_exigidos: [],
  prazo_estimado_dias: null,
  id_unidade_responsavel: null,
  id_tipo_processo_padrao: null,
  id_assunto_padrao: null,
  id_especie_documental_padrao: null,
  nivel_sigilo_padrao: "ostensivo",
  canal_entrada_permitido: "portal",
  destaque: false,
  ordem_exibicao: 0,
  categoria: "",
  texto_confirmacao: "",
};

function slugify(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function nullify(v: string | null | undefined): string | null {
  const t = (v ?? "").trim();
  return t === "" ? null : t;
}

export default function ServicosPage() {
  const { can } = useAuth();
  const canEdit = can("servico", "atualizar");
  const canCreate = can("servico", "inserir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [incluirInativos, setIncluirInativos] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Servico | null>(null);
  const [form, setForm] = useState<ServicoInput>(EMPTY);
  const [slugTocado, setSlugTocado] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const servicosQ = useQuery({
    queryKey: ["servicos", incluirInativos],
    queryFn: () => servicosApi.list(incluirInativos),
  });
  const unidadesQ = useQuery({ queryKey: ["unidades-all"], queryFn: () => api.unidades.list({ page_size: 200 }) });
  const tiposQ = useQuery({ queryKey: ["tipos-processo"], queryFn: api.tiposProcesso.list });
  const assuntosQ = useAssuntosAll();
  const especiesQ = useQuery({ queryKey: ["especies"], queryFn: () => protocoloApi.listEspecies(false) });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["servicos"] });
  };

  const saveM = useMutation({
    mutationFn: (data: ServicoInput) =>
      editing ? servicosApi.update(editing.id, data) : servicosApi.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Serviço atualizado." : "Serviço criado.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const toggleM = useMutation({
    mutationFn: ({ id, ativo }: { id: number; ativo: boolean }) =>
      ativo ? servicosApi.ativar(id) : servicosApi.desativar(id),
    onSuccess: () => {
      invalidate();
      toast.success("Status atualizado.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setSlugTocado(false);
    setErr(null);
    setDialogOpen(true);
  }

  function openEdit(s: Servico) {
    setEditing(s);
    setForm({
      nome: s.nome,
      slug: s.slug,
      descricao_curta: s.descricao_curta ?? "",
      descricao_detalhada: s.descricao_detalhada ?? "",
      publico_alvo: s.publico_alvo ?? "",
      instrucoes_cidadao: s.instrucoes_cidadao ?? "",
      documentos_exigidos: s.documentos_exigidos ?? [],
      prazo_estimado_dias: s.prazo_estimado_dias,
      id_unidade_responsavel: s.id_unidade_responsavel,
      id_tipo_processo_padrao: s.id_tipo_processo_padrao,
      id_assunto_padrao: s.id_assunto_padrao,
      id_especie_documental_padrao: s.id_especie_documental_padrao,
      nivel_sigilo_padrao: s.nivel_sigilo_padrao,
      canal_entrada_permitido: s.canal_entrada_permitido,
      destaque: s.destaque,
      ordem_exibicao: s.ordem_exibicao,
      categoria: s.categoria ?? "",
      texto_confirmacao: s.texto_confirmacao ?? "",
    });
    setSlugTocado(true);
    setErr(null);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }

  function set<K extends keyof ServicoInput>(key: K, value: ServicoInput[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function onNomeChange(v: string) {
    setForm((f) => ({
      ...f,
      nome: v,
      slug: slugTocado ? f.slug : slugify(v),
    }));
  }

  function addDoc() {
    set("documentos_exigidos", [
      ...(form.documentos_exigidos ?? []),
      { nome: "", obrigatorio: false, descricao: "" },
    ]);
  }
  function updateDoc(i: number, patch: Partial<ServicoDocumento>) {
    const docs = [...(form.documentos_exigidos ?? [])];
    docs[i] = { ...docs[i], ...patch };
    set("documentos_exigidos", docs);
  }
  function removeDoc(i: number) {
    set(
      "documentos_exigidos",
      (form.documentos_exigidos ?? []).filter((_, idx) => idx !== i),
    );
  }

  function salvar() {
    setErr(null);
    const docs = (form.documentos_exigidos ?? [])
      .map((d) => ({ ...d, nome: d.nome.trim(), descricao: nullify(d.descricao) }))
      .filter((d) => d.nome !== "");
    const payload: ServicoInput = {
      nome: form.nome.trim(),
      slug: form.slug.trim(),
      descricao_curta: nullify(form.descricao_curta),
      descricao_detalhada: nullify(form.descricao_detalhada),
      publico_alvo: nullify(form.publico_alvo),
      instrucoes_cidadao: nullify(form.instrucoes_cidadao),
      documentos_exigidos: docs.length ? docs : null,
      prazo_estimado_dias: form.prazo_estimado_dias ?? null,
      id_unidade_responsavel: form.id_unidade_responsavel ?? null,
      id_tipo_processo_padrao: form.id_tipo_processo_padrao ?? null,
      id_assunto_padrao: form.id_assunto_padrao ?? null,
      id_especie_documental_padrao: form.id_especie_documental_padrao ?? null,
      nivel_sigilo_padrao: form.nivel_sigilo_padrao,
      canal_entrada_permitido: form.canal_entrada_permitido,
      destaque: form.destaque,
      ordem_exibicao: form.ordem_exibicao ?? 0,
      categoria: nullify(form.categoria),
      texto_confirmacao: nullify(form.texto_confirmacao),
    };
    saveM.mutate(payload);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={ClipboardList}
        title="Catálogo de Serviços"
        description="Carta de Serviços do município. Cadastre os serviços que aparecem no portal do cidadão."
        actions={
          canCreate && (
            <Button onClick={openNew}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Novo serviço
            </Button>
          )
        }
      />

      <FilterBar ariaLabel="Filtros do catálogo">
        <label className="flex h-11 items-center gap-2 text-sm text-foreground-muted">
          <Checkbox
            checked={incluirInativos}
            onChange={(e) => setIncluirInativos(e.target.checked)}
          />
          Mostrar inativos
        </label>
      </FilterBar>

      {!servicosQ.isLoading && servicosQ.data && servicosQ.data.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhum serviço cadastrado"
          description="Cadastre o primeiro serviço para que ele apareça no portal do cidadão."
          action={
            canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Cadastrar serviço
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Nome</TH>
              <TH>Slug</TH>
              <TH>Categoria</TH>
              <TH>Ordem</TH>
              <TH>Status</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {servicosQ.isLoading && (
              <TR>
                <TD colSpan={6} className="text-center text-muted-foreground">
                  Carregando serviços...
                </TD>
              </TR>
            )}
            {servicosQ.data?.map((s) => (
              <TR key={s.id}>
                <TD className="font-medium">
                  {s.nome}
                  {s.destaque && (
                    <Badge intent="brand" className="ml-2">
                      Destaque
                    </Badge>
                  )}
                </TD>
                <TD className="font-mono text-xs">{s.slug}</TD>
                <TD className="text-muted-foreground">{s.categoria ?? "—"}</TD>
                <TD className="tabular-nums">{s.ordem_exibicao}</TD>
                <TD>
                  <BadgeAtivo ativo={s.ativo} />
                </TD>
                <TD className="text-right">
                  <AcoesDaLinha
                    acoes={[
                      { label: "Editar", icon: Pencil, oculta: !canEdit, onClick: () => openEdit(s) },
                      {
                        label: s.ativo ? "Desativar" : "Ativar",
                        icon: s.ativo ? Pause : Play,
                        perigo: s.ativo,
                        oculta: !canEdit,
                        disabled: toggleM.isPending,
                        onClick: async () => {
                          const ok = await confirm({
                            title: s.ativo ? "Desativar serviço" : "Ativar serviço",
                            message: s.ativo
                              ? `Desativar "${s.nome}"? Ele deixa de aparecer no portal público.`
                              : `Ativar "${s.nome}"? Ele volta a aparecer no portal público.`,
                            confirmLabel: s.ativo ? "Desativar" : "Ativar",
                          });
                          if (ok) toggleM.mutate({ id: s.id, ativo: !s.ativo });
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
        title={editing ? `Editar serviço — ${editing.nome}` : "Novo serviço"}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={salvar} loading={saveM.isPending}>
              {saveM.isPending ? "Salvando…" : editing ? "Salvar alterações" : "Criar serviço"}
            </Button>
          </>
        }
      >
        <div className="space-y-4" data-testid="servico-form">
          <SectionCard
            icon={FileText}
            title="Identificação do serviço"
            description="Como o serviço aparece no portal do cidadão (nome, categoria, descrições)."
          >
            <FormField label="Nome" required hint="Como o cidadão procura o serviço.">
              <Input
                id="nome"
                value={form.nome}
                onChange={(e) => onNomeChange(e.target.value)}
                placeholder="Ex.: Poda de árvore"
              />
            </FormField>
            <GradeCampos>
              <FormField
                label="Slug"
                required
                hint="Endereço na URL: minúsculas, números e hífens (3 a 80). Sai do nome sozinho."
              >
                <Input
                  id="slug"
                  value={form.slug}
                  onChange={(e) => {
                    setSlugTocado(true);
                    set("slug", e.target.value);
                  }}
                  className="font-mono"
                  placeholder="Ex.: poda-de-arvore"
                />
              </FormField>
              <FormField label="Categoria" hint="Agrupa serviços parecidos no portal.">
                <Input
                  id="categoria"
                  value={form.categoria ?? ""}
                  onChange={(e) => set("categoria", e.target.value)}
                  placeholder="Ex.: Meio ambiente"
                />
              </FormField>
            </GradeCampos>
            <FormField
              label="Descrição curta"
              hint={`Resumo nos cards da listagem. ${(form.descricao_curta ?? "").length}/300`}
            >
              <Input
                id="desc-curta"
                maxLength={300}
                value={form.descricao_curta ?? ""}
                onChange={(e) => set("descricao_curta", e.target.value)}
                placeholder="Ex.: Peça a poda de árvores em vias e praças públicas."
              />
            </FormField>
            <FormField label="Descrição detalhada">
              <Textarea
                id="desc-det"
                rows={3}
                value={form.descricao_detalhada ?? ""}
                onChange={(e) => set("descricao_detalhada", e.target.value)}
              />
            </FormField>
            <FormField label="Público-alvo" hint="Quem pode pedir o serviço.">
              <Input
                id="publico"
                value={form.publico_alvo ?? ""}
                onChange={(e) => set("publico_alvo", e.target.value)}
                placeholder="Ex.: Pessoa física, microempreendedor"
              />
            </FormField>
          </SectionCard>

          <SectionCard
            icon={Settings2}
            title="Configuração operacional"
            description="Para onde o pedido vai e como nasce o processo. Não aparece ao cidadão."
          >
            <FormField label="Unidade responsável" hint="Recebe os processos abertos por este serviço.">
              <Select
                id="unidade"
                value={form.id_unidade_responsavel ?? ""}
                onChange={(e) => set("id_unidade_responsavel", e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Nenhuma</option>
                {unidadesQ.data?.items.map((u) => (
                  <option key={u.id} value={u.id}>{u.unidade_trabalho}</option>
                ))}
              </Select>
            </FormField>
            <GradeCampos>
              <FormField label="Tipo de processo padrão">
                <Select
                  id="tipo"
                  value={form.id_tipo_processo_padrao ?? ""}
                  onChange={(e) => set("id_tipo_processo_padrao", e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">Nenhum</option>
                  {tiposQ.data?.map((t) => (
                    <option key={t.id} value={t.id}>{t.tipo_processo}</option>
                  ))}
                </Select>
              </FormField>
              <FormField label="Assunto padrão">
                <Select
                  id="assunto"
                  value={form.id_assunto_padrao ?? ""}
                  onChange={(e) => set("id_assunto_padrao", e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">Nenhum</option>
                  {assuntosQ.data?.map((a) => (
                    <option key={a.id} value={a.id}>{a.assunto}</option>
                  ))}
                </Select>
              </FormField>
              <FormField label="Espécie documental padrão">
                <Select
                  id="especie"
                  value={form.id_especie_documental_padrao ?? ""}
                  onChange={(e) => set("id_especie_documental_padrao", e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">Nenhuma</option>
                  {especiesQ.data?.map((e) => (
                    <option key={e.id} value={e.id}>{e.nome}</option>
                  ))}
                </Select>
              </FormField>
              <FormField label="Nível de sigilo padrão">
                <Select
                  id="sigilo"
                  value={form.nivel_sigilo_padrao ?? "ostensivo"}
                  onChange={(e) => set("nivel_sigilo_padrao", e.target.value)}
                >
                  {NIVEIS_SIGILO.map((n) => (
                    <option key={n} value={n}>
                      {NIVEL_SIGILO_LABEL[n as NivelSigilo] ?? n}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField
                label="Prazo estimado"
                hint="Mostrado ao cidadão como previsão, não como promessa."
              >
                <CampoComUnidade
                  id="prazo"
                  type="number"
                  min={0}
                  sufixo="dias"
                  value={form.prazo_estimado_dias ?? ""}
                  onChange={(e) => set("prazo_estimado_dias", e.target.value ? Number(e.target.value) : null)}
                  placeholder="Ex.: 15"
                />
              </FormField>
              <FormField label="Ordem de exibição" hint="Menor número aparece primeiro.">
                <Input
                  id="ordem"
                  type="number"
                  value={form.ordem_exibicao ?? 0}
                  onChange={(e) => set("ordem_exibicao", e.target.value ? Number(e.target.value) : 0)}
                />
              </FormField>
            </GradeCampos>
            <div className="flex items-start gap-2.5 rounded-md border border-border bg-surface-1 px-3 py-2.5">
              <Checkbox
                id="destaque"
                checked={form.destaque ?? false}
                onChange={(e) => set("destaque", e.target.checked)}
                className="mt-0.5 h-4 w-4"
                aria-describedby="destaque-dica"
              />
              <div className="text-sm">
                <label htmlFor="destaque" className="block cursor-pointer font-medium text-foreground">
                  Destaque no portal
                </label>
                <p id="destaque-dica" className="text-xs text-foreground-muted">
                  Aparece em destaque no portal do cidadão.
                </p>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            icon={MessageSquareText}
            title="Orientações ao cidadão"
            description="Textos e documentos solicitados que o cidadão verá ao abrir o serviço."
          >
            <FormField
              label="Instruções ao cidadão"
              hint="Passo a passo ou observações importantes para quem vai pedir."
            >
              <Textarea
                id="instrucoes"
                rows={3}
                value={form.instrucoes_cidadao ?? ""}
                onChange={(e) => set("instrucoes_cidadao", e.target.value)}
              />
            </FormField>

            <div>
              <div className="mb-2 flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-foreground">Documentos exigidos</p>
                  <p className="mt-0.5 text-xs text-foreground-muted">
                    Lista mostrada ao cidadão ao pedir o serviço. Marque como obrigatório o que bloqueia o envio.
                  </p>
                </div>
                <Button type="button" variant="secondary" size="sm" onClick={addDoc}>
                  <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Adicionar documento
                </Button>
              </div>
              <div className="space-y-2 rounded-md border border-border bg-surface-1 p-3" data-testid="servicos-docs-area">
                {(form.documentos_exigidos ?? []).length === 0 ? (
                  <div className="flex flex-col items-center justify-center gap-1 py-4 text-center text-xs text-foreground-muted">
                    <p>Nenhum documento exigido.</p>
                    <p>Clique em &quot;Adicionar documento&quot; para listar o que o cidadão deve enviar.</p>
                  </div>
                ) : (
                  (form.documentos_exigidos ?? []).map((d, i) => (
                    <div
                      key={i}
                      className="rounded-md border border-border bg-surface-2 p-2"
                      data-testid="servicos-doc-item"
                    >
                      <div className="flex items-center gap-2">
                        <Input
                          placeholder="Ex.: RG ou CNH"
                          value={d.nome}
                          onChange={(e) => updateDoc(i, { nome: e.target.value })}
                          className="flex-1"
                          aria-label={`Documento ${i + 1} — nome`}
                        />
                        <label className="flex shrink-0 cursor-pointer items-center gap-1.5 text-xs text-foreground">
                          <Checkbox
                            checked={d.obrigatorio}
                            onChange={(e) => updateDoc(i, { obrigatorio: e.target.checked })}
                            className="h-4 w-4"
                          />
                          Obrigatório
                        </label>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => removeDoc(i)}
                          aria-label={`Remover documento ${i + 1}`}
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </Button>
                      </div>
                      <Input
                        placeholder="Descrição, se precisar (ex.: frente e verso, legível)"
                        value={d.descricao ?? ""}
                        onChange={(e) => updateDoc(i, { descricao: e.target.value })}
                        className="mt-2"
                        aria-label={`Documento ${i + 1} — descrição`}
                      />
                    </div>
                  ))
                )}
              </div>
            </div>

            <FormField
              label="Texto de confirmação"
              hint="Mensagem que o cidadão vê depois de enviar o pedido."
            >
              <Textarea
                id="confirmacao"
                rows={2}
                value={form.texto_confirmacao ?? ""}
                onChange={(e) => set("texto_confirmacao", e.target.value)}
                placeholder="Ex.: Recebemos seu pedido. Acompanhe pelo número do protocolo."
              />
            </FormField>
          </SectionCard>

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
