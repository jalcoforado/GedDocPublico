"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  Building2,
  Inbox,
  PauseCircle,
  Pencil,
  Plus,
  RotateCcw,
  SearchX,
  Trash2,
} from "lucide-react";
import { useState } from "react";

import {
  dicaVigencia,
  erroEmail,
  erroValidade,
  GrupoCampos,
  InputMascarado,
  mascaraCompleta,
  useValidacao,
} from "@/components/transporte/formulario";
import { documentoParaExibir } from "@/components/transporte/rotulos";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { SkeletonRow } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type Empresa,
  type EmpresaSituacao,
  type TipoServico,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TIPOS: { value: TipoServico; label: string }[] = [
  { value: "taxi", label: "Táxi" },
  { value: "mototaxi", label: "Mototáxi" },
  { value: "transporte_escolar", label: "Transporte escolar" },
  { value: "motofrete", label: "Motofrete" },
  { value: "transporte_distrital", label: "Transporte distrital" },
  { value: "aplicativo", label: "Aplicativo" },
  { value: "outro", label: "Outro" },
];
const SITUACOES: { value: EmpresaSituacao; label: string }[] = [
  { value: "pendente", label: "Pendente" },
  { value: "ativa", label: "Ativa" },
  { value: "suspensa", label: "Suspensa" },
  { value: "cassada", label: "Cassada" },
  { value: "inativa", label: "Inativa" },
];
const PAGE_SIZE = 50;
const TIPO_LABEL: Record<string, string> = Object.fromEntries(TIPOS.map((t) => [t.value, t.label]));
const SIT_LABEL: Record<string, string> = Object.fromEntries(SITUACOES.map((s) => [s.value, s.label]));
const SIT_INTENT: Record<string, "success" | "warning" | "info" | "danger" | "neutral"> = {
  ativa: "success",
  pendente: "warning",
  suspensa: "info",
  cassada: "danger",
  inativa: "neutral",
};

interface EmpresaForm {
  razao_social: string;
  nome_fantasia: string;
  cnpj: string;
  inscricao_municipal: string;
  inscricao_estadual: string;
  telefone: string;
  email: string;
  cep: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  municipio: string;
  uf: string;
  tipo_servico: TipoServico;
  numero_autorizacao: string;
  data_inicio_autorizacao: string;
  data_validade_autorizacao: string;
  id_representante_permissionario: string;
  situacao: EmpresaSituacao;
  observacoes: string;
}

