/**
 * O mapa pathname → módulo é o que sustenta a Sidebar nesta fatia e os
 * redirects na F3. Os casos abaixo vêm do apêndice §12 do spec, incluindo as
 * ambiguidades que ele resolveu de propósito.
 */
import { describe, expect, it } from "vitest";

import { moduloDoPathname } from "@/lib/modulos";

describe("moduloDoPathname", () => {
  it.each([
    ["/processos", "protocolo"],
    ["/processos/123", "protocolo"],
    ["/protocolo/balcao", "protocolo"],
    ["/workflow/7/editar", "protocolo"],
    ["/relatorios/tramitacao", "protocolo"],
    ["/servicos", "protocolo"],
    ["/manifestantes", "protocolo"],
    ["/tipos-manifestante", "protocolo"],
    ["/tipos-processo", "protocolo"],
    ["/tipos-anexo", "protocolo"],
    ["/assuntos", "protocolo"],
    ["/templates-documento", "protocolo"],
    ["/cidades", "protocolo"],
    ["/bairros", "protocolo"],
    ["/enderecos", "protocolo"],
    ["/pagamentos", "pagamentos"],
    ["/pagamentos/dashboard", "pagamentos"],
    ["/pagamentos/cadastros/fornecedores", "pagamentos"],
    ["/frotas", "frota"],
    ["/frotas/veiculos/9", "frota"],
    ["/transporte-regulado", "transporte"],
    ["/transporte-regulado/alvaras/3", "transporte"],
    ["/usuarios", "administracao"],
    ["/grupos", "administracao"],
    ["/unidades-trabalho", "administracao"],
    ["/organograma", "administracao"],
    ["/auditoria", "administracao"],
    ["/configuracoes", "administracao"],
    ["/jobs", "administracao"],
  ])("%s → %s", (path, esperado) => {
    expect(moduloDoPathname(path)).toBe(esperado);
  });

  it.each(["/home", "/dashboard", "/perfil", "/perfil/notificacoes", "/para-assinar", "/busca", "/modulos"])(
    "%s é transversal (null)",
    (path) => {
      // §12/D5: transversais não pertencem a módulo — agregam ATRAVÉS deles.
      expect(moduloDoPathname(path)).toBeNull();
    },
  );

  it("não confunde prefixo com palavra maior", () => {
    // "/processos" não pode capturar "/processos-antigos" de um módulo futuro,
    // e "/pagamentos" não pode capturar um "/pagamentosx" qualquer.
    expect(moduloDoPathname("/processosx")).toBeNull();
    expect(moduloDoPathname("/pagamentosx")).toBeNull();
  });

  it("tolera querystring e barra final", () => {
    expect(moduloDoPathname("/frotas/")).toBe("frota");
    expect(moduloDoPathname("/frotas?tab=ativos")).toBe("frota");
  });

  // ---- F3: a forma canônica `/m/<slug>` ----
  //
  // As duas formas convivem por decisão, não por transição inacabada: o mapa
  // legado é a fonte dos redirects 308, e `notificacao.link_url` é registro
  // histórico permanente. Apagar a forma antiga apagaria os redirects junto.
  describe("prefixo canônico /m/<slug> (F3)", () => {
    it.each([
      ["/m/transporte", "transporte"],
      ["/m/transporte/alvaras/3", "transporte"],
      ["/m/protocolo/processos/123", "protocolo"],
      ["/m/pagamentos", "pagamentos"],
      ["/m/frota/veiculos", "frota"],
      ["/m/administracao/usuarios", "administracao"],
    ])("%s → %s", (path, esperado) => {
      expect(moduloDoPathname(path)).toBe(esperado);
    });

    it("slug desconhecido vira null, não o texto cru da URL", () => {
      // Quem consome isto monta menu e guard. Devolver o texto deixaria um
      // slug inventado na barra de endereços virar estado de aplicação.
      expect(moduloDoPathname("/m/inexistente")).toBeNull();
      expect(moduloDoPathname("/m/inexistente/foo")).toBeNull();
      expect(moduloDoPathname("/m/comum")).toBeNull();
    });

    it("não confunde `/m` com rota que só começa com m", () => {
      expect(moduloDoPathname("/m")).toBeNull();
      expect(moduloDoPathname("/manifestantes")).toBe("protocolo");
      expect(moduloDoPathname("/modulos")).toBeNull();
    });

    it("tolera querystring e barra final na forma nova", () => {
      expect(moduloDoPathname("/m/frota/")).toBe("frota");
      expect(moduloDoPathname("/m/frota?tab=ativos")).toBe("frota");
    });
  });
});
