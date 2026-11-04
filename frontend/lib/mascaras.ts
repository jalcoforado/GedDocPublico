/**
 * Máscaras de digitação (CPF, CNPJ, telefones) sem dependência externa.
 *
 * `aplicarMascara` devolve, além do valor formatado, a `guia`: o resto do
 * padrão ainda não preenchido (`__.___-__`), que o campo mostra em cinza
 * atrás do texto digitado. O backend guarda o CPF/CNPJ só com dígitos e o
 * telefone formatado (`schemas/manifestante.py`); a máscara é só da tela.
 */

export type Mascara = "cpf" | "cnpj" | "celular" | "telefone";

// `0` é posição de dígito; o resto é literal.
const PADRAO = {
  cpf: "000.000.000-00",
  cnpj: "00.000.000/0000-00",
  celular: "(00) 00000-0000",
  fixo: "(00) 0000-0000",
} as const;

export function soDigitos(v: unknown): string {
  return typeof v === "string" ? v.replace(/\D/g, "") : typeof v === "number" ? String(v) : "";
}

function padraoDe(m: Mascara, digitos: string): string {
  if (m === "telefone") return digitos.length > 10 ? PADRAO.celular : PADRAO.fixo;
  return PADRAO[m];
}

/** Padrão de exibição, com `_` nas posições de dígito (para mensagens). */
export function exemploDaMascara(m: Mascara): string {
  return padraoDe(m, "").replace(/0/g, "_");
}

export interface ValorMascarado {
  valor: string;
  guia: string;
  completo: boolean;
}

export function aplicarMascara(m: Mascara, entrada: unknown): ValorMascarado {
  const padrao = padraoDe(m, soDigitos(entrada));
  const vagas = padrao.replace(/[^0]/g, "").length;
  const digitos = soDigitos(entrada).slice(0, vagas);
  let valor = "";
  let i = 0;
  for (const ch of padrao) {
    if (i >= digitos.length) break;
    if (ch === "0") valor += digitos[i++];
    else valor += ch;
  }
  return {
    valor,
    guia: padrao.slice(valor.length).replace(/0/g, "_"),
    completo: digitos.length === vagas,
  };
}

// Mesma regra do backend (`schemas/manifestante.py::_EMAIL`): forma, não existência.
export function emailValido(v: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.trim());
}
