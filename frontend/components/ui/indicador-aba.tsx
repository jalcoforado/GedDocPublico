"use client";

import { type RefObject, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Sublinhado que DESLIZA até a aba ativa, em vez de piscar de uma para a
 * outra. Vai dentro da própria lista de abas (que precisa ser `relative`):
 * mede a aba marcada pelo `seletor` e se posiciona por `transform`.
 *
 * Na primeira medida não anima — senão ele entraria correndo da esquerda a
 * cada tela aberta. Acompanha mudança de tamanho (contador que chega,
 * janela que muda) pelo ResizeObserver, quando o navegador o tem.
 */
export function IndicadorDeAba({
  lista,
  seletor,
  chave,
  className,
}: {
  lista: RefObject<HTMLElement | null>;
  /** Como achar a aba ativa dentro da lista. */
  seletor: string;
  /** Muda quando a aba ativa muda — dispara nova medida. */
  chave: unknown;
  className?: string;
}) {
  const [pos, setPos] = useState<{ x: number; w: number } | null>(null);
  const animar = useRef(false);

  // `useEffect`, não `useLayoutEffect`: o sublinhado mora DENTRO da lista que
  // mede, e o React roda o layout effect do filho antes de ligar a ref do
  // pai — a lista ainda seria `null` e ele nunca apareceria.
  useEffect(() => {
    const el = lista.current;
    if (!el) return;
    const medir = () => {
      const ativa = el.querySelector<HTMLElement>(seletor);
      const novo = ativa ? { x: ativa.offsetLeft, w: ativa.offsetWidth } : null;
      // Igual ao atual: não re-renderiza (o MutationObserver abaixo também
      // vê a própria inserção do sublinhado).
      setPos((p) => (p?.x === novo?.x && p?.w === novo?.w ? p : novo));
    };
    medir();
    // Na carga da página (hidratação) a primeira medida pode sair antes de a
    // aba ativa estar marcada — e nada mais a repetiria. Mede de novo no
    // quadro seguinte e sempre que a marca de "ativa" mudar de lugar.
    const quadro = requestAnimationFrame(medir);
    const mo = new MutationObserver(medir);
    mo.observe(el, { subtree: true, childList: true, attributeFilter: ["aria-current", "aria-selected"] });
    const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(medir);
    ro?.observe(el);
    return () => {
      cancelAnimationFrame(quadro);
      mo.disconnect();
      ro?.disconnect();
    };
  }, [lista, seletor, chave]);

  useEffect(() => {
    if (!pos) return;
    // A partir do quadro seguinte à primeira posição, as trocas deslizam.
    const id = requestAnimationFrame(() => {
      animar.current = true;
    });
    return () => cancelAnimationFrame(id);
  }, [pos]);

  if (!pos) return null;
  return (
    <span
      aria-hidden="true"
      data-indicador-aba=""
      className={cn(
        "pointer-events-none absolute bottom-0 left-0 h-0.5 rounded-full bg-primary",
        animar.current && "transition-[transform,width] duration-base ease-out-expo motion-reduce:transition-none",
        className,
      )}
      style={{ width: pos.w, transform: `translateX(${pos.x}px)` }}
    />
  );
}
