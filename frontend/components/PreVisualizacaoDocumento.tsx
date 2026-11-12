"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { useDeferredValue, useEffect, useRef } from "react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Largura da folha A4 em px CSS (21 cm a 96 dpi) — para reduzir a folha ao espaço. */
const LARGURA_A4 = 794;

const TOKEN = /\{\{\s*[\w.]+\s*\}\}/g;

/** `{{campo}}` que sobrou no texto: sai literal no PDF, então a prévia acusa. */
export function camposPendentes(html: string): string[] {
  return Array.from(new Set(html.match(TOKEN) ?? []));
}

function escapar(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

/** Conteúdo da folha: o mesmo `<h1 class="doc-titulo">` + corpo que `html_to_pdf_bytes` monta. */
export function montarFolha(titulo: string, corpoHtml: string): string {
  const cabecalho = titulo.trim() ? `<h1 class="doc-titulo">${escapar(titulo.trim())}</h1>` : "";
  const corpo = corpoHtml.replace(
    TOKEN,
    (t) => `<mark class="campo-pendente" title="Campo não preenchido — sai assim no PDF">${t}</mark>`,
  );
  return cabecalho + corpo;
}

/**
 * Pré-visualização da minuta enquanto ela é editada (SI-30): o documento como
 * o PDF final vai sair, atualizado a cada tecla, sem salvar.
 *
 * - O estilo é o MESMO do PDF: vem de `GET /templates-documento/estilo-impressao`
 *   (o `CSS_DOCUMENTO` do `html_pdf.py`), não de uma cópia aqui. A moldura da
 *   tela (papel A4 sobre fundo cinza, destaque de campo) vem junto, em
 *   `css_tela` — aparência do documento, que o tema da aplicação não pinta.
 * - Num `<iframe>` para o CSS do documento não vazar para a tela nem o da tela
 *   para o documento. `sandbox` sem `allow-scripts`: nenhum script do conteúdo
 *   roda; `allow-same-origin` deixa as imagens do editor (rota autenticada)
 *   carregarem e deixa este componente escrever no corpo.
 * - Escreve só o miolo da folha a cada mudança, sem recarregar o iframe — a
 *   rolagem fica onde o usuário deixou.
 * - A folha tem a largura real do A4 e é reduzida para caber no espaço.
 *
 * O que NÃO mostra: a quebra de página. Ela é do motor de PDF; a prévia é uma
 * folha contínua.
 */
export function PreVisualizacaoDocumento({
  titulo,
  corpoHtml,
  className,
}: {
  titulo: string;
  corpoHtml: string;
  className?: string;
}) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const estiloQ = useQuery({
    queryKey: ["templates-documento", "estilo-impressao"],
    queryFn: () => api.templatesDocumento.estiloImpressao(),
    staleTime: Infinity,
  });
  // Digitação rápida não repinta a folha a cada tecla: o React entrega o
  // valor atrasado quando há folga.
  const titulo_ = useDeferredValue(titulo);
  const corpo_ = useDeferredValue(corpoHtml);
  const pendentes = camposPendentes(corpoHtml);

  // Monta o esqueleto uma vez por estilo carregado.
  useEffect(() => {
    const doc = iframeRef.current?.contentDocument;
    if (!doc || !estiloQ.data) return;
    doc.open();
    doc.write(
      `<!DOCTYPE html><html><head><meta charset="utf-8">` +
        `<style>${estiloQ.data.css}</style><style>${estiloQ.data.css_tela}</style>` +
        `</head><body><div class="folha"></div></body></html>`,
    );
    doc.close();
  }, [estiloQ.data]);

  // Escreve o conteúdo a cada mudança (sem recarregar: preserva a rolagem).
  useEffect(() => {
    const folha = iframeRef.current?.contentDocument?.querySelector(".folha");
    if (folha) folha.innerHTML = montarFolha(titulo_, corpo_);
  }, [titulo_, corpo_, estiloQ.data]);

  // Reduz a folha para caber na largura disponível.
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    const ajustar = () => {
      const html = iframe.contentDocument?.documentElement;
      if (!html) return;
      const escala = Math.min(1, (iframe.clientWidth - 24) / LARGURA_A4);
      html.style.setProperty("zoom", String(Math.max(0.3, escala)));
    };
    ajustar();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(ajustar);
    ro.observe(iframe);
    return () => ro.disconnect();
  }, [estiloQ.data]);

  return (
    <div className={cn("flex min-h-0 flex-col gap-2", className)}>
      {pendentes.length > 0 && (
        <p
          role="status"
          className="flex items-start gap-2 rounded-md bg-warning-soft px-3 py-2 text-xs text-warning-soft-foreground"
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>
            {pendentes.length === 1 ? "Um campo não foi preenchido" : `${pendentes.length} campos não foram preenchidos`}{" "}
            e {pendentes.length === 1 ? "vai" : "vão"} sair assim no PDF: {pendentes.join(", ")}
          </span>
        </p>
      )}
      {estiloQ.isError ? (
        <p role="alert" className="text-sm text-danger-soft-foreground">
          Não foi possível carregar o estilo do documento para a pré-visualização.
        </p>
      ) : (
        <iframe
          ref={iframeRef}
          title="Pré-visualização do documento"
          sandbox="allow-same-origin"
          className="min-h-[420px] w-full flex-1 rounded-md border border-border"
        />
      )}
    </div>
  );
}
