"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  CheckCircle2,
  ChevronRight,
  Circle,
  Hash,
  ListChecks,
  Loader2,
  Settings,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FormField, GradeCampos, focarPrimeiroInvalido } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { UnidadePicker } from "@/components/UnidadePicker";
import {
  tenantsApi,
  type NupConfigUpdate,
  type TenantInstitucionalUpdate,
  type TenantMe,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useRecarregarBranding } from "@/lib/branding";
import { emailValido } from "@/lib/mascaras";
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
  id_unidade_padrao: null,
};

function doTenant(t: TenantMe): InstitucionalForm {
  return {
    nome: t.nome ?? "",
    sigla: t.sigla ?? "",
    email_institucional: t.email_institucional ?? "",
    telefone_institucional: t.telefone_institucional ?? "",
    endereco: t.endereco ?? "",
    site_oficial: t.site_oficial ?? "",
    horario_atendimento: t.horario_atendimento ?? "",
    texto_boas_vindas_portal: t.texto_boas_vindas_portal ?? "",
    logo_url: t.logo_url ?? "",
    id_unidade_padrao: t.id_unidade_padrao ?? null,
  };
}

/** "" → null para limpar campos opcionais; mantém o texto quando preenchido. */
function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

const SEM_PERMISSAO = "Você não tem permissão para editar — somente leitura.";

export default function ConfiguracoesPage() {
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
        title="Configurações"
        description="Identidade institucional, configuração inicial e ajustes administrativos da prefeitura."
      />

      <OnboardingCard />

      <InstitucionalSection canEdit={canEdit} />

      <NupSection canEdit={canEdit} />

      <SectionCard
        icon={Building2}
        title="Identificação na plataforma"
        description="Somente leitura: estes dados mudam pela administração da plataforma."
      >
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm md:grid-cols-3">
          <KV label="ID" value={String(tenantQ.data?.id ?? "—")} mono />
          <KV label="Slug" value={tenantQ.data?.slug ?? "—"} mono />
          <KV label="Plano" value={tenantQ.data?.plano ?? "—"} />
        </div>
      </SectionCard>
    </div>
  );
}

// ===== Checklist de onboarding ===============================================

function OnboardingCard() {
  const onboardingQ = useQuery({
    queryKey: ["tenant-onboarding"],
    queryFn: () => tenantsApi.onboarding(),
  });
  const dados = onboardingQ.data;
  const pct = dados && dados.total > 0 ? Math.round((dados.concluidos / dados.total) * 100) : 0;

  return (
    <SectionCard
      icon={ListChecks}
      title="Checklist de configuração inicial"
      description="Passos sugeridos para deixar o sistema pronto para uso. Calculado a partir do estado atual."
      actions={
        dados && (
          <Badge intent={dados.pendentes === 0 ? "success" : "neutral"}>
            {dados.concluidos}/{dados.total} concluídos
          </Badge>
        )
      }
    >
      {onboardingQ.isLoading && (
        <p className="text-sm text-foreground-muted">
          <Loader2 className="mr-1 inline h-4 w-4 animate-spin" aria-hidden="true" />
          Carregando…
        </p>
      )}
      {dados && (
        <>
          {/* Barra de progresso: o "quanto falta" de relance, antes da lista. */}
          <div
            role="progressbar"
            aria-label="Configuração inicial"
            aria-valuemin={0}
            aria-valuemax={dados.total}
            aria-valuenow={dados.concluidos}
            className="h-1.5 overflow-hidden rounded-full bg-surface-3"
          >
            <div
              className={cn("h-full rounded-full", pct === 100 ? "bg-success" : "bg-brand")}
              style={{ width: `${pct}%` }}
            />
          </div>
          <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {/* Pendentes primeiro: é o que pede ação. */}
            {[...dados.itens]
              .sort((a, b) => Number(a.concluido === true) - Number(b.concluido === true))
              .map((item) => {
                const href = CHECKLIST_HREF[item.chave];
                const done = item.concluido === true;
                return (
                  <li
                    key={item.chave}
                    className="flex items-center gap-2 rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm"
                  >
                    {done ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-success" aria-label="Concluído" />
                    ) : (
                      <Circle className="h-4 w-4 shrink-0 text-foreground-subtle" aria-label="Pendente" />
                    )}
                    <span className={cn("flex-1", done && "text-foreground-muted")}>
                      {item.rotulo}
                    </span>
                    {!done && href && (
                      <Link
                        href={href}
                        className="inline-flex shrink-0 items-center gap-0.5 text-xs font-medium text-primary hover:underline"
                      >
                        Configurar
                        <ChevronRight className="h-3 w-3" aria-hidden="true" />
                      </Link>
                    )}
                  </li>
                );
              })}
          </ul>
        </>
      )}
    </SectionCard>
  );
}