const EMPTY: EmpresaForm = {
  razao_social: "",
  nome_fantasia: "",
  cnpj: "",
  inscricao_municipal: "",
  inscricao_estadual: "",
  telefone: "",
  email: "",
  cep: "",
  logradouro: "",
  numero: "",
  complemento: "",
  bairro: "",
  municipio: "",
  uf: "",
  tipo_servico: "taxi",
  numero_autorizacao: "",
  data_inicio_autorizacao: "",
  data_validade_autorizacao: "",
  id_representante_permissionario: "",
  situacao: "pendente",
  observacoes: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

export default function EmpresasPage() {
  const { can } = useAuth();
  const canCreate = can("transporte_regulado", "inserir");
  const canEdit = can("transporte_regulado", "atualizar");
  const canDelete = can("transporte_regulado", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [situacaoFiltro, setSituacaoFiltro] = useState("");
  const [tipoFiltro, setTipoFiltro] = useState("");
  const [busca, setBusca] = useState("");
  // Truncava em 50 sem aviso (backend já pagina desde 2026-07-20; a UI nunca
  // ganhou controle). Reseta pra 1 a cada troca de filtro/busca.
  const [page, setPage] = useState(1);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Empresa | null>(null);
  const [form, setForm] = useState<EmpresaForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const listaQ = useQuery({
    queryKey: ["tr-empresas", situacaoFiltro, tipoFiltro, busca, page],
    queryFn: () =>
      api.empresas.list({
        situacao: situacaoFiltro || undefined,
        tipo_servico: tipoFiltro || undefined,
        q: busca.trim() || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  });
  const totalPages = Math.max(1, Math.ceil((listaQ.data?.total ?? 0) / PAGE_SIZE));
  const filtrando = situacaoFiltro !== "" || tipoFiltro !== "" || busca.trim() !== "";

  function limparFiltros() {
    setSituacaoFiltro("");
    setTipoFiltro("");
    setBusca("");
    setPage(1);
  }

  // Permissionários para o select de representante (opcional).
  const permsQ = useQuery({
    queryKey: ["tr-permissionarios-rep"],
    queryFn: () => api.permissionarios.list(),
    enabled: dialogOpen,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["tr-empresas"] });

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing ? api.empresas.update(editing.id, data) : api.empresas.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Empresa atualizada." : "Empresa cadastrada.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const actionM = useMutation({
    mutationFn: ({ id, acao }: { id: number; acao: "inativar" | "reativar" | "suspender" }) =>
      acao === "inativar"
        ? api.empresas.inativar(id)
        : acao === "reativar"
          ? api.empresas.reativar(id)
          : api.empresas.suspender(id),
    onSuccess: () => {
      invalidate();
      toast.success("Situação atualizada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.empresas.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Empresa excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Regras do backend (`EmpresaCreate`) ditas no campo, com o conserto.
  const val = useValidacao<"razao_social" | "cnpj" | "email" | "uf" | "data_validade_autorizacao">({
    razao_social: form.razao_social.trim() === "" ? "Informe a razão social." : undefined,
    cnpj:
      form.cnpj.trim() === ""
        ? "Informe o CNPJ."
        : !mascaraCompleta("cnpj", form.cnpj)
          ? "CNPJ incompleto: use o formato 00.000.000/0000-00."
          : undefined,
    email: erroEmail(form.email),
    uf: form.uf.trim() !== "" && form.uf.trim().length !== 2 ? "Use a sigla de 2 letras (ex.: CE)." : undefined,
    data_validade_autorizacao: erroValidade(form.data_inicio_autorizacao, form.data_validade_autorizacao),
  });

  function set<K extends keyof EmpresaForm>(key: K, value: EmpresaForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }
  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    val.reiniciar();
    setDialogOpen(true);
  }
  function openEdit(e: Empresa) {
    setEditing(e);
    setForm({
      razao_social: e.razao_social,
      nome_fantasia: e.nome_fantasia ?? "",
      cnpj: e.cnpj,
      inscricao_municipal: e.inscricao_municipal ?? "",
      inscricao_estadual: e.inscricao_estadual ?? "",
      telefone: e.telefone ?? "",
      email: e.email ?? "",
      cep: e.cep ?? "",
      logradouro: e.logradouro ?? "",
      numero: e.numero ?? "",
      complemento: e.complemento ?? "",
      bairro: e.bairro ?? "",
      municipio: e.municipio ?? "",
      uf: e.uf ?? "",
      tipo_servico: e.tipo_servico,
      numero_autorizacao: e.numero_autorizacao ?? "",
      data_inicio_autorizacao: e.data_inicio_autorizacao ?? "",
      data_validade_autorizacao: e.data_validade_autorizacao ?? "",
      id_representante_permissionario:
        e.id_representante_permissionario != null
          ? String(e.id_representante_permissionario)
          : "",
      situacao: e.situacao,
      observacoes: e.observacoes ?? "",
    });
    setErr(null);
    val.reiniciar();
    setDialogOpen(true);
  }
  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }
  function salvar() {
    setErr(null);
    if (!val.conferir()) return;
    const payload = {
      razao_social: form.razao_social.trim(),
      nome_fantasia: nullify(form.nome_fantasia),
      cnpj: form.cnpj.trim(),
      inscricao_municipal: nullify(form.inscricao_municipal),
      inscricao_estadual: nullify(form.inscricao_estadual),
      telefone: nullify(form.telefone),
      email: nullify(form.email),
      cep: nullify(form.cep),
      logradouro: nullify(form.logradouro),
      numero: nullify(form.numero),
      complemento: nullify(form.complemento),
      bairro: nullify(form.bairro),
      municipio: nullify(form.municipio),
      uf: nullify(form.uf),
      tipo_servico: form.tipo_servico,
      numero_autorizacao: nullify(form.numero_autorizacao),
      data_inicio_autorizacao: nullify(form.data_inicio_autorizacao),
      data_validade_autorizacao: nullify(form.data_validade_autorizacao),
      id_representante_permissionario:
        form.id_representante_permissionario === ""
          ? null
          : Number(form.id_representante_permissionario),
      situacao: form.situacao,
      observacoes: nullify(form.observacoes),
    };
    saveM.mutate(payload);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Building2}
        title="Empresas"
        description="Cadastro de empresas e operadoras do transporte regulado."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Empresas" },
        ]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Nova empresa
            </Button>
          ) : undefined
        }
      />

      <FilterBar ariaLabel="Filtros das empresas">
        <FilterBar.Group label="Situação" className="w-full sm:w-48">
          <Select
            id="f_sit"
            aria-label="Situação"
            value={situacaoFiltro}
            onChange={(e) => {
              setSituacaoFiltro(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Todas</option>
            {SITUACOES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        <FilterBar.Group label="Tipo de serviço" className="w-full sm:w-56">
          <Select
            id="f_tipo"
            aria-label="Tipo de serviço"
            value={tipoFiltro}
            onChange={(e) => {
              setTipoFiltro(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            {TIPOS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        <FilterBar.Group label="Busca" className="min-w-[200px] flex-1">
          <Input
            id="f_q"
            aria-label="Busca"
            value={busca}
            onChange={(e) => {
              setBusca(e.target.value);
              setPage(1);
            }}
            placeholder="Razão social, nome fantasia ou CNPJ"
          />
        </FilterBar.Group>
        {filtrando && (
          <FilterBar.Actions>
            <Button variant="ghost" onClick={limparFiltros}>
              Limpar
            </Button>
          </FilterBar.Actions>
        )}
      </FilterBar>

      {!listaQ.isLoading && (listaQ.data?.items.length ?? 0) === 0 ? (
        <EmptyState
          icon={filtrando ? SearchX : Inbox}
          title={filtrando ? "Nenhuma empresa encontrada" : "Nenhuma empresa"}
          description={
            filtrando
              ? "Nenhuma empresa corresponde à busca ou aos filtros aplicados."
              : "Cadastre a primeira empresa do transporte regulado."
          }
          action={
            filtrando ? (
              <Button variant="secondary" onClick={limparFiltros}>
                Limpar filtros
              </Button>
            ) : canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Cadastrar empresa
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Razão social</TH>
              <TH>CNPJ</TH>
              <TH>Tipo de serviço</TH>
              <TH>Autorização</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {listaQ.isLoading &&
              Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} cols={6} />)}
            {listaQ.data?.items.map((e) => (
              <TR key={e.id}>
                <TD>
                  <div className="font-medium">{e.razao_social}</div>
                  {e.nome_fantasia && (
                    <div className="text-xs text-muted-foreground">{e.nome_fantasia}</div>
                  )}
                </TD>
                <TD className="whitespace-nowrap font-mono">{documentoParaExibir(e.cnpj)}</TD>
                <TD>{TIPO_LABEL[e.tipo_servico] ?? e.tipo_servico}</TD>
                <TD className="text-muted-foreground">{e.numero_autorizacao ?? "—"}</TD>
                <TD>
                  <Badge intent={SIT_INTENT[e.situacao] ?? "neutral"}>
                    {SIT_LABEL[e.situacao] ?? e.situacao}
                  </Badge>
                </TD>
                <TD className="text-right">
                  {/* Mesmo arranjo de permissionários e veículos: o que muda
                      com a situação à vista; Inativar e Excluir no ⋯. */}
                  <AcoesDaLinha
                    acoes={[
                      { label: "Editar", icon: Pencil, onClick: () => openEdit(e), oculta: !canEdit },
                      {
                        label: "Reativar",
                        icon: RotateCcw,
                        onClick: () => actionM.mutate({ id: e.id, acao: "reativar" }),
                        oculta: !canEdit || e.situacao === "ativa",
                      },
                      {
                        label: "Suspender",
                        icon: PauseCircle,
                        onClick: () => actionM.mutate({ id: e.id, acao: "suspender" }),
                        oculta: !canEdit || e.situacao === "suspensa",
                      },
                      {
                        label: "Inativar",
                        icon: Ban,
                        perigo: true,
                        onClick: () => actionM.mutate({ id: e.id, acao: "inativar" }),
                        oculta: !canEdit || e.situacao === "inativa",
                      },
                      {
                        label: "Excluir",
                        icon: Trash2,
                        perigo: true,
                        disabled: deleteM.isPending,
                        oculta: !canDelete,
                        onClick: async () => {
                          const ok = await confirm({
                            title: "Excluir empresa",
                            message: `Excluir a empresa "${e.razao_social}"? Esta ação não pode ser desfeita.`,
                            confirmLabel: "Excluir",
                            intent: "danger",
                          });
                          if (ok) deleteM.mutate(e.id);
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

      {listaQ.data && listaQ.data.total > 0 && (
        <div className="flex flex-col items-start justify-between gap-2 text-sm text-muted-foreground sm:flex-row sm:items-center">
          <span className="tabular-nums">
            {listaQ.data.total} empresas — página {page} de {totalPages}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              Anterior
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              Próxima
            </Button>
          </div>
        </div>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? `Editar empresa — ${editing.razao_social}` : "Nova empresa"}
        description={
          editing ? undefined : "Quem é a empresa, onde fica e com que autorização opera. Só razão social e CNPJ são obrigatórios."
        }
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={salvar} loading={saveM.isPending}>
              {editing ? "Salvar alterações" : "Cadastrar empresa"}
            </Button>
          </>
        }
      >
        <div ref={val.ref} className="space-y-5">
          <GrupoCampos titulo="Empresa">
            <FormField label="Razão social" required error={val.erro("razao_social")}>
              <Input
                id="razao"
                value={form.razao_social}
                onChange={(e) => set("razao_social", e.target.value)}
                onBlur={val.sair("razao_social")}
                placeholder="Ex.: Transportes Boa Viagem Ltda."
              />
            </FormField>
            <GradeCampos>
              <FormField label="CNPJ" required error={val.erro("cnpj")}>
                <InputMascarado
                  id="cnpj"
                  mascara="cnpj"
                  value={form.cnpj}
                  onValueChange={(x) => set("cnpj", x)}
                  onBlur={val.sair("cnpj")}
                  placeholder="00.000.000/0000-00"
                />
              </FormField>
              <FormField label="Nome fantasia" opcional>
                <Input
                  id="fantasia"
                  value={form.nome_fantasia}
                  onChange={(e) => set("nome_fantasia", e.target.value)}
                  placeholder="Ex.: Boa Viagem Táxi"
                />
              </FormField>
            </GradeCampos>
            <GradeCampos>
              <FormField label="Inscrição municipal" opcional>
                <Input id="im" value={form.inscricao_municipal} onChange={(e) => set("inscricao_municipal", e.target.value)} />
              </FormField>
              <FormField label="Inscrição estadual" opcional>
                <Input id="ie" value={form.inscricao_estadual} onChange={(e) => set("inscricao_estadual", e.target.value)} />
              </FormField>
            </GradeCampos>
            <GradeCampos>
              <FormField label="Telefone" opcional>
                <Input
                  id="tel"
                  type="tel"
                  value={form.telefone}
                  onChange={(e) => set("telefone", e.target.value)}
                  placeholder="Ex.: (88) 3611-0000"
                />
              </FormField>
              <FormField label="E-mail" opcional error={val.erro("email")}>
                <Input
                  id="email"
                  type="email"
                  value={form.email}
                  onChange={(e) => set("email", e.target.value)}
                  onBlur={val.sair("email")}
                  placeholder="Ex.: contato@empresa.com.br"
                />
              </FormField>
            </GradeCampos>
          </GrupoCampos>

          <GrupoCampos titulo="Endereço" descricao="Opcional, mas ajuda a fiscalização a localizar a sede.">
            <GradeCampos>
              <FormField label="CEP">
                <Input
                  id="cep"
                  inputMode="numeric"
                  maxLength={9}
                  value={form.cep}
                  onChange={(e) => set("cep", e.target.value)}
                  placeholder="Ex.: 62010-000"
                />
              </FormField>
              <FormField label="Bairro">
                <Input id="bairro" value={form.bairro} onChange={(e) => set("bairro", e.target.value)} />
              </FormField>
            </GradeCampos>
            <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_8rem]">
              <FormField label="Logradouro">
                <Input
                  id="logr"
                  value={form.logradouro}
                  onChange={(e) => set("logradouro", e.target.value)}
                  placeholder="Ex.: Rua Coronel Ernesto Deocleciano"
                />
              </FormField>
              <FormField label="Número">
                <Input id="num" value={form.numero} onChange={(e) => set("numero", e.target.value)} placeholder="Ex.: 120" />
              </FormField>
            </div>
            <FormField label="Complemento">
              <Input
                id="compl"
                value={form.complemento}
                onChange={(e) => set("complemento", e.target.value)}
                placeholder="Ex.: Sala 3"
              />
            </FormField>
            <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_8rem]">
              <FormField label="Município">
                <Input id="mun" value={form.municipio} onChange={(e) => set("municipio", e.target.value)} />
              </FormField>
              <FormField label="UF" error={val.erro("uf")}>
                <Input
                  id="uf"
                  value={form.uf}
                  maxLength={2}
                  className="uppercase"
                  onChange={(e) => set("uf", e.target.value.toUpperCase())}
                  onBlur={val.sair("uf")}
                  placeholder="CE"
                />
              </FormField>
            </div>
          </GrupoCampos>

          <GrupoCampos titulo="Serviço e autorização">
            <GradeCampos>
              <FormField label="Tipo de serviço" required>
                <Select
                  id="tipo"
                  value={form.tipo_servico}
                  onChange={(e) => set("tipo_servico", e.target.value as TipoServico)}
                >
                  {TIPOS.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField label="Número da autorização" opcional>
                <Input
                  id="numaut"
                  value={form.numero_autorizacao}
                  onChange={(e) => set("numero_autorizacao", e.target.value)}
                  placeholder="Ex.: AUT-0012/2026"
                />
              </FormField>
            </GradeCampos>
            <GradeCampos>
              <FormField label="Início da autorização" opcional>
                <Input
                  id="ini"
                  type="date"
                  value={form.data_inicio_autorizacao}
                  onChange={(e) => set("data_inicio_autorizacao", e.target.value)}
                />
              </FormField>
              <FormField
                label="Validade da autorização"
                opcional
                error={val.erro("data_validade_autorizacao")}
                hint={dicaVigencia(
                  form.data_inicio_autorizacao,
                  form.data_validade_autorizacao,
                  "Último dia em que a autorização vale.",
                )}
              >
                <Input
                  id="val"
                  type="date"
                  value={form.data_validade_autorizacao}
                  onChange={(e) => set("data_validade_autorizacao", e.target.value)}
                  onBlur={val.sair("data_validade_autorizacao")}
                />
              </FormField>
            </GradeCampos>
            <FormField label="Representante" opcional hint="Permissionário que representa a empresa. Busque pelo nome ou CPF.">
              <Combobox
                id="rep"
                options={(permsQ.data?.items ?? []).map((p) => ({
                  value: p.id,
                  label: p.nome,
                  hint: documentoParaExibir(p.cpf),
                }))}
                value={form.id_representante_permissionario ? Number(form.id_representante_permissionario) : null}
                onChange={(id) => set("id_representante_permissionario", id == null ? "" : String(id))}
                placeholder="Nenhum"
                searchPlaceholder="Nome ou CPF…"
                emptyText="Nenhum permissionário com esse nome."
                loading={permsQ.isLoading}
              />
            </FormField>
            <FormField
              label="Situação"
              hint={
                editing
                  ? "Suspender e reativar também ficam nas ações da linha."
                  : "Cadastro novo entra como Pendente, salvo se mudar aqui."
              }
            >
              <Select id="sit" value={form.situacao} onChange={(e) => set("situacao", e.target.value as EmpresaSituacao)}>
                {SITUACOES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </Select>
            </FormField>
          </GrupoCampos>

          <div className="border-t border-border pt-5">
            <FormField label="Observações" opcional>
              <Textarea
                id="obs"
                rows={2}
                value={form.observacoes}
                onChange={(e) => set("observacoes", e.target.value)}
                placeholder="Ex.: frota em renovação até março"
              />
            </FormField>
          </div>

          {err && <Alert intent="danger">{err}</Alert>}
        </div>
      </Dialog>
    </div>
  );
}
