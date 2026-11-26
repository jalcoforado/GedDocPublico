"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Landmark, Pencil, Plus, Power, PowerOff } from "lucide-react";
import { useRef, useState } from "react";
import { flushSync } from "react-dom";

import { CampoCpf } from "@/components/admin/CampoCpf";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos, focarPrimeiroInvalido } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type AdminTenantCreated } from "@/lib/api";
import { emailValido } from "@/lib/mascaras";

export const PLANOS = ["basico", "profissional", "enterprise"];

/** O valor gravado é o código; a tela mostra o nome. */
export const PLANO_LABEL: Record<string, string> = {
  basico: "Básico",
  profissional: "Profissional",
  enterprise: "Enterprise",
};

export function TenantsAdmin() {
  const qc = useQueryClient();
  const toast = useToast();
  const [openCriar, setOpenCriar] = useState(false);

  const listQ = useQuery({ queryKey: ["admin-tenants"], queryFn: () => api.admin.tenants.list() });

  const toggleM = useMutation({
    mutationFn: ({ id, ativo }: { id: number; ativo: boolean }) =>
      ativo ? api.admin.tenants.desativar(id) : api.admin.tenants.ativar(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-tenants"] });
      toast.success("Status atualizado.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Landmark}
        title="Prefeituras"
        description="Os municípios atendidos pela plataforma: plano, limite de usuários e situação de cada um."
        actions={
          <Button onClick={() => setOpenCriar(true)}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Nova prefeitura
          </Button>
        }
      />

      <Table>
        <THead>
          <TR>
            <TH>Slug</TH>
            <TH>Nome</TH>
            <TH>Plano</TH>
            <TH className="text-right">Limite de usuários</TH>
            <TH>Situação</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {listQ.isLoading &&
            Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} cols={6} />)}
          {listQ.data && listQ.data.length === 0 && (
            <TR>
              <TD colSpan={6} className="p-0">
                <EmptyState
                  icon={Landmark}
                  title="Nenhuma prefeitura cadastrada"
                  description="Use “Nova prefeitura” para cadastrar o primeiro município."
                  className="border-0 bg-transparent"
                />
              </TD>
            </TR>
          )}
          {(listQ.data ?? []).map((t) => (
            <TR key={t.id}>
              <TD className="font-mono text-xs">{t.slug}</TD>
              <TD className="font-medium">{t.nome}</TD>
              <TD>{PLANO_LABEL[t.plano] ?? t.plano}</TD>
              <TD className="text-right tabular-nums">{t.limite_usuarios ?? "—"}</TD>
              <TD>
                <Badge intent={t.ativo ? "success" : "neutral"}>{t.ativo ? "Ativo" : "Inativo"}</Badge>
              </TD>
              <TD className="text-right">
                <AcoesDaLinha
                  acoes={[
                    { label: "Editar", icon: Pencil, href: `/admin/tenants/${t.id}` },
                    {
                      label: t.ativo ? "Desativar" : "Ativar",
                      icon: t.ativo ? PowerOff : Power,
                      // Desligar uma prefeitura derruba o acesso de todos os
                      // servidores dela: é a ação destrutiva da linha.
                      perigo: t.ativo,
                      disabled: toggleM.isPending,
                      onClick: () => toggleM.mutate({ id: t.id, ativo: t.ativo }),
                    },
                  ]}
                />
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <CriarTenantDialog
        open={openCriar}
        onClose={() => setOpenCriar(false)}
        onCreated={() => qc.invalidateQueries({ queryKey: ["admin-tenants"] })}
      />
    </div>
  );
}

const VAZIO_CRIAR = {
  slug: "",
  nome: "",
  admin_email: "",
  admin_nome: "",
  admin_cpf: "",
  plano: "basico",
  cnpj: "",
  limite_usuarios: "",
};

type FormCriar = typeof VAZIO_CRIAR;
type CampoCriar = "nome" | "slug" | "admin_nome" | "admin_email" | "admin_cpf";

/**
 * Slug sugerido a partir do nome: "Prefeitura Municipal de São Gonçalo do
 * Amarante" → "sao-goncalo-do-amarante". Só letras minúsculas, dígitos e
 * hífen — é subdomínio.
 */
export function slugDoNome(nome: string): string {
  return nome
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/^\s*prefeitura(\s+municipal)?(\s+d[eoa]s?)?\s+/, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50);
}

/** O que a pessoa digita no slug, já no formato de subdomínio. */
function limparSlug(v: string): string {
  return v
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[\s_]+/g, "-")
    .replace(/[^a-z0-9-]/g, "")
    .slice(0, 50);
}

/** Erros do cadastro — as mesmas regras do backend (`AdminTenantCreate`). */
function validarCriar(f: FormCriar): Partial<Record<CampoCriar, string>> {
  const e: Partial<Record<CampoCriar, string>> = {};
  if (!f.nome.trim()) e.nome = "Informe o nome da prefeitura.";
  if (!f.slug.trim()) e.slug = "Informe o endereço no sistema.";
  else if (f.slug.trim().length < 3) e.slug = "Use pelo menos 3 caracteres.";
  if (!f.admin_nome.trim()) e.admin_nome = "Informe o nome do administrador.";
  if (!f.admin_email.trim()) e.admin_email = "Informe o e-mail do administrador.";
  else if (!emailValido(f.admin_email))
    e.admin_email = "Confira o e-mail: use o formato nome@prefeitura.gov.br.";
  if (!f.admin_cpf) e.admin_cpf = "Informe o CPF do administrador.";
  else if (f.admin_cpf.length !== 11) {
    const faltam = 11 - f.admin_cpf.length;
    e.admin_cpf = `O CPF tem 11 dígitos — falta${faltam > 1 ? "m" : ""} ${faltam}.`;
  }
  return e;
}

/** Subtítulo de um bloco do formulário. */
function Bloco({
  titulo,
  dica,
  children,
}: {
  titulo: string;
  dica?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <div className="border-b border-border pb-1.5">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
          {titulo}
        </h3>
        {dica && <p className="mt-0.5 text-xs text-foreground-muted">{dica}</p>}
      </div>
      {children}
    </section>
  );
}

function CriarTenantDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState<FormCriar>(VAZIO_CRIAR);
  // Enquanto a pessoa não mexe no slug, ele acompanha o nome.
  const [slugEditado, setSlugEditado] = useState(false);
  const [tocados, setTocados] = useState<Set<CampoCriar>>(new Set());
  const [tentou, setTentou] = useState(false);
  const [criado, setCriado] = useState<AdminTenantCreated | null>(null);
  const [copiada, setCopiada] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  const erros = validarCriar(form);
  const erroVisivel = (c: CampoCriar) => (tentou || tocados.has(c) ? erros[c] : undefined);
  const tocar = (c: CampoCriar) => () => setTocados((s) => (s.has(c) ? s : new Set(s).add(c)));

  const set = (k: keyof FormCriar) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const m = useMutation({
    mutationFn: () =>
      api.admin.tenants.criar({
        slug: form.slug.trim(),
        nome: form.nome.trim(),
        admin_email: form.admin_email.trim(),
        admin_nome: form.admin_nome.trim(),
        admin_cpf: form.admin_cpf.trim(),
        plano: form.plano,
        cnpj: form.cnpj.trim() || null,
        limite_usuarios: form.limite_usuarios ? Number(form.limite_usuarios) : null,
      }),
    onSuccess: (res) => {
      setCriado(res);
      onCreated();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function criar(e?: React.FormEvent) {
    e?.preventDefault();
    if (Object.keys(erros).length > 0) {
      flushSync(() => setTentou(true));
      focarPrimeiroInvalido(formRef.current ?? document);
      return;
    }
    m.mutate();
  }

  function fechar() {
    setCriado(null);
    setForm(VAZIO_CRIAR);
    setSlugEditado(false);
    setTocados(new Set());
    setTentou(false);
    setCopiada(false);
    onClose();
  }

  return (
    <Dialog
      open={open}
      onClose={fechar}
      title={criado ? "Prefeitura criada" : "Nova prefeitura"}
      description={
        criado ? undefined : "O município e a pessoa que vai administrá-lo no sistema."
      }
      size="lg"
      footer={
        criado ? (
          <Button onClick={fechar}>Fechar</Button>
        ) : (
          <>
            <Button variant="ghost" onClick={fechar}>
              Cancelar
            </Button>
            <Button onClick={() => criar()} loading={m.isPending}>
              {m.isPending ? "Criando…" : "Criar prefeitura"}
            </Button>
          </>
        )
      }
    >
      {criado ? (
        <div className="space-y-3 text-sm">
          <p className="text-foreground">
            Prefeitura <b>{criado.tenant.nome}</b> (
            <span className="font-mono">{criado.tenant.slug}</span>) criada.
          </p>
          <div className="space-y-1">
            <div className="text-sm font-medium text-foreground">
              Senha temporária do administrador ({criado.admin_email})
            </div>
            <div className="flex items-center gap-2">
              <code className="flex-1 break-all rounded-md border border-border bg-surface-1 px-3 py-2 font-mono text-base text-foreground">
                {criado.senha_temporaria}
              </code>
              <Button
                variant="secondary"
                size="sm"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(criado.senha_temporaria);
                    setCopiada(true);
                    toast.success("Senha copiada.");
                  } catch {
                    toast.error("Não foi possível copiar — selecione e copie manualmente.");
                  }
                }}
              >
                <Copy className="h-4 w-4" aria-hidden="true" />
                {copiada ? "Copiada" : "Copiar"}
              </Button>
            </div>
          </div>
          <p className="rounded-md bg-warning-soft px-3 py-2 text-xs text-warning-soft-foreground">
            {criado.aviso}
          </p>
        </div>
      ) : (
        <form ref={formRef} onSubmit={criar} noValidate className="space-y-6">
          <Bloco titulo="Prefeitura">
            <FormField label="Nome" required error={erroVisivel("nome")}>
              <Input
                value={form.nome}
                onChange={(e) => {
                  const nome = e.target.value;
                  setForm((f) => ({ ...f, nome, slug: slugEditado ? f.slug : slugDoNome(nome) }));
                }}
                onBlur={tocar("nome")}
                placeholder="Ex.: Prefeitura Municipal de Fortaleza"
                autoFocus
              />
            </FormField>
            <GradeCampos>
              <FormField
                label="Endereço no sistema (slug)"
                required
                error={erroVisivel("slug")}
                hint={
                  slugEditado
                    ? "Vira o subdomínio e não muda depois. Letras minúsculas, números e hífen."
                    : "Sugerido a partir do nome. Vira o subdomínio e não muda depois."
                }
              >
                <Input
                  value={form.slug}
                  onChange={(e) => {
                    setSlugEditado(true);
                    setForm((f) => ({ ...f, slug: limparSlug(e.target.value) }));
                  }}
                  onBlur={tocar("slug")}
                  placeholder="Ex.: fortaleza"
                  className="font-mono"
                  autoCapitalize="none"
                  spellCheck={false}
                />
              </FormField>
              <FormField label="CNPJ" opcional>
                <Input
                  value={form.cnpj}
                  onChange={set("cnpj")}
                  maxLength={20}
                  placeholder="Ex.: 00.000.000/0001-00"
                />
              </FormField>
            </GradeCampos>
            <EscolhaSegmentada
              nome="plano-novo"
              titulo="Plano"
              valor={form.plano}
              onChange={(plano) => setForm((f) => ({ ...f, plano }))}
              opcoes={PLANOS.map((p) => ({ valor: p, rotulo: PLANO_LABEL[p] ?? p }))}
              moldura={false}
            />
            <FormField
              label="Limite de usuários"
              opcional
              hint="Em branco, sem limite definido."
              className="max-w-xs"
            >
              <CampoComUnidade
                type="number"
                min={0}
                sufixo="usuários"
                value={form.limite_usuarios}
                onChange={set("limite_usuarios")}
                placeholder="Ex.: 50"
              />
            </FormField>
          </Bloco>

          <Bloco
            titulo="Administrador da prefeitura"
            dica="Recebe uma senha temporária, mostrada uma única vez depois de criar."
          >
            <FormField label="Nome completo" required error={erroVisivel("admin_nome")}>
              <Input
                value={form.admin_nome}
                onChange={set("admin_nome")}
                onBlur={tocar("admin_nome")}
                placeholder="Ex.: Maria da Silva Souza"
              />
            </FormField>
            <GradeCampos>
              <FormField label="E-mail" required error={erroVisivel("admin_email")}>
                <Input
                  type="email"
                  inputMode="email"
                  value={form.admin_email}
                  onChange={set("admin_email")}
                  onBlur={tocar("admin_email")}
                  placeholder="Ex.: ti@fortaleza.ce.gov.br"
                />
              </FormField>
              <FormField label="CPF" required error={erroVisivel("admin_cpf")}>
                <CampoCpf
                  value={form.admin_cpf}
                  onValor={(admin_cpf) => setForm((f) => ({ ...f, admin_cpf }))}
                  onBlur={tocar("admin_cpf")}
                />
              </FormField>
            </GradeCampos>
          </Bloco>
        </form>
      )}
    </Dialog>
  );
}
