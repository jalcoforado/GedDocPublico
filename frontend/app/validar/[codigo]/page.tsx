"use client";

import { ArrowLeft, Download, SearchX, ShieldAlert, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { use, useEffect, useState } from "react";

import { fmtDiaHora } from "@/components/cidadao/formato";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Carregando } from "@/components/ui/carregando";
import {
  validacaoPublicaComprovanteUrl,
  validarAssinaturaPublica,
  type ValidacaoPublica,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type Estado =
  | { fase: "carregando" }
  | { fase: "erro"; mensagem: string }
  | { fase: "ok"; resultado: ValidacaoPublica };

export default function ValidarResultadoPage({
  params,
}: {
  params: Promise<{ codigo: string }>;
}) {
  const { codigo } = use(params);
  const [estado, setEstado] = useState<Estado>({ fase: "carregando" });

  useEffect(() => {
    let vivo = true;
    setEstado({ fase: "carregando" });
    validarAssinaturaPublica(codigo)
      .then((resultado) => vivo && setEstado({ fase: "ok", resultado }))
      .catch((e: unknown) => {
        const msg =
          (e as { status?: number })?.status === 429
            ? "Muitas consultas em pouco tempo. Aguarde alguns instantes e tente novamente."
            : "Não foi possível consultar a validação agora. Tente novamente.";
        if (vivo) setEstado({ fase: "erro", mensagem: msg });
      });
    return () => {
      vivo = false;
    };
  }, [codigo]);

  return (
    <div className="space-y-6">
      {estado.fase === "carregando" && (
        <div role="status">
          <Carregando className="text-sm text-foreground-muted" />
          <span className="sr-only">Validando…</span>
        </div>
      )}

      {estado.fase === "erro" && <Alert intent="danger">{estado.mensagem}</Alert>}

      {estado.fase === "ok" && <Resultado codigo={codigo} r={estado.resultado} />}

      <Link
        href="/validar"
        className="inline-flex min-h-9 items-center gap-1 rounded text-sm text-primary underline-offset-4 hover:underline"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Validar outro código
      </Link>
    </div>
  );
}

function Linha({ rotulo, valor, mono }: { rotulo: string; valor: string; mono?: boolean }) {
  return (
    <div className="grid gap-0.5 border-b border-border py-3 last:border-0 sm:grid-cols-3 sm:gap-2">
      <dt className="text-xs font-medium text-foreground-muted">{rotulo}</dt>
      <dd className={cn("break-words text-sm text-foreground sm:col-span-2", mono && "break-all font-mono text-xs")}>
        {valor}
      </dd>
    </div>
  );
}

function Resultado({ codigo, r }: { codigo: string; r: ValidacaoPublica }) {
  // Caso negativo (neutro): não confirma existência. Mesma mensagem para
  // inexistente/revogado/sigiloso.
  if (!r.valido) {
    return (
      <div className="flex items-start gap-4 rounded-card border border-border bg-card p-5 shadow-card">
        <SearchX className="mt-0.5 h-8 w-8 shrink-0 text-foreground-muted" aria-hidden="true" />
        <div>
          <h1 className="text-lg font-semibold text-titulo">Validação indisponível</h1>
          <p className="mt-1 text-sm text-foreground-muted">
            Não encontramos uma assinatura pública válida para este código. Ele
            pode estar incorreto, expirado ou indisponível para consulta pública.
          </p>
          <p className="mt-2 text-sm text-foreground-muted">
            Confira o código no comprovante — maiúsculas e minúsculas contam.
          </p>
        </div>
      </div>
    );
  }

  const integro = r.integro === true;
  const Icone = integro ? ShieldCheck : ShieldAlert;

  return (
    <div className="space-y-5">
      <div
        className={cn(
          "flex items-start gap-4 rounded-card border p-5",
          integro ? "border-success/40 bg-success-soft" : "border-danger/40 bg-danger-soft",
        )}
      >
        <Icone
          className={cn(
            "mt-0.5 h-8 w-8 shrink-0",
            integro ? "text-success-soft-foreground" : "text-danger-soft-foreground",
          )}
          aria-hidden="true"
        />
        <div className="min-w-0">
          <h1
            className={cn(
              "text-lg font-semibold",
              integro ? "text-success-soft-foreground" : "text-danger-soft-foreground",
            )}
          >
            {integro ? "Assinatura válida e íntegra" : "Documento alterado após a assinatura"}
          </h1>
          <p className="mt-1 text-sm text-foreground">
            {r.detalhe ??
              (integro
                ? "A assinatura é verdadeira e o documento é o mesmo que foi assinado."
                : "A assinatura existe, mas o documento mudou depois de assinado. Não confie nesta cópia.")}
          </p>
        </div>
      </div>

      <dl className="rounded-card border border-border bg-card px-4 shadow-card">
        <Linha rotulo="Assinado por" valor={r.signatario ?? "—"} />
        <Linha rotulo="Assinado em" valor={fmtDiaHora(r.assinado_em)} />
        {r.processo_numero && <Linha rotulo="Processo" valor={r.processo_numero} mono />}
        <Linha rotulo="Versão do documento" valor={String(r.versao_documento ?? "—")} />
        <Linha rotulo={`Impressão digital (${r.algoritmo ?? "sha256"})`} valor={r.hash ?? "—"} mono />
      </dl>

      <Button asChild variant="secondary" className="w-full sm:w-auto">
        <a href={validacaoPublicaComprovanteUrl(codigo)} target="_blank" rel="noreferrer">
          <Download className="h-4 w-4" aria-hidden="true" />
          Baixar comprovante (PDF)
        </a>
      </Button>

      {r.aviso && <p className="text-xs text-foreground-muted">{r.aviso}</p>}
    </div>
  );
}
