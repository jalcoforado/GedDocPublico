"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function ValidarFormPage() {
  const router = useRouter();
  const [codigo, setCodigo] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const c = codigo.trim();
    if (c) router.push(`/validar/${encodeURIComponent(c)}`);
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-foreground">
          Validar assinatura eletrônica
        </h1>
        <p className="text-sm text-muted-foreground">
          Informe o código de validação impresso no comprovante para verificar a
          autenticidade e a integridade da assinatura.
        </p>
      </div>

      <form onSubmit={submit} className="space-y-3">
        <label htmlFor="codigo" className="block text-sm font-medium text-foreground">
          Código de validação
        </label>
        <input
          id="codigo"
          name="codigo"
          value={codigo}
          onChange={(e) => setCodigo(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          placeholder="ex.: aBc123-XyZ..."
          className="h-11 w-full rounded-md border border-border bg-card px-3 font-mono text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <button
          type="submit"
          disabled={!codigo.trim()}
          className="h-11 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
        >
          Validar
        </button>
      </form>

      <p className="text-xs text-muted-foreground">
        Assinatura eletrônica interna com evidências — não é assinatura
        qualificada ICP-Brasil.
      </p>
    </div>
  );
}
