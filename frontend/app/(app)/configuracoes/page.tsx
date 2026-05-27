"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  CheckCircle2,
  Hash,
  Loader2,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { useToast } from "@/components/ui/toast";
import { tenantsApi, type NupConfigUpdate } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export default function ConfiguracoesPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const canEdit = can("usuario", "atualizar");

  const tenantQ = useQuery({
    queryKey: ["tenant-me"],
    queryFn: () => tenantsApi.me(),
  });

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
    <div className="space-y-6">
      <PageHeader
        icon={Settings}
        title="Configurações do tenant"
        description="Ajustes administrativos da prefeitura. Apenas usuários com permissão de atualização podem editar."
      />

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
              <code className="font-mono">NNNNN.NNNNNN/AAAA-DD</code>. Quando
              ativo, processos novos recebem o NUP além do número proprietário (
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
                    className={cn(
                      "font-mono",
                      codigo && !codigoValido && "border-danger",
                    )}
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
                        <span className="text-foreground">
                          {new Date().getFullYear()}
                        </span>
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
                    Quando marcado, o NUP é gerado e gravado em cada protocolo
                    novo. Processos pré-existentes não ganham NUP retroativo. O
                    número proprietário (
                    <code className="font-mono">P000011/2026</code>) continua
                    sendo gerado independentemente — usado como referência
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
                <Button
                  onClick={salvar}
                  disabled={!canEdit || !dirty || saveM.isPending}
                >
                  {saveM.isPending && (
                    <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                  )}
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
              Informações somente leitura (alteração via CLI de administração).
            </p>
          </div>
        </header>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 p-5 text-sm md:grid-cols-3">
          <KV label="ID" value={String(tenantQ.data?.id ?? "—")} mono />
          <KV label="Slug" value={tenantQ.data?.slug ?? "—"} mono />
          <KV label="Plano" value={tenantQ.data?.plano ?? "—"} />
          <KV
            label="Nome"
            value={tenantQ.data?.nome ?? "—"}
            className="col-span-2 md:col-span-3"
          />
        </div>
      </section>
    </div>
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
      <div className={cn("mt-0.5 text-foreground", mono && "font-mono")}>
        {value}
      </div>
    </div>
  );
}
