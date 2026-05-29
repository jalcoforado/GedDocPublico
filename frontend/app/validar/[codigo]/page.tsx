"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import {
  validacaoPublicaComprovanteUrl,
  validarAssinaturaPublica,
  type ValidacaoPublica,
} from "@/lib/api";

type Estado =
  | { fase: "carregando" }
  | { fase: "erro"; mensagem: string }
  | { fase: "ok"; resultado: ValidacaoPublica };

function fmtData(s: string | null): string {
  if (!s) return "—";
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? s : d.toLocaleString("pt-BR");
}

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
        <p className="text-sm text-muted-foreground" role="status">
          Validando…
        </p>
      )}

      {estado.fase === "erro" && (
        <div className="rounded-md border border-border bg-card p-4">
          <p className="text-sm text-foreground">{estado.mensagem}</p>
        </div>
      )}

      {estado.fase === "ok" && <Resultado codigo={codigo} r={estado.resultado} />}

      <Link
        href="/validar"
        className="inline-block text-sm text-primary underline-offset-4 hover:underline"
      >
        Validar outro código
      </Link>
    </div>
  );
}

function Linha({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="grid grid-cols-3 gap-2 border-b border-border py-2 last:border-0">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {rotulo}
      </dt>
      <dd className="col-span-2 break-words font-mono text-sm text-foreground">
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
      <div className="rounded-md border border-border bg-card p-5">
        <h2 className="text-lg font-semibold text-foreground">
          Validação indisponível
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Não encontramos uma assinatura pública válida para este código. Ele
          pode estar incorreto, expirado ou indisponível para consulta pública.
        </p>
      </div>
    );
  }

  const integro = r.integro === true;
  const cor = integro
    ? "border-success/40 bg-success-soft"
    : "border-danger/40 bg-danger-soft";
  const titulo = integro
    ? "Assinatura válida e íntegra"
    : "Documento alterado após a assinatura";
  const corTexto = integro ? "text-success" : "text-danger";

  return (
    <div className="space-y-5">
      <div className={`rounded-md border p-5 ${cor}`}>
        <h2 className={`text-lg font-semibold ${corTexto}`}>{titulo}</h2>
        {r.detalhe && (
          <p className="mt-1 text-sm text-foreground">{r.detalhe}</p>
        )}
      </div>

      <dl className="rounded-md border border-border bg-card px-4">
        <Linha rotulo="Signatário" valor={r.signatario ?? "—"} />
        <Linha rotulo="Data/hora" valor={fmtData(r.assinado_em)} />
        {r.processo_numero && (
          <Linha rotulo="Processo" valor={r.processo_numero} />
        )}
        <Linha rotulo="Versão doc." valor={String(r.versao_documento ?? "—")} />
        <Linha rotulo={`Hash (${r.algoritmo ?? "sha256"})`} valor={r.hash ?? "—"} />
      </dl>

      <div className="flex flex-wrap items-center gap-3">
        <a
          href={validacaoPublicaComprovanteUrl(codigo)}
          target="_blank"
          rel="noreferrer"
          className="h-10 rounded-md border border-border px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring inline-flex items-center"
        >
          Baixar comprovante público (PDF)
        </a>
      </div>

      {r.aviso && <p className="text-xs text-muted-foreground">{r.aviso}</p>}
    </div>
  );
}
