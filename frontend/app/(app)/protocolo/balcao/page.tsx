"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  ChevronRight,
  Clock,
  FileText,
  Hash,
  Inbox,
  Loader2,
  Lock,
  Plus,
  Printer,
  Receipt,
  Tag,
  User,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { UnidadePicker } from "@/components/UnidadePicker";
import {
  api,
  ccdApi,
  protocoloApi,
  protocoloComprovantePdfUrl,
  protocoloEtiquetaPdfUrl,
  type CcdClasseTreeNode,
  type ProtocoloBalcaoResult,
  type SugestaoCcd,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type FormState = {
  id_especie_documental: number | "";
  id_manifestante: number | "";
  id_assunto: number | "";
  id_unidade_proprietaria: number | "";
  id_ccd_classe: number | "";
  numero_origem: string;
  observacao: string;
  publico: boolean;
};

function flatTreeForCombobox(
  nodes: CcdClasseTreeNode[],
): ComboboxOption[] {
  const out: ComboboxOption[] = [];
  function walk(ns: CcdClasseTreeNode[], depth: number) {
    for (const n of ns) {
      const indent = depth === 0 ? "" : "— ".repeat(depth);
      out.push({
        value: n.id,
        label: `${indent}${n.codigo} ${n.nome}`,
        hint: depth === 0 ? "raiz" : undefined,
      });
      if (n.filhos.length) walk(n.filhos, depth + 1);
    }
  }
  walk(nodes, 0);
  return out;
}

const PROTOCOLO_HISTORY_KEY = "aprimora.protocolo.balcao.recentes.v1";
const HISTORY_MAX = 8;

interface ProtocoloRecente {
  numero_processo: string;
  id: number;
  manifestante: string;
  especie_documental: string | null;
  data_recepcao: string | null;
}

function carregarRecentes(): ProtocoloRecente[] {
  try {
    const raw = window.localStorage.getItem(PROTOCOLO_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, HISTORY_MAX) : [];
  } catch {
    return [];
  }
}

function gravarRecente(r: ProtocoloRecente, prev: ProtocoloRecente[]): ProtocoloRecente[] {
  const next = [r, ...prev.filter((p) => p.id !== r.id)].slice(0, HISTORY_MAX);
  try {
    window.localStorage.setItem(PROTOCOLO_HISTORY_KEY, JSON.stringify(next));
  } catch {
    // ignore quota
  }
  return next;
}

function fmtHora(s: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export default function ProtocoloBalcaoPage() {
  const toast = useToast();
  const { user } = useAuth();
  const manifestanteRef = useRef<HTMLDivElement>(null);

  const especiesQ = useQuery({
    queryKey: ["especies-documentais"],
    queryFn: () => protocoloApi.listEspecies(false),
  });
  const manifestantesQ = useQuery({
    queryKey: ["manifestantes-all"],
    queryFn: () => api.manifestantes.list({ page_size: 500 }),
  });
  const assuntosQ = useQuery({
    queryKey: ["assuntos-all"],
    queryFn: () => api.assuntos.list({ page_size: 500 }),
  });
  const ccdTreeQ = useQuery({
    queryKey: ["ccd-tree"],
    queryFn: () => ccdApi.tree(),
  });

  const [form, setForm] = useState<FormState>({
    id_especie_documental: "",
    id_manifestante: "",
    id_assunto: "",
    id_unidade_proprietaria: user?.id_unidade_trabalho ?? "",
    id_ccd_classe: "",
    numero_origem: "",
    observacao: "",
    publico: true,
  });
  const [err, setErr] = useState<string | null>(null);
  const [recentes, setRecentes] = useState<ProtocoloRecente[]>([]);
  const [lastProtocolo, setLastProtocolo] = useState<ProtocoloBalcaoResult | null>(
    null,
  );
  const [sugestoes, setSugestoes] = useState<SugestaoCcd[]>([]);
  const [loadingSugestoes, setLoadingSugestoes] = useState(false);

  useEffect(() => {
    setRecentes(carregarRecentes());
  }, []);

  // Garante que unidade pega o default do usuário quando user carrega
  useEffect(() => {
    if (form.id_unidade_proprietaria === "" && user?.id_unidade_trabalho) {
      setForm((f) => ({ ...f, id_unidade_proprietaria: user.id_unidade_trabalho! }));
    }
  }, [user?.id_unidade_trabalho, form.id_unidade_proprietaria]);

  const especies = especiesQ.data ?? [];

  const manifestanteOptions = useMemo<ComboboxOption[]>(() => {
    return (manifestantesQ.data?.items ?? []).map((m) => ({
      value: m.id,
      label: m.nome ?? "(sem nome)",
      hint: m.cpf_cnpj ?? undefined,
    }));
  }, [manifestantesQ.data]);

  const assuntoOptions = useMemo<ComboboxOption[]>(() => {
    return (assuntosQ.data?.items ?? []).map((a) => ({
      value: a.id,
      label: a.assunto,
    }));
  }, [assuntosQ.data]);

  const ccdOptions = useMemo<ComboboxOption[]>(
    () => (ccdTreeQ.data ? flatTreeForCombobox(ccdTreeQ.data) : []),
    [ccdTreeQ.data],
  );

  // Sugestão automática de CCD quando o usuário escolhe um assunto e ainda
  // não definiu classe — debounced 300ms pra evitar request por keystroke.
  useEffect(() => {
    if (!form.id_assunto || form.id_ccd_classe) {
      setSugestoes([]);
      return;
    }
    const id_assunto = Number(form.id_assunto);
    const t = setTimeout(async () => {
      try {
        setLoadingSugestoes(true);
        const sug = await ccdApi.sugerir({ id_assunto, limit: 3 });
        setSugestoes(sug);
      } catch {
        setSugestoes([]);
      } finally {
        setLoadingSugestoes(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [form.id_assunto, form.id_ccd_classe]);

  const submitM = useMutation({
    mutationFn: () => {
      if (
        !form.id_especie_documental ||
        !form.id_manifestante ||
        !form.id_assunto ||
        !form.id_unidade_proprietaria
      ) {
        return Promise.reject(
          new Error(
            "Preencha espécie, manifestante, assunto e unidade proprietária.",
          ),
        );
      }
      return protocoloApi.protocolarBalcao({
        id_especie_documental: Number(form.id_especie_documental),
        id_manifestante: Number(form.id_manifestante),
        id_assunto: Number(form.id_assunto),
        id_unidade_proprietaria: Number(form.id_unidade_proprietaria),
        id_ccd_classe: form.id_ccd_classe ? Number(form.id_ccd_classe) : null,
        numero_origem: form.numero_origem || null,
        observacao: form.observacao || null,
        publico: form.publico,
      });
    },
    onSuccess: (data) => {
      setLastProtocolo(data);
      setRecentes((prev) =>
        gravarRecente(
          {
            id: data.id,
            numero_processo: data.numero_processo,
            manifestante: data.manifestante,
            especie_documental: data.especie_documental,
            data_recepcao: data.data_recepcao,
          },
          prev,
        ),
      );
      toast.success(`Protocolado: ${data.numero_processo}`);
      setErr(null);
    },
    onError: (e: Error) => {
      setErr(e.message);
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
  });

  function submit(e?: React.FormEvent) {
    e?.preventDefault();
    submitM.mutate();
  }

  function novoProtocolo() {
    // Reset apenas campos do processo, mantém unidade default + público
    setForm((f) => ({
      ...f,
      id_especie_documental: "",
      id_manifestante: "",
      id_assunto: "",
      id_ccd_classe: "",
      numero_origem: "",
      observacao: "",
    }));
    setSugestoes([]);
    setLastProtocolo(null);
    setErr(null);
    // Foca manifestante combo
    requestAnimationFrame(() => {
      const btn = manifestanteRef.current?.querySelector<HTMLButtonElement>(
        "button[role='combobox']",
      );
      btn?.focus();
    });
  }

  // Ctrl+Enter atalho para protocolar
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !submitM.isPending) {
        e.preventDefault();
        if (lastProtocolo) novoProtocolo();
        else submit();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [submitM.isPending, lastProtocolo, form]);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Inbox}
        title="Balcão de Protocolo"
        description="Registre documentos recebidos pessoalmente, por mensageiro ou ofício externo. Cada protocolo gera número oficial automático."
      />

      {err && (
        <div className="rounded-md border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {err}
        </div>
      )}

      {lastProtocolo ? (
        <SuccessCard
          protocolo={lastProtocolo}
          onNext={novoProtocolo}
        />
      ) : (
        <form onSubmit={submit} className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
          <div className="space-y-5">
            <section className="rounded-xl border border-border bg-card p-5 shadow-xs">
              <header className="mb-4 flex items-center gap-2">
                <FileText className="h-4 w-4 text-brand" aria-hidden="true" />
                <h2 className="text-sm font-semibold tracking-tight">
                  Espécie do documento
                </h2>
              </header>
              <div className="flex flex-wrap gap-2">
                {especiesQ.isLoading && (
                  <p className="text-sm text-foreground-muted">Carregando…</p>
                )}
                {especies.map((esp) => {
                  const isSelected = form.id_especie_documental === esp.id;
                  return (
                    <button
                      key={esp.id}
                      type="button"
                      onClick={() =>
                        setForm({ ...form, id_especie_documental: esp.id })
                      }
                      className={cn(
                        "rounded-lg border px-3 py-1.5 text-sm transition-colors duration-fast",
                        isSelected
                          ? "border-brand bg-brand/10 font-medium text-brand"
                          : "border-border bg-surface-1 text-foreground hover:border-border-strong hover:bg-surface-2",
                      )}
                    >
                      {esp.nome}
                    </button>
                  );
                })}
              </div>
            </section>

            <section className="rounded-xl border border-border bg-card p-5 shadow-xs">
              <header className="mb-4 flex items-center gap-2">
                <User className="h-4 w-4 text-brand" aria-hidden="true" />
                <h2 className="text-sm font-semibold tracking-tight">
                  Manifestante e classificação
                </h2>
              </header>

              <div className="grid grid-cols-1 gap-4">
                <div ref={manifestanteRef}>
                  <Label htmlFor="manifestante-cb">
                    Manifestante <span className="text-danger">*</span>
                  </Label>
                  <Combobox
                    id="manifestante-cb"
                    options={manifestanteOptions}
                    value={form.id_manifestante || null}
                    onChange={(v) =>
                      setForm({
                        ...form,
                        id_manifestante: typeof v === "number" ? v : "",
                      })
                    }
                    placeholder="Buscar por nome ou CPF/CNPJ…"
                    loading={manifestantesQ.isLoading}
                    footer={
                      <Link
                        href="/manifestantes"
                        className="text-primary hover:underline"
                      >
                        + Cadastrar novo manifestante
                      </Link>
                    }
                  />
                </div>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <Label htmlFor="assunto-cb">
                      Assunto <span className="text-danger">*</span>
                    </Label>
                    <Combobox
                      id="assunto-cb"
                      options={assuntoOptions}
                      value={form.id_assunto || null}
                      onChange={(v) =>
                        setForm({
                          ...form,
                          id_assunto: typeof v === "number" ? v : "",
                        })
                      }
                      placeholder="Selecione um assunto…"
                      loading={assuntosQ.isLoading}
                    />
                  </div>

                  <div>
                    <Label htmlFor="numero-origem">
                      Nº de origem
                      <span className="ml-1 text-xs text-foreground-muted">
                        (opcional)
                      </span>
                    </Label>
                    <div className="relative">
                      <Hash
                        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-muted"
                        aria-hidden="true"
                      />
                      <Input
                        id="numero-origem"
                        value={form.numero_origem}
                        onChange={(e) =>
                          setForm({ ...form, numero_origem: e.target.value })
                        }
                        placeholder="Ex: OFICIO 123/2026"
                        className="pl-9"
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <Label htmlFor="ccd-cb">
                    Classe CCD
                    <span className="ml-1 text-xs text-foreground-muted">
                      (recomendado — define prazo de guarda)
                    </span>
                  </Label>
                  <Combobox
                    id="ccd-cb"
                    options={ccdOptions}
                    value={form.id_ccd_classe || null}
                    onChange={(v) =>
                      setForm({
                        ...form,
                        id_ccd_classe: typeof v === "number" ? v : "",
                      })
                    }
                    placeholder="Selecione a classe documental…"
                    loading={ccdTreeQ.isLoading}
                  />
                  {!form.id_ccd_classe && sugestoes.length > 0 && (
                    <div className="mt-2 space-y-1.5">
                      <p className="text-xs text-foreground-muted">
                        {loadingSugestoes
                          ? "Buscando sugestões…"
                          : "Sugestões baseadas no assunto:"}
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {sugestoes.map((s) => (
                          <button
                            key={s.id_ccd_classe}
                            type="button"
                            onClick={() =>
                              setForm({ ...form, id_ccd_classe: s.id_ccd_classe })
                            }
                            className="inline-flex items-center gap-1.5 rounded-full border border-brand/30 bg-brand/5 px-2.5 py-1 text-xs text-brand transition-colors hover:bg-brand/10"
                            title={`Score: ${(s.score * 100).toFixed(0)}% · match: ${s.matched_keywords.join(", ")}`}
                          >
                            <span className="font-mono font-semibold">{s.codigo}</span>
                            <span className="truncate">{s.nome}</span>
                            <span className="text-[10px] text-foreground-muted">
                              {(s.score * 100).toFixed(0)}%
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div>
                  <Label>
                    Unidade proprietária <span className="text-danger">*</span>
                  </Label>
                  <UnidadePicker
                    value={
                      typeof form.id_unidade_proprietaria === "number"
                        ? form.id_unidade_proprietaria
                        : null
                    }
                    onChange={(v) =>
                      setForm({ ...form, id_unidade_proprietaria: v ?? "" })
                    }
                  />
                  <p className="mt-1 text-xs text-foreground-muted">
                    Sugerido: sua unidade. Use o picker pra escolher outra.
                  </p>
                </div>

                <div>
                  <Label htmlFor="observacao">
                    Observação
                    <span className="ml-1 text-xs text-foreground-muted">
                      (opcional, livre)
                    </span>
                  </Label>
                  <Textarea
                    id="observacao"
                    value={form.observacao}
                    onChange={(e) =>
                      setForm({ ...form, observacao: e.target.value })
                    }
                    placeholder="Resumo do conteúdo, exigência, contato adicional…"
                    rows={3}
                  />
                </div>

                <label className="flex cursor-pointer items-start gap-2 rounded-md border border-border bg-surface-1 px-3 py-2 hover:bg-surface-2">
                  <input
                    type="checkbox"
                    checked={!form.publico}
                    onChange={(e) =>
                      setForm({ ...form, publico: !e.target.checked })
                    }
                    className="mt-0.5 h-4 w-4 accent-brand"
                  />
                  <div className="flex-1 text-sm">
                    <div className="flex items-center gap-2 font-medium text-foreground">
                      <Lock className="h-3.5 w-3.5" aria-hidden="true" />
                      Sigiloso
                    </div>
                    <p className="text-xs text-foreground-muted">
                      Marque se o conteúdo é restrito (LGPD, sigilo profissional).
                      Padrão é público.
                    </p>
                  </div>
                </label>
              </div>
            </section>

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button
                type="submit"
                disabled={submitM.isPending}
                className="min-w-48"
              >
                {submitM.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                    Protocolando…
                  </>
                ) : (
                  <>
                    <Receipt className="mr-2 h-4 w-4" aria-hidden="true" />
                    Protocolar
                  </>
                )}
              </Button>
              <span className="text-xs text-foreground-muted">
                Atalho:{" "}
                <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px]">
                  Ctrl + Enter
                </kbd>
              </span>
            </div>
          </div>

          <aside className="space-y-4">
            <div className="rounded-xl border border-border bg-card p-4 shadow-xs">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
                <Clock className="h-4 w-4 text-foreground-muted" aria-hidden="true" />
                Protocolos recentes (sessão)
              </div>
              {recentes.length === 0 ? (
                <p className="text-xs text-foreground-muted">
                  Os últimos {HISTORY_MAX} protocolos desta sessão aparecem aqui.
                </p>
              ) : (
                <ul className="space-y-1.5">
                  {recentes.map((r) => (
                    <li
                      key={r.id}
                      className="rounded-md border border-border bg-surface-1 px-2.5 py-1.5"
                    >
                      <Link
                        href={`/processos/${r.id}`}
                        className="flex items-center justify-between gap-2 text-xs"
                      >
                        <span className="min-w-0 flex-1 truncate">
                          <span className="font-mono font-semibold text-primary">
                            {r.numero_processo}
                          </span>
                          <span className="ml-1.5 text-foreground-muted">
                            {r.especie_documental ?? "—"} ·{" "}
                            {r.manifestante.slice(0, 28)}
                          </span>
                        </span>
                        <span className="shrink-0 text-foreground-muted">
                          {fmtHora(r.data_recepcao)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-xl border border-border bg-card p-4 text-xs text-foreground-muted shadow-xs">
              <div className="mb-1.5 font-semibold text-foreground">
                Atalhos rápidos
              </div>
              <ul className="space-y-1">
                <li>
                  <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px]">
                    Ctrl + Enter
                  </kbd>{" "}
                  protocola
                </li>
                <li>
                  <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px]">
                    Tab
                  </kbd>{" "}
                  avança campo
                </li>
                <li>
                  <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px]">
                    Esc
                  </kbd>{" "}
                  fecha popups
                </li>
              </ul>
            </div>
          </aside>
        </form>
      )}
    </div>
  );
}

function SuccessCard({
  protocolo,
  onNext,
}: {
  protocolo: ProtocoloBalcaoResult;
  onNext: () => void;
}) {
  return (
    <div className="rounded-xl border border-success/30 bg-success/5 p-6 shadow-xs">
      <div className="flex items-start gap-3">
        <span
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-success/10 text-success"
          aria-hidden="true"
        >
          <CheckCircle2 className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-success">
            Protocolado{protocolo.nup ? " (NUP federal)" : ""}
          </p>
          <h2 className="mt-1 font-mono text-2xl font-bold tracking-tight text-foreground">
            {protocolo.nup ?? protocolo.numero_processo}
          </h2>
          {protocolo.nup && (
            <p className="mt-0.5 font-mono text-xs text-foreground-muted">
              Legado: {protocolo.numero_processo}
            </p>
          )}
          <p className="mt-1 text-sm text-foreground-muted">
            {protocolo.especie_documental ?? "Espécie não informada"} ·{" "}
            {protocolo.manifestante}
          </p>
          <p className="mt-0.5 text-xs text-foreground-muted">
            {protocolo.assunto} → {protocolo.unidade_proprietaria}
          </p>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <Button onClick={onNext} className="min-w-44">
          <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
          Protocolar próximo
        </Button>
        <a
          href={protocoloEtiquetaPdfUrl(protocolo.id)}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Button variant="secondary">
            <Tag className="mr-2 h-4 w-4" aria-hidden="true" />
            Etiqueta
          </Button>
        </a>
        <a
          href={protocoloComprovantePdfUrl(protocolo.id)}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Button variant="secondary">
            <Printer className="mr-2 h-4 w-4" aria-hidden="true" />
            Comprovante (2 vias)
          </Button>
        </a>
        <Link href={`/processos/${protocolo.id}`}>
          <Button variant="secondary">
            Ver processo
            <ChevronRight className="ml-1 h-4 w-4" aria-hidden="true" />
          </Button>
        </Link>
      </div>

      <p className="mt-4 text-xs text-foreground-muted">
        Atalho:{" "}
        <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px]">
          Ctrl + Enter
        </kbd>{" "}
        para protocolar o próximo · etiqueta e comprovante abrem em nova aba.
      </p>
    </div>
  );
}
