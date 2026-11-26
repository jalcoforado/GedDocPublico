"use client";

import { useIsMutating } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { type CSSProperties, useCallback, useEffect, useRef, useState } from "react";

/**
 * Barra de progresso no topo, na troca de tela e enquanto algo é salvo.
 *
 * A versão anterior tinha três defeitos que juntos davam a sensação de
 * travamento (2026-11-06):
 * - só começava DEPOIS que a URL mudava — ou seja, depois que a tela nova já
 *   tinha carregado. A espera de verdade (clique → tela) passava sem barra, e
 *   ela aparecia no fim, quando já não informava nada;
 * - andava por `setInterval` de 120ms mexendo em `width`: um degrau a cada
 *   tique, com layout recalculado em cada um;
 * - qualquer busca em segundo plano (sino, contadores, refetch ao voltar à
 *   aba) acendia a barra, que piscava sem o usuário ter feito nada.
 *
 * Agora ela começa no CLIQUE do link e anda por transições CSS de
 * `transform` — o compositor anima; o React só troca de fase três vezes. Uma
 * transição interrompida parte do ponto em que está, então "terminar" no
 * meio da espera completa a partir dali, sem pulo. Termina quando a URL nova
 * é publicada no `history`. Buscas de fundo não acendem; gravações
 * (`useIsMutating`) sim — são ação do usuário esperando resposta.
 */

type Fase = "parada" | "inicio" | "andando" | "terminando";

/** Teto de espera: navegação cancelada (link interceptado por outro handler,
 * por exemplo) fecha a barra em vez de deixá-la parada no topo. */
const TETO_MS = 10_000;

const ESTILO: Record<Exclude<Fase, "parada">, CSSProperties> = {
  // Nasce em zero, sem transição; no quadro seguinte vai para "andando".
  inicio: { transform: "scaleX(0)", transition: "none" },
  // Sobe rápido e desacelera: ~60% no primeiro segundo, nunca chega a 90%.
  andando: {
    transform: "scaleX(0.88)",
    transition: `transform ${TETO_MS}ms cubic-bezier(0.05, 0.8, 0.1, 1)`,
  },
  terminando: {
    transform: "scaleX(1)",
    opacity: 0,
    transition: "transform 200ms var(--ease-out), opacity 250ms ease 200ms",
  },
};

function ehNavegacaoInterna(ev: MouseEvent): boolean {
  if (ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return false;
  const a = (ev.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
  if (!a || a.target === "_blank" || a.hasAttribute("download")) return false;
  const url = new URL(a.href, window.location.href);
  if (url.origin !== window.location.origin) return false;
  // Mesma tela (ou só a âncora): não há o que carregar.
  return url.pathname + url.search !== window.location.pathname + window.location.search;
}

export function LoadingBar() {
  const salvando = useIsMutating() > 0;
  const pathname = usePathname();
  const [fase, setFase] = useState<Fase>("parada");
  const faseRef = useRef<Fase>("parada");
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const quadro = useRef(0);

  const mudar = useCallback((f: Fase) => {
    faseRef.current = f;
    setFase(f);
  }, []);
  const limpar = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    cancelAnimationFrame(quadro.current);
  }, []);

  const terminar = useCallback(() => {
    const f = faseRef.current;
    if (f !== "andando" && f !== "inicio") return;
    limpar();
    mudar("terminando");
    timers.current.push(setTimeout(() => mudar("parada"), 500));
  }, [limpar, mudar]);

  const iniciar = useCallback(() => {
    if (faseRef.current === "andando") return;
    limpar();
    mudar("inicio");
    // Dois quadros: o primeiro pinta o zero, o segundo dispara a transição.
    quadro.current = requestAnimationFrame(() => {
      quadro.current = requestAnimationFrame(() => mudar("andando"));
    });
    timers.current.push(setTimeout(terminar, TETO_MS));
  }, [limpar, mudar, terminar]);

  // Começa no clique — em captura, porque o `<Link>` do Next cancela o
  // evento e navega por conta própria.
  useEffect(() => {
    const aoClicar = (ev: MouseEvent) => {
      if (ehNavegacaoInterna(ev)) iniciar();
    };
    document.addEventListener("click", aoClicar, true);
    return () => document.removeEventListener("click", aoClicar, true);
  }, [iniciar]);

  // Termina quando a URL nova chega: o App Router publica a rota com
  // pushState/replaceState depois de montar a tela; voltar/avançar é popstate.
  useEffect(() => {
    const { pushState, replaceState } = window.history;
    window.history.pushState = function (...args) {
      terminar();
      return pushState.apply(this, args);
    };
    window.history.replaceState = function (...args) {
      terminar();
      return replaceState.apply(this, args);
    };
    window.addEventListener("popstate", terminar);
    return () => {
      window.history.pushState = pushState;
      window.history.replaceState = replaceState;
      window.removeEventListener("popstate", terminar);
    };
  }, [terminar]);

  // Rede de segurança: rota que mudou sem passar pelo history acima.
  useEffect(() => {
    terminar();
  }, [pathname, terminar]);

  useEffect(() => {
    if (salvando) iniciar();
    else terminar();
  }, [salvando, iniciar, terminar]);

  useEffect(() => limpar, [limpar]);

  if (fase === "parada") return null;

  return (
    <div
      role="progressbar"
      aria-label="Carregando"
      className="pointer-events-none fixed inset-x-0 top-0 z-toast h-[3px]"
    >
      <div
        className="h-full origin-left bg-accent motion-reduce:!transition-none"
        style={ESTILO[fase]}
      />
    </div>
  );
}
