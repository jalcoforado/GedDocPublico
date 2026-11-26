import { Extension, type CommandProps, type Editor } from "@tiptap/react";

/**
 * Recuo do parágrafo (SI-67) — o que a régua do editor de documento mexe, como
 * no Google Docs: recuo esquerdo, recuo direito e recuo da primeira linha.
 *
 * Grava em cm, no `style` do parágrafo/título (`margin-left: 1.25cm`,
 * `margin-right`, `text-indent`). O sanitizador do servidor deixa essas três
 * propriedades passarem e o PDF respeita (`tests/test_si67_recuo_e_imagem.py`).
 *
 * A margem da PÁGINA (2 cm) é do PDF e não muda por documento: o recuo é
 * contado a partir dela.
 */

export const TIPOS_COM_RECUO = ["paragraph", "heading"] as const;

/** Um clique em "Aumentar recuo" — o mesmo passo do Google Docs (0,5"). */
export const PASSO_RECUO_CM = 1.25;
/** Largura do texto na A4 com 2 cm de margem de cada lado. */
export const LARGURA_TEXTO_CM = 17;
/** O que sobra de texto, no mínimo, entre os recuos. */
const TEXTO_MINIMO_CM = 2;

export interface Recuos {
  recuoEsquerdo: number;
  recuoDireito: number;
  recuoPrimeiraLinha: number;
}

/** Arredonda para 2 casas — `0.1 + 0.2` não vira `0.30000000000000004cm`. */
export function arredondarCm(v: number): number {
  return Math.round(v * 100) / 100;
}

function lerCm(valor: string | null | undefined): number {
  const m = /^(-?\d+(?:\.\d+)?)cm$/.exec((valor ?? "").trim());
  return m ? Number(m[1]) : 0;
}

/** Mantém os três recuos dentro da largura do texto. */
export function limitarRecuos(r: Recuos): Recuos {
  const esquerdo = Math.max(0, Math.min(r.recuoEsquerdo, LARGURA_TEXTO_CM - TEXTO_MINIMO_CM));
  const direito = Math.max(0, Math.min(r.recuoDireito, LARGURA_TEXTO_CM - TEXTO_MINIMO_CM - esquerdo));
  const primeira = Math.max(
    -esquerdo,
    Math.min(r.recuoPrimeiraLinha, LARGURA_TEXTO_CM - TEXTO_MINIMO_CM - esquerdo - direito),
  );
  return {
    recuoEsquerdo: arredondarCm(esquerdo),
    recuoDireito: arredondarCm(direito),
    recuoPrimeiraLinha: arredondarCm(primeira),
  };
}

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    recuo: {
      /** Aplica os recuos dados a todos os parágrafos da seleção. */
      definirRecuo: (recuos: Partial<Recuos>) => ReturnType;
      /** Soma `delta` cm ao recuo esquerdo de cada parágrafo da seleção. */
      mudarRecuoEsquerdo: (deltaCm: number) => ReturnType;
    };
  }
}

export const Recuo = Extension.create({
  name: "recuo",

  addGlobalAttributes() {
    const atributo = (cssProp: "marginLeft" | "marginRight" | "textIndent", css: string, nome: keyof Recuos) => ({
      default: 0,
      parseHTML: (el: HTMLElement) => lerCm(el.style[cssProp]),
      renderHTML: (attrs: Record<string, unknown>) => {
        const v = Number(attrs[nome]) || 0;
        return v ? { style: `${css}: ${arredondarCm(v)}cm` } : {};
      },
    });
    return [
      {
        types: [...TIPOS_COM_RECUO],
        attributes: {
          recuoEsquerdo: atributo("marginLeft", "margin-left", "recuoEsquerdo"),
          recuoDireito: atributo("marginRight", "margin-right", "recuoDireito"),
          recuoPrimeiraLinha: atributo("textIndent", "text-indent", "recuoPrimeiraLinha"),
        },
      },
    ];
  },

  addCommands() {
    const aplicar =
      (calcular: (atual: Recuos) => Partial<Recuos>) =>
      ({ tr, state, dispatch }: CommandProps) => {
        const { from, to } = state.selection;
        let mudou = false;
        state.doc.nodesBetween(from, to, (node, pos) => {
          if (!(TIPOS_COM_RECUO as readonly string[]).includes(node.type.name)) return;
          const atual: Recuos = {
            recuoEsquerdo: Number(node.attrs.recuoEsquerdo) || 0,
            recuoDireito: Number(node.attrs.recuoDireito) || 0,
            recuoPrimeiraLinha: Number(node.attrs.recuoPrimeiraLinha) || 0,
          };
          const novo = limitarRecuos({ ...atual, ...calcular(atual) });
          tr.setNodeMarkup(pos, undefined, { ...node.attrs, ...novo });
          mudou = true;
          return false;
        });
        if (mudou && dispatch) dispatch(tr);
        return mudou;
      };
    return {
      definirRecuo: (recuos) => aplicar(() => recuos),
      mudarRecuoEsquerdo: (delta) =>
        aplicar((atual) => ({ recuoEsquerdo: atual.recuoEsquerdo + delta })),
    };
  },

  addKeyboardShortcuts() {
    return {
      // Google Docs: Ctrl+] aumenta e Ctrl+[ diminui o recuo.
      "Mod-]": () => this.editor.commands.mudarRecuoEsquerdo(PASSO_RECUO_CM),
      "Mod-[": () => this.editor.commands.mudarRecuoEsquerdo(-PASSO_RECUO_CM),
    };
  },
});

/** Os recuos do parágrafo onde está o cursor. */
export function recuosNoCursor(editor: Editor): Recuos {
  const no = editor.state.selection.$from.parent;
  return {
    recuoEsquerdo: Number(no.attrs.recuoEsquerdo) || 0,
    recuoDireito: Number(no.attrs.recuoDireito) || 0,
    recuoPrimeiraLinha: Number(no.attrs.recuoPrimeiraLinha) || 0,
  };
}
