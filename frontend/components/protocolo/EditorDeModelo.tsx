"use client";

import { Blocks, Eye, EyeOff, Type } from "lucide-react";
import { useEffect, useState } from "react";

import { PreVisualizacaoDocumento } from "@/components/PreVisualizacaoDocumento";
import { MontadorTemplate, type CampoDisponivel } from "@/components/protocolo/MontadorTemplate";
import { RichTextEditor } from "@/components/ui/rich-text-editor";
import type { Bloco } from "@/lib/template-blocos";
import { cn } from "@/lib/utils";

/** Montar com blocos (SI-31) ou editar o HTML corrido no editor de texto. */
export type ModoEdicao = "blocos" | "livre";

/** Preferência de quem usa, neste navegador: abre como deixou da última vez. */
const CHAVE_PREVIA = "aprimora.modelo.previa";

function lerPrevia(): boolean {
  try {
    return window.localStorage.getItem(CHAVE_PREVIA) !== "0";
  } catch {
    return true;
  }
}

/**
 * O conteúdo do modelo de documento: o seletor de modo (blocos × editor
 * livre), a chave da prévia e, conforme a chave, a pré-visualização ao lado.
 *
 * Prévia desligada = o editor ocupa a largura toda. É o que se quer ao montar
 * um modelo comprido; ligada, confere-se como sai no PDF. A escolha fica
 * guardada neste navegador.
 */
export function EditorDeModelo({
  modo,
  onTrocarModo,
  blocos,
  onBlocos,
  corpoHtml,
  onCorpoHtml,
  campos,
  onUploadImage,
}: {
  modo: ModoEdicao;
  onTrocarModo: (m: ModoEdicao) => void;
  blocos: Bloco[];
  onBlocos: (b: Bloco[]) => void;
  corpoHtml: string;
  onCorpoHtml: (html: string) => void;
  campos: CampoDisponivel[];
  onUploadImage?: (file: File) => Promise<string>;
}) {
  const [verPrevia, setVerPrevia] = useState(lerPrevia);
  useEffect(() => {
    try {
      window.localStorage.setItem(CHAVE_PREVIA, verPrevia ? "1" : "0");
    } catch {
      /* navegador sem armazenamento: vale só nesta abertura */
    }
  }, [verPrevia]);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-foreground-muted">
          {modo === "blocos"
            ? "Monte o documento com blocos."
            : "Texto corrido. Voltar para blocos junta o que não for bloco num bloco de Texto."}
        </p>
        <div className="flex items-center gap-2">
          <div
            role="group"
            aria-label="Modo de edição do modelo"
            className="inline-flex rounded-md border border-border bg-surface-1 p-0.5"
          >
            {(
              [
                ["blocos", "Montar com blocos", Blocks],
                ["livre", "Editor livre", Type],
              ] as const
            ).map(([valor, nome, Icone]) => (
              <button
                key={valor}
                type="button"
                aria-pressed={modo === valor}
                onClick={() => onTrocarModo(valor)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs font-medium transition-colors duration-fast",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  modo === valor
                    ? "bg-card text-foreground shadow-sm"
                    : "text-foreground-muted hover:text-foreground",
                )}
              >
                <Icone className="h-3.5 w-3.5" aria-hidden="true" />
                {nome}
              </button>
            ))}
          </div>
          <button
            type="button"
            aria-pressed={verPrevia}
            onClick={() => setVerPrevia((v) => !v)}
            title={verPrevia ? "Esconder a prévia e usar a largura toda" : "Ver ao lado como o modelo sai no PDF"}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors duration-fast",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              verPrevia
                ? "border-brand/40 bg-brand/10 text-brand"
                : "border-border bg-surface-1 text-foreground-muted hover:text-foreground",
            )}
          >
            {verPrevia ? (
              <Eye className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <EyeOff className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            Prévia
          </button>
        </div>
      </div>

      <div className={cn("grid gap-4", verPrevia && "lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]")}>
        <div className="min-w-0">
          {modo === "blocos" ? (
            <MontadorTemplate
              blocos={blocos}
              onChange={onBlocos}
              campos={campos}
              onUploadImage={onUploadImage}
            />
          ) : (
            <RichTextEditor
              value={corpoHtml}
              onChange={onCorpoHtml}
              minHeight={280}
              ariaLabel="Conteúdo do template"
              campos={campos}
              onUploadImage={onUploadImage}
            />
          )}
        </div>
        {verPrevia && (
          <div className="lg:sticky lg:top-0 lg:self-start">
            <PreVisualizacaoDocumento
              titulo=""
              corpoHtml={corpoHtml}
              modelo
              className="h-[min(44rem,62vh)]"
            />
          </div>
        )}
      </div>
    </div>
  );
}
