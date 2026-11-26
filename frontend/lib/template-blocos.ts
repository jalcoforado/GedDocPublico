/**
 * Template montado por blocos (SI-31): o modelo vira uma lista de blocos
 * (título, texto, campo automático, data e local, assinatura, separador) que
 * se arrastam e reordenam. O que se grava continua sendo `corpo_html` — o
 * resto do sistema (redigir, placeholders, PDF) não muda nada.
 *
 * Como o bloco sobrevive à gravação: cada um sai embrulhado num
 * `<div class="bloco bloco-<tipo>">` — `div` com `class` é o que o
 * `html_sanitizer` do backend aceita. Dentro do embrulho só vai o que o editor
 * (TipTap) entende: `<h2>`, `<p>` com `text-align`, `<strong>`, `<hr>`. Ao
 * redigir uma minuta, o editor descarta o embrulho e fica com o conteúdo —
 * o bloco só importa para quem edita o MODELO.
 *
 * HTML que não veio de bloco (template antigo, ou editado no editor livre)
 * vira bloco de Texto: nada se perde ao abrir um modelo existente.
 */

export type TipoBloco = "titulo" | "texto" | "campo" | "data_local" | "assinatura" | "separador";

export type Alinhamento = "center" | "left";

export type Bloco =
  | { id: string; tipo: "titulo"; texto: string; alinhamento: Alinhamento }
  | { id: string; tipo: "texto"; html: string }
  | { id: string; tipo: "campo"; rotulo: string; chave: string }
  | { id: string; tipo: "data_local"; local: string }
  | { id: string; tipo: "assinatura"; nome: string; cargo: string }
  | { id: string; tipo: "separador" };

export interface InfoBloco {
  tipo: TipoBloco;
  rotulo: string;
  /** Uma linha: para que serve. Aparece na paleta. */
  descricao: string;
}

/** Ordem da paleta: a ordem em que um documento oficial costuma ser lido. */
export const CATALOGO_BLOCOS: InfoBloco[] = [
  { tipo: "titulo", rotulo: "Título", descricao: "Nome do documento, em destaque" },
  { tipo: "texto", rotulo: "Texto", descricao: "Parágrafos com negrito, listas e tabelas" },
  { tipo: "campo", rotulo: "Campo automático", descricao: "Dado do processo, preenchido ao redigir" },
  { tipo: "data_local", rotulo: "Data e local", descricao: "Cidade e a data do dia, à direita" },
  { tipo: "assinatura", rotulo: "Assinatura", descricao: "Linha, nome e cargo, centralizados" },
  { tipo: "separador", rotulo: "Separador", descricao: "Linha horizontal entre partes" },
];

export const ROTULO_BLOCO: Record<TipoBloco, string> = Object.fromEntries(
  CATALOGO_BLOCOS.map((b) => [b.tipo, b.rotulo]),
) as Record<TipoBloco, string>;

let seq = 0;
function novoId(): string {
  seq += 1;
  return `b${Date.now().toString(36)}${seq}`;
}

export function novoBloco(tipo: TipoBloco): Bloco {
  const id = novoId();
  switch (tipo) {
    case "titulo":
      return { id, tipo, texto: "", alinhamento: "center" };
    case "texto":
      return { id, tipo, html: "" };
    case "campo":
      return { id, tipo, rotulo: "", chave: "processo.numero" };
    case "data_local":
      return { id, tipo, local: "" };
    case "assinatura":
      return { id, tipo, nome: "{{usuario.nome}}", cargo: "" };
    case "separador":
      return { id, tipo };
  }
}

/** Mesmo bloco com id novo (para duplicar). */
export function copiarBloco(b: Bloco): Bloco {
  return { ...b, id: novoId() };
}

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

const CENTRO = ' style="text-align: center"';
const DIREITA = ' style="text-align: right"';

/** O miolo de um bloco — sem o embrulho. Bloco vazio não gera nada. */
export function htmlDoBloco(b: Bloco): string {
  switch (b.tipo) {
    case "titulo":
      return b.texto.trim()
        ? `<h2${b.alinhamento === "center" ? CENTRO : ""}>${esc(b.texto.trim())}</h2>`
        : "";
    case "texto":
      return b.html.trim();
    case "campo": {
      if (!b.chave) return "";
      const rotulo = b.rotulo.trim().replace(/:$/, "");
      return rotulo
        ? `<p><strong>${esc(rotulo)}:</strong> {{${b.chave}}}</p>`
        : `<p>{{${b.chave}}}</p>`;
    }
    case "data_local": {
      const local = b.local.trim();
      return `<p${DIREITA}>${local ? `${esc(local)}, ` : ""}{{data_hoje}}.</p>`;
    }
    case "assinatura":
      return (
        `<p${CENTRO}>________________________________________</p>` +
        `<p${CENTRO}><strong>${esc(b.nome.trim())}</strong></p>` +
        (b.cargo.trim() ? `<p${CENTRO}>${esc(b.cargo.trim())}</p>` : "")
      );
    case "separador":
      return "<hr>";
  }
}

