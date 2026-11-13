import { aplicarMascara, documentoValido, soDigitos } from "@/lib/mascaras";

/**
 * CPF ou CNPJ num campo só, como o cidadão pensa ("meu documento"): até 11
 * números vira CPF (000.000.000-00), do 12º em diante vira CNPJ
 * (00.000.000/0000-00). A pontuação entra sozinha; quem cola o número já
 * pontuado também cai certo.
 *
 * Só dígitos: o backend do portal guarda e procura o documento só com os
 * números (`cidadao_auth._normaliza_cpf_cnpj`), então o CNPJ alfanumérico
 * ainda não tem como entrar por aqui. Para a API vai sempre `soDigitos(...)`
 * — o cadastro aceita no máximo 14 caracteres, e o CNPJ pontuado tem 18.
 */
export function mascararDocumento(entrada: string): string {
  const d = soDigitos(entrada).slice(0, 14);
  return aplicarMascara(d.length > 11 ? "cnpj" : "cpf", d).valor;
}

/** 11 números (CPF) ou 14 (CNPJ). */
export function documentoCompleto(v: string): boolean {
  const n = soDigitos(v).length;
  return n === 11 || n === 14;
}

/**
 * Mensagem de erro do campo de documento, ou `null` se está bom.
 * `conferirDigitos` liga a conta do dígito verificador — no cadastro, para o
 * erro de digitação não virar uma conta com o documento de outra pessoa; no
 * login não, porque ali o servidor já responde "CPF ou senha incorretos".
 */
export function erroDoDocumento(v: string, conferirDigitos = false): string | null {
  const n = soDigitos(v).length;
  if (n === 0) return "Digite o seu CPF (ou o CNPJ, se for empresa).";
  if (n !== 11 && n !== 14) {
    return n < 11
      ? `Faltam ${11 - n} ${11 - n === 1 ? "número" : "números"} do CPF.`
      : "O CNPJ tem 14 números. Confira o que foi digitado.";
  }
  if (conferirDigitos && !documentoValido(n === 11 ? "cpf" : "cnpj", v)) {
    return `Esse ${n === 11 ? "CPF" : "CNPJ"} não existe. Confira os números — um deles pode ter sido trocado.`;
  }
  return null;
}
