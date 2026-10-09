/**
 * Tema por município — deriva a paleta do sistema a partir de até três cores
 * configuradas no tenant (`cor_primaria`, `cor_destaque`, `cor_lateral`).
 *
 * O Design System fala em tokens HSL (`--brand: 166 45% 28%`), consumidos como
 * `hsl(var(--brand) / <alpha>)`. Este módulo produz esses tokens; quem aplica é
 * `lib/branding.tsx` (no `<html>`) e a pré-visualização de Configurações (num
 * contêiner). Cor que o município não definiu não entra no mapa — e o token
 * continua valendo o padrão do `globals.css`.
 *
 * A cor escolhida NÃO é usada crua: o contraste manda. Um amarelo como cor
 * primária viraria botão ilegível com texto branco, então a luminosidade é
 * ajustada até o par passar em AA (4.5:1). O matiz e a saturação — o que faz a
 * cor "ser" a do município — são preservados.
 */

export type ModoTema = "light" | "dark";

export interface CoresDoTema {
  cor_primaria?: string | null;
  cor_destaque?: string | null;
  cor_lateral?: string | null;
  /** Cor dos títulos de página. Ausente = cada título segue o seu padrão. */
  cor_titulos?: string | null;
  /** Chave de `FONTES`. Ausente ou desconhecida = a fonte padrão dos títulos. */
  fonte_titulos?: string | null;
}

/**
 * Fontes de título que o município pode escolher — lista FECHADA.
 *
 * `css` é o valor de `--font-display`: sempre uma `var()` de fonte que o
 * `app/layout.tsx` hospeda, nunca um nome de fonte. `null` é a padrão (não há
 * o que sobrescrever). Tem de casar com `FONTES_DE_TITULO` do backend e com o
 * CHECK da migration 0132 — fonte nova pede arquivo, declaração no layout e
 * migration.
 */
export const FONTES: { chave: string; rotulo: string; css: string | null }[] = [
  { chave: "montserrat", rotulo: "Montserrat (padrão)", css: null },
  { chave: "inter", rotulo: "Inter", css: "var(--font-sans)" },
  { chave: "roboto_slab", rotulo: "Roboto Slab (com serifa)", css: "var(--font-roboto-slab)" },
  { chave: "nunito", rotulo: "Nunito (arredondada)", css: "var(--font-nunito)" },
];

/** Valor de `--font-display` para a chave, ou `null` se for a padrão/desconhecida. */
export function cssDaFonte(chave: string | null | undefined): string | null {
  return FONTES.find((f) => f.chave === chave)?.css ?? null;
}

/** Aplica (ou remove) a fonte dos títulos num elemento. */
export function aplicarFonte(el: HTMLElement, chave: string | null | undefined): void {
  const css = cssDaFonte(chave);
  if (css) el.style.setProperty("--font-display", css);
  else el.style.removeProperty("--font-display");
}

/** Mapa `--token` → valor HSL sem `hsl()`, pronto para `style.setProperty`. */
export type TokensDeTema = Record<string, string>;

export interface Hsl {
  h: number;
  s: number;
  l: number;
}

const HEX = /^#[0-9a-f]{6}$/i;
const CONTRASTE_AA = 4.5;
const BRANCO: Hsl = { h: 0, s: 0, l: 100 };
// Fundo do modo escuro (`--bg` em `:root.dark`), contra o qual a marca clareia.
const FUNDO_ESCURO: Hsl = { h: 158, s: 20, l: 8 };
// Canvas do tema claro (`--bg` = `--neutral-25`): é sobre ele que os títulos leem.
const FUNDO_CLARO: Hsl = { h: 120, s: 6, l: 97 };

export function corValida(cor: string | null | undefined): cor is string {
  return typeof cor === "string" && HEX.test(cor);
}

