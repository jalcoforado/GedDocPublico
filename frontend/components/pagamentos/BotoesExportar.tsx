"use client";

/**
 * Botões de exportação das listagens de Pagamentos (Onda C).
 *
 * **Por que um componente e não um botão solto por tela:** a C1.1 entregou o
 * endpoint de export de débitos em 2026-08-07 e nenhuma tela ganhou botão —
 * o recurso ficou alcançável só digitando a URL, e ninguém no município
 * descobriria. Concentrar a UI aqui torna "exportar" uma coisa só, com o
 * mesmo aspecto em toda tela, e faz o esquecimento aparecer como ausência
 * visível do componente em vez de como nada.
 *
 * É um `<a download>` e não `fetch`+`blob`: o navegador já baixa com o cookie
 * de sessão, já mostra progresso e já trata erro de rede. Reimplementar isso
 * em JS acrescentaria estados para manter sem melhorar nada — mesmo raciocínio
 * do `ordens.pdfUrl`, que existe desde a R2.
 */

import { Download, FileSpreadsheet, FileText } from "lucide-react";

import { Button } from "@/components/ui/button";

interface Props {
  /** URL do CSV. Obrigatório: toda listagem exporta ao menos em planilha. */
  csvUrl: string;
  /** URL do PDF, quando a listagem é um documento (painel, ordens). */
  pdfUrl?: string;
  /** Rótulo do que está sendo exportado, para o `aria-label` fazer sentido
   *  lido em voz alta ("Exportar painel de caixa em CSV"). */
  rotulo: string;
  className?: string;
}

export function BotoesExportar({ csvUrl, pdfUrl, rotulo, className }: Props) {
  return (
    <div className={`flex items-center gap-2 ${className ?? ""}`}>
      <Button asChild variant="secondary" size="sm">
        <a href={csvUrl} download aria-label={`Exportar ${rotulo} em CSV`}>
          <FileSpreadsheet className="mr-2 h-4 w-4" aria-hidden />
          CSV
        </a>
      </Button>
      {pdfUrl && (
        <Button asChild variant="secondary" size="sm">
          <a href={pdfUrl} download aria-label={`Exportar ${rotulo} em PDF`}>
            <FileText className="mr-2 h-4 w-4" aria-hidden />
            PDF
          </a>
        </Button>
      )}
    </div>
  );
}

/** Variante de um botão só, para cabeçalhos apertados. */
export function BotaoExportarCsv({ csvUrl, rotulo }: { csvUrl: string; rotulo: string }) {
  return (
    <Button asChild variant="secondary" size="sm">
      <a href={csvUrl} download aria-label={`Exportar ${rotulo} em CSV`}>
        <Download className="mr-2 h-4 w-4" aria-hidden />
        Exportar
      </a>
    </Button>
  );
}
