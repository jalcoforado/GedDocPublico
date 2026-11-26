"use client";

// Peças dos formulários da Frota (todos em diálogo). A regra de erro é a do
// padrão de formulário (docs/design-system.md): nada em vermelho ao abrir; o
// erro aparece sob o campo depois que a pessoa sai dele ou tenta enviar, e o
// envio com erro leva o foco ao primeiro campo a consertar.

import { useState } from "react";

import type { Veiculo } from "@/lib/api";

/**
 * Data de hoje em aaaa-mm-dd no fuso de quem usa. `toISOString()` daria a
 * data em UTC — depois das 21h em Brasília já seria "amanhã".
 */
export function hojeLocal(): string {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

/** "ABC1D23 — Fiat Strada": o que se reconhece numa lista de veículos. */
export function rotuloVeiculo(v: Pick<Veiculo, "placa" | "marca" | "modelo">): string {
  const nome = [v.marca, v.modelo].filter(Boolean).join(" ");
  return nome ? `${v.placa} — ${nome}` : v.placa;
}

/** "12.345 km". */
export function fmtKm(v: number): string {
  return `${v.toLocaleString("pt-BR")} km`;
}

/**
 * Erros visíveis de um formulário. `erros` é recalculado a cada render a
 * partir do estado do formulário, com as chaves = `id` dos campos, na ordem
 * em que aparecem na tela (é essa ordem que decide quem recebe o foco).
 *
 * - `erro(id)`: a mensagem, só se o campo já foi visitado ou houve tentativa
 *   de envio. Depois disso o erro acompanha a digitação e some ao consertar.
 * - `tocar(id)`: handler de `onBlur`.
 * - `podeEnviar()`: no clique do botão principal. Revela todos os erros e,
 *   havendo algum, foca o primeiro campo e devolve `false`. O botão nunca
 *   fica desabilitado por validação — clicar é o que mostra o que falta.
 * - `limpar()`: ao abrir o diálogo de novo.
 *
 * O foco vai pelo `id` (e não por `aria-invalid`) porque, no clique, o campo
 * ainda não foi redesenhado como inválido.
 */
export function useErrosDoFormulario(erros: Record<string, string | undefined>) {
  const [tocados, setTocados] = useState<Record<string, true>>({});
  const [tentou, setTentou] = useState(false);

  return {
    erro: (id: string) => (tentou || tocados[id] ? erros[id] : undefined),
    tocar: (id: string) => () => setTocados((t) => (t[id] ? t : { ...t, [id]: true })),
    podeEnviar: () => {
      setTentou(true);
      const primeiro = Object.keys(erros).find((id) => erros[id]);
      if (!primeiro) return true;
      document.getElementById(primeiro)?.focus();
      return false;
    },
    limpar: () => {
      setTocados({});
      setTentou(false);
    },
  };
}

/** Número digitado → número, ou `null` com o campo vazio. */
export function numeroOuNulo(v: string): number | null {
  return v.trim() === "" ? null : Number(v);
}