export function hexParaHsl(hex: string): Hsl {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const d = max - min;
  if (d === 0) return { h: 0, s: 0, l: l * 100 };
  const s = d / (1 - Math.abs(2 * l - 1));
  let h: number;
  if (max === r) h = ((g - b) / d) % 6;
  else if (max === g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  return { h: (h * 60 + 360) % 360, s: s * 100, l: l * 100 };
}

function hslParaRgb({ h, s, l }: Hsl): [number, number, number] {
  const sat = s / 100;
  const lum = l / 100;
  const c = (1 - Math.abs(2 * lum - 1)) * sat;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = lum - c / 2;
  const [r, g, b] =
    h < 60 ? [c, x, 0]
    : h < 120 ? [x, c, 0]
    : h < 180 ? [0, c, x]
    : h < 240 ? [0, x, c]
    : h < 300 ? [x, 0, c]
    : [c, 0, x];
  return [r + m, g + m, b + m];
}

export function hslParaHex(cor: Hsl): string {
  return (
    "#" +
    hslParaRgb(cor)
      .map((v) => Math.round(Math.min(1, Math.max(0, v)) * 255).toString(16).padStart(2, "0"))
      .join("")
  );
}

/** Lê um token HSL do CSS (`166 45% 28%`) como hex — `null` se não for um. */
export function tokenParaHex(valor: string): string | null {
  const m = /^\s*([\d.]+)\s+([\d.]+)%\s+([\d.]+)%\s*$/.exec(valor);
  return m ? hslParaHex({ h: Number(m[1]), s: Number(m[2]), l: Number(m[3]) }) : null;
}

/** Luminância relativa (WCAG 2.x). */
function luminancia(cor: Hsl): number {
  const [r, g, b] = hslParaRgb(cor).map((v) =>
    v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contraste(a: Hsl, b: Hsl): number {
  const la = luminancia(a);
  const lb = luminancia(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

const limitar = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v));

/** Anda a luminosidade (`passo` negativo escurece) até o par passar em AA. */
function ajustarAteContrastar(cor: Hsl, contra: Hsl, passo: number): Hsl {
  let atual = cor;
  // O limite é só o do sentido em que se anda: branco puro (l=100) tem de
  // poder escurecer, e preto puro tem de poder clarear.
  const podeAndar = (l: number) => (passo < 0 ? l > 2 : l < 98);
  while (contraste(atual, contra) < CONTRASTE_AA && podeAndar(atual.l)) {
    atual = { ...atual, l: atual.l + passo };
  }
  return atual;
}

const token = ({ h, s, l }: Hsl) =>
  `${Math.round(h)} ${Math.round(limitar(s, 0, 100))}% ${Math.round(limitar(l, 0, 100))}%`;

const comL = (cor: Hsl, l: number): Hsl => ({ ...cor, l: limitar(l, 0, 100) });

/**
 * Texto que LÊ sobre `fundo`: anda a luminosidade no sentido `passo` até AA
 * e, se nem assim chegar, cai no preto ou branco puro.
 *
 * O último degrau existe por causa do cinza médio. `ajustarAteContrastar`
 * para em l=2/98 e o token é arredondado para inteiro; num fundo cinza médio
 * isso deixa o texto em 4.49 — abaixo de AA por um arredondamento. Preto ou
 * branco puros sempre resolvem: o produto dos dois contrastes é 21, então um
 * deles passa de 4.5.
 */
function textoLegivel(cor: Hsl, fundo: Hsl, passo: number): Hsl {
  const ajustado = ajustarAteContrastar(cor, fundo, passo);
  const arredondado: Hsl = {
    h: Math.round(ajustado.h),
    s: Math.round(ajustado.s),
    l: Math.round(ajustado.l),
  };
  if (contraste(arredondado, fundo) >= CONTRASTE_AA) return ajustado;
  return { h: 0, s: 0, l: passo < 0 ? 0 : 100 };
}

/**
 * Deriva os tokens de tema. Devolve só o que as cores informadas determinam.
 *
 * - **primária** → `--brand*`. No claro escurece até texto branco ler sobre
 *   ela; no escuro clareia até ela ler sobre o fundo.
 * - **destaque** → `--accent*`, e o texto sobre ela (claro ou escuro, o que
 *   contrastar mais).
 * - **lateral** → `--sidebar*`. A cor ESCOLHIDA é respeitada como está, clara
 *   ou escura, e o texto do menu é que se adapta (claro sobre fundo escuro,
 *   escuro sobre fundo claro), até ler em AA. Até 2026-10-09 a barra era
 *   forçada a escura: quem escolhia branco ou um azul vivo recebia um quase
 *   preto, e a tela parecia ignorar a escolha.
 *   Duas exceções continuam escurecendo: o tema ESCURO (uma faixa clara ao
 *   lado de uma tela escura ofusca) e a barra SEM cor própria, que acompanha
 *   o matiz da primária — ali ninguém escolheu a cor do menu, e a primária
 *   pura como fundo de menu grita.
 */
export function derivarTema(cores: CoresDoTema, modo: ModoTema): TokensDeTema {
  const tokens: TokensDeTema = {};

  if (corValida(cores.cor_primaria)) {
    const base = hexParaHsl(cores.cor_primaria);
    const marca =
      modo === "light"
        ? ajustarAteContrastar(base, BRANCO, -2)
        : ajustarAteContrastar(comL(base, Math.max(base.l, 55)), FUNDO_ESCURO, 2);
    tokens["--brand"] = token(marca);
    tokens["--brand-light"] = token(comL(marca, marca.l + (modo === "light" ? 6 : 10)));
    tokens["--brand-dark"] = token(comL(marca, marca.l - (modo === "light" ? 7 : 16)));
  }

  if (corValida(cores.cor_destaque)) {
    const base = hexParaHsl(cores.cor_destaque);
    const acento = modo === "light" ? base : comL(base, Math.max(base.l, 58));
    tokens["--accent"] = token(acento);
    tokens["--accent-light"] = token(comL(acento, acento.l + 12));
    tokens["--accent-dark"] = token(comL(acento, acento.l - 12));
    const escuro: Hsl = { h: acento.h, s: 60, l: 10 };
    tokens["--accent-foreground"] = token(
      contraste(acento, BRANCO) >= contraste(acento, escuro) ? BRANCO : escuro,
    );
  }

  // Títulos: a cor escolhida, andando só o necessário para ler sobre o canvas
  // do modo (escurece no claro, clareia no escuro). Os dois tokens recebem o
  // mesmo valor — sem a cor, cada um volta ao seu padrão do `globals.css`
  // (texto para o título de tela, marca para o do "Menu principal").
  if (corValida(cores.cor_titulos)) {
    const titulo = textoLegivel(
      hexParaHsl(cores.cor_titulos),
      modo === "light" ? FUNDO_CLARO : FUNDO_ESCURO,
      modo === "light" ? -2 : 2,
    );
    tokens["--titulo"] = token(titulo);
    tokens["--titulo-destaque"] = token(titulo);
  }

  const lateral = corValida(cores.cor_lateral)
    ? hexParaHsl(cores.cor_lateral)
    : corValida(cores.cor_primaria)
      ? hexParaHsl(cores.cor_primaria)
      : null;
  if (lateral) {
    const escolhida = corValida(cores.cor_lateral) && modo === "light";
    const bruto: Hsl = escolhida
      ? lateral
      : {
          h: lateral.h,
          s: limitar(lateral.s, 0, 62),
          l: limitar(lateral.l, 8, modo === "light" ? 20 : 14),
        };
    // O token é gravado com HSL inteiro. O contraste do texto tem de ser
    // medido contra o fundo que VAI PARA A TELA, não contra o de antes do
    // arredondamento — a diferença é pequena, mas decide o caso no limite.
    const fundo: Hsl = {
      h: Math.round(bruto.h),
      s: Math.round(bruto.s),
      l: Math.round(bruto.l),
    };
    // Texto: o lado que contrastar mais com o fundo, levado até AA. Num
    // cinza médio nem o quase-branco nem o quase-preto chegam a 4.5 (dão
    // ~4.4), mas branco ou preto PUROS sempre chegam — o produto dos dois
    // contrastes é 21. Por isso o ajuste final, e não só a escolha do lado.
    const textoClaro: Hsl = { h: fundo.h, s: 18, l: 94 };
    const textoEscuro: Hsl = { h: fundo.h, s: 30, l: 12 };
    const fundoClaro = contraste(fundo, textoEscuro) > contraste(fundo, textoClaro);
    // Sobre fundo claro tudo anda para o ESCURO (hover, borda, texto apagado);
    // sobre fundo escuro, para o claro. `d` é esse sentido.
    const d = fundoClaro ? -1 : 1;
    tokens["--sidebar"] = token(fundo);
    tokens["--sidebar-accent"] = token(comL(fundo, fundo.l + 4 * d));
    tokens["--sidebar-active"] = token(comL(fundo, fundo.l + 7 * d));
    tokens["--sidebar-border"] = token({ ...fundo, s: fundo.s * 0.75, l: limitar(fundo.l + 9 * d, 0, 100) });
    tokens["--sidebar-foreground"] = token(
      textoLegivel(fundoClaro ? textoEscuro : textoClaro, fundo, 2 * d),
    );
    tokens["--sidebar-muted-foreground"] = token(
      textoLegivel({ h: fundo.h, s: 16, l: fundoClaro ? 40 : 70 }, fundo, 2 * d),
    );
  }

  return tokens;
}

/** Todos os tokens que `derivarTema` pode definir — usado para limpar. */
export const TOKENS_DE_TEMA = [
  "--brand",
  "--brand-light",
  "--brand-dark",
  "--accent",
  "--accent-light",
  "--accent-dark",
  "--accent-foreground",
  "--sidebar",
  "--sidebar-accent",
  "--sidebar-active",
  "--sidebar-border",
  "--sidebar-foreground",
  "--sidebar-muted-foreground",
  "--titulo",
  "--titulo-destaque",
] as const;

/** Aplica o tema num elemento, removendo o que a paleta nova não define. */
export function aplicarTema(el: HTMLElement, tokens: TokensDeTema): void {
  for (const nome of TOKENS_DE_TEMA) {
    if (nome in tokens) el.style.setProperty(nome, tokens[nome]);
    else el.style.removeProperty(nome);
  }
}

// --- Cache local, para a cor do município já valer antes da 1ª resposta da API
//
// O branding chega por fetch, depois da hidratação: sem cache, toda navegação
// abriria no verde padrão e "piscaria" para a cor do município. O script de
// `<head>` abaixo aplica o último tema conhecido antes da primeira pintura.

export const STORAGE_TEMA = "aprimora.tema-cores";

export function guardarTema(cores: CoresDoTema): void {
  try {
    const temas = {
      light: derivarTema(cores, "light"),
      dark: derivarTema(cores, "dark"),
      // Só a CHAVE vai para o cache; o script de `<head>` a traduz por uma
      // tabela própria. Guardar o valor de CSS seria confiar no localStorage.
      fonte: cssDaFonte(cores.fonte_titulos) ? cores.fonte_titulos : null,
    };
    window.localStorage.setItem(STORAGE_TEMA, JSON.stringify(temas));
  } catch {
    // Armazenamento bloqueado: o tema só chega depois do fetch, como antes.
  }
}

/**
 * Roda no `<head>`, depois do `THEME_INIT_SCRIPT` (que já pôs a classe `dark`).
 * Só aceita nome começando por `--` e valor no formato de token HSL: o conteúdo
 * do `localStorage` não é confiável o bastante para virar CSS sem filtro. A
 * fonte segue a mesma regra por outro caminho: do cache sai só a CHAVE, e o
 * valor de CSS vem da tabela embutida aqui.
 */
export const TEMA_CORES_INIT_SCRIPT = `(function(){try{var t=JSON.parse(localStorage.getItem(${JSON.stringify(
  STORAGE_TEMA,
)})||"null");if(!t)return;var r=document.documentElement,m=t[r.classList.contains("dark")?"dark":"light"]||{};for(var k in m){if(/^--[a-z-]+$/.test(k)&&/^\\d{1,3} \\d{1,3}% \\d{1,3}%$/.test(m[k]))r.style.setProperty(k,m[k]);}var F=${JSON.stringify(
  Object.fromEntries(FONTES.filter((f) => f.css).map((f) => [f.chave, f.css])),
)};if(typeof t.fonte==="string"&&Object.prototype.hasOwnProperty.call(F,t.fonte))r.style.setProperty("--font-display",F[t.fonte]);}catch(e){}})();`;
