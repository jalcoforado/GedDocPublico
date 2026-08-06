/**
 * Guarda do split do menu. O NAV tinha 637 linhas num arquivo; o risco do split
 * não é escrever errado, é PERDER item no caminho — e item perdido não quebra
 * teste nenhum, só desaparece da tela de alguém.
 */
import { describe, expect, it } from "vitest";

import { MENUS, menuDoModulo } from "@/lib/menus";
import type { NavItem } from "@/lib/menus/tipos";
import { moduloDoPathname } from "@/lib/modulos";

/** Todos os hrefs de um menu, incluindo os de subitens. */
function hrefs(items: NavItem[]): string[] {
  return items.flatMap((i) => [i.href, ...(i.children ? hrefs(i.children) : [])]);
}

/** Todos os itens de um menu "achatados" — inclui subitens de `children`. */
function achatar(items: NavItem[]): NavItem[] {
  return items.flatMap((i) => [i, ...(i.children ? achatar(i.children) : [])]);
}

const TODOS = Object.values(MENUS).flatMap((m) => hrefs(m.grupos.flatMap((g) => g.items)));

/**
 * Tabela explícita de `perm`/`anyOf` esperados por `href`, copiada do NAV
 * original (Sidebar.tsx antes do split, commit 8569f5a). É a fonte de
 * verdade INDEPENDENTE dos arquivos de menu — se um item perder ou trocar
 * permissão, esta tabela não muda junto, e o teste acusa a divergência.
 *
 * `{}` significa "sem poda por permissão" (nem `perm` nem `anyOf`).
 */
const PERMISSOES_ESPERADAS: Record<string, { perm?: string; anyOf?: string[] }> = {
  "/home": {},
  "/dashboard": {},
  "/para-assinar": {},
  "/m/protocolo/processos": { perm: "processo" },
  "/m/protocolo/workflow": {},
  "/m/protocolo/relatorios": { perm: "processo" },
  "/m/protocolo/protocolo/balcao": { perm: "processo" },
  "/m/protocolo/protocolo/vencendo-prazo": { perm: "processo" },
  "/m/protocolo/protocolo/ccd": { perm: "catalogo" },
  "/m/protocolo/protocolo/ttd": { perm: "catalogo" },
  "/m/protocolo/manifestantes": { perm: "manifestante" },
  "/m/protocolo/tipos-manifestante": { perm: "manifestante" },
  "/m/protocolo/tipos-processo": { perm: "catalogo" },
  "/m/protocolo/assuntos": { perm: "assunto" },
  "/m/protocolo/servicos": { perm: "servico" },
  "/m/protocolo/tipos-anexo": { perm: "catalogo" },
  "/m/protocolo/templates-documento": { perm: "minuta_template" },
  "/m/protocolo/cidades": { perm: "cidade" },
  "/m/protocolo/bairros": { perm: "endereco" },
  "/m/protocolo/enderecos": { perm: "endereco" },
  "/m/frota": { perm: "frota" },
  "/m/frota/veiculos": { perm: "frota" },
  "/m/frota/motoristas": { perm: "frota" },
  "/m/frota/solicitacoes": { perm: "frota" },
  "/m/transporte": { perm: "transporte_regulado" },
  "/m/transporte/permissionarios": { perm: "transporte_regulado" },
  "/m/transporte/empresas": { perm: "transporte_regulado" },
  "/m/transporte/veiculos": { perm: "transporte_regulado" },
  "/m/transporte/alvaras": { perm: "transporte_regulado" },
  "/m/transporte/pontos": { perm: "transporte_regulado" },
  "/m/transporte/recadastramento": { perm: "transporte_regulado" },
  "/m/transporte/relatorio": { perm: "transporte_regulado" },
  "/m/pagamentos": {
    anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar", "pagamento_cadastro"],
  },
  "/m/pagamentos/dashboard": {
    anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar", "pagamento_cadastro"],
  },
  "/m/pagamentos/contas-a-pagar": {
    anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar"],
  },
  "/m/pagamentos/autorizacao": { anyOf: ["pagamento_autorizar"] },
  "/m/pagamentos/tesouraria": { perm: "pagamento_pagar" },
  "/m/pagamentos/caixa": { perm: "pagamento_cadastro" },
  "/m/pagamentos/conciliacao": {
    anyOf: ["pagamento_pagar", "pagamento_autorizar", "pagamento_auditar", "pagamento_cadastro"],
  },
  "/m/pagamentos/cadastros/fornecedores": { perm: "pagamento_cadastro" },
  "/m/pagamentos/cadastros/naturezas": { perm: "pagamento_cadastro" },
  "/m/pagamentos/cadastros/fontes": { perm: "pagamento_cadastro" },
  "/m/pagamentos/cadastros/contas": { perm: "pagamento_cadastro" },
  "/m/pagamentos/cadastros/contratos": { perm: "pagamento_cadastro" },
  "/m/pagamentos/cadastros/alcadas": { perm: "pagamento_cadastro" },
  "/m/pagamentos/cadastros/checklist": { perm: "pagamento_cadastro" },
  "/m/administracao/usuarios": { perm: "usuario" },
  "/m/administracao/unidades-trabalho": { perm: "unidadeTrabalho" },
  "/m/administracao/organograma": {},
  "/m/administracao/grupos": {},
  "/m/administracao/configuracoes": { perm: "usuario" },
  "/m/administracao/auditoria": {},
  "/m/administracao/jobs": {},
};

