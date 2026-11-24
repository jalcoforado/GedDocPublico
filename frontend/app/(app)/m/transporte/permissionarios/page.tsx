"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  IdCard,
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
import { Alert } from "@/components/ui/alert";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  type Permissionario,
  type PermissionarioSituacao,
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
const SITUACOES: { value: PermissionarioSituacao; label: string }[] = [
  { value: "pendente", label: "Pendente" },
  { value: "ativo", label: "Ativo" },
  { value: "suspenso", label: "Suspenso" },
  { value: "cassado", label: "Cassado" },
  { value: "inativo", label: "Inativo" },
];
const CNH_CATS = ["A", "B", "AB", "C", "D", "E", "AC", "AD", "AE"];
const PAGE_SIZE = 50;
const TIPO_LABEL: Record<string, string> = Object.fromEntries(TIPOS.map((t) => [t.value, t.label]));
const SIT_LABEL: Record<string, string> = Object.fromEntries(SITUACOES.map((s) => [s.value, s.label]));
const SIT_INTENT: Record<string, "success" | "warning" | "info" | "danger" | "neutral"> = {
  ativo: "success",
  pendente: "warning",
  suspenso: "info",
  cassado: "danger",
  inativo: "neutral",
};

interface PermForm {
  nome: string;
  cpf: string;
  rg: string;
  data_nascimento: string;
  telefone: string;
  email: string;
  cnh_numero: string;
  cnh_categoria: string;
  cnh_validade: string;
  tipo_servico: TipoServico;
  numero_permissao: string;
  data_inicio_permissao: string;
  data_validade_permissao: string;
  situacao: PermissionarioSituacao;
  observacoes: string;
}

