"use client";

/**
 * Mostra o PDF e um quadrado do selo que a pessoa arrasta até onde a
 * assinatura deve aparecer (SI-68). Devolve a posição pelo `onChange`, no
 * formato que o backend espera (`lib/selo-assinatura.ts`).
 *
 * O PDF mostrado é o CARIMBADO (com os selos de quem já assinou), para a
 * pessoa ver o que já ocupa a página; se ele falhar, tenta o original. Se
 * nenhum abrir, avisa e devolve `null` — a assinatura segue sem selo, como
 * antes, em vez de travar quem precisa assinar.
 */

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { abrirPdf, type DocumentoPdf, type PaginaPdf } from "@/lib/pdf-render";
import {
  fracaoDoSelo,
  limitarPosicao,
  moverComTeclado,
  posicaoDoPonteiro,
  posicaoInicial,
  type PosicaoSelo,
} from "@/lib/selo-assinatura";

interface Props {
  /** URLs a tentar, em ordem. */
  fontes: string[];
  onChange: (posicao: PosicaoSelo | null) => void;
}

const arred = (v: number) => Math.round(v * 10000) / 10000;

export function PosicionarSelo({ fontes, onChange }: Props) {
  const [doc, setDoc] = useState<DocumentoPdf | null>(null);
  const [estado, setEstado] = useState<"carregando" | "pronto" | "erro">("carregando");
  const [numero, setNumero] = useState(1);
  const [pagina, setPagina] = useState<PaginaPdf | null>(null);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const [escala, setEscala] = useState(1);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const areaRef = useRef<HTMLDivElement>(null);
  const caixaRef = useRef<HTMLDivElement>(null);
  const seloRef = useRef<HTMLButtonElement>(null);
  const pega = useRef<{ x: number; y: number } | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const chaveFontes = fontes.join("|");

  // 1. Abre o documento (primeira fonte que funcionar).
  useEffect(() => {
    let cancelado = false;
    let aberto: DocumentoPdf | null = null;
    setEstado("carregando");
    setDoc(null);
    setPagina(null);
    setPos(null);
    (async () => {
      for (const url of chaveFontes.split("|").filter(Boolean)) {
        try {
          const d = await abrirPdf(url);
          if (cancelado) {
            d.fechar();
            return;
          }
          aberto = d;
          // A assinatura costuma ir na última página.
          setNumero(d.numPaginas);
          setDoc(d);
          setEstado("pronto");
          return;
        } catch {
          // tenta a próxima fonte
        }
      }
      if (!cancelado) {
        setEstado("erro");
        onChangeRef.current(null);
      }
    })();
    return () => {
      cancelado = true;
      aberto?.fechar();
    };
  }, [chaveFontes]);

  // 2. Carrega a página escolhida; a posição é mantida, mas cabendo nela.
  useEffect(() => {
    if (!doc) return;
    let cancelado = false;
    doc
      .pagina(numero)
      .then((p) => {
        if (cancelado) return;
        setPagina(p);
        setPos((atual) => (atual ? limitarPosicao(atual.x, atual.y, p) : posicaoInicial(p)));
      })
      .catch(() => {
        if (!cancelado) {
          setEstado("erro");
          onChangeRef.current(null);
        }
      });
    return () => {
      cancelado = true;
    };
  }, [doc, numero]);

  // 3. Escala: a página inteira à vista, sem rolar, para arrastar com folga.
  useEffect(() => {
    if (!pagina) return;
    const calcular = () => {
      const largura = caixaRef.current?.clientWidth || pagina.larguraPt;
      const alturaMax = Math.max(window.innerHeight * 0.6, 320);
      setEscala(Math.min(largura / pagina.larguraPt, alturaMax / pagina.alturaPt));
    };
    calcular();
    window.addEventListener("resize", calcular);
    return () => window.removeEventListener("resize", calcular);
  }, [pagina]);

  // 4. Desenha.
  useEffect(() => {
    if (!pagina || !canvasRef.current) return;
    pagina.desenhar(canvasRef.current, escala).catch(() => {
      // cancelado por um desenho mais novo, ou falha pontual: o quadrado
      // continua utilizável sobre a área da página
    });
  }, [pagina, escala]);

  // 5. Avisa a posição.
  useEffect(() => {
    if (estado !== "pronto" || !pos || !pagina) return;
    onChangeRef.current({ pagina: numero, x: arred(pos.x), y: arred(pos.y) });
  }, [estado, pos, pagina, numero]);

  if (estado === "erro") {
    return (
      <div
        role="status"
        className="rounded-md bg-warning-soft px-3 py-2 text-sm text-warning-soft-foreground"
      >
        Não foi possível mostrar o documento aqui. Você ainda pode assinar; a assinatura fica
        registrada, mas sem o selo na página.
      </div>
    );
  }

  const total = doc?.numPaginas ?? 0;
  const fracao = pagina ? fracaoDoSelo(pagina) : null;

  function iniciarArraste(e: React.PointerEvent<HTMLDivElement>) {
    if (!pagina || !areaRef.current) return;
    const area = areaRef.current.getBoundingClientRect();
    const selo = seloRef.current?.getBoundingClientRect();
    if (selo && seloRef.current?.contains(e.target as Node) && selo.width > 0) {
      // Segura o quadrado no ponto onde foi pego — não dá salto.
      pega.current = {
        x: (e.clientX - selo.left) / selo.width,
        y: (e.clientY - selo.top) / selo.height,
      };
    } else {
      // Clique na página: o quadrado vem para o ponto clicado.
      pega.current = { x: 0.5, y: 0.5 };
      setPos(posicaoDoPonteiro(e.clientX, e.clientY, area, pagina));
    }
    e.currentTarget.setPointerCapture?.(e.pointerId);
    seloRef.current?.focus();
    e.preventDefault();
  }

  function arrastar(e: React.PointerEvent<HTMLDivElement>) {
    if (!pega.current || !pagina || !areaRef.current) return;
    const area = areaRef.current.getBoundingClientRect();
    setPos(posicaoDoPonteiro(e.clientX, e.clientY, area, pagina, pega.current));
  }

  function soltar() {
    pega.current = null;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <Button
          variant="ghost"
          size="sm"
          aria-label="Página anterior"
          disabled={!doc || numero <= 1}
          onClick={() => setNumero((n) => Math.max(1, n - 1))}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="text-sm text-foreground-muted tabular-nums" aria-live="polite">
          {doc ? `Página ${numero} de ${total}` : "Carregando documento…"}
        </span>
        <Button
          variant="ghost"
          size="sm"
          aria-label="Próxima página"
          disabled={!doc || numero >= total}
          onClick={() => setNumero((n) => Math.min(total, n + 1))}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      <div ref={caixaRef} className="flex justify-center rounded-md bg-muted p-2">
        <div
          ref={areaRef}
          data-testid="area-pagina"
          className="relative cursor-crosshair touch-none select-none bg-background shadow-sm"
          onPointerDown={iniciarArraste}
          onPointerMove={arrastar}
          onPointerUp={soltar}
          onPointerCancel={soltar}
        >
          <canvas ref={canvasRef} className="block" aria-hidden="true" />
          {!pagina && <div className="h-[420px] w-[300px] animate-pulse bg-muted/60" />}
          {pagina && pos && fracao && (
            <button
              ref={seloRef}
              type="button"
              aria-label={`Posição da assinatura na página ${numero}. Arraste ou use as setas para mover.`}
              onKeyDown={(e) => {
                const nova = moverComTeclado(e.key, e.shiftKey, pos, pagina);
                if (nova) {
                  e.preventDefault();
                  setPos(nova);
                }
              }}
              className="absolute flex cursor-move flex-col justify-center overflow-hidden rounded border-2 border-dashed border-primary bg-primary/10 px-1.5 text-left leading-tight text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              style={{
                left: `${pos.x * 100}%`,
                top: `${pos.y * 100}%`,
                width: `${fracao.largura * 100}%`,
                height: `${fracao.altura * 100}%`,
                fontSize: `${Math.max(7, 8 * escala)}px`,
              }}
            >
              <span className="font-semibold uppercase tracking-wide">Sua assinatura</span>
              <span className="text-foreground-muted">nome, cargo, data e hora, código</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
