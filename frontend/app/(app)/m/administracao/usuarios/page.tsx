"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, KeyRound, Mail, Pencil, Plus, Search, Trash2, Users } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";

import { CampoCpf } from "@/components/admin/CampoCpf";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField, GradeCampos, focarPrimeiroInvalido } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { PasswordInput } from "@/components/ui/password-input";
import { Select } from "@/components/ui/select";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { UnidadePicker } from "@/components/UnidadePicker";
import {
  api,
  NIVEL_SIGILO_LABEL,
  type Grupo,
  type NivelSigilo,
  type ResetSenhaResponse,
  type UsuarioDetail,
  type UsuarioInput,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";
import { aplicarMascara, emailValido } from "@/lib/mascaras";
import { cn } from "@/lib/utils";

const NIVEIS_SIGILO: NivelSigilo[] = [
  "ostensivo",
  "interno",
  "reservado",
  "secreto",
  "ultrassecreto",
];

/** Piso do backend para senha temporária (`UsuarioCreate.senha`, min_length=4). */
const SENHA_TEMPORARIA_MINIMA = 4;

/** Acima disso a lista de grupos ganha uma caixa de busca. */
const GRUPOS_COM_BUSCA = 8;

type CampoValidado = "nome" | "email" | "cpf" | "senha";

/**
 * Erros do formulário de usuário. Mesmas regras do backend (`UsuarioBase`):
 * nome e e-mail obrigatórios, CPF com 11 dígitos, senha temporária com 4+
 * caracteres. O formato do e-mail só é conferido quando ele foi digitado
 * agora — um cadastro antigo com e-mail fora do padrão não pode travar a
 * edição do cargo.
 */
function validarUsuario(
  form: UsuarioInput,
  ctx: { emailOriginal: string; exigeSenha: boolean },
): Partial<Record<CampoValidado, string>> {
  const erros: Partial<Record<CampoValidado, string>> = {};
  if (!form.nome.trim()) erros.nome = "Informe o nome completo.";
  const email = form.email.trim();
  if (!email) erros.email = "Informe o e-mail.";
  else if (email !== ctx.emailOriginal && !emailValido(email))
    erros.email = "Confira o e-mail: use o formato nome@prefeitura.gov.br.";
  const cpf = form.cpf ?? "";
  if (!cpf) erros.cpf = "Informe o CPF.";
  else if (cpf.length !== 11)
    erros.cpf = `O CPF tem 11 dígitos — falta${11 - cpf.length > 1 ? "m" : ""} ${11 - cpf.length}.`;
  const senha = form.senha ?? "";
  if (ctx.exigeSenha && !senha)
    erros.senha = "Defina a senha temporária que você vai repassar ao usuário.";
  else if (senha && senha.length < SENHA_TEMPORARIA_MINIMA)
    erros.senha = `Use pelo menos ${SENHA_TEMPORARIA_MINIMA} caracteres.`;
  return erros;
}

const EMPTY_FORM: UsuarioInput = {
  nome: "",
  email: "",
  cpf: "",
  id_unidade_trabalho: null,
  cargo: "",
  ativo: true,
  senha: "",
  grupos: [],
};

export default function UsuariosPage() {
  const { can, perms } = useAuth();
  const contaPorEmail = useBranding()?.conta_por_email ?? false;
  const isSuper = perms?.is_super_usuario ?? false;
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<UsuarioDetail | null>(null);
  const [form, setForm] = useState<UsuarioInput>(EMPTY_FORM);
  const [err, setErr] = useState<string | null>(null);
  // Erro só depois da tentativa: campo tocado (saiu dele) ou envio tentado.
  const [tocados, setTocados] = useState<Set<CampoValidado>>(new Set());
  const [tentouEnviar, setTentouEnviar] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  const [resetResult, setResetResult] = useState<ResetSenhaResponse | null>(null);
  const [resetNome, setResetNome] = useState("");
  const [senhaCopiada, setSenhaCopiada] = useState(false);

  const usuariosQ = useQuery({
    queryKey: ["usuarios", page, q],
    queryFn: () => api.usuarios.list({ page, page_size: 20, q: q || undefined }),
  });
  const gruposQ = useQuery({ queryKey: ["grupos"], queryFn: api.grupos.list });

  const exigeSenha = !editing && !contaPorEmail;
  const erros = validarUsuario(form, { emailOriginal: editing?.email ?? "", exigeSenha });
  const erroVisivel = (c: CampoValidado) =>
    tentouEnviar || tocados.has(c) ? erros[c] : undefined;
  const tocar = (c: CampoValidado) => () =>
    setTocados((s) => (s.has(c) ? s : new Set(s).add(c)));

  const createM = useMutation({
    mutationFn: (data: UsuarioInput) => api.usuarios.create(data),
    onSuccess: (criado) => {
      qc.invalidateQueries({ queryKey: ["usuarios"] });
      toast.success(
        contaPorEmail ? `Usuário criado. Enviamos o convite para ${criado.email}.` : "Usuário criado.",
      );
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const updateM = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<UsuarioInput> }) =>
      api.usuarios.update(id, data),
    onSuccess: async (_updated, { id, data }) => {
      if (data.grupos) await api.usuarios.setGrupos(id, data.grupos);
      qc.invalidateQueries({ queryKey: ["usuarios"] });
      toast.success("Alterações salvas.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.usuarios.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["usuarios"] });
      toast.success("Usuário excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const conviteM = useMutation({
    mutationFn: (u: { id: number; email: string }) => api.usuarios.reenviarConvite(u.id),
    onSuccess: (_r, u) => toast.success(`Convite reenviado para ${u.email}.`),
    onError: (e: Error) => toast.error(e.message),
  });
  const resetM = useMutation({
    mutationFn: (id: number) => api.usuarios.resetarSenha(id),
    onSuccess: (res) => {
      setSenhaCopiada(false);
      setResetResult(res);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function limparValidacao() {
    setErr(null);
    setTocados(new Set());
    setTentouEnviar(false);
  }

  function openNew() {
    setEditing(null);
    setForm(EMPTY_FORM);
    limparValidacao();
    setDialogOpen(true);
  }

  async function openEdit(id: number) {
    limparValidacao();
    const detail = await api.usuarios.get(id);
    setEditing(detail);
    setForm({
      nome: detail.nome,
      email: detail.email,
      cpf: detail.cpf,
      id_unidade_trabalho: detail.id_unidade_trabalho,
      cargo: detail.cargo ?? "",
      ativo: detail.ativo,
      senha: "",
      grupos: detail.grupos,
      nivel_acesso_sigilo: detail.nivel_acesso_sigilo,
    });
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY_FORM);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (Object.keys(erros).length > 0) {
      // flushSync: o aria-invalid precisa estar no DOM antes de procurar o
      // primeiro inválido para focar.
      flushSync(() => setTentouEnviar(true));
      focarPrimeiroInvalido(formRef.current ?? document);
      return;
    }
    if (editing) {
      const payload: Partial<UsuarioInput> = { ...form };
      if (!payload.senha) delete payload.senha;
      // Só super-usuário altera credencial de sigilo (backend bloqueia com 403).
      if (!isSuper) delete payload.nivel_acesso_sigilo;
      updateM.mutate({ id: editing.id, data: payload });
    } else if (contaPorEmail) {
      // 0137 — sem senha: o backend cria por convite e manda o e-mail; a
      // própria pessoa escolhe a senha ao ativar a conta.
      const { senha: _semSenha, ...semSenha } = form;
      createM.mutate(semSenha);
    } else {
      // Conta por e-mail desligada: o admin define a senha temporária.
      createM.mutate(form);
    }
  }

  function toggleGrupo(id: number) {
    setForm((f) => {
      const has = f.grupos?.includes(id);
      return {
        ...f,
        grupos: has ? f.grupos!.filter((x) => x !== id) : [...(f.grupos ?? []), id],
      };
    });
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Users}
        title="Usuários"
        description="Quem acessa o sistema, em que unidade trabalha e de quais grupos faz parte."
        actions={
          can("usuario", "inserir") && (
            <Button onClick={openNew}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Novo usuário
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
          placeholder="Buscar por nome ou e-mail…"
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
            <TH>E-mail</TH>
            <TH>CPF</TH>
            <TH>Situação</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {usuariosQ.isLoading &&
            Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={5} />)}
          {!usuariosQ.isLoading && usuariosQ.data?.items.length === 0 && (
            <TR>
              <TD colSpan={5} className="p-0">
                <EmptyState
                  icon={Users}
                  title={q ? "Nenhum usuário encontrado" : "Nenhum usuário cadastrado"}
                  description={
                    q
                      ? "Confira o nome ou o e-mail digitado na busca."
                      : "Use “Novo usuário” para dar acesso ao primeiro servidor."
                  }
                  className="border-0 bg-transparent"
                />
              </TD>
            </TR>
          )}
          {usuariosQ.data?.items.map((u) => (
            <TR key={u.id}>
              <TD className="font-medium">{u.nome}</TD>
              <TD className="text-foreground-muted">{u.email}</TD>
              {/* Gravado só com dígitos; a máscara é só da tela. */}
              <TD className="whitespace-nowrap tabular-nums">
                {u.cpf ? aplicarMascara("cpf", u.cpf).valor : "—"}
              </TD>
              <TD>
                {u.email_verificado_em === null ? (
                  <Badge intent="warning" title="O convite foi enviado e ainda não foi aceito.">
                    Convite pendente
                  </Badge>
                ) : u.ativo ? (
                  <Badge intent="success">Ativo</Badge>
                ) : (
                  <Badge intent="neutral">Inativo</Badge>
                )}
              </TD>
              <TD className="text-right">
                <AcoesDaLinha
                  acoes={[
                    {
                      label: "Editar",
                      icon: Pencil,
                      oculta: !can("usuario", "atualizar"),
                      onClick: () => openEdit(u.id),
                    },
                    {
                      label: "Reenviar convite",
                      icon: Mail,
                      oculta: !(
                        can("usuario", "atualizar") &&
                        contaPorEmail &&
                        u.email_verificado_em === null
                      ),
                      disabled: conviteM.isPending,
                      onClick: () => conviteM.mutate({ id: u.id, email: u.email }),
                    },
                    // Sem e-mail, o "Resetar senha" é a saída de quem ficou com
                    // convite pendente: o reset também ativa a conta.
                    {
                      label: "Resetar senha",
                      icon: KeyRound,
                      oculta: !(
                        can("usuario", "atualizar") &&
                        (u.email_verificado_em !== null || !contaPorEmail)
                      ),
                      disabled: resetM.isPending,
                      onClick: async () => {
                        const ok = await confirm({
                          title: "Resetar senha",
                          message: `Gerar uma senha temporária para ${u.nome}? A senha atual deixa de funcionar na hora. A nova aparece uma única vez, para você repassar.`,
                          confirmLabel: "Gerar senha temporária",
                        });
                        if (ok) {
                          setResetNome(u.nome);
                          resetM.mutate(u.id);
                        }
                      },
                    },
                    {
                      label: "Excluir",
                      icon: Trash2,
                      perigo: true,
                      oculta: !can("usuario", "excluir"),
                      onClick: async () => {
                        const ok = await confirm({
                          title: "Excluir usuário",
                          message: `Excluir ${u.nome}? Esta ação não pode ser desfeita.`,
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

      {usuariosQ.data && (
        <div className="flex items-center justify-between text-sm text-foreground-muted">
          <span>
            {usuariosQ.data.total} usuários — página {page}
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
              disabled={page * 20 >= usuariosQ.data.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Próxima
            </Button>
          </div>
        </div>
      )}


      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? "Editar usuário" : "Novo usuário"}
        description={
          editing
            ? editing.nome
            : "Quem é, onde trabalha e o que pode fazer no sistema."
        }
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={submit} loading={createM.isPending || updateM.isPending}>
              {createM.isPending || updateM.isPending
                ? "Salvando…"
                : editing
                  ? "Salvar alterações"
                  : contaPorEmail
                    ? "Cadastrar e enviar convite"
                    : "Cadastrar usuário"}
            </Button>
          </>
        }
      >
        <form ref={formRef} onSubmit={submit} noValidate className="space-y-6">
          {err && (
            <div
              role="alert"
              className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              {err}
            </div>
          )}

          <BlocoFormulario titulo="Quem é">
            <FormField label="Nome completo" required error={erroVisivel("nome")}>
              <Input
                value={form.nome}
                onChange={(e) => setForm({ ...form, nome: e.target.value })}
                onBlur={tocar("nome")}
                autoComplete="off"
                placeholder="Ex.: Maria da Silva Souza"
              />
            </FormField>
            <GradeCampos>
              <FormField
                label="E-mail"
                required
                error={erroVisivel("email")}
                hint={
                  !editing && contaPorEmail
                    ? "O convite de acesso vai para este endereço."
                    : "É com ele que a pessoa entra no sistema."
                }
              >
                <Input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  onBlur={tocar("email")}
                  autoComplete="off"
                  inputMode="email"
                  placeholder="Ex.: maria.souza@prefeitura.gov.br"
                />
              </FormField>
              <FormField label="CPF" required error={erroVisivel("cpf")}>
                <CampoCpf
                  value={form.cpf}
                  onValor={(cpf) => setForm({ ...form, cpf })}
                  onBlur={tocar("cpf")}
                />
              </FormField>
            </GradeCampos>
          </BlocoFormulario>

          <BlocoFormulario titulo="Onde trabalha">
            <GradeCampos>
              <FormField
                label="Unidade de trabalho"
                opcional
                hint="Onde a pessoa está lotada: é a caixa em que ela recebe os processos."
              >
                <UnidadePicker
                  value={form.id_unidade_trabalho ?? null}
                  onChange={(v) => setForm({ ...form, id_unidade_trabalho: v })}
                  placeholder="Buscar pelo nome ou pela sigla"
                />
              </FormField>
              <FormField label="Cargo" opcional>
                <Input
                  value={form.cargo ?? ""}
                  onChange={(e) => setForm({ ...form, cargo: e.target.value })}
                  placeholder="Ex.: Assistente administrativo"
                />
              </FormField>
            </GradeCampos>
          </BlocoFormulario>

          <BlocoFormulario titulo="Acesso">
            <EscolhaGrupos
              grupos={gruposQ.data ?? []}
              carregando={gruposQ.isLoading}
              selecionados={form.grupos ?? []}
              onAlternar={toggleGrupo}
            />

            {editing && isSuper && (
              <FormField
                label="Credencial de sigilo"
                hint="Até qual grau de sigilo este servidor pode ver processos e documentos."
              >
                <Select
                  value={form.nivel_acesso_sigilo ?? "interno"}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      nivel_acesso_sigilo: e.target.value as NivelSigilo,
                    })
                  }
                >
                  {NIVEIS_SIGILO.map((n) => (
                    <option key={n} value={n}>
                      {NIVEL_SIGILO_LABEL[n]}
                    </option>
                  ))}
                </Select>
              </FormField>
            )}

            {!editing && contaPorEmail ? (
              // Conta por e-mail ligada: sem senha no cadastro (0137). O
              // backend cria por convite e manda o e-mail.
              <div className="flex items-start gap-3 rounded-lg border border-border bg-surface-1 px-3 py-2.5">
                <Mail className="mt-0.5 h-4 w-4 shrink-0 text-foreground-muted" aria-hidden="true" />
                <div className="text-sm">
                  <p className="font-medium text-foreground">Acesso por convite</p>
                  <p className="mt-0.5 text-xs text-foreground-muted">
                    A pessoa recebe um convite no e-mail acima e escolhe a própria senha ao
                    ativar a conta. Até lá, aparece na lista como &quot;Convite pendente&quot;.
                  </p>
                </div>
              </div>
            ) : (
              // Conta por e-mail desligada (o padrão): no cadastro o admin
              // define a senha temporária. Na edição o campo é opcional.
              <FormField
                label={editing ? "Nova senha temporária" : "Senha temporária"}
                required={!editing}
                opcional={!!editing}
                error={erroVisivel("senha")}
                hint={
                  editing
                    ? "Deixe em branco para manter a senha atual. Se preencher, o usuário será obrigado a alterá-la no próximo acesso."
                    : "Repasse ao usuário por um canal seguro. Ele será obrigado a alterá-la no próximo acesso."
                }
              >
                <PasswordInput
                  value={form.senha ?? ""}
                  onChange={(e) => setForm({ ...form, senha: e.target.value })}
                  onBlur={tocar("senha")}
                  autoComplete="new-password"
                />
              </FormField>
            )}

            <div className="flex items-start gap-3 rounded-lg border border-border px-3 py-2.5">
              <Checkbox
                id="usuario-ativo"
                checked={form.ativo}
                onChange={(e) => setForm({ ...form, ativo: e.target.checked })}
                aria-describedby="usuario-ativo-dica"
                className="mt-0.5"
              />
              <div>
                <label htmlFor="usuario-ativo" className="text-sm font-medium text-foreground">
                  Usuário ativo
                </label>
                <p id="usuario-ativo-dica" className="text-xs text-foreground-muted">
                  {form.ativo
                    ? "Pode entrar no sistema."
                    : "Não consegue entrar. O cadastro e o histórico continuam guardados."}
                </p>
              </div>
            </div>
          </BlocoFormulario>
        </form>
      </Dialog>

      <Dialog
        open={resetResult !== null}
        onClose={() => setResetResult(null)}
        title="Senha temporária gerada"
        description={resetNome ? `Para ${resetNome}.` : undefined}
        footer={<Button onClick={() => setResetResult(null)}>Fechar</Button>}
      >
        {resetResult && (
          <div className="space-y-3">
            <p className="text-sm text-foreground-muted">{resetResult.aviso}</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 break-all rounded-md border border-border bg-surface-1 px-3 py-2 font-mono text-base">
                {resetResult.senha_temporaria}
              </code>
              <Button
                variant="secondary"
                size="sm"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(resetResult.senha_temporaria);
                    setSenhaCopiada(true);
                    toast.success("Senha copiada.");
                  } catch {
                    toast.error("Não foi possível copiar — selecione e copie manualmente.");
                  }
                }}
              >
                <Copy className="h-4 w-4" aria-hidden="true" />
                {senhaCopiada ? "Copiada" : "Copiar"}
              </Button>
            </div>
            <ol className="list-decimal space-y-0.5 pl-5 text-xs text-foreground-muted">
              <li>Copie a senha.</li>
              <li>Repasse ao usuário por um canal seguro (pessoalmente ou por telefone).</li>
              <li>No primeiro acesso, o sistema pede que ele escolha uma senha nova.</li>
            </ol>
            <p
              role="alert"
              className="rounded-md bg-warning-soft px-3 py-2 text-xs text-warning-soft-foreground"
            >
              Anote ou copie agora: esta senha não será exibida novamente.
            </p>
          </div>
        )}
      </Dialog>
    </div>
  );
}

/** Subtítulo de um bloco do formulário (quem é → onde trabalha → acesso). */
function BlocoFormulario({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <h3 className="border-b border-border pb-1.5 text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
        {titulo}
      </h3>
      {children}
    </section>
  );
}

/** Minúsculas e sem acento: "saude" acha "Saúde". */
function semAcento(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/**
 * Grupos do usuário: lista de marcar com a contagem do que já foi escolhido
 * e, quando a lista é longa, uma busca — numa prefeitura com dezenas de
 * grupos, rolar uma caixa de 40 linhas atrás de um nome era o gargalo.
 */
function EscolhaGrupos({
  grupos,
  carregando,
  selecionados,
  onAlternar,
}: {
  grupos: Grupo[];
  carregando: boolean;
  selecionados: number[];
  onAlternar: (id: number) => void;
}) {
  const [busca, setBusca] = useState("");
  const ordenados = useMemo(
    () => [...grupos].sort((a, b) => a.grupo.localeCompare(b.grupo, "pt-BR")),
    [grupos],
  );
  const termo = semAcento(busca.trim());
  const visiveis = termo ? ordenados.filter((g) => semAcento(g.grupo).includes(termo)) : ordenados;
  const n = selecionados.length;

  return (
    <fieldset aria-describedby="grupos-dica">
      <legend className="mb-1 flex w-full items-baseline justify-between gap-3 text-sm font-medium text-foreground">
        Grupos
        <span className="text-xs font-normal text-foreground-muted" aria-live="polite">
          {n === 0 ? "nenhum marcado" : n === 1 ? "1 marcado" : `${n} marcados`}
        </span>
      </legend>
      <p id="grupos-dica" className="mb-2 text-xs text-foreground-muted">
        O grupo decide o que a pessoa pode fazer. As permissões de cada grupo ficam em Grupos
        &amp; Permissões.
      </p>
      {grupos.length > GRUPOS_COM_BUSCA && (
        <div className="relative mb-2">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-subtle"
            aria-hidden="true"
          />
          <Input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Filtrar grupos…"
            aria-label="Filtrar grupos"
            className="pl-9"
          />
        </div>
      )}
      <div className="grid max-h-48 grid-cols-1 gap-0.5 overflow-y-auto rounded-md border border-border p-1.5 sm:grid-cols-2">
        {carregando && (
          <p className="px-2 py-1.5 text-sm text-foreground-muted">Carregando grupos…</p>
        )}
        {!carregando && grupos.length === 0 && (
          <p className="px-2 py-1.5 text-sm text-foreground-muted">Nenhum grupo cadastrado ainda.</p>
        )}
        {!carregando && grupos.length > 0 && visiveis.length === 0 && (
          <p className="px-2 py-1.5 text-sm text-foreground-muted">Nenhum grupo com esse nome.</p>
        )}
        {visiveis.map((g) => {
          const marcado = selecionados.includes(g.id);
          return (
            <label
              key={g.id}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm transition-colors duration-fast hover:bg-muted",
                marcado && "font-medium text-foreground",
              )}
            >
              <Checkbox checked={marcado} onChange={() => onAlternar(g.id)} />
              {g.grupo}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
