"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  protocoloApi,
  servicosApi,
  type Servico,
  type ServicoDocumento,
  type ServicoInput,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

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
  const assuntosQ = useQuery({ queryKey: ["assuntos-all"], queryFn: () => api.assuntos.listAll() });
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
      />

      <div className="flex items-center justify-between gap-2">
        <label className="flex items-center gap-2 text-sm text-foreground-muted">
          <Checkbox
            checked={incluirInativos}
            onChange={(e) => setIncluirInativos(e.target.checked)}
          />
          Mostrar inativos
        </label>
        {canCreate && <Button onClick={openNew}>Novo serviço</Button>}
      </div>

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
                Carregando...
              </TD>
            </TR>
          )}
          {servicosQ.data?.length === 0 && (
            <TR>
              <TD colSpan={6} className="text-center text-muted-foreground">
                Nenhum serviço cadastrado.
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
                <Badge intent={s.ativo ? "success" : "neutral"}>
                  {s.ativo ? "Ativo" : "Inativo"}
                </Badge>
              </TD>
              <TD className="text-right">
                <div className="inline-flex gap-2">
                  {canEdit && (
                    <Button variant="secondary" size="sm" onClick={() => openEdit(s)}>
                      Editar
                    </Button>
                  )}
                  {canEdit && (
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={toggleM.isPending}
                      onClick={async () => {
                        const ok = await confirm({
                          title: s.ativo ? "Desativar serviço" : "Ativar serviço",
                          message: s.ativo
                            ? `Desativar "${s.nome}"? Ele deixa de aparecer no portal público.`
                            : `Ativar "${s.nome}"? Ele volta a aparecer no portal público.`,
                          confirmLabel: s.ativo ? "Desativar" : "Ativar",
                        });
                        if (ok) toggleM.mutate({ id: s.id, ativo: !s.ativo });
                      }}
                    >
                      {s.ativo ? "Desativar" : "Ativar"}
                    </Button>
                  )}
                </div>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? `Editar — ${editing.nome}` : "Novo serviço"}
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
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Label htmlFor="nome" required>
              Nome
            </Label>
            <Input id="nome" value={form.nome} onChange={(e) => onNomeChange(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="slug" required>
              Slug
            </Label>
            <Input
              id="slug"
              value={form.slug}
              onChange={(e) => {
                setSlugTocado(true);
                set("slug", e.target.value);
              }}
              className="font-mono"
            />
            <p className="mt-1 text-xs text-foreground-muted">
              Minúsculas, números e hífens (3–80 caracteres).
            </p>
          </div>
          <div>
            <Label htmlFor="categoria">Categoria</Label>
            <Input id="categoria" value={form.categoria ?? ""} onChange={(e) => set("categoria", e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="desc-curta">Descrição curta</Label>
            <Input id="desc-curta" maxLength={300} value={form.descricao_curta ?? ""} onChange={(e) => set("descricao_curta", e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="desc-det">Descrição detalhada</Label>
            <Textarea id="desc-det" rows={3} value={form.descricao_detalhada ?? ""} onChange={(e) => set("descricao_detalhada", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="publico">Público-alvo</Label>
            <Input id="publico" value={form.publico_alvo ?? ""} onChange={(e) => set("publico_alvo", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="prazo">Prazo estimado (dias)</Label>
            <Input
              id="prazo"
              type="number"
              min={0}
              value={form.prazo_estimado_dias ?? ""}
              onChange={(e) => set("prazo_estimado_dias", e.target.value ? Number(e.target.value) : null)}
            />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="instrucoes">Instruções ao cidadão</Label>
            <Textarea id="instrucoes" rows={2} value={form.instrucoes_cidadao ?? ""} onChange={(e) => set("instrucoes_cidadao", e.target.value)} />
          </div>

          <div>
            <Label htmlFor="unidade">Unidade responsável</Label>
            <Select id="unidade" value={form.id_unidade_responsavel ?? ""} onChange={(e) => set("id_unidade_responsavel", e.target.value ? Number(e.target.value) : null)}>
              <option value="">—</option>
              {unidadesQ.data?.items.map((u) => (
                <option key={u.id} value={u.id}>{u.unidade_trabalho}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="tipo">Tipo de processo padrão</Label>
            <Select id="tipo" value={form.id_tipo_processo_padrao ?? ""} onChange={(e) => set("id_tipo_processo_padrao", e.target.value ? Number(e.target.value) : null)}>
              <option value="">—</option>
              {tiposQ.data?.map((t) => (
                <option key={t.id} value={t.id}>{t.tipo_processo}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="assunto">Assunto padrão</Label>
            <Select id="assunto" value={form.id_assunto_padrao ?? ""} onChange={(e) => set("id_assunto_padrao", e.target.value ? Number(e.target.value) : null)}>
              <option value="">—</option>
              {assuntosQ.data?.map((a) => (
                <option key={a.id} value={a.id}>{a.assunto}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="especie">Espécie documental padrão</Label>
            <Select id="especie" value={form.id_especie_documental_padrao ?? ""} onChange={(e) => set("id_especie_documental_padrao", e.target.value ? Number(e.target.value) : null)}>
              <option value="">—</option>
              {especiesQ.data?.map((e) => (
                <option key={e.id} value={e.id}>{e.nome}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="sigilo">Nível de sigilo padrão</Label>
            <Select id="sigilo" value={form.nivel_sigilo_padrao ?? "ostensivo"} onChange={(e) => set("nivel_sigilo_padrao", e.target.value)}>
              {NIVEIS_SIGILO.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="ordem">Ordem de exibição</Label>
            <Input id="ordem" type="number" value={form.ordem_exibicao ?? 0} onChange={(e) => set("ordem_exibicao", e.target.value ? Number(e.target.value) : 0)} />
          </div>
          <div className="flex items-center gap-2 sm:col-span-2">
            <Checkbox id="destaque" checked={form.destaque ?? false} onChange={(e) => set("destaque", e.target.checked)} />
            <Label htmlFor="destaque" className="!mb-0">Destaque no portal</Label>
          </div>

          <div className="sm:col-span-2">
            <div className="mb-1 flex items-center justify-between">
              <Label className="!mb-0">Documentos exigidos</Label>
              <Button type="button" variant="secondary" size="sm" onClick={addDoc}>
                <Plus className="mr-1 h-3.5 w-3.5" /> Adicionar
              </Button>
            </div>
            <div className="space-y-2 rounded-md border border-border p-2">
              {(form.documentos_exigidos ?? []).length === 0 && (
                <p className="text-xs text-foreground-muted">Nenhum documento.</p>
              )}
              {(form.documentos_exigidos ?? []).map((d, i) => (
                <div key={i} className="flex items-center gap-2">
                  <Input
                    placeholder="Nome do documento"
                    value={d.nome}
                    onChange={(e) => updateDoc(i, { nome: e.target.value })}
                    className="flex-1"
                  />
                  <Input
                    placeholder="Descrição (opcional)"
                    value={d.descricao ?? ""}
                    onChange={(e) => updateDoc(i, { descricao: e.target.value })}
                    className="flex-1"
                  />
                  <label className="flex shrink-0 items-center gap-1 text-xs">
                    <Checkbox checked={d.obrigatorio} onChange={(e) => updateDoc(i, { obrigatorio: e.target.checked })} />
                    Obrig.
                  </label>
                  <Button type="button" variant="ghost" size="sm" onClick={() => removeDoc(i)} aria-label="Remover documento">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          </div>

          <div className="sm:col-span-2">
            <Label htmlFor="confirmacao">Texto de confirmação</Label>
            <Textarea id="confirmacao" rows={2} value={form.texto_confirmacao ?? ""} onChange={(e) => set("texto_confirmacao", e.target.value)} />
          </div>

          {err && (
            <div role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground sm:col-span-2">
              {err}
            </div>
          )}
        </div>
      </Dialog>
    </div>
  );
}
