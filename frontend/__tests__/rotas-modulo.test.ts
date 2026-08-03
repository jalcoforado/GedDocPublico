import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { beforeAll, describe, expect, it } from "vitest";

import {
  ITENS_EXTRA,
  KEYWORDS_POR_HREF,
} from "@/components/CommandPalette";
import { MENUS, type NavItem } from "@/lib/menus";
import { ROTA_MODULO, SLUGS_MODULO } from "@/lib/modulos";

/**
 * Guardas estruturais da F3. Não testam comportamento — testam que ninguém
 * desfez a fatia sem perceber.
 *
 * Existem porque, movendo os cinco módulos, a varredura manual por linha
 * contendo "href" falhou **três vezes**, sempre em silêncio e sempre com a
 * suíte verde:
 *
 * 1. `abrirHref` — o filtro casava "href" sensível a maiúscula;
 * 2. `CHECKLIST_HREF` — mapa de rotas cujo NOME tem "HREF" e cujas LINHAS não;
 * 3. `KEYWORDS_POR_HREF` — mapa em `components/`, fora do diretório varrido,
 *    que ficou com chave órfã por duas tarefas inteiras.
 *
 * Nenhuma das três quebrou teste. A primeira e a segunda produziriam salto
 * extra pelo 308 com URL velha na barra; a terceira degradaria o Ctrl+K. O
 * ponto destas guardas é converter "pior em silêncio" em vermelho.
 */

const RAIZ = join(__dirname, "..");
const DIR_APP = join(RAIZ, "app", "(app)");
const DIR_M = join(DIR_APP, "m");

/**
 * Diretórios que PODEM ficar na raiz de `app/(app)/`. São as transversais da
 * decisão D5 do spec: agregam ATRAVÉS dos módulos, então não pertencem a
 * nenhum. Acrescentar nome aqui é decisão de arquitetura — se a tela é de um
 * módulo, o lugar dela é `m/<slug>/`.
 */
const TRANSVERSAIS = new Set(["home", "dashboard", "perfil", "para-assinar", "m"]);

function subdiretorios(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name);
}

function hrefsDe(items: NavItem[]): string[] {
  return items.flatMap((i) => [
    ...(i.href ? [i.href] : []),
    ...(i.children ? hrefsDe(i.children) : []),
  ]);
}

type Regra = { source: string; destination: string; permanent: boolean };

/**
 * Regras de `redirects()`, lidas do próprio `next.config.js`.
 *
 * `await` obrigatório: o Next declara `redirects()` como async, e uma versão
 * sincrona desta funcao devolvia `[]` silenciosamente — o que deixaria as
 * asserções abaixo passando sobre lista vazia se nao houvesse o controle
 * `length > 0`. Foi o que aconteceu na primeira execucao.
 */
async function regrasDeRedirect(): Promise<Regra[]> {
  // `require` e não import: o config é CommonJS e não tem tipos.
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const cfg = require(join(RAIZ, "next.config.js"));
  if (typeof cfg.redirects !== "function") return [];
  return await cfg.redirects();
}

describe("F3 — nenhuma tela de módulo fora de /m", () => {
  it("app/(app)/ só tem transversais e o segmento m/", () => {
    const inesperados = subdiretorios(DIR_APP).filter((d) => !TRANSVERSAIS.has(d));
    expect(inesperados, [
      "Diretório de topo em `app/(app)/` que não é transversal.",
      "Tela de módulo mora em `app/(app)/m/<slug>/` desde a F3.",
      "Se for mesmo transversal (agrega ATRAVÉS dos módulos, como /busca),",
      "acrescente a `TRANSVERSAIS` neste arquivo — é decisão de arquitetura,",
      "não ajuste de teste.",
    ].join(" ")).toEqual([]);
  });

  it("todo slug de módulo com menu tem diretório em m/", () => {
    const comMenu = Object.keys(MENUS).filter((s) => s !== "comum");
    const emDisco = new Set(subdiretorios(DIR_M));
    const faltando = comMenu.filter((s) => !emDisco.has(s));
    expect(faltando, "módulo com menu mas sem pasta em `app/(app)/m/`").toEqual([]);
  });

  it("todo diretório em m/ é slug conhecido do catálogo", () => {
    const desconhecidos = subdiretorios(DIR_M).filter(
      (d) => !d.startsWith("[") && !SLUGS_MODULO.has(d),
    );
    expect(
      desconhecidos,
      "pasta em `m/` que não é slug de `ROTA_MODULO` — `moduloDoPathname` devolveria null e o guard mandaria para o launcher",
    ).toEqual([]);
  });
});

