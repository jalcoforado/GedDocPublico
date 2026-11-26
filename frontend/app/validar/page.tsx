"use client";

import { FileCheck2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { normalizarCodigoValidacao } from "@/components/cidadao/codigo-validacao";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";

export default function ValidarFormPage() {
  const router = useRouter();
  const [codigo, setCodigo] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    // Aceita o código com espaços/quebras (cópia do PDF) e o link inteiro do QR.
    const c = normalizarCodigoValidacao(codigo);
    if (!c) {
      setErro("Digite ou cole o código que está no comprovante.");
      document.getElementById("codigo")?.focus();
      return;
    }
    router.push(`/validar/${encodeURIComponent(c)}`);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={FileCheck2}
        title="Validar documento assinado"
        description="Confira se uma assinatura eletrônica é verdadeira e se o documento não foi mudado depois de assinado."
      />

      <form onSubmit={submit} className="space-y-4 rounded-card border border-border bg-card p-4 shadow-card sm:p-6" noValidate>
        <FormField
          label="Código de validação"
          required
          error={erro ?? undefined}
          hint="Está no comprovante da assinatura, perto do QR code. Pode colar o código ou o link inteiro — maiúsculas e minúsculas contam."
        >
          <Input
            id="codigo"
            name="codigo"
            value={codigo}
            onChange={(e) => {
              setCodigo(e.target.value);
              if (erro) setErro(null);
            }}
            autoComplete="off"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            placeholder="Ex.: aB3dE-fG7h_iJ9kLmN0pQr"
            className="font-mono"
          />
        </FormField>
        <Button type="submit" size="lg" className="w-full sm:w-auto">
          Validar
        </Button>
      </form>

      <p className="text-xs text-foreground-muted">
        Assinatura eletrônica interna com evidências — não é assinatura
        qualificada ICP-Brasil.
      </p>
    </div>
  );
}
