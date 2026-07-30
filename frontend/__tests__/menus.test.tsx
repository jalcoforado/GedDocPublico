/**
 * Guarda do split do menu. O NAV tinha 637 linhas num arquivo; o risco do split
 * não é escrever errado, é PERDER item no caminho — e item perdido não quebra
 * teste nenhum, só desaparece da tela de alguém.
 */
import { describe, expect, it } from "vitest";

import { MENUS, ORDEM_GRUPOS_ORIGINAL, menuDoModulo } from "@/lib/menus";
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
  "/processos": { perm: "processo" },
  "/workflow": {},
  "/relatorios": { perm: "processo" },
  "/protocolo/balcao": { perm: "processo" },
  "/protocolo/vencendo-prazo": { perm: "processo" },
  "/protocolo/ccd": { perm: "catalogo" },
  "/protocolo/ttd": { perm: "catalogo" },
  "/manifestantes": { perm: "manifestante" },
  "/tipos-manifestante": { perm: "manifestante" },
  "/tipos-processo": { perm: "catalogo" },
  "/assuntos": { perm: "assunto" },
  "/servicos": { perm: "servico" },
  "/tipos-anexo": { perm: "catalogo" },
  "/templates-documento": { perm: "minuta_template" },
  "/cidades": { perm: "cidade" },
  "/bairros": { perm: "endereco" },
  "/enderecos": { perm: "endereco" },
  "/frotas": { perm: "frota" },
  "/frotas/veiculos": { perm: "frota" },
  "/frotas/motoristas": { perm: "frota" },
  "/frotas/solicitacoes": { perm: "frota" },
  "/transporte-regulado": { perm: "transporte_regulado" },
  "/transporte-regulado/permissionarios": { perm: "transporte_regulado" },
  "/transporte-regulado/empresas": { perm: "transporte_regulado" },
  "/transporte-regulado/veiculos": { perm: "transporte_regulado" },
  "/pagamentos": {
    anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar", "pagamento_cadastro"],
  },
  "/pagamentos/dashboard": {
    anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar", "pagamento_cadastro"],
  },
  "/pagamentos/contas-a-pagar": {
    anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar"],
  },
  "/pagamentos/autorizacao": { anyOf: ["pagamento_autorizar"] },
  "/pagamentos/tesouraria": { perm: "pagamento_pagar" },
  "/pagamentos/caixa": { perm: "pagamento_cadastro" },
  "/pagamentos/conciliacao": {
    anyOf: ["pagamento_pagar", "pagamento_autorizar", "pagamento_auditar", "pagamento_cadastro"],
  },
  "/pagamentos/cadastros/fornecedores": { perm: "pagamento_cadastro" },
  "/pagamentos/cadastros/naturezas": { perm: "pagamento_cadastro" },
  "/pagamentos/cadastros/fontes": { perm: "pagamento_cadastro" },
  "/pagamentos/cadastros/contas": { perm: "pagamento_cadastro" },
  "/pagamentos/cadastros/contratos": { perm: "pagamento_cadastro" },
  "/pagamentos/cadastros/alcadas": { perm: "pagamento_cadastro" },
  "/pagamentos/cadastros/checklist": { perm: "pagamento_cadastro" },
  "/usuarios": { perm: "usuario" },
  "/unidades-trabalho": { perm: "unidadeTrabalho" },
  "/organograma": {},
  "/grupos": {},
  "/configuracoes": { perm: "usuario" },
  "/auditoria": {},
  "/jobs": {},
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

  it("a ponte temporária (ORDEM_GRUPOS_ORIGINAL) reproduz a ordem original do NAV", () => {
    // A Sidebar monta NAV com `ORDEM_GRUPOS_ORIGINAL.flatMap((slug) => MENUS[slug].grupos)`.
    // Esta é a mesma composição — se a ordem regredir (ex.: "Geral" deixar de
    // vir primeiro), o usuário vê o menu reorganizado sem que ninguém pediu.
    const titulosReconstruidos = ORDEM_GRUPOS_ORIGINAL.flatMap((slug) =>
      MENUS[slug].grupos.map((g) => g.title),
    );
    expect(titulosReconstruidos).toEqual([
      "Geral",
      "Processos",
      "Protocolo",
      "Cadastros",
      "Frota",
      "Transporte Regulado",
      "Pagamentos",
      "Administração",
    ]);
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
});
