"use client";

import { BarChart3, Download, FileText, TrendingUp } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { RelatoriosNav } from "@/components/RelatoriosNav";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/lib/auth";

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
  const { can } = useAuth();
  return (
    <>
      <PageHeader
        icon={BarChart3}
        title="Relatórios"
        description="Onde os processos param, quem está com assinatura pendente e a lista para exportar. O endereço guarda o filtro: dá para mandar o link."
        actions={
          // O Dashboard executivo (/dashboard) não estava em menu nenhum: só
          // abria quem sabia o endereço. Mora aqui porque responde a mesma
          // pergunta em escala de gestão; quem não tem `dashboard` não vê.
          can("dashboard") ? (
            <Button asChild variant="secondary" size="sm">
              <Link href="/dashboard">
                <TrendingUp className="h-4 w-4" aria-hidden="true" /> Dashboard executivo
              </Link>
            </Button>
          ) : undefined
        }
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