// ===== Identidade institucional ==============================================

type CampoValidado = "nome" | "email_institucional";

/** Subtítulo de um grupo de campos dentro da seção. */
function Grupo({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <fieldset className="space-y-4">
      <legend className="mb-3 w-full border-b border-border pb-1.5 text-xs font-semibold uppercase tracking-wider text-foreground-subtle">
        {titulo}
      </legend>
      {children}
    </fieldset>
  );
}

function InstitucionalSection({ canEdit }: { canEdit: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const tenantQ = useQuery({ queryKey: ["tenant-me"], queryFn: () => tenantsApi.me() });

  const [form, setForm] = useState<InstitucionalForm>(EMPTY_INSTITUCIONAL);
  const [tocados, setTocados] = useState<Set<CampoValidado>>(new Set());
  const [tentou, setTentou] = useState(false);
  const [logoQuebrado, setLogoQuebrado] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (tenantQ.data) setForm(doTenant(tenantQ.data));
  }, [tenantQ.data]);

  const recarregarBranding = useRecarregarBranding();

  const saveM = useMutation({
    mutationFn: (payload: TenantInstitucionalUpdate) =>
      tenantsApi.updateInstitucional(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenant-me"] });
      qc.invalidateQueries({ queryKey: ["tenant-onboarding"] });
      // Nome e logo aparecem no cabeçalho e no login: valem já.
      recarregarBranding();
      toast.success("Dados institucionais salvos.");
      setTentou(false);
      setTocados(new Set());
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof InstitucionalForm>(key: K, value: InstitucionalForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  // O formato do e-mail só é cobrado quando ele mudou: um cadastro antigo
  // fora do padrão não pode travar a troca do horário de atendimento.
  const erros: Partial<Record<CampoValidado, string>> = {};
  if (!form.nome.trim()) erros.nome = "Informe o nome da prefeitura.";
  const email = form.email_institucional.trim();
  if (email && email !== (tenantQ.data?.email_institucional ?? "") && !emailValido(email))
    erros.email_institucional = "Confira o e-mail: use o formato protocolo@prefeitura.gov.br.";
  const erroVisivel = (c: CampoValidado) => (tentou || tocados.has(c) ? erros[c] : undefined);
  const tocar = (c: CampoValidado) => () =>
    setTocados((s) => (s.has(c) ? s : new Set(s).add(c)));

  const alterado =
    !!tenantQ.data && JSON.stringify(form) !== JSON.stringify(doTenant(tenantQ.data));

  function salvar(e?: React.FormEvent) {
    e?.preventDefault();
    if (Object.keys(erros).length > 0) {
      flushSync(() => setTentou(true));
      focarPrimeiroInvalido(formRef.current ?? document);
      return;
    }
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
      // As cores e a fonte NÃO vão neste payload: são da tela Aparência, e
      // mandá-las daqui regravaria por cima o que foi salvo lá.
      id_unidade_padrao: form.id_unidade_padrao,
    });
  }

  const logo = form.logo_url.trim();

  return (
    <SectionCard
      id="identidade"
      icon={Building2}
      title="Identidade institucional"
      description="Dados de contato e apresentação da prefeitura, usados no portal do cidadão e em documentos."
    >
      {tenantQ.isLoading && (
        <p className="text-sm text-foreground-muted">
          <Loader2 className="mr-1 inline h-4 w-4 animate-spin" aria-hidden="true" />
          Carregando…
        </p>
      )}

      {tenantQ.data && (
        <form ref={formRef} onSubmit={salvar} noValidate className="max-w-3xl space-y-6">
          <Grupo titulo="Como a prefeitura aparece">
            <GradeCampos className="sm:grid-cols-[minmax(0,1fr)_10rem]">
              <FormField label="Nome da prefeitura" required error={erroVisivel("nome")}>
                <Input
                  id="nome"
                  value={form.nome}
                  onChange={(e) => set("nome", e.target.value)}
                  onBlur={tocar("nome")}
                  placeholder="Ex.: Prefeitura Municipal de Santa Luzia"
                  disabled={!canEdit}
                />
              </FormField>
              <FormField label="Sigla">
                <Input
                  id="sigla"
                  value={form.sigla}
                  maxLength={20}
                  onChange={(e) => set("sigla", e.target.value)}
                  placeholder="Ex.: PMSL"
                  disabled={!canEdit}
                />
              </FormField>
            </GradeCampos>
            <FormField
              label="Logo"
              hint="Endereço (URL) de uma imagem PNG ou SVG. Aparece no cabeçalho e na tela de entrada."
            >
              <Input
                id="logo-url"
                value={form.logo_url}
                placeholder="Ex.: https://www.santaluzia.ce.gov.br/logo.png"
                onChange={(e) => {
                  set("logo_url", e.target.value);
                  setLogoQuebrado(false);
                }}
                disabled={!canEdit}
              />
            </FormField>
            {/* Prévia: dá para ver se o endereço aponta mesmo para a imagem
                antes de salvar e levar o logo quebrado para o cabeçalho. */}
            {logo && /^https?:\/\//i.test(logo) && (
              <div className="flex items-center gap-3 rounded-lg border border-border bg-surface-1 px-3 py-2">
                {logoQuebrado ? (
                  <p className="text-xs text-warning-soft-foreground">
                    Não foi possível abrir a imagem neste endereço. Confira o link.
                  </p>
                ) : (
                  <>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={logo}
                      alt="Prévia do logo"
                      className="h-10 max-w-[10rem] object-contain"
                      onError={() => setLogoQuebrado(true)}
                    />
                    <span className="text-xs text-foreground-muted">Prévia do logo</span>
                  </>
                )}
              </div>
            )}
            <p className="text-sm text-foreground-muted">
              As cores e a fonte do sistema ficam em{" "}
              <Link
                href="/m/administracao/aparencia"
                className="font-medium text-primary underline-offset-2 hover:underline"
              >
                Aparência
              </Link>
              .
            </p>
          </Grupo>

          <Grupo titulo="Contato">
            <GradeCampos>
              <FormField
                label="E-mail institucional"
                error={erroVisivel("email_institucional")}
              >
                <Input
                  id="email-inst"
                  type="email"
                  inputMode="email"
                  value={form.email_institucional}
                  onChange={(e) => set("email_institucional", e.target.value)}
                  onBlur={tocar("email_institucional")}
                  placeholder="Ex.: protocolo@santaluzia.ce.gov.br"
                  disabled={!canEdit}
                />
              </FormField>
              <FormField label="Telefone institucional">
                <Input
                  id="telefone-inst"
                  inputMode="tel"
                  maxLength={20}
                  value={form.telefone_institucional}
                  onChange={(e) => set("telefone_institucional", e.target.value)}
                  placeholder="Ex.: (88) 3600-0000"
                  disabled={!canEdit}
                />
              </FormField>
            </GradeCampos>
            <FormField label="Site oficial">
              <Input
                id="site"
                value={form.site_oficial}
                placeholder="Ex.: https://www.santaluzia.ce.gov.br"
                onChange={(e) => set("site_oficial", e.target.value)}
                disabled={!canEdit}
              />
            </FormField>
            <FormField label="Endereço">
              <Textarea
                id="endereco"
                rows={2}
                value={form.endereco}
                onChange={(e) => set("endereco", e.target.value)}
                placeholder="Ex.: Rua Principal, 100 — Centro"
                disabled={!canEdit}
              />
            </FormField>
            <FormField label="Horário de atendimento">
              <Input
                id="horario"
                value={form.horario_atendimento}
                placeholder="Ex.: Seg a Sex, 8h–17h"
                onChange={(e) => set("horario_atendimento", e.target.value)}
                disabled={!canEdit}
              />
            </FormField>
          </Grupo>

          <Grupo titulo="Protocolo e portal">
            <FormField
              label="Unidade padrão"
              hint="Destino sugerido para os protocolos novos."
            >
              <UnidadePicker
                id="unidade-padrao"
                value={form.id_unidade_padrao}
                onChange={(v) => set("id_unidade_padrao", v)}
                placeholder="Nenhuma — quem protocola escolhe"
                disabled={!canEdit}
              />
            </FormField>
            <FormField
              label="Mensagem de boas-vindas do portal"
              hint="Exibida aos cidadãos no portal público."
            >
              <Textarea
                id="boas-vindas"
                rows={3}
                value={form.texto_boas_vindas_portal}
                onChange={(e) => set("texto_boas_vindas_portal", e.target.value)}
                placeholder="Ex.: Bem-vindo ao portal de serviços da Prefeitura. Abra e acompanhe seus pedidos por aqui."
                disabled={!canEdit}
              />
            </FormField>
          </Grupo>

          <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
            <Button type="submit" disabled={!canEdit} loading={saveM.isPending}>
              Salvar dados institucionais
            </Button>
            <span className="text-xs text-foreground-muted" aria-live="polite">
              {!canEdit ? SEM_PERMISSAO : alterado ? "Há alterações não salvas." : ""}
            </span>
          </div>
        </form>
      )}
    </SectionCard>
  );
}

