"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  CheckCircle2,
  Circle,
  Hash,
  ListChecks,
  Loader2,
  Settings,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  tenantsApi,
  type NupConfigUpdate,
  type TenantInstitucionalUpdate,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

// Deep-links do checklist para áreas já existentes (só as que têm página).
// NAO e um `href` por linha: e um MAPA. Varredura por linha contendo "href"
// nao alcanca isto — foi assim que quase ficou apontando para a URL antiga
// na F3. `assuntos` e `tipos_processo` pertencem ao protocolo.
const CHECKLIST_HREF: Record<string, string> = {
  unidades: "/m/administracao/unidades-trabalho",
  usuarios: "/m/administracao/usuarios",
  grupos: "/m/administracao/grupos",
  assuntos: "/m/protocolo/assuntos",
  tipos_processo: "/m/protocolo/tipos-processo",
};

interface InstitucionalForm {
  nome: string;
  sigla: string;
  email_institucional: string;
  telefone_institucional: string;
  endereco: string;
  site_oficial: string;
  horario_atendimento: string;
  texto_boas_vindas_portal: string;
  logo_url: string;
  cor_primaria: string;
  id_unidade_padrao: number | null;
}

const EMPTY_INSTITUCIONAL: InstitucionalForm = {
  nome: "",
  sigla: "",
  email_institucional: "",
  telefone_institucional: "",
  endereco: "",
  site_oficial: "",
  horario_atendimento: "",
  texto_boas_vindas_portal: "",
  logo_url: "",
  cor_primaria: "",
  id_unidade_padrao: null,
};

/** "" → null para limpar campos opcionais; mantém o texto quando preenchido. */
function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

export default function ConfiguracoesPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const canEdit = can("configuracao", "atualizar");

  const tenantQ = useQuery({
    queryKey: ["tenant-me"],
    queryFn: () => tenantsApi.me(),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Settings}
        title="Configurações do tenant"
        description="Identidade institucional, configuração inicial e ajustes administrativos da prefeitura."
      />

      <OnboardingCard />

      <InstitucionalSection canEdit={canEdit} />

      <NupSection canEdit={canEdit} />

      <section className="rounded-xl border border-border bg-card shadow-xs">
        <header className="flex items-start gap-3 border-b border-border px-5 py-4">
          <span
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-3 text-foreground-muted"
            aria-hidden="true"
          >
            <Building2 className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold tracking-tight">Tenant atual</h2>
            <p className="mt-0.5 text-xs text-foreground-muted">
              Identificadores de plataforma (somente leitura — alteração via Admin SaaS).
            </p>
          </div>
        </header>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 p-5 text-sm md:grid-cols-3">
          <KV label="ID" value={String(tenantQ.data?.id ?? "—")} mono />
          <KV label="Slug" value={tenantQ.data?.slug ?? "—"} mono />
          <KV label="Plano" value={tenantQ.data?.plano ?? "—"} />
        </div>
      </section>
    </div>
  );
}

// ===== Checklist de onboarding ===============================================