describe("F3 — todo prefixo legado tem redirect 308", () => {
  let regras: Regra[] = [];
  beforeAll(async () => {
    regras = await regrasDeRedirect();
  });

  it("as regras foram lidas do next.config.js", () => {
    // Sem isto, um `redirects()` que virasse async faria as duas asserções
    // abaixo passarem sobre uma lista VAZIA — verde por não medir nada.
    expect(regras.length).toBeGreaterThan(0);
  });

  it.each(ROTA_MODULO.map(([prefixo, slug]) => ({ prefixo, slug })))(
    "$prefixo → /m/$slug",
    ({ prefixo, slug }) => {
      const regra = regras.find((r) => r.source.startsWith(`${prefixo}/`));
      expect(
        regra,
        `sem regra de redirect para \`${prefixo}\` em next.config.js. Prefixo novo em ROTA_MODULO exige regra nova lá, senão o link antigo vira 404.`,
      ).toBeDefined();
      expect(regra!.destination).toContain(`/m/${slug}/`);
      // 308, não 302: preserva método e corpo, e há caminhos que recebem POST.
      expect(regra!.permanent, `${prefixo} precisa de permanent: true (308)`).toBe(true);
    },
  );

  it("nenhuma regra aponta para módulo inexistente", () => {
    const orfas = regras
      .map((r) => r.destination.match(/^\/m\/([^/]+)/)?.[1])
      .filter((s): s is string => !!s && !SLUGS_MODULO.has(s));
    expect(orfas, "redirect para slug que não existe").toEqual([]);
  });
});

describe("F3 — nenhum href aponta para o caminho antigo", () => {
  const prefixosLegados = ROTA_MODULO.map(([p]) => p);

  it("os menus só apontam para /m/<slug> ou transversal", () => {
    const problemas: string[] = [];
    for (const [slug, menu] of Object.entries(MENUS)) {
      for (const href of hrefsDe(menu.grupos.flatMap((g) => g.items))) {
        if (prefixosLegados.some((p) => href === p || href.startsWith(`${p}/`))) {
          problemas.push(`${slug}: ${href}`);
        }
      }
    }
    expect(
      problemas,
      "href de menu no caminho ANTIGO. Funcionaria pelo 308, mas com salto extra e URL velha na barra de endereço.",
    ).toEqual([]);
  });

  it("as chaves de KEYWORDS_POR_HREF existem em algum menu", () => {
    // A guarda que faltava: este mapa é indexado por href e ficou com chave
    // órfã por duas tarefas da F3 sem quebrar nada. Chave que não bate com
    // item de menu é sinônimo de Ctrl+K que nunca casa.
    const doMenu = new Set(
      Object.values(MENUS).flatMap((m) => hrefsDe(m.grupos.flatMap((g) => g.items))),
    );
    // A paleta tem acoes estaticas proprias, fora de `lib/menus`
    // (`/perfil`, `/perfil/notificacoes`, atalhos de criacao). Sao href
    // legitimos; o que se proibe e chave que nao existe em lugar NENHUM.
    for (const e of ITENS_EXTRA) if (e.item.href) doMenu.add(e.item.href);
    const orfas = Object.keys(KEYWORDS_POR_HREF).filter((h) => !doMenu.has(h));
    expect(
      orfas,
      "chave de KEYWORDS_POR_HREF que não é href de nenhum item de menu — o sinônimo nunca vai casar",
    ).toEqual([]);
  });
});

describe("F3 — o nginx precisa conhecer as rotas", () => {
  const conf = readFileSync(join(RAIZ, "..", "nginx", "default.conf"), "utf-8");
  // `startsWith("#")` nao e detalhe: o arquivo tem um COMENTARIO que cita
  // `location ~ ^/(login|home|...)` textualmente, ANTES da diretiva. Sem o
  // filtro este teste lia "..." como lista de tokens e reprovava tudo.
  const linha = conf
    .split("\n")
    .find((l) => !l.trimStart().startsWith("#") && l.includes("location ~ ^/(login"));
  const tokens = new Set(linha?.match(/\(([^)]+)\)/)?.[1].split("|") ?? []);

  it("achou a diretiva, nao um comentario", () => {
    // Controle: `linha` indefinida daria `tokens` vazio, e um dia isso
    // poderia virar verde por nao medir nada.
    expect(linha, "diretiva do nginx nao encontrada").toBeDefined();
    expect(tokens.size).toBeGreaterThan(20);
  });

  it("o token `m` está na regex", () => {
    expect(
      tokens.has("m"),
      "sem o token `m` a rota /m/... cai no fallback legado e 'não existe' no :8090, mesmo funcionando em dev",
    ).toBe(true);
  });

  it.each(ROTA_MODULO.map(([p]) => p.slice(1)))(
    "o token legado `%s` continua na regex",
    (token) => {
      expect(
        tokens.has(token),
        `token legado removido. Sem ele a URL antiga cai no fallback ANTES de chegar ao Next, e o 308 nunca acontece — ou seja, remover aqui mata o redirect.`,
      ).toBe(true);
    },
  );
});
