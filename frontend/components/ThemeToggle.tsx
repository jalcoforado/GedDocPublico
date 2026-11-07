"use client";

import { useId, useRef } from "react";
import { flushSync } from "react-dom";

import { type Theme, useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

type ComTransicao = Document & {
  startViewTransition?: (atualizar: () => void) => { ready: Promise<void> };
};

/** Aplica o tema no `<html>` na hora — o efeito do ThemeProvider chegaria
 * depois da captura da transição, e o "depois" sairia com o tema velho. */
function aplicarNoHtml(tema: Theme) {
  const root = document.documentElement;
  root.classList.toggle("dark", tema === "dark");
  root.dataset.theme = tema;
  root.style.colorScheme = tema;
}

/**
 * Chave claro ↔ escuro, no cabeçalho ao lado do sino (2026-11-06).
 *
 * Substitui o grupo de três botões (sistema / claro / escuro) do rodapé da
 * barra lateral. Sem preferência gravada o tema continua seguindo o sistema;
 * a chave só passa a mandar quando alguém a usa.
 *
 * Duas animações, no espírito da chave do Telegram: o sol vira lua dentro do
 * botão, e o tema novo se espalha pela tela num círculo que nasce do próprio
 * botão (View Transitions API). Navegador sem a API, ou quem pediu menos
 * movimento, troca de tema na hora.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setPreference } = useTheme();
  const ref = useRef<HTMLButtonElement>(null);
  const mascara = useId();
  const escuro = theme === "dark";
  // O ícone mostra o destino: lua no tema claro, sol no escuro.
  const lua = !escuro;

  const alternar = () => {
    const proximo: Theme = escuro ? "light" : "dark";
    const doc = document as ComTransicao;
    const calmo = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (!doc.startViewTransition || calmo || !ref.current) {
      setPreference(proximo);
      return;
    }
    const r = ref.current.getBoundingClientRect();
    const x = r.left + r.width / 2;
    const y = r.top + r.height / 2;
    const raio = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    const t = doc.startViewTransition(() => {
      aplicarNoHtml(proximo);
      flushSync(() => setPreference(proximo));
    });
    t.ready
      .then(() =>
        document.documentElement.animate(
          { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${raio}px at ${x}px ${y}px)`] },
          { duration: 480, easing: "cubic-bezier(0.4, 0, 0.2, 1)", pseudoElement: "::view-transition-new(root)" },
        ),
      )
      .catch(() => {});
  };

  return (
    <button
      ref={ref}
      type="button"
      role="switch"
      aria-checked={escuro}
      aria-label="Tema escuro"
      title={escuro ? "Mudar para o tema claro" : "Mudar para o tema escuro"}
      onClick={alternar}
      className={cn(
        // Botão de ícone, do tamanho do sino ao lado — sem trilho nem botão
        // deslizante. O ícone mostra o tema para onde se vai: lua no claro,
        // sol no escuro.
        "group relative inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md text-foreground",
        "transition-colors duration-fast hover:bg-muted",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="inline-flex transition-transform duration-slow ease-out-expo group-active:scale-90 motion-reduce:transition-none"
      >
        {/* Sol ↔ lua: o disco cresce, um segundo círculo (máscara)
            entra pela diagonal e recorta o crescente, os raios giram e somem. */}
        <svg viewBox="0 0 24 24" className="h-5 w-5 overflow-visible">
          <mask id={mascara}>
            <rect x="0" y="0" width="24" height="24" fill="white" />
            <circle
              cx="12"
              cy="12"
              r="9"
              fill="black"
              className="transition-transform duration-slow ease-out-expo motion-reduce:transition-none"
              style={{ transform: lua ? "translate(5px, -5px)" : "translate(14px, -14px)" }}
            />
          </mask>
          <circle
            cx="12"
            cy="12"
            r="8"
            fill="currentColor"
            mask={`url(#${mascara})`}
            className="origin-center transition-transform duration-slow ease-out-expo motion-reduce:transition-none"
            style={{ transform: lua ? "scale(1)" : "scale(0.6)", transformBox: "fill-box" }}
          />
          <g
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            className="transition-[transform,opacity] duration-slow ease-out-expo motion-reduce:transition-none"
            style={{
              transformOrigin: "12px 12px",
              transform: lua ? "rotate(-90deg) scale(0.4)" : "rotate(0deg) scale(1)",
              opacity: lua ? 0 : 1,
            }}
          >
            <line x1="12" y1="1" x2="12" y2="3" />
            <line x1="12" y1="21" x2="12" y2="23" />
            <line x1="1" y1="12" x2="3" y2="12" />
            <line x1="21" y1="12" x2="23" y2="12" />
            <line x1="4.2" y1="4.2" x2="5.6" y2="5.6" />
            <line x1="18.4" y1="18.4" x2="19.8" y2="19.8" />
            <line x1="4.2" y1="19.8" x2="5.6" y2="18.4" />
            <line x1="18.4" y1="5.6" x2="19.8" y2="4.2" />
          </g>
        </svg>
      </span>
    </button>
  );
}
