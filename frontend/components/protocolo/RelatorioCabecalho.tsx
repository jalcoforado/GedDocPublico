"use client";

import { BarChart3, Download, FileText } from "lucide-react";
import * as React from "react";

import { RelatoriosNav } from "@/components/RelatoriosNav";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";

/**
 * Topo comum dos três relatórios do Protocolo (Processos, Tramitação,
 * Assinaturas): o mesmo PageHeader, a navegação entre eles e a linha com o
 * nome do relatório e as exportações. Cada página desenhava o seu `<h1>`
 * laranja solto e os botões CSV/PDF como `<a>` com classe à mão.
 */
export function RelatorioCabecalho({
  subtitulo,
  csvUrl,
  pdfUrl,
  acoesExtras,
}: {
  subtitulo: string;
  csvUrl: string;
  pdfUrl: string;
  /** Ação além das exportações (ex.: gerar em background). */
  acoesExtras?: React.ReactNode;
}) {
  return (
    <>
      <PageHeader
        icon={BarChart3}
        title="Relatórios"
        description="Processos, tramitação e assinaturas em números, com exportação em CSV e PDF."
      />
      <RelatoriosNav />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-semibold text-foreground">{subtitulo}</h2>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="secondary" size="sm">
            <a href={csvUrl} target="_blank" rel="noreferrer">
              <Download className="h-4 w-4" aria-hidden="true" /> CSV
            </a>
          </Button>
          <Button asChild variant="secondary" size="sm">
            <a href={pdfUrl} target="_blank" rel="noreferrer">
              <FileText className="h-4 w-4" aria-hidden="true" /> PDF
            </a>
          </Button>
          {acoesExtras}
        </div>
      </div>
    </>
  );
}

/** Há filtro de fato? `setDraft` deixa chaves com `undefined` para trás. */
export function temFiltro(f: object): boolean {
  return Object.values(f).some((v) => v !== undefined && v !== null && v !== "" && v !== false);
}

/**
 * Rodapé da barra de filtros dos relatórios: o filtro é um rascunho até
 * "Gerar relatório"; "Limpar" só aparece quando há o que limpar.
 */
export function AcoesDoFiltro({
  filtrado,
  onGerar,
  onLimpar,
}: {
  filtrado: boolean;
  onGerar: () => void;
  onLimpar: () => void;
}) {
  return (
    <div className="ml-auto flex items-end gap-2">
      {filtrado && (
        <Button variant="ghost" onClick={onLimpar}>
          Limpar
        </Button>
      )}
      <Button onClick={onGerar}>Gerar relatório</Button>
    </div>
  );
}
