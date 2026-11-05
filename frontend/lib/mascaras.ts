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

/**
 * Telefone gravado só com dígitos (`85999998888`) → `(85) 99999-8888`.
 * Cadastro anterior à regra, gravado como foi digitado, volta como está.
 * Espelha `telefone_para_exibir` do backend.
 */
export function telefoneParaExibir(v: string | null | undefined): string {
  if (!v) return "";
  return /^\d{10,11}$/.test(v) ? aplicarMascara("telefone", v).valor : v;
}

// Mesma regra do backend (`schemas/manifestante.py::_EMAIL`): forma, não
// existência. Usuário sem ponto na ponta nem ponto duplo; domínio com rótulos
// de letra/dígito/hífen e terminação de 2+ letras.
const EMAIL =
  /^[a-z0-9_%+-]+(?:\.[a-z0-9_%+-]+)*@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$/;

export function emailValido(v: string): boolean {
  return EMAIL.test(v.trim().toLowerCase());
}

/**
 * Dígito verificador (módulo 11) de CPF e CNPJ, numérico ou alfanumérico.
 * Espelha `documento_valido` do backend. No CNPJ cada posição vale o código
 * ASCII menos 48 ("0".."9" → 0..9, "A".."Z" → 17..42), com pesos 2 a 9 da
 * direita para a esquerda; exemplo oficial da Receita: 12.ABC.345/01DE-35.
 * Sequência repetida ("111.111.111-11") fecha a conta e é recusada.
 */
export function documentoValido(m: "cpf" | "cnpj", entrada: unknown): boolean {
  const doc = caracteres(m, entrada);
  const tamanho = m === "cpf" ? 11 : 14;
  if (doc.length !== tamanho || doc === doc[0].repeat(tamanho)) return false;
  if (!/^\d{2}$/.test(doc.slice(-2))) return false;
  const valores = doc.split("").map((ch) => ch.charCodeAt(0) - 48);
  const corpo = tamanho - 2;
  for (const n of [corpo, corpo + 1]) {
    let soma = 0;
    for (let i = 0; i < n; i++) {
      // CPF: pesos n+1 descendo até 2. CNPJ: 2..9 ciclando, da direita.
      const peso = m === "cpf" ? n + 1 - i : ((n - 1 - i) % 8) + 2;
      soma += valores[i] * peso;
    }
    const resto = soma % 11;
    const dv = m === "cpf" ? (soma * 10) % 11 % 10 : resto < 2 ? 0 : 11 - resto;
    if (dv !== valores[n]) return false;
  }
  return true;
}