export function blocosParaHtml(blocos: Bloco[]): string {
  return blocos
    .map((b) => {
      const miolo = htmlDoBloco(b);
      return miolo ? `<div class="bloco bloco-${b.tipo}">${miolo}</div>` : "";
    })
    .join("");
}

const TOKEN = /\{\{\s*([\w.]+)\s*\}\}/;
const TIPOS = new Set<TipoBloco>(CATALOGO_BLOCOS.map((b) => b.tipo));

function tipoDoEmbrulho(el: Element): TipoBloco | null {
  if (el.tagName !== "DIV" || !el.classList.contains("bloco")) return null;
  for (const c of Array.from(el.classList)) {
    const t = c.startsWith("bloco-") ? (c.slice(6) as TipoBloco) : null;
    if (t && TIPOS.has(t)) return t;
  }
  return null;
}

/** Lê os campos de um bloco embrulhado. `null` = não reconheceu: vira Texto. */
function lerBloco(tipo: TipoBloco, el: Element): Bloco | null {
  const id = novoId();
  const filhos = Array.from(el.children);
  switch (tipo) {
    case "titulo": {
      const h = el.querySelector("h1, h2, h3");
      if (!h || filhos.length !== 1) return null;
      const alinhamento: Alinhamento =
        (h as HTMLElement).style.textAlign === "center" ? "center" : "left";
      return { id, tipo, texto: h.textContent ?? "", alinhamento };
    }
    case "texto":
      return { id, tipo, html: el.innerHTML };
    case "campo": {
      const texto = el.textContent ?? "";
      const m = texto.match(TOKEN);
      if (!m || filhos.length !== 1) return null;
      const strong = el.querySelector("strong");
      const rotulo = strong ? (strong.textContent ?? "").replace(/:\s*$/, "") : "";
      return { id, tipo, rotulo, chave: m[1] };
    }
    case "data_local": {
      const texto = (el.textContent ?? "").trim();
      const m = texto.match(/^(?:(.*),\s*)?\{\{\s*data_hoje\s*\}\}\.?$/);
      if (!m) return null;
      return { id, tipo, local: m[1] ?? "" };
    }
    case "assinatura": {
      if (filhos.length < 2 || filhos.length > 3) return null;
      const nome = filhos[1].textContent ?? "";
      const cargo = filhos[2]?.textContent ?? "";
      return { id, tipo, nome, cargo };
    }
    case "separador":
      return el.querySelector("hr") ? { id, tipo } : null;
  }
}

/**
 * HTML → blocos. Embrulho reconhecido vira o bloco dele; o resto — em
 * sequência — vira um bloco de Texto só, com o HTML como estava.
 */
export function htmlParaBlocos(html: string): Bloco[] {
  if (!html.trim()) return [];
  const doc = new DOMParser().parseFromString(`<body>${html}</body>`, "text/html");
  const blocos: Bloco[] = [];
  let solto = "";
  const soltar = () => {
    if (solto.trim()) blocos.push({ id: novoId(), tipo: "texto", html: solto.trim() });
    solto = "";
  };
  for (const no of Array.from(doc.body.childNodes)) {
    if (no.nodeType === Node.ELEMENT_NODE) {
      const el = no as Element;
      const tipo = tipoDoEmbrulho(el);
      if (tipo) {
        soltar();
        blocos.push(lerBloco(tipo, el) ?? { id: novoId(), tipo: "texto", html: el.innerHTML });
        continue;
      }
      solto += el.outerHTML;
    } else if (no.nodeType === Node.TEXT_NODE && (no.textContent ?? "").trim()) {
      solto += `<p>${esc((no.textContent ?? "").trim())}</p>`;
    }
  }
  soltar();
  return blocos;
}

/** Move o item de `de` para a posição `para` (índice no array ANTES da remoção). */
export function moverPara<T>(lista: T[], de: number, para: number): T[] {
  if (de === para || de + 1 === para) return lista;
  const copia = lista.slice();
  const [item] = copia.splice(de, 1);
  copia.splice(para > de ? para - 1 : para, 0, item);
  return copia;
}
