/**
 * SI-19 — o clique no título de coluna, padronizado. O desenho (setinha,
 * `aria-sort`) já mora no `<TH sortable>` de `components/ui/table.tsx`; aqui
 * fica só a regra de qual é a próxima ordenação, para toda tabela fazer igual:
 * coluna nova começa crescente, a mesma coluna alterna.
 */

export type Direcao = "asc" | "desc";

export interface Ordenacao<C extends string> {
  campo: C;
  direcao: Direcao;
}

export function proximaOrdenacao<C extends string>(
  atual: Ordenacao<C> | undefined,
  campo: C,
): Ordenacao<C> {
  if (atual?.campo !== campo) return { campo, direcao: "asc" };
  return { campo, direcao: atual.direcao === "asc" ? "desc" : "asc" };
}

/** O `sortState` que o `<TH sortable>` espera para esta coluna. */
export function estadoDaColuna<C extends string>(
  atual: Ordenacao<C> | undefined,
  campo: C,
): Direcao | null {
  return atual?.campo === campo ? atual.direcao : null;
}