const EMPTY: PermForm = {
  nome: "",
  cpf: "",
  rg: "",
  data_nascimento: "",
  telefone: "",
  email: "",
  cnh_numero: "",
  cnh_categoria: "",
  cnh_validade: "",
  tipo_servico: "taxi",
  numero_permissao: "",
  data_inicio_permissao: "",
  data_validade_permissao: "",
  situacao: "pendente",
  observacoes: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

export default function PermissionariosPage() {
  const { can } = useAuth();
  const canCreate = can("transporte_regulado", "inserir");
  const canEdit = can("transporte_regulado", "atualizar");
  const canDelete = can("transporte_regulado", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [situacaoFiltro, setSituacaoFiltro] = useState("");
  const [tipoFiltro, setTipoFiltro] = useState("");
  // Truncava em 50 sem aviso (backend já pagina desde 2026-07-20; a UI nunca
  // ganhou controle). Reseta pra 1 a cada troca de filtro — senão a página 3
  // de "Todas" pode não existir mais sob "Ativo".
  const [page, setPage] = useState(1);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Permissionario | null>(null);
  const [form, setForm] = useState<PermForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const listaQ = useQuery({
    queryKey: ["tr-permissionarios", situacaoFiltro, tipoFiltro, page],
    queryFn: () =>
      api.permissionarios.list({
        situacao: situacaoFiltro || undefined,
        tipo_servico: tipoFiltro || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  });
  const totalPages = Math.max(1, Math.ceil((listaQ.data?.total ?? 0) / PAGE_SIZE));
  const filtrando = situacaoFiltro !== "" || tipoFiltro !== "";

  function limparFiltros() {
    setSituacaoFiltro("");
    setTipoFiltro("");
    setPage(1);
  }

  const invalidate = () => qc.invalidateQueries({ queryKey: ["tr-permissionarios"] });

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing ? api.permissionarios.update(editing.id, data) : api.permissionarios.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Permissionário atualizado." : "Permissionário cadastrado.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const actionM = useMutation({
    mutationFn: ({ id, acao }: { id: number; acao: "inativar" | "reativar" | "suspender" }) =>
      acao === "inativar"
        ? api.permissionarios.inativar(id)
        : acao === "reativar"
          ? api.permissionarios.reativar(id)
          : api.permissionarios.suspender(id),
    onSuccess: () => {
      invalidate();
      toast.success("Situação atualizada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.permissionarios.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Permissionário excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Mesmas regras do backend (`PermissionarioCreate`), ditas no campo e com
  // o conserto — o servidor devolvia "cnh_validade é obrigatória…" no topo.
  const cnhDigitos = form.cnh_numero.replace(/\D/g, "");
  const v = useValidacao<"nome" | "cpf" | "email" | "cnh_numero" | "cnh_validade" | "data_validade_permissao">({
    nome: form.nome.trim() === "" ? "Informe o nome completo." : undefined,
    cpf:
      form.cpf.trim() === ""
        ? "Informe o CPF."
        : !mascaraCompleta("cpf", form.cpf)
          ? "CPF incompleto: use o formato 000.000.000-00."
          : undefined,
    email: erroEmail(form.email),
    cnh_numero:
      cnhDigitos !== "" && cnhDigitos.length !== 11 ? "A CNH tem 11 dígitos: confira o número." : undefined,
    cnh_validade:
      cnhDigitos !== "" && form.cnh_validade === "" ? "Informe a validade: é obrigatória quando há CNH." : undefined,
    data_validade_permissao: erroValidade(form.data_inicio_permissao, form.data_validade_permissao),
  });

  function set<K extends keyof PermForm>(key: K, value: PermForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }
  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    v.reiniciar();
    setDialogOpen(true);
  }
  function openEdit(p: Permissionario) {
    setEditing(p);
    setForm({
      nome: p.nome,
      cpf: p.cpf,
      rg: p.rg ?? "",
      data_nascimento: p.data_nascimento ?? "",
      telefone: p.telefone ?? "",
      email: p.email ?? "",
      cnh_numero: p.cnh_numero ?? "",
      cnh_categoria: p.cnh_categoria ?? "",
      cnh_validade: p.cnh_validade ?? "",
      tipo_servico: p.tipo_servico,
      numero_permissao: p.numero_permissao ?? "",
      data_inicio_permissao: p.data_inicio_permissao ?? "",
      data_validade_permissao: p.data_validade_permissao ?? "",
      situacao: p.situacao,
      observacoes: p.observacoes ?? "",
    });
    setErr(null);
    v.reiniciar();
    setDialogOpen(true);
  }
  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }
  function salvar() {
    setErr(null);
    if (!v.conferir()) return;
    const payload = {
      nome: form.nome.trim(),
      cpf: form.cpf.trim(),
      rg: nullify(form.rg),
      data_nascimento: nullify(form.data_nascimento),
      telefone: nullify(form.telefone),
      email: nullify(form.email),
      cnh_numero: nullify(form.cnh_numero),
      cnh_categoria: nullify(form.cnh_categoria),
      cnh_validade: nullify(form.cnh_validade),
      tipo_servico: form.tipo_servico,
      numero_permissao: nullify(form.numero_permissao),
      data_inicio_permissao: nullify(form.data_inicio_permissao),
      data_validade_permissao: nullify(form.data_validade_permissao),
      situacao: form.situacao,
      observacoes: nullify(form.observacoes),
    };
    saveM.mutate(payload);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={IdCard}
        title="Permissionários"
        description="Cadastro de permissionários do transporte regulado."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Permissionários" },
        ]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Novo permissionário
            </Button>
          ) : undefined
        }
      />

      <FilterBar ariaLabel="Filtros dos permissionários">
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
        {filtrando && (
          <FilterBar.Actions>
            <Button variant="ghost" onClick={limparFiltros}>
              Limpar
            </Button>
          </FilterBar.Actions>
        )}
      </FilterBar>

      {!listaQ.isLoading && (listaQ.data?.items.length ?? 0) === 0 ? (
        // Filtro sem resultado não é cadastro vazio: o botão de cadastrar
        // convidaria a duplicar quem já existe sob outra situação.
        <EmptyState
          icon={filtrando ? SearchX : Inbox}
          title={filtrando ? "Nenhum permissionário encontrado" : "Nenhum permissionário"}
          description={
            filtrando
              ? "Nenhum permissionário corresponde aos filtros aplicados."
              : "Cadastre o primeiro permissionário do transporte regulado."
          }
          action={
            filtrando ? (
              <Button variant="secondary" onClick={limparFiltros}>
                Limpar filtros
              </Button>
            ) : canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Cadastrar permissionário
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Nome</TH>
              <TH>CPF</TH>
              <TH>Tipo de serviço</TH>
              <TH>Permissão</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {listaQ.isLoading &&
              Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} cols={6} />)}
            {listaQ.data?.items.map((p) => (
              <TR key={p.id}>
                <TD>{p.nome}</TD>
                <TD className="whitespace-nowrap font-mono">{documentoParaExibir(p.cpf)}</TD>
                <TD>{TIPO_LABEL[p.tipo_servico] ?? p.tipo_servico}</TD>
                <TD className="whitespace-nowrap text-muted-foreground">
                  {p.numero_permissao ?? "—"}
                </TD>
                <TD>
                  <Badge intent={SIT_INTENT[p.situacao] ?? "neutral"}>
                    {SIT_LABEL[p.situacao] ?? p.situacao}
                  </Badge>
                </TD>
                <TD className="text-right">
                  {/* Reativar/Suspender vêm antes: são o que muda na linha
                      conforme a situação. Inativar e Excluir, destrutivas,
                      ficam no ⋯. */}
                  <AcoesDaLinha
                    acoes={[
                      { label: "Editar", icon: Pencil, onClick: () => openEdit(p), oculta: !canEdit },
                      {
                        label: "Reativar",
                        icon: RotateCcw,
                        onClick: () => actionM.mutate({ id: p.id, acao: "reativar" }),
                        oculta: !canEdit || p.situacao === "ativo",
                      },
                      {
                        label: "Suspender",
                        icon: PauseCircle,
                        onClick: () => actionM.mutate({ id: p.id, acao: "suspender" }),
                        oculta: !canEdit || p.situacao === "suspenso",
                      },
                      {
                        label: "Inativar",
                        icon: Ban,
                        perigo: true,
                        onClick: () => actionM.mutate({ id: p.id, acao: "inativar" }),
                        oculta: !canEdit || p.situacao === "inativo",
                      },
                      {
                        label: "Excluir",
                        icon: Trash2,
                        perigo: true,
                        disabled: deleteM.isPending,
                        oculta: !canDelete,
                        onClick: async () => {
                          const ok = await confirm({
                            title: "Excluir permissionário",
                            message: `Excluir o permissionário "${p.nome}"? Esta ação não pode ser desfeita.`,
                            confirmLabel: "Excluir",
                            intent: "danger",
                          });
                          if (ok) deleteM.mutate(p.id);
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
            {listaQ.data.total} permissionários — página {page} de {totalPages}
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
        title={editing ? `Editar permissionário — ${editing.nome}` : "Novo permissionário"}
        description={
          editing
            ? undefined
            : "Quem é, o que pode dirigir e qual permissão tem. Só nome e CPF são obrigatórios."
        }
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={salvar} loading={saveM.isPending}>
              {editing ? "Salvar alterações" : "Cadastrar permissionário"}
            </Button>
          </>
        }
      >
        <div ref={v.ref} className="space-y-5">
          <GrupoCampos titulo="Dados pessoais">
            <FormField label="Nome completo" required error={v.erro("nome")}>
              <Input
                id="nome"
                value={form.nome}
                onChange={(e) => set("nome", e.target.value)}
                onBlur={v.sair("nome")}
                placeholder="Ex.: Maria da Silva Souza"
                autoComplete="off"
              />
            </FormField>
            <GradeCampos colunas={3}>
              <FormField label="CPF" required error={v.erro("cpf")}>
                <InputMascarado
                  id="cpf"
                  mascara="cpf"
                  value={form.cpf}
                  onValueChange={(x) => set("cpf", x)}
                  onBlur={v.sair("cpf")}
                  placeholder="000.000.000-00"
                />
              </FormField>
              <FormField label="RG" opcional>
                <Input id="rg" value={form.rg} onChange={(e) => set("rg", e.target.value)} placeholder="Ex.: 2001234567" />
              </FormField>
              <FormField label="Data de nascimento" opcional>
                <Input
                  id="nasc"
                  type="date"
                  value={form.data_nascimento}
                  onChange={(e) => set("data_nascimento", e.target.value)}
                />
              </FormField>
            </GradeCampos>
            <GradeCampos>
              <FormField label="Telefone" opcional>
                <Input
                  id="tel"
                  type="tel"
                  value={form.telefone}
                  onChange={(e) => set("telefone", e.target.value)}
                  placeholder="Ex.: (88) 99999-0000"
                />
              </FormField>
              <FormField label="E-mail" opcional error={v.erro("email")}>
                <Input
                  id="email"
                  type="email"
                  value={form.email}
                  onChange={(e) => set("email", e.target.value)}
                  onBlur={v.sair("email")}
                  placeholder="Ex.: maria@email.com"
                />
              </FormField>
            </GradeCampos>
          </GrupoCampos>

          <GrupoCampos titulo="Serviço e permissão" descricao="O que a pessoa está autorizada a explorar.">
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
              <FormField label="Número da permissão" opcional hint="Como consta no termo de permissão.">
                <Input
                  id="numperm"
                  value={form.numero_permissao}
                  onChange={(e) => set("numero_permissao", e.target.value)}
                  placeholder="Ex.: TX-0123/2026"
                />
              </FormField>
            </GradeCampos>
            <GradeCampos>
              <FormField label="Início da permissão" opcional>
                <Input
                  id="ini"
                  type="date"
                  value={form.data_inicio_permissao}
                  onChange={(e) => set("data_inicio_permissao", e.target.value)}
                />
              </FormField>
              <FormField
                label="Validade da permissão"
                opcional
                error={v.erro("data_validade_permissao")}
                hint={dicaVigencia(
                  form.data_inicio_permissao,
                  form.data_validade_permissao,
                  "Último dia em que a permissão vale.",
                )}
              >
                <Input
                  id="val"
                  type="date"
                  value={form.data_validade_permissao}
                  onChange={(e) => set("data_validade_permissao", e.target.value)}
                  onBlur={v.sair("data_validade_permissao")}
                />
              </FormField>
            </GradeCampos>
            <FormField
              label="Situação"
              hint={
                editing
                  ? "Suspender e reativar também ficam nas ações da linha."
                  : "Cadastro novo entra como Pendente, salvo se mudar aqui."
              }
            >
              <Select
                id="sit"
                value={form.situacao}
                onChange={(e) => set("situacao", e.target.value as PermissionarioSituacao)}
              >
                {SITUACOES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </Select>
            </FormField>
          </GrupoCampos>

          <GrupoCampos titulo="CNH" descricao="Opcional. Se informar o número, informe também a validade.">
            <GradeCampos colunas={3}>
              <FormField label="Número da CNH" error={v.erro("cnh_numero")} hint="11 dígitos.">
                <Input
                  id="cnh"
                  inputMode="numeric"
                  maxLength={11}
                  className="font-mono tabular-nums"
                  value={form.cnh_numero}
                  onChange={(e) => set("cnh_numero", e.target.value.replace(/\D/g, ""))}
                  onBlur={v.sair("cnh_numero")}
                  placeholder="Ex.: 01234567890"
                />
              </FormField>
              <FormField label="Categoria">
                <Select id="cnhcat" value={form.cnh_categoria} onChange={(e) => set("cnh_categoria", e.target.value)}>
                  <option value="">Selecione…</option>
                  {CNH_CATS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField
                label="Validade da CNH"
                required={cnhDigitos !== ""}
                error={v.erro("cnh_validade")}
                hint={form.cnh_validade ? dicaVigencia("", form.cnh_validade, "") : undefined}
              >
                <Input
                  id="cnhval"
                  type="date"
                  value={form.cnh_validade}
                  onChange={(e) => set("cnh_validade", e.target.value)}
                  onBlur={v.sair("cnh_validade")}
                />
              </FormField>
            </GradeCampos>
          </GrupoCampos>

          <div className="border-t border-border pt-5">
            <FormField label="Observações" opcional>
              <Textarea
                id="obs"
                rows={2}
                value={form.observacoes}
                onChange={(e) => set("observacoes", e.target.value)}
                placeholder="Ex.: ponto de táxi habitual, pendências de documento"
              />
            </FormField>
          </div>

          {err && <Alert intent="danger">{err}</Alert>}
        </div>
      </Dialog>
    </div>
  );
}