describe("split dos menus", () => {
  it("não está vazio", () => {
    // Sem isto, todas as asserções abaixo passam vacuamente.
    expect(TODOS.length).toBeGreaterThan(40);
    expect(Object.keys(MENUS).sort()).toEqual([
      "administracao", "comum", "frota", "pagamentos", "protocolo", "transporte",
    ]);
  });

  it("nenhum href aparece em dois módulos", () => {
    const vistos = new Map<string, string>();
    const duplicados: string[] = [];
    for (const [slug, menu] of Object.entries(MENUS)) {
      for (const href of hrefs(menu.grupos.flatMap((g) => g.items))) {
        const antes = vistos.get(href);
        if (antes && antes !== slug) duplicados.push(`${href}: ${antes} e ${slug}`);
        vistos.set(href, slug);
      }
    }
    expect(duplicados).toEqual([]);
  });

  it("cada item está no módulo que o mapa de pathname aponta", () => {
    // Se um item foi para o arquivo errado, o menu do módulo A mostra tela do
    // módulo B — e na F3 o redirect vai jogar o usuário para fora do menu em
    // que ele acabou de clicar.
    const divergentes: string[] = [];
    for (const [slug, menu] of Object.entries(MENUS)) {
      if (slug === "comum") continue; // transversais não têm módulo
      for (const href of hrefs(menu.grupos.flatMap((g) => g.items))) {
        const derivado = moduloDoPathname(href);
        if (derivado !== slug) divergentes.push(`${href}: arquivo=${slug} mapa=${derivado}`);
      }
    }
    expect(divergentes).toEqual([]);
  });

  it("todo módulo tem raiz navegável e ela pertence ao próprio módulo", () => {
    for (const [slug, menu] of Object.entries(MENUS)) {
      expect(menu.raiz, `${slug} sem raiz`).toMatch(/^\//);
      if (slug !== "comum") expect(moduloDoPathname(menu.raiz)).toBe(slug);
    }
  });

  it("menuDoModulo devolve null para slug desconhecido", () => {
    expect(menuDoModulo("nao-existe")).toBeNull();
  });

  // O teste antigo aqui ("a ponte temporária reproduz a ordem original do NAV")
  // reconstruía a ordem a partir de `ORDEM_GRUPOS_ORIGINAL` e comparava contra
  // 8 títulos fixos — mas nunca olhava a `Sidebar`. Ele passou verde enquanto
  // a Task 3 montava o `NAV` na ordem oposta (módulo antes de comum), porque
  // não exercitava o componente que decide a ordem de verdade. Removido junto
  // com `ORDEM_GRUPOS_ORIGINAL` (ficou sem uso depois da Task 3). O teste que
  // MORDE essa regressão — renderiza a Sidebar de verdade e afirma que
  // "comum" vem antes do módulo — está em `Sidebar.modulo.test.tsx`, perto da
  // infraestrutura de mocks (QueryClient/ThemeProvider) que a Sidebar exige.
  // O que sobra como invariante de DADO (independe de a Sidebar existir) é a
  // ordem dos grupos DENTRO de cada módulo — é o que este teste afirma agora.
  it("a ordem dos grupos dentro de cada módulo é a do NAV original", () => {
    const ORDEM_ESPERADA: Record<string, string[]> = {
      comum: ["Geral"],
      protocolo: ["Processos", "Protocolo", "Cadastros"],
      frota: ["Frota"],
      transporte: ["Transporte Regulado"],
      pagamentos: ["Pagamentos"],
      administracao: ["Administração"],
    };
    for (const [slug, menu] of Object.entries(MENUS)) {
      expect(menu.grupos.map((g) => g.title), slug).toEqual(ORDEM_ESPERADA[slug]);
    }
  });

  it("perm/anyOf de cada item bate com a tabela original — não só o href", () => {
    // A poda por permissão esconde do usuário o que ele não pode fazer; ela é
    // independente do filtro de módulo, e nenhum dos dois substitui o outro.
    // Um `perm` perdido ou trocado por engano não quebra tela nenhuma — vira
    // item visível pra quem não deveria ver, e ninguém reporta isso.
    const divergencias: string[] = [];
    for (const menu of Object.values(MENUS)) {
      for (const item of achatar(menu.grupos.flatMap((g) => g.items))) {
        const esperado = PERMISSOES_ESPERADAS[item.href];
        if (!esperado) {
          divergencias.push(`${item.href}: sem entrada na tabela PERMISSOES_ESPERADAS`);
          continue;
        }
        const permBate = (item.perm ?? null) === (esperado.perm ?? null);
        const anyOfBate =
          JSON.stringify(item.anyOf ?? null) === JSON.stringify(esperado.anyOf ?? null);
        if (!permBate || !anyOfBate) {
          divergencias.push(
            `${item.href} ("${item.label}"): perm=${JSON.stringify(item.perm ?? null)} ` +
              `anyOf=${JSON.stringify(item.anyOf ?? null)} — esperado perm=${JSON.stringify(esperado.perm ?? null)} ` +
              `anyOf=${JSON.stringify(esperado.anyOf ?? null)}`,
          );
        }
      }
    }
    expect(divergencias).toEqual([]);
  });

  it("o menu do transporte alcança alvarás e relatórios", () => {
    // P1–P4 entregaram estas duas telas e ninguém as ligou à navegação: por
    // meses só se chegava nelas digitando a URL. Este teste é o que impede
    // que uma tela entregue volte a ficar invisível.
    const menu = menuDoModulo("transporte");
    expect(menu).not.toBeNull();
    const doTransporte = hrefs(menu!.grupos.flatMap((g) => g.items));
    expect(doTransporte).toContain("/m/transporte/alvaras");
    expect(doTransporte).toContain("/m/transporte/relatorio");
    expect(doTransporte).toContain("/m/transporte/recadastramento");
  });
});
