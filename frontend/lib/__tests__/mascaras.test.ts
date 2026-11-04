import { describe, expect, it } from "vitest";

import { aplicarMascara, emailValido, exemploDaMascara } from "@/lib/mascaras";

describe("aplicarMascara", () => {
  it.each([
    ["cpf", "", "", "___.___.___-__", false],
    ["cpf", "123", "123", ".___.___-__", false],
    ["cpf", "1234", "123.4", "__.___-__", false],
    ["cpf", "12345678909", "123.456.789-09", "", true],
    ["cpf", "123.456.789-0999", "123.456.789-09", "", true],
    ["cnpj", "12345678000190", "12.345.678/0001-90", "", true],
    ["cnpj", "12345678", "12.345.678", "/____-__", false],
    ["celular", "85999998888", "(85) 99999-8888", "", true],
    ["celular", "85", "(85", ") _____-____", false],
    ["telefone", "8533334444", "(85) 3333-4444", "", true],
    ["telefone", "85333344445", "(85) 33334-4445", "", true],
  ] as const)("%s %j → %j + guia %j", (m, entrada, valor, guia, completo) => {
    expect(aplicarMascara(m, entrada)).toEqual({ valor, guia, completo });
  });

  it("ignora o que não é dígito e reformata quando a máscara muda", () => {
    const comoCpf = aplicarMascara("cpf", "abc123.456.789-09").valor;
    expect(comoCpf).toBe("123.456.789-09");
    // trocar o tipo para jurídica re-formata os mesmos dígitos como CNPJ
    expect(aplicarMascara("cnpj", comoCpf).valor).toBe("12.345.678/909");
  });

  it("valor nulo vira vazio, com a guia inteira", () => {
    expect(aplicarMascara("cpf", null)).toEqual({ valor: "", guia: "___.___.___-__", completo: false });
  });
});

describe("exemploDaMascara e emailValido", () => {
  it("exemplo usa _ nas posições de dígito", () => {
    expect(exemploDaMascara("cnpj")).toBe("__.___.___/____-__");
  });

  it.each([
    ["maria@exemplo.com.br", true],
    [" maria@x.test ", true],
    ["maria@sem-ponto", false],
    ["maria.exemplo.com", false],
    ["ma ria@x.com", false],
  ])("%j → %s", (v, ok) => {
    expect(emailValido(v)).toBe(ok);
  });
});
