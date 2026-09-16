/**
 * Formatação de duração (F1).
 *
 * O que estes testes travam não é a aparência do texto — é que o número
 * **nunca cresce** por arredondamento. Um processo com 2 h 59 min exibido como
 * "3 h" é o tipo de erro que só aparece quando alguém usa o número para
 * cobrar alguém, e aí a conversa é sobre o sistema, não sobre o processo.
 */
import { describe, expect, it } from "vitest";

import { decorridoDesde, formatarDuracao } from "@/lib/duracao";

describe("formatarDuracao", () => {
  it("abaixo de um minuto não finge precisão", () => {
    expect(formatarDuracao(0)).toBe("menos de 1 min");
    expect(formatarDuracao(59)).toBe("menos de 1 min");
  });

  it("minutos, horas e dias com no máximo duas unidades", () => {
    expect(formatarDuracao(60)).toBe("1 min");
    expect(formatarDuracao(45 * 60)).toBe("45 min");
    expect(formatarDuracao(3600)).toBe("1 h");
    expect(formatarDuracao(2 * 3600 + 30 * 60)).toBe("2 h 30 min");
    expect(formatarDuracao(24 * 3600)).toBe("1 d");
    expect(formatarDuracao(3 * 24 * 3600 + 4 * 3600)).toBe("3 d 4 h");
  });

  it("nunca arredonda para cima", () => {
    // 2 h 59 min 59 s continua sendo "2 h ...", nunca "3 h".
    expect(formatarDuracao(3 * 3600 - 1)).toBe("2 h 59 min");
    // 1 d menos um segundo continua sendo horas, nunca "1 d".
    expect(formatarDuracao(24 * 3600 - 1)).toBe("23 h 59 min");
  });

  it("some com a unidade zerada em vez de escrever '0 min'", () => {
    expect(formatarDuracao(2 * 3600)).toBe("2 h");
    expect(formatarDuracao(5 * 24 * 3600)).toBe("5 d");
  });

  it("entrada inválida vira travessão, não zero", () => {
    // Zero seria uma afirmação ("não passou tempo nenhum"); travessão é a
    // ausência de afirmação, que é o que de fato se sabe.
    expect(formatarDuracao(-1)).toBe("—");
    expect(formatarDuracao(Number.NaN)).toBe("—");
    expect(formatarDuracao(Number.POSITIVE_INFINITY)).toBe("—");
  });
});

describe("decorridoDesde", () => {
  it("conta do instante informado até agora", () => {
    const agora = new Date("2026-03-02T12:00:00Z");
    expect(decorridoDesde("2026-03-02T09:30:00Z", agora)).toBe("2 h 30 min");
  });

  it("data no futuro não vira negativo", () => {
    // O relógio é do navegador do usuário e pode estar adiantado.
    const agora = new Date("2026-03-02T12:00:00Z");
    expect(decorridoDesde("2026-03-02T18:00:00Z", agora)).toBe("menos de 1 min");
  });

  it("data ilegível vira travessão", () => {
    expect(decorridoDesde("nem data é")).toBe("—");
  });
});