// ===== NUP federal (Fase P2) =================================================

function NupSection({ canEdit }: { canEdit: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const tenantQ = useQuery({ queryKey: ["tenant-me"], queryFn: () => tenantsApi.me() });

  const [codigo, setCodigo] = useState("");
  const [flag, setFlag] = useState(false);
  const [codigoTocado, setCodigoTocado] = useState(false);

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
      setCodigoTocado(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const dirty =
    tenantQ.data &&
    (codigo !== (tenantQ.data.codigo_orgao_nup ?? "") ||
      flag !== tenantQ.data.usar_nup_federal);

  const codigoValido = /^[0-9]{5}$/.test(codigo);
  const podeAtivar = codigoValido;
  // Mesma regra do backend: código vazio ou com exatamente 5 dígitos.
  const faltam = 5 - codigo.length;
  const erroCodigo =
    codigo && !codigoValido
      ? `O código tem 5 dígitos — falta${faltam > 1 ? "m" : ""} ${faltam}.`
      : undefined;

  function salvar() {
    if (erroCodigo) {
      setCodigoTocado(true);
      document.getElementById("codigo-orgao")?.focus();
      return;
    }
    saveM.mutate({
      codigo_orgao_nup: codigo.trim() === "" ? null : codigo,
      usar_nup_federal: flag,
    });
  }

  return (
    <SectionCard
      icon={Hash}
      title="NUP — Número Único de Protocolo (Decreto 8.539/2015)"
      description="Formato federal NNNNN.NNNNNN/AAAA-DD. Quando ativo, processos novos recebem o NUP além do número próprio (P000011/2026) — necessário para integração com sistemas da União."
      actions={
        tenantQ.data?.usar_nup_federal && (
          <Badge intent="success" icon={CheckCircle2}>
            Ativo
          </Badge>
        )
      }
    >
      {tenantQ.isLoading && (
        <p className="text-sm text-foreground-muted">
          <Loader2 className="mr-1 inline h-4 w-4 animate-spin" aria-hidden="true" />
          Carregando…
        </p>
      )}

      {tenantQ.data && (
        <div className="max-w-3xl space-y-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-[12rem_1fr]">
            <FormField
              label="Código do órgão"
              hint="5 dígitos atribuídos pelo SIORG."
              error={codigoTocado ? erroCodigo : undefined}
            >
              <Input
                id="codigo-orgao"
                value={codigo}
                onChange={(e) => {
                  const v = e.target.value.replace(/\D/g, "").slice(0, 5);
                  setCodigo(v);
                }}
                onBlur={() => setCodigoTocado(true)}
                placeholder="Ex.: 00394"
                maxLength={5}
                inputMode="numeric"
                disabled={!canEdit}
                className="font-mono"
              />
            </FormField>

            <div>
              <div className="mb-1 text-sm font-medium text-foreground">Como o NUP vai sair</div>
              <div
                className="flex h-[var(--density-row-h)] items-center rounded-input border border-border bg-surface-1 px-3 font-mono text-base tracking-wide"
                aria-live="polite"
              >
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
                  <span className="font-sans text-sm text-foreground-subtle">
                    Preencha o código para ver o exemplo.
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-foreground-muted">
                O <code className="font-mono">DD</code> (dígitos verificadores Mod-11) é
                calculado automaticamente a cada NUP.
              </p>
            </div>
          </div>

          <label
            className={cn(
              "flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors",
              flag
                ? "border-brand/40 bg-brand/5"
                : "border-border bg-surface-1 hover:border-border-strong",
              (!canEdit || !podeAtivar) && "cursor-not-allowed",
              !canEdit && "opacity-60",
            )}
          >
            <input
              type="checkbox"
              checked={flag}
              disabled={!canEdit || !podeAtivar}
              onChange={(e) => setFlag(e.target.checked)}
              aria-describedby="nup-flag-dica"
              className="mt-0.5 h-4 w-4 accent-brand"
            />
            <div className="flex-1 text-sm">
              <div className="flex items-center gap-2 font-medium">
                <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                Gerar NUP federal nos processos novos
              </div>
              <p id="nup-flag-dica" className="mt-0.5 text-xs text-foreground-muted">
                Processos que já existem não ganham NUP retroativo. O número próprio
                (<code className="font-mono">P000011/2026</code>) continua sendo gerado, como
                referência interna.
                {!podeAtivar && (
                  <span className="mt-1 block font-medium text-warning-soft-foreground">
                    Preencha o código do órgão para poder ativar.
                  </span>
                )}
              </p>
            </div>
          </label>

          <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
            <Button onClick={salvar} disabled={!canEdit || !dirty} loading={saveM.isPending}>
              Salvar configuração do NUP
            </Button>
            <span className="text-xs text-foreground-muted" aria-live="polite">
              {!canEdit ? SEM_PERMISSAO : dirty ? "Há alterações não salvas." : ""}
            </span>
          </div>
        </div>
      )}
    </SectionCard>
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
