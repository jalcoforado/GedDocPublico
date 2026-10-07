"use client";

import "leaflet/dist/leaflet.css";

import type { LayerGroup, Map as LeafletMap } from "leaflet";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

export type LatLng = [number, number];

/**
 * Tons de série do mapa, em tokens do Design System. O Leaflet grava cor como
 * atributo de apresentação do SVG (`stroke="…"`), onde `var(--…)` não vale —
 * por isso a cor entra por CLASSE, que vence o atributo. As classes ficam
 * escritas por extenso para o Tailwind enxergá-las.
 */
export const MAPA_TONS = {
  brand: { traco: "stroke-brand", ponto: "fill-brand", chip: "bg-brand" },
  accent: { traco: "stroke-accent", ponto: "fill-accent", chip: "bg-accent" },
  success: { traco: "stroke-success", ponto: "fill-success", chip: "bg-success" },
  warning: { traco: "stroke-warning", ponto: "fill-warning", chip: "bg-warning" },
  danger: { traco: "stroke-danger", ponto: "fill-danger", chip: "bg-danger" },
  info: { traco: "stroke-info", ponto: "fill-info", chip: "bg-info" },
  "brand-dark": { traco: "stroke-brand-dark", ponto: "fill-brand-dark", chip: "bg-brand-dark" },
  "accent-dark": { traco: "stroke-accent-dark", ponto: "fill-accent-dark", chip: "bg-accent-dark" },
} as const;

export type MapaTom = keyof typeof MAPA_TONS;

export const MAPA_TONS_EM_ORDEM = Object.keys(MAPA_TONS) as MapaTom[];

export interface MapaTrajeto {
  tom: MapaTom;
  pontos: LatLng[];
}

export interface MapaMarcador {
  posicao: LatLng;
  tom: MapaTom;
  titulo: string;
  /** Linhas do balão, abaixo do título. */
  linhas?: string[];
}

interface MapaProps {
  /** Enquadramento usado enquanto não há nada para desenhar. */
  centro: LatLng;
  zoom?: number;
  trajetos?: MapaTrajeto[];
  marcadores?: MapaMarcador[];
  ariaLabel: string;
  className?: string;
}

/** Balão montado com `textContent`: título e linhas vêm do banco (nome de
 *  ponto, placa), e o `bindPopup` com string interpretaria como HTML. */
function balao(m: MapaMarcador): HTMLElement {
  const el = document.createElement("div");
  const titulo = document.createElement("strong");
  titulo.textContent = m.titulo;
  el.appendChild(titulo);
  for (const linha of m.linhas ?? []) {
    const div = document.createElement("div");
    div.textContent = linha;
    el.appendChild(div);
  }
  return el;
}

/** Mapa Leaflet + OpenStreetMap, com trajetos e marcadores em tons do tema. */
export function Mapa({
  centro,
  zoom = 13,
  trajetos,
  marcadores,
  ariaLabel,
  className,
}: MapaProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const [pronto, setPronto] = useState(false);
  // Só o enquadramento INICIAL: mudar `centro` depois não deve tirar o mapa de
  // onde o usuário o deixou.
  const inicial = useRef({ centro, zoom });

  // Cria o mapa uma vez. `import()` dinâmico: o Leaflet toca em `window` ao
  // carregar e quebraria a renderização no servidor.
  useEffect(() => {
    let cancelado = false;
    import("leaflet").then((L) => {
      if (cancelado || !containerRef.current || mapRef.current) return;
      const map = L.map(containerRef.current).setView(
        inicial.current.centro,
        inicial.current.zoom,
      );
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map);
      mapRef.current = map;
      setPronto(true);
    });
    return () => {
      cancelado = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  // Redesenha a cada mudança de dados e enquadra o que foi desenhado.
  useEffect(() => {
    const map = mapRef.current;
    if (!pronto || !map) return;
    let camada: LayerGroup | null = null;
    let cancelado = false;
    import("leaflet").then((L) => {
      if (cancelado) return;
      camada = L.layerGroup().addTo(map);
      const todos: LatLng[] = [];
      for (const t of trajetos ?? []) {
        if (t.pontos.length === 0) continue;
        todos.push(...t.pontos);
        L.polyline(t.pontos, {
          className: MAPA_TONS[t.tom].traco,
          weight: 3,
          opacity: 0.7,
        }).addTo(camada);
      }
      for (const m of marcadores ?? []) {
        todos.push(m.posicao);
        L.circleMarker(m.posicao, {
          radius: 8,
          className: `stroke-white ${MAPA_TONS[m.tom].ponto}`,
          weight: 2,
          fillOpacity: 1,
        })
          .bindPopup(balao(m))
          .addTo(camada);
      }
      if (todos.length > 0) {
        map.fitBounds(L.latLngBounds(todos), { padding: [40, 40], maxZoom: 16 });
      }
    });
    return () => {
      cancelado = true;
      camada?.remove();
    };
  }, [pronto, trajetos, marcadores]);

  return (
    <div
      ref={containerRef}
      aria-label={ariaLabel}
      className={cn(
        "relative z-0 h-[65vh] min-h-[24rem] overflow-hidden rounded-lg border border-border bg-surface-1",
        className,
      )}
    />
  );
}