function OnboardingCard() {
  const onboardingQ = useQuery({
    queryKey: ["tenant-onboarding"],
    queryFn: () => tenantsApi.onboarding(),
  });

  return (
    <section className="rounded-xl border border-border bg-card shadow-xs">
      <header className="flex items-start gap-3 border-b border-border px-5 py-4">
        <span
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand/8 text-brand"
          aria-hidden="true"
        >
          <ListChecks className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold tracking-tight">
              Checklist de configuração inicial
            </h2>
            {onboardingQ.data && (
              <Badge intent={onboardingQ.data.pendentes === 0 ? "success" : "neutral"}>
                {onboardingQ.data.concluidos}/{onboardingQ.data.total} concluídos
              </Badge>
            )}
          </div>
          <p className="mt-0.5 text-xs text-foreground-muted">
            Passos sugeridos para deixar o tenant pronto para uso. Calculado a
            partir do estado atual.
          </p>
        </div>
      </header>

      <div className="p-5">
        {onboardingQ.isLoading && (
          <p className="text-sm text-foreground-muted">
            <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />
            Carregando…
          </p>
        )}
        {onboardingQ.data && (
          <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {onboardingQ.data.itens.map((item) => {
              const href = CHECKLIST_HREF[item.chave];
              const done = item.concluido === true;
              return (
                <li
                  key={item.chave}
                  className="flex items-center gap-2 rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm"
                >
                  {done ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-success" aria-hidden="true" />
                  ) : (
                    <Circle className="h-4 w-4 shrink-0 text-foreground-subtle" aria-hidden="true" />
                  )}
                  <span className={cn("flex-1", done && "text-foreground-muted")}>
                    {item.rotulo}
                  </span>
                  {!done && href && (
                    <Link
                      href={href}
                      className="shrink-0 text-xs font-medium text-brand hover:underline"
                    >
                      Configurar
                    </Link>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}

// ===== Identidade institucional ==============================================

function InstitucionalSection({ canEdit }: { canEdit: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const tenantQ = useQuery({ queryKey: ["tenant-me"], queryFn: () => tenantsApi.me() });
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });

  const [form, setForm] = useState<InstitucionalForm>(EMPTY_INSTITUCIONAL);

  useEffect(() => {
    const t = tenantQ.data;
    if (t) {
      setForm({
        nome: t.nome ?? "",
        sigla: t.sigla ?? "",
        email_institucional: t.email_institucional ?? "",
        telefone_institucional: t.telefone_institucional ?? "",
        endereco: t.endereco ?? "",
        site_oficial: t.site_oficial ?? "",
        horario_atendimento: t.horario_atendimento ?? "",
        texto_boas_vindas_portal: t.texto_boas_vindas_portal ?? "",
        logo_url: t.logo_url ?? "",
        cor_primaria: t.cor_primaria ?? "",
        id_unidade_padrao: t.id_unidade_padrao ?? null,
      });
    }
  }, [tenantQ.data]);

  const saveM = useMutation({
    mutationFn: (payload: TenantInstitucionalUpdate) =>
      tenantsApi.updateInstitucional(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenant-me"] });
      qc.invalidateQueries({ queryKey: ["tenant-onboarding"] });
      toast.success("Dados institucionais salvos.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof InstitucionalForm>(key: K, value: InstitucionalForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function salvar() {
    saveM.mutate({
      nome: form.nome.trim(),
      sigla: nullify(form.sigla),
      email_institucional: nullify(form.email_institucional),
      telefone_institucional: nullify(form.telefone_institucional),
      endereco: nullify(form.endereco),
      site_oficial: nullify(form.site_oficial),
      horario_atendimento: nullify(form.horario_atendimento),
      texto_boas_vindas_portal: nullify(form.texto_boas_vindas_portal),
      logo_url: nullify(form.logo_url),
      cor_primaria: nullify(form.cor_primaria),
      id_unidade_padrao: form.id_unidade_padrao,
    });
  }

  return (
    <section id="identidade" className="rounded-xl border border-border bg-card shadow-xs">
      <header className="flex items-start gap-3 border-b border-border px-5 py-4">
        <span
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand/8 text-brand"
          aria-hidden="true"
        >
          <Building2 className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold tracking-tight">Identidade institucional</h2>
          <p className="mt-0.5 text-xs text-foreground-muted">
            Dados de contato e apresentação da prefeitura, usados no portal do
            cidadão e em documentos.
          </p>
        </div>
      </header>

      <div className="space-y-5 p-5">
        {tenantQ.isLoading && (
          <p className="text-sm text-foreground-muted">
            <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />
            Carregando…
          </p>
        )}

        {tenantQ.data && (
          <>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="md:col-span-2">
                <Label htmlFor="nome" required>
                  Nome da prefeitura
                </Label>
                <Input
                  id="nome"
                  value={form.nome}
                  onChange={(e) => set("nome", e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div>
                <Label htmlFor="sigla">Sigla</Label>
                <Input
                  id="sigla"
                  value={form.sigla}
                  maxLength={20}
                  onChange={(e) => set("sigla", e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div>
                <Label htmlFor="email-inst">E-mail institucional</Label>
                <Input
                  id="email-inst"
                  type="email"
                  inputMode="email"
                  value={form.email_institucional}
                  onChange={(e) => set("email_institucional", e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div>
                <Label htmlFor="telefone-inst">Telefone institucional</Label>
                <Input
                  id="telefone-inst"
                  inputMode="tel"
                  value={form.telefone_institucional}
                  onChange={(e) => set("telefone_institucional", e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div>
                <Label htmlFor="site">Site oficial</Label>
                <Input
                  id="site"
                  value={form.site_oficial}
                  placeholder="https://"
                  onChange={(e) => set("site_oficial", e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div className="md:col-span-2">
                <Label htmlFor="endereco">Endereço</Label>
                <Textarea
                  id="endereco"
                  rows={2}
                  value={form.endereco}
                  onChange={(e) => set("endereco", e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div>
                <Label htmlFor="horario">Horário de atendimento</Label>
                <Input
                  id="horario"
                  value={form.horario_atendimento}
                  placeholder="Seg a Sex, 8h–17h"
                  onChange={(e) => set("horario_atendimento", e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div>
                <Label htmlFor="unidade-padrao">Unidade padrão</Label>
                <Select
                  id="unidade-padrao"
                  value={form.id_unidade_padrao ?? ""}
                  onChange={(e) =>
                    set(
                      "id_unidade_padrao",
                      e.target.value ? Number(e.target.value) : null,
                    )
                  }
                  disabled={!canEdit}
                >
                  <option value="">—</option>
                  {unidadesQ.data?.items.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.unidade_trabalho}
                    </option>
                  ))}
                </Select>
                <p className="mt-1 text-xs text-foreground-muted">
                  Unidade sugerida como destino inicial de novos protocolos.
                </p>
              </div>
              <div>
                <Label htmlFor="logo-url">Logo (URL)</Label>
                <Input
                  id="logo-url"
                  value={form.logo_url}
                  placeholder="https://…/logo.png"
                  onChange={(e) => set("logo_url", e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div>
                <Label htmlFor="cor">Cor primária</Label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    aria-label="Cor primária"
                    value={/^#[0-9a-fA-F]{6}$/.test(form.cor_primaria) ? form.cor_primaria : "#1e3a8a"}
                    onChange={(e) => set("cor_primaria", e.target.value)}
                    disabled={!canEdit}
                    className="h-10 w-12 shrink-0 cursor-pointer rounded-md border border-border bg-card disabled:cursor-not-allowed disabled:opacity-50"
                  />
                  <Input
                    id="cor"
                    value={form.cor_primaria}
                    placeholder="#1e3a8a"
                    maxLength={7}
                    onChange={(e) => set("cor_primaria", e.target.value)}
                    disabled={!canEdit}
                    className="font-mono"
                  />
                </div>
              </div>
              <div className="md:col-span-2">
                <Label htmlFor="boas-vindas">Mensagem de boas-vindas do portal</Label>
                <Textarea
                  id="boas-vindas"
                  rows={3}
                  value={form.texto_boas_vindas_portal}
                  onChange={(e) => set("texto_boas_vindas_portal", e.target.value)}
                  disabled={!canEdit}
                />
                <p className="mt-1 text-xs text-foreground-muted">
                  Exibida aos cidadãos no portal público.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 pt-1">
              <Button onClick={salvar} disabled={!canEdit || saveM.isPending}>
                {saveM.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                Salvar dados institucionais
              </Button>
              {!canEdit && (
                <span className="text-xs text-foreground-muted">
                  Você não tem permissão para editar — somente leitura.
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

// ===== NUP federal (Fase P2) =================================================

function NupSection({ canEdit }: { canEdit: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const tenantQ = useQuery({ queryKey: ["tenant-me"], queryFn: () => tenantsApi.me() });

  const [codigo, setCodigo] = useState("");
  const [flag, setFlag] = useState(false);

  useEffect(() => {
    if (tenantQ.data) {
      setCodigo(tenantQ.data.codigo_orgao_nup ?? "");
      setFlag(tenantQ.data.usar_nup_federal);
    }
  }, [tenantQ.data]);

  const saveM = useMutation({
    mutationFn: (payload: NupConfigUpdate) => tenantsApi.updateNupConfig(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenant-me"] });
      toast.success("Configuração de NUP salva.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const dirty =
    tenantQ.data &&
    (codigo !== (tenantQ.data.codigo_orgao_nup ?? "") ||
      flag !== tenantQ.data.usar_nup_federal);

  const codigoValido = /^[0-9]{5}$/.test(codigo);
  const podeAtivar = codigoValido;

  function salvar() {
    saveM.mutate({
      codigo_orgao_nup: codigo.trim() === "" ? null : codigo,
      usar_nup_federal: flag,
    });
  }

  return (
    <section className="rounded-xl border border-border bg-card shadow-xs">
      <header className="flex items-start gap-3 border-b border-border px-5 py-4">
        <span
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand/8 text-brand"
          aria-hidden="true"
        >
          <Hash className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold tracking-tight">
              NUP — Número Único de Protocolo (Decreto 8.539/2015)
            </h2>
            {tenantQ.data?.usar_nup_federal && (
              <Badge intent="success" icon={CheckCircle2}>
                Ativo
              </Badge>
            )}
          </div>
          <p className="mt-0.5 text-xs text-foreground-muted">
            Formato federal{" "}
            <code className="font-mono">NNNNN.NNNNNN/AAAA-DD</code>. Quando ativo,
            processos novos recebem o NUP além do número proprietário (
            <code className="font-mono">P000011/2026</code>) — necessário para
            integração com sistemas da União.
          </p>
        </div>
      </header>

      <div className="space-y-5 p-5">
        {tenantQ.isLoading && (
          <p className="text-sm text-foreground-muted">
            <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />
            Carregando…
          </p>
        )}

        {tenantQ.data && (
          <>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-[200px_1fr]">
              <div>
                <Label htmlFor="codigo-orgao">
                  Código do órgão <span className="text-danger">*</span>
                </Label>
                <Input
                  id="codigo-orgao"
                  value={codigo}
                  onChange={(e) => {
                    const v = e.target.value.replace(/\D/g, "").slice(0, 5);
                    setCodigo(v);
                  }}
                  placeholder="00000"
                  maxLength={5}
                  inputMode="numeric"
                  disabled={!canEdit}
                  className={cn("font-mono", codigo && !codigoValido && "border-danger")}
                />
                <p className="mt-1 text-xs text-foreground-muted">
                  5 dígitos atribuídos pelo SIORG/MP.
                </p>
              </div>

              <div>
                <Label>Exemplo de NUP gerado</Label>
                <div className="flex h-10 items-center rounded-md border border-border bg-surface-1 px-3 font-mono text-base tracking-wide">
                  {codigoValido ? (
                    <>
                      <span className="text-foreground">{codigo}</span>
                      <span className="text-foreground-muted">.</span>
                      <span className="text-foreground-muted">000001</span>
                      <span className="text-foreground-muted">/</span>
                      <span className="text-foreground">{new Date().getFullYear()}</span>
                      <span className="text-foreground-muted">-</span>
                      <span className="text-foreground-muted">DD</span>
                    </>
                  ) : (
                    <span className="text-foreground-subtle">
                      Preencha um código de 5 dígitos…
                    </span>
                  )}
                </div>
                <p className="mt-1 text-xs text-foreground-muted">
                  O <code className="font-mono">DD</code> (dígitos verificadores
                  Mod-11) é calculado automaticamente a cada NUP.
                </p>
              </div>
            </div>

            <label
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors",
                flag
                  ? "border-brand/40 bg-brand/5"
                  : "border-border bg-surface-1 hover:border-border-strong",
                !canEdit && "cursor-not-allowed opacity-60",
              )}
            >
              <input
                type="checkbox"
                checked={flag}
                disabled={!canEdit || !podeAtivar}
                onChange={(e) => setFlag(e.target.checked)}
                className="mt-0.5 h-4 w-4 accent-brand"
              />
              <div className="flex-1 text-sm">
                <div className="flex items-center gap-2 font-medium">
                  <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                  Gerar NUP federal nos processos novos
                </div>
                <p className="mt-0.5 text-xs text-foreground-muted">
                  Quando marcado, o NUP é gerado e gravado em cada protocolo novo.
                  Processos pré-existentes não ganham NUP retroativo. O número
                  proprietário (<code className="font-mono">P000011/2026</code>)
                  continua sendo gerado independentemente — usado como referência
                  interna.
                </p>
                {!podeAtivar && (
                  <p className="mt-1 text-xs text-warning">
                    Defina o código do órgão antes de ativar.
                  </p>
                )}
              </div>
            </label>

            <div className="flex items-center gap-3 pt-1">
              <Button onClick={salvar} disabled={!canEdit || !dirty || saveM.isPending}>
                {saveM.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                Salvar configuração
              </Button>
              {!canEdit && (
                <span className="text-xs text-foreground-muted">
                  Você não tem permissão para editar — somente leitura.
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function KV({
  label,
  value,
  mono = false,
  className,
}: {
  label: string;
  value: string;
  mono?: boolean;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
        {label}
      </div>
      <div className={cn("mt-0.5 text-foreground", mono && "font-mono")}>{value}</div>
    </div>
  );
}
