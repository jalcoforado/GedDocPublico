import { FileText } from "lucide-react";

import { cn } from "@/lib/utils";

interface Documento {
  nome: string;
  obrigatorio: boolean;
  descricao?: string | null;
}

/**
 * "Documentos necessários" de um serviço, igual na carta, no detalhe e no
 * pedido. Era uma lista com asterisco vermelho e a legenda "* obrigatório"
 * em letra de 10px — código de formulário que o cidadão não lê. Agora a
 * regra é a do formulário: o normal (obrigatório) não leva marca; a exceção
 * leva a palavra "se tiver".
 */
export function ListaDocumentos({
  documentos,
  titulo = "Documentos necessários",
  compacta,
  className,
}: {
  documentos: Documento[];
  titulo?: string;
  /** Na carta de serviços (cartão pequeno): itens mais juntos. */
  compacta?: boolean;
  className?: string;
}) {
  if (documentos.length === 0) return null;
  return (
    <div className={className}>
      <h3 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
        <FileText className="h-4 w-4 text-foreground-muted" aria-hidden="true" />
        {titulo}
      </h3>
      <ul className={cn("mt-2", compacta ? "space-y-1" : "space-y-2")}>
        {documentos.map((d, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
            <span className="min-w-0">
              <span className="text-foreground">{d.nome}</span>
              {!d.obrigatorio && (
                <span className="ml-1.5 text-xs text-foreground-subtle">(se tiver)</span>
              )}
              {d.descricao && (
                <span className="block text-xs text-foreground-muted">{d.descricao}</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
