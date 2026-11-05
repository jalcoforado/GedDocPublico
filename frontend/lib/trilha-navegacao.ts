"use client";

import { useEffect, useState } from "react";

/**
 * O caminho que o usuário percorreu nesta aba (SI-17/SI-18).
 *
 * Serve a duas coisas: a seta de voltar do `PageHeader` leva à página de onde
 * se veio *de verdade* (veio do painel, volta ao painel), e todo link de volta
 * para uma lista — seta ou trilha — chega com os filtros como estavam.
 *
 * Por que não `router.back()`: depois de editar um rascunho a tela vai para o
 * processo, e "voltar" cairia de novo no formulário. Aqui a trilha é uma
 * pilha por endereço: revisitar uma página corta tudo o que veio depois dela,
 * então lista → processo → editar → processo deixa [lista, processo], e a
 * seta do processo leva à lista.
 *
 * Fica no `sessionStorage`: sobrevive a recarregar a página, morre com a aba.
 * Sem ele (modo privado, armazenamento bloqueado) a seta cai na tela-mãe.
 */

const CHAVE = "aprimora.trilha.v1";
const EVENTO = "aprimora:trilha";
const MAXIMO = 30;

function caminhoDe(url: string): string {
  return url.split("?")[0].split("#")[0];
}

function ler(): string[] {
  try {
    const bruto = window.sessionStorage.getItem(CHAVE);
    const lido: unknown = bruto ? JSON.parse(bruto) : [];
    return Array.isArray(lido) ? lido.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function gravar(trilha: string[]) {
  try {
    window.sessionStorage.setItem(CHAVE, JSON.stringify(trilha.slice(-MAXIMO)));
  } catch {
    // Armazenamento indisponível: a seta cai na tela-mãe, nada quebra.
  }
  window.dispatchEvent(new Event(EVENTO));
}

/** Registra a visita a `url` (caminho + query). Mesma página com outra query
 * — trocar filtro, aba, página — atualiza a entrada em vez de empilhar. */
export function registrarVisita(url: string) {
  const trilha = ler();
  const caminho = caminhoDe(url);
  let i = -1;
  for (let k = trilha.length - 1; k >= 0; k--) {
    if (caminhoDe(trilha[k]) === caminho) {
      i = k;
      break;
    }
  }
  gravar(i >= 0 ? [...trilha.slice(0, i), url] : [...trilha, url]);
}

/** Para onde a seta leva quem está em `caminhoAtual`: a última página
 * visitada que não é esta. `null` se a aba começou aqui. */
export function destinoDeVolta(trilha: string[], caminhoAtual: string): string | null {
  for (let k = trilha.length - 1; k >= 0; k--) {
    if (caminhoDe(trilha[k]) !== caminhoAtual) return trilha[k];
  }
  return null;
}

/** `href` de uma lista, com os filtros com que ela foi vista por último.
 * `href` que já traz query fica como está — quem o montou sabia o que queria. */
export function comFiltrosLembrados(trilha: string[], href: string): string {
  if (href.includes("?")) return href;
  for (let k = trilha.length - 1; k >= 0; k--) {
    if (caminhoDe(trilha[k]) === href) return trilha[k];
  }
  return href;
}

/** A trilha, relida quando muda. Vazia no primeiro render (no servidor não
 * há `sessionStorage`), para não divergir da hidratação. */
export function useTrilha(): string[] {
  const [trilha, setTrilha] = useState<string[]>([]);
  useEffect(() => {
    const atualizar = () => setTrilha(ler());
    atualizar();
    window.addEventListener(EVENTO, atualizar);
    return () => window.removeEventListener(EVENTO, atualizar);
  }, []);
  return trilha;
}
