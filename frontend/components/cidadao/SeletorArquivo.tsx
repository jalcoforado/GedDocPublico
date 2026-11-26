"use client";

import { FileText, RefreshCw, Upload, X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

import { EXTENSOES_PERMITIDAS, FORMATOS_EM_PALAVRAS, MAX_UPLOAD_MB, tamanhoLegivel } from "./formato";

interface SeletorArquivoProps {
  id?: string;
  arquivo: File | null;
  /** Arquivo escolhido no seletor do sistema (ou `null` ao remover). */
  onEscolher: (f: File | null) => void;
  /** Texto do alvo de toque quando não há arquivo. */
  chamada?: string;
  /** Repassados pelo `FormField` ao controle. */
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
  required?: boolean;
}

/**
 * Escolha de arquivo pensada para o celular: uma área grande para tocar
 * (abre a câmera/galeria/arquivos do aparelho), e, depois de escolhido, o
 * nome e o tamanho do arquivo com "Trocar" e "Remover" à vista. O `<input>`
 * nativo fica escondido mas é ele que recebe o foco e o `aria-*` do
 * `FormField` — teclado e leitor de tela continuam funcionando.
 */
export function SeletorArquivo({
  id,
  arquivo,
  onEscolher,
  chamada = "Toque para escolher o arquivo",
  required,
  ...aria
}: SeletorArquivoProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const invalido = aria["aria-invalid"] === true;

  return (
    // `relative` prende o input `sr-only` (absoluto) aqui dentro: sem ele, o
    // foco rolava a página até o topo do documento.
    <div className="relative">
      <input
        ref={inputRef}
        id={id}
        type="file"
        required={required}
        accept={EXTENSOES_PERMITIDAS.map((e) => `.${e}`).join(",")}
        onChange={(e) => {
          onEscolher(e.target.files?.[0] ?? null);
          // Limpa o valor para que escolher o MESMO arquivo de novo (depois
          // de remover) ainda dispare o onChange.
          e.target.value = "";
        }}
        className="peer sr-only"
        {...aria}
      />
      {arquivo ? (
        <div className="flex items-center gap-3 rounded-lg border border-border bg-surface-1 p-3">
          <div
            aria-hidden="true"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-brand/10 text-brand"
          >
            <FileText className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-foreground">{arquivo.name}</div>
            <div className="text-xs text-foreground-muted">{tamanhoLegivel(arquivo.size)}</div>
          </div>
          <div className="flex shrink-0 gap-1">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              aria-label="Trocar arquivo"
              title="Trocar arquivo"
              className="inline-flex h-11 w-11 items-center justify-center rounded-md text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => onEscolher(null)}
              aria-label="Remover arquivo"
              title="Remover arquivo"
              className="inline-flex h-11 w-11 items-center justify-center rounded-md text-foreground-muted transition-colors duration-fast hover:bg-danger-soft hover:text-danger-soft-foreground"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      ) : (
        <label
          htmlFor={id}
          className={cn(
            "flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-6 text-center transition-colors duration-fast",
            "peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-background",
            invalido
              ? "border-danger/60 bg-danger-soft/40"
              : "border-border-strong bg-surface-1 hover:border-brand/60 hover:bg-muted",
          )}
        >
          <span
            aria-hidden="true"
            className="flex h-11 w-11 items-center justify-center rounded-full bg-brand/10 text-brand"
          >
            <Upload className="h-5 w-5" />
          </span>
          <span className="text-sm font-medium text-foreground">{chamada}</span>
          <span className="text-xs text-foreground-muted">
            {FORMATOS_EM_PALAVRAS} · até {MAX_UPLOAD_MB} MB
          </span>
        </label>
      )}
    </div>
  );
}
