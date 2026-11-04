/**
 * Máscaras de digitação (CPF, CNPJ, telefones) sem dependência externa.
 *
 * `aplicarMascara` devolve, além do valor formatado, a `guia`: o resto do
 * padrão ainda não preenchido (`__.___-__`), que o campo mostra em cinza
 * atrás do texto digitado. O backend guarda o CPF/CNPJ sem máscara e o
 * telefone formatado (`schemas/manifestante.py`); a máscara é só da tela.
 */

export type Mascara = "cpf" | "cnpj" | "celular" | "telefone";

// `0` é posição de dígito; `A`, de letra ou dígito; o resto é literal.
// CNPJ alfanumérico (IN RFB 2.229/2024, emitido desde julho de 2026): as 12
// primeiras posições aceitam letra; os 2 dígitos verificadores, só número.
const PADRAO = {
  cpf: "000.000.000-00",
  cnpj: "AA.AAA.AAA/AAAA-00",
  celular: "(00) 00000-0000",
  fixo: "(00) 0000-0000",
} as const;

const VAGA = /[0A]/;

export function soDigitos(v: unknown): string {
  return typeof v === "string" ? v.replace(/\D/g, "") : typeof v === "number" ? String(v) : "";
}

/** A máscara aceita letra? Decide também o teclado do celular. */
export function aceitaLetras(m: Mascara): boolean {
  return m === "cnpj";
}

function caracteres(m: Mascara, v: unknown): string {
  if (!aceitaLetras(m)) return soDigitos(v);
  const s = typeof v === "string" ? v : typeof v === "number" ? String(v) : "";
  return s.replace(/[^0-9A-Za-z]/g, "").toUpperCase();
}

function padraoDe(m: Mascara, chars: string): string {
  if (m === "telefone") return chars.length > 10 ? PADRAO.celular : PADRAO.fixo;
  return PADRAO[m];
}

/** Padrão de exibição, com `_` nas posições a preencher (para mensagens). */
export function exemploDaMascara(m: Mascara): string {
  return padraoDe(m, "").replace(/[0A]/g, "_");
}

export interface ValorMascarado {
  valor: string;
  guia: string;
  completo: boolean;
}

export function aplicarMascara(m: Mascara, entrada: unknown): ValorMascarado {
  const chars = caracteres(m, entrada);
  const padrao = padraoDe(m, chars);
  const vagas = padrao.split("").filter((ch) => VAGA.test(ch)).length;
  let valor = "";
  let ate = 0; // comprimento de `valor` até a última vaga preenchida
  let preenchidas = 0;
  let i = 0;
  for (const ch of padrao) {
    if (i >= chars.length) break;
    if (!VAGA.test(ch)) {
      valor += ch;
      continue;
    }
    // Letra em posição só de dígito (DV do CNPJ) é descartada.
    while (i < chars.length && ch === "0" && !/\d/.test(chars[i])) i++;
    if (i >= chars.length) break;
    valor += chars[i++];
    preenchidas++;
    ate = valor.length;
  }
  // Literal que sobrou depois da última vaga ("123." ou "…/0001-") sai.
  valor = valor.slice(0, ate);
  return {
    valor,
    guia: padrao.slice(valor.length).replace(/[0A]/g, "_"),
    completo: preenchidas === vagas,
  };
}

// Mesma regra do backend (`schemas/manifestante.py::_EMAIL`): forma, não existência.
export function emailValido(v: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.trim());
}
