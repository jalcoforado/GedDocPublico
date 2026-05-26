"use client";

import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/**
 * Barra de loading global no topo (estilo NProgress, sem a lib).
 * Ativa quando:
 *   - react-query tem fetch ou mutation em andamento
 *   - rota acabou de mudar (briefly, ~250ms — dá feedback visual no clique)
 *
 * Posicionada via fixed top-0, z-index altíssimo (acima do header sticky).
 */
export function LoadingBar() {
  const isFetching = useIsFetching();
  const isMutating = useIsMutating();
  const pathname = usePathname();

  const active = isFetching > 0 || isMutating > 0;

  const [visible, setVisible] = useState(false);
  const [progress, setProgress] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const routeFlashRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Flash on route change — força barra a piscar mesmo sem fetch (ex: rota estática)
  const lastRouteRef = useRef(pathname);
  useEffect(() => {
    if (lastRouteRef.current === pathname) return;
    lastRouteRef.current = pathname;
    setVisible(true);
    setProgress(40);
    if (routeFlashRef.current) clearTimeout(routeFlashRef.current);
    routeFlashRef.current = setTimeout(() => {
      // Se não tem fetch pendente, encerra o flash de rota
      if (!active) {
        setProgress(100);
        setTimeout(() => {
          setVisible(false);
          setProgress(0);
        }, 200);
      }
    }, 250);
  }, [pathname, active]);

  useEffect(() => {
    if (active) {
      if (hideTimerRef.current) {
        clearTimeout(hideTimerRef.current);
        hideTimerRef.current = null;
      }
      setVisible(true);
      // Easing assimptotic — sobe rápido, desacelera perto de 90%
      if (!timerRef.current) {
        setProgress((p) => Math.max(p, 15));
        timerRef.current = setInterval(() => {
          setProgress((p) => {
            if (p >= 90) return p;
            const remaining = 90 - p;
            return p + Math.max(0.5, remaining * 0.08);
          });
        }, 120);
      }
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      if (visible) {
        setProgress(100);
        hideTimerRef.current = setTimeout(() => {
          setVisible(false);
          setProgress(0);
        }, 200);
      }
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [active, visible]);

  if (!visible) return null;

  return (
    <div
      role="progressbar"
      aria-label="Carregando"
      aria-valuenow={Math.round(progress)}
      aria-valuemin={0}
      aria-valuemax={100}
      className="pointer-events-none fixed inset-x-0 top-0 z-[200] h-0.5"
    >
      <div
        className="h-full bg-gradient-to-r from-brand via-brand-light to-accent shadow-[0_0_8px_rgba(217,119,6,0.5)]"
        style={{
          width: `${progress}%`,
          transition: progress === 100 ? "width 200ms ease-out" : "width 220ms ease-out",
        }}
      />
    </div>
  );
}
