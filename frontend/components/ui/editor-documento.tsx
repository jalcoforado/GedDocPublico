"use client";

import type { Editor } from "@tiptap/react";
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Bold,
  Columns3,
  Eye,
  Image as ImageIcon,
  IndentDecrease,
  IndentIncrease,
  Italic,
  Link as LinkIcon,
  List,
  ListOrdered,
  Loader2,
  Printer,
  Quote,
  Redo2,
  RemoveFormatting,
  Rows3,
  SeparatorHorizontal,
  Strikethrough,
  Table as TableIcon,
  Trash2,
  Underline as UnderlineIcon,
  Undo2,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ActionsMenu, type ActionsMenuItem } from "@/components/ui/actions-menu";
import {
  LARGURA_TEXTO_CM,
  PASSO_RECUO_CM,
  arredondarCm,
  limitarRecuos,
  recuosNoCursor,
  type Recuos,
} from "@/components/ui/extensao-recuo";
import { cn } from "@/lib/utils";

/**
 * Editor de documento com cara de Google Docs (SI-67) — a moldura do
 * `RichTextEditor variante="documento"`: no topo, o nome do documento com a
 * barra de menus embaixo (Arquivo, Editar, Ver, Inserir, Formatar) e as ações
 * à direita; a barra de ferramentas; a régua com os recuos que se arrastam; e
 * a folha A4 sobre fundo cinza, com o papel timbrado da prefeitura.
 *
 * Por que o nosso editor e não o Google Docs embutido: o SI-66 testaria o
 * Google num `<iframe>`, mas depende da credencial do Google, e o despacho
 * nunca pode ir para o Google (o texto sairia do sistema antes de ser ato).
 * Este é o "plano B" do card: a mesma tela para os dois.
 *
 * O texto na folha usa o MESMO CSS do PDF (`estilo-impressao`), escopado à
 * folha por `escoparCss`: o que se vê ao escrever é o que sai impresso.
 */

/** Escopo do CSS do documento: as regras do PDF valem só dentro dele. */
export const ESCOPO_FOLHA = ".folha-doc";

/** Margem da página (cm), a do `@page` do PDF. Os recuos contam a partir dela. */
const MARGEM_CM = 2;
const LARGURA_PAGINA_CM = 21;
/** 21 cm em px CSS (96 dpi). */
const LARGURA_PAGINA_PX = (LARGURA_PAGINA_CM / 2.54) * 96;

/**
 * Reescreve o CSS do PDF para valer só dentro de `escopo`: `body`/`html` viram
 * o próprio escopo e todo seletor ganha o escopo na frente. `@page` (margens
 * de impressão) é do motor de PDF e fica de fora — a folha da tela já tem as
 * mesmas margens. Usa o parser do navegador; sem ele (ambiente de teste),
 * devolve vazio e a folha fica só com a moldura.
 */
export function escoparCss(css: string, escopo: string = ESCOPO_FOLHA): string {
  if (!css || typeof CSSStyleSheet === "undefined") return "";
  let folha: CSSStyleSheet;
  try {
    folha = new CSSStyleSheet();
    folha.replaceSync(css);
  } catch {
    return "";
  }
  const saida: string[] = [];
  for (const regra of Array.from(folha.cssRules)) {
    if (!(regra instanceof CSSStyleRule)) continue;
    const seletores = regra.selectorText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .map((s) => (s === "body" || s === "html" ? escopo : `${escopo} ${s}`));
    saida.push(`${seletores.join(", ")} { ${regra.style.cssText} }`);
  }
  return saida.join("\n");
}

/** Imprime o documento inteiro (timbre + título + corpo) com o CSS do PDF. */
export function imprimirDocumento({
  css,
  cabecalhoHtml,
  rodapeHtml,
  conteudoHtml,
  titulo,
}: {
  css: string;
  cabecalhoHtml: string;
  rodapeHtml: string;
  conteudoHtml: string;
  titulo: string;
}) {
  const iframe = document.createElement("iframe");
  // Sem `allow-scripts`: nada do conteúdo roda. `allow-modals` é o que deixa
  // o diálogo de impressão abrir a partir do iframe.
  iframe.setAttribute("sandbox", "allow-same-origin allow-modals");
  iframe.style.position = "fixed";
  iframe.style.width = "0";
  iframe.style.height = "0";
  iframe.style.border = "0";
  document.body.appendChild(iframe);
  const doc = iframe.contentDocument;
  if (!doc) {
    iframe.remove();
    return;
  }
  doc.open();
  doc.write(
    `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${escaparHtml(titulo)}</title>` +
      `<style>${css}</style></head><body>${cabecalhoHtml}${conteudoHtml}${rodapeHtml}</body></html>`,
  );
  doc.close();
  const limpar = () => setTimeout(() => iframe.remove(), 1000);
  iframe.contentWindow?.addEventListener("afterprint", limpar);
  setTimeout(() => {
    iframe.contentWindow?.focus();
    iframe.contentWindow?.print();
    limpar();
  }, 250);
}

function escaparHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

const ZOOMS = [50, 75, 90, 100, 125, 150, 200];
type Zoom = number | "ajustar";
/** "Ajustar": a folha ocupa a largura disponível, sem ficar ilegível nem enorme. */
const AJUSTE_MIN = 0.5;
const AJUSTE_MAX = 1.25;

type Estilo = "normal" | "titulo" | "subtitulo";

function estiloAtual(editor: Editor): Estilo {
  if (editor.isActive("heading", { level: 2 })) return "titulo";
  if (editor.isActive("heading", { level: 3 })) return "subtitulo";
  return "normal";
}

function aplicarEstilo(editor: Editor, estilo: Estilo) {
  const c = editor.chain().focus();
  if (estilo === "titulo") c.setHeading({ level: 2 }).run();
  else if (estilo === "subtitulo") c.setHeading({ level: 3 }).run();
  else c.setParagraph().run();
}

function hojePorExtenso(): string {
  return new Date().toLocaleDateString("pt-BR", { day: "numeric", month: "long", year: "numeric" });
}

/** "1,25 cm" */
function cm(v: number): string {
  return `${arredondarCm(v).toLocaleString("pt-BR")} cm`;
}

function Botao({
  rotulo,
  icon: Icon,
  onClick,
  ativo,
  desabilitado,
  girando,
}: {
  rotulo: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick: () => void;
  ativo?: boolean;
  desabilitado?: boolean;
  girando?: boolean;
}) {
  return (
    <button
      type="button"
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
      disabled={desabilitado}
      title={rotulo}
      aria-label={rotulo}
      aria-pressed={ativo}
      className={cn(
        "inline-flex h-7 w-7 shrink-0 items-center justify-center rounded transition-colors duration-fast",
        "hover:bg-foreground/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent",
        ativo ? "bg-brand/15 text-brand" : "text-foreground",
      )}
    >
      <Icon className={cn("h-4 w-4", girando && "animate-spin")} aria-hidden="true" />
    </button>
  );
}

function Separador() {
  return <span className="mx-1 h-5 w-px shrink-0 bg-border-strong/60" aria-hidden="true" />;
}

const SELECT_BARRA =
  "h-7 shrink-0 cursor-pointer rounded border-0 bg-transparent px-1.5 text-sm text-foreground " +
  "hover:bg-foreground/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

type Marcador = "esquerdo" | "primeira" | "direito";

const ROTULO_MARCADOR: Record<Marcador, string> = {
  esquerdo: "Recuo esquerdo",
  primeira: "Recuo da primeira linha",
  direito: "Recuo direito",
};

/**
 * Régua em centímetros com os recuos do parágrafo onde está o cursor, como no
 * Google Docs: arraste o triângulo da esquerda (recuo esquerdo), a barrinha de
 * cima (primeira linha) ou o triângulo da direita (recuo direito). Teclado:
 * setas movem 0,25 cm. As faixas cinza são a margem da página (2 cm), a mesma
 * do PDF.
 */
function Regua({ editor }: { editor: Editor }) {
  const reguaRef = useRef<HTMLDivElement>(null);
  const [arrastando, setArrastando] = useState<{ marcador: Marcador; valor: number } | null>(null);
  const atual = recuosNoCursor(editor);

  // Posição de cada marcador, em cm a partir da borda esquerda da folha.
  const posicao: Record<Marcador, number> = {
    esquerdo: MARGEM_CM + atual.recuoEsquerdo,
    primeira: MARGEM_CM + atual.recuoEsquerdo + atual.recuoPrimeiraLinha,
    direito: LARGURA_PAGINA_CM - MARGEM_CM - atual.recuoDireito,
  };

  /** Recuos novos a partir da posição (cm na folha) de um marcador. */
  function recuosPara(marcador: Marcador, cmNaFolha: number, base: Recuos): Recuos {
    const passo = Math.round(cmNaFolha * 4) / 4; // 0,25 cm, como o Google
    if (marcador === "esquerdo") {
      return limitarRecuos({ ...base, recuoEsquerdo: passo - MARGEM_CM });
    }
    if (marcador === "primeira") {
      return limitarRecuos({ ...base, recuoPrimeiraLinha: passo - MARGEM_CM - base.recuoEsquerdo });
    }
    return limitarRecuos({ ...base, recuoDireito: LARGURA_PAGINA_CM - MARGEM_CM - passo });
  }

  function aplicar(r: Recuos, historico: boolean) {
    editor
      .chain()
      .command(({ tr }) => {
        if (!historico) tr.setMeta("addToHistory", false);
        return true;
      })
      .definirRecuo(r)
      .run();
  }

  function comecarArrasto(marcador: Marcador, e: React.PointerEvent) {
    e.preventDefault();
    const regua = reguaRef.current;
    if (!regua) return;
    const original = recuosNoCursor(editor);
    let ultimo = original;
    const mover = (ev: PointerEvent) => {
      // A régua está dentro do zoom: o retângulo já vem na escala da tela.
      const r = regua.getBoundingClientRect();
      const cmNaFolha = ((ev.clientX - r.left) / r.width) * LARGURA_PAGINA_CM;
      ultimo = recuosPara(marcador, cmNaFolha, original);
      setArrastando({ marcador, valor: valorDo(marcador, ultimo) });
      aplicar(ultimo, false);
    };
    const soltar = () => {
      window.removeEventListener("pointermove", mover);
      window.removeEventListener("pointerup", soltar);
      setArrastando(null);
      // Um passo só no "desfazer": volta ao original sem histórico e aplica o
      // final com histórico.
      aplicar(original, false);
      aplicar(ultimo, true);
      editor.commands.focus();
    };
    window.addEventListener("pointermove", mover);
    window.addEventListener("pointerup", soltar);
  }

  function valorDo(marcador: Marcador, r: Recuos): number {
    return marcador === "esquerdo"
      ? r.recuoEsquerdo
      : marcador === "primeira"
        ? r.recuoPrimeiraLinha
        : r.recuoDireito;
  }

  function teclado(marcador: Marcador, e: React.KeyboardEvent) {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const delta = e.key === "ArrowRight" ? 0.25 : -0.25;
    aplicar(recuosPara(marcador, posicao[marcador] + delta, atual), true);
  }

  return (
    <div ref={reguaRef} className="editor-doc-regua" role="group" aria-label="Régua e recuos do parágrafo">
      <span
        className="editor-doc-regua-margem"
        style={{ left: 0 }}
        title="Margem da página: 2 cm (a mesma do PDF)"
      />
      <span
        className="editor-doc-regua-margem"
        style={{ right: 0 }}
        title="Margem da página: 2 cm (a mesma do PDF)"
      />
      {Array.from({ length: LARGURA_TEXTO_CM - 1 }, (_, i) => i + 1).map((n) => (
        <span key={n} className="editor-doc-regua-numero" style={{ left: `${MARGEM_CM + n}cm` }} aria-hidden="true">
          {n}
        </span>
      ))}
      {(["primeira", "esquerdo", "direito"] as const).map((m) => (
        <button
          key={m}
          type="button"
          className={cn("editor-doc-marcador", `editor-doc-marcador-${m}`)}
          style={{ left: `${posicao[m]}cm` }}
          aria-label={`${ROTULO_MARCADOR[m]}: ${cm(valorDo(m, atual))}`}
          title={`${ROTULO_MARCADOR[m]}: ${cm(valorDo(m, atual))} — arraste para mudar`}
          onPointerDown={(e) => comecarArrasto(m, e)}
          onKeyDown={(e) => teclado(m, e)}
        />
      ))}
      {arrastando && (
        <span className="editor-doc-regua-dica" style={{ left: `${posicao[arrastando.marcador]}cm` }}>
          {ROTULO_MARCADOR[arrastando.marcador]}: {cm(arrastando.valor)}
        </span>
      )}
    </div>
  );
}

export interface OpcoesDocumento {
  /** CSS do PDF (`estilo-impressao.css`), aplicado só dentro da folha. */
  css?: string;
  /** Dentro da folha, acima do texto: o papel timbrado e o título. */
  cabecalho?: React.ReactNode;
  /** Dentro da folha, no pé: o rodapé do timbre. */
  rodape?: React.ReactNode;
  /** Itens do menu Arquivo (salvar, modelos, imprimir, fechar…): são da tela. */
  menuArquivo?: ActionsMenuItem[];
  /** Ctrl+S. */
  onSalvar?: () => void;
  onImprimir?: () => void;
  /** Pré-visualização do PDF à direita da folha (Ver › Pré-visualização). */
  previa?: React.ReactNode;
  previaAberta?: boolean;
  onAlternarPrevia?: () => void;
  /** Acima da folha, fora dela: avisos (ex.: campo não preenchido). */
  aviso?: React.ReactNode;
}

/** Topo, barras, régua e folha. Recebe o editor já criado pelo `RichTextEditor`. */
export function MolduraDocumento({
  editor,
  opcoes,
  conteudo,
  uploading,
  onInserirImagem,
  onLink,
  className,
}: {
  editor: Editor;
  opcoes: OpcoesDocumento;
  /** O `<EditorContent>`. */
  conteudo: React.ReactNode;
  uploading: boolean;
  onInserirImagem: () => void;
  onLink: () => void;
  className?: string;
}) {
  const [zoom, setZoom] = useState<Zoom>("ajustar");
  const [regua, setRegua] = useState(true);
  const [largura, setLargura] = useState(0);
  const telaRef = useRef<HTMLDivElement>(null);
  const cssEscopado = useMemo(() => escoparCss(opcoes.css ?? ""), [opcoes.css]);
  const emTabela = editor.isActive("table");
  const ch = () => editor.chain().focus();

  // Largura da área da folha, para o "Ajustar".
  useEffect(() => {
    const el = telaRef.current;
    if (!el) return;
    const medir = () => setLargura(el.clientWidth);
    medir();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(medir);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const escala =
    zoom === "ajustar"
      ? largura > 0
        ? Math.min(AJUSTE_MAX, Math.max(AJUSTE_MIN, (largura - 64) / LARGURA_PAGINA_PX))
        : 1
      : zoom / 100;

  // Ctrl + roda do mouse muda o zoom da folha (como no Google Docs), em vez do
  // zoom da página inteira. Ouvinte nativo: o do React é passivo e não deixa
  // cancelar o zoom do navegador.
  const escalaRef = useRef(escala);
  escalaRef.current = escala;
  useEffect(() => {
    const el = telaRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const atual = Math.round(escalaRef.current * 100);
      const proximo = e.deltaY < 0 ? ZOOMS.find((z) => z > atual) : [...ZOOMS].reverse().find((z) => z < atual);
      if (proximo) setZoom(proximo);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const recuoPrimeira = recuosNoCursor(editor).recuoPrimeiraLinha;

  const menus: { rotulo: string; itens: ActionsMenuItem[] }[] = [
    { rotulo: "Arquivo", itens: opcoes.menuArquivo ?? [] },
    {
      rotulo: "Editar",
      itens: [
        { label: "Desfazer (Ctrl+Z)", icon: Undo2, onClick: () => ch().undo().run(), disabled: !editor.can().undo() },
        { label: "Refazer (Ctrl+Y)", icon: Redo2, onClick: () => ch().redo().run(), disabled: !editor.can().redo() },
        { label: "Selecionar tudo (Ctrl+A)", onClick: () => ch().selectAll().run() },
      ],
    },
    {
      rotulo: "Ver",
      itens: [
        ...(opcoes.onAlternarPrevia
          ? [
              {
                label: opcoes.previaAberta ? "Ocultar pré-visualização do PDF" : "Pré-visualização do PDF ao lado",
                icon: Eye,
                onClick: opcoes.onAlternarPrevia,
              },
            ]
          : []),
        { label: regua ? "Ocultar régua" : "Mostrar régua", onClick: () => setRegua((r) => !r) },
        { label: "Ajustar à largura", onClick: () => setZoom("ajustar") },
        { label: "Zoom 100%", onClick: () => setZoom(100) },
        { label: "Zoom 150%", onClick: () => setZoom(150) },
      ],
    },
    {
      rotulo: "Inserir",
      itens: [
        { label: "Imagem", icon: ImageIcon, onClick: onInserirImagem, disabled: uploading },
        {
          label: "Tabela",
          icon: TableIcon,
          onClick: () => ch().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(),
          disabled: emTabela,
        },
        { label: "Link", icon: LinkIcon, onClick: onLink },
        { label: "Linha horizontal", icon: SeparatorHorizontal, onClick: () => ch().setHorizontalRule().run() },
        { label: "Data de hoje", onClick: () => ch().insertContent(hojePorExtenso()).run() },
      ],
    },
    {
      rotulo: "Formatar",
      itens: [
        { label: "Negrito (Ctrl+B)", icon: Bold, onClick: () => ch().toggleBold().run() },
        { label: "Itálico (Ctrl+I)", icon: Italic, onClick: () => ch().toggleItalic().run() },
        { label: "Sublinhado (Ctrl+U)", icon: UnderlineIcon, onClick: () => ch().toggleUnderline().run() },
        { label: "Tachado", icon: Strikethrough, onClick: () => ch().toggleStrike().run() },
        { label: "Texto normal", onClick: () => aplicarEstilo(editor, "normal") },
        { label: "Título", onClick: () => aplicarEstilo(editor, "titulo") },
        { label: "Subtítulo", onClick: () => aplicarEstilo(editor, "subtitulo") },
        { label: "Alinhar à esquerda", icon: AlignLeft, onClick: () => ch().setTextAlign("left").run() },
        { label: "Centralizar", icon: AlignCenter, onClick: () => ch().setTextAlign("center").run() },
        { label: "Alinhar à direita", icon: AlignRight, onClick: () => ch().setTextAlign("right").run() },
        { label: "Justificar", icon: AlignJustify, onClick: () => ch().setTextAlign("justify").run() },
        { label: "Aumentar recuo (Ctrl+])", icon: IndentIncrease, onClick: () => ch().mudarRecuoEsquerdo(PASSO_RECUO_CM).run() },
        { label: "Diminuir recuo (Ctrl+[)", icon: IndentDecrease, onClick: () => ch().mudarRecuoEsquerdo(-PASSO_RECUO_CM).run() },
        {
          label: recuoPrimeira ? "Tirar o recuo da primeira linha" : "Recuo da primeira linha (1,25 cm)",
          onClick: () => ch().definirRecuo({ recuoPrimeiraLinha: recuoPrimeira ? 0 : PASSO_RECUO_CM }).run(),
        },
        {
          label: "Limpar formatação",
          icon: RemoveFormatting,
          onClick: () =>
            ch()
              .unsetAllMarks()
              .clearNodes()
              .definirRecuo({ recuoEsquerdo: 0, recuoDireito: 0, recuoPrimeiraLinha: 0 })
              .run(),
        },
      ],
    },
  ];

  return (
    <div
      className={cn("flex min-h-0 flex-1 flex-col", className)}
      onKeyDown={(e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && opcoes.onSalvar) {
          e.preventDefault();
          opcoes.onSalvar();
        }
      }}
    >
      {/* Menus logo abaixo do nome do documento (que a tela põe acima, com o
          ícone à esquerda): o recuo alinha os menus com o nome, como no Google
          Docs. */}
      <div className="shrink-0 bg-card px-3">
        <div>
          <div className="min-w-0 pl-[2.6rem]">
            <nav aria-label="Menus do documento" className="-ml-2 flex flex-wrap items-center">
              {menus.map((m) => (
                <ActionsMenu
                  key={m.rotulo}
                  label={m.rotulo}
                  items={m.itens}
                  variant="ghost"
                  semSeta
                  placement="bottom-start"
                  className="[&>button]:h-7 [&>button]:px-2 [&>button]:text-sm [&>button]:font-normal"
                />
              ))}
            </nav>
          </div>
        </div>
        <div
          role="toolbar"
          aria-label="Formatação do texto"
          className="my-2 flex items-center gap-0.5 overflow-x-auto rounded-full bg-surface-2 px-3 py-1"
        >
          <Botao rotulo="Desfazer (Ctrl+Z)" icon={Undo2} onClick={() => ch().undo().run()} desabilitado={!editor.can().undo()} />
          <Botao rotulo="Refazer (Ctrl+Y)" icon={Redo2} onClick={() => ch().redo().run()} desabilitado={!editor.can().redo()} />
          {opcoes.onImprimir && <Botao rotulo="Imprimir" icon={Printer} onClick={opcoes.onImprimir} />}
          <Separador />
          <select
            aria-label="Zoom"
            title="Zoom (Ctrl + roda do mouse)"
            value={zoom === "ajustar" ? "ajustar" : String(zoom)}
            onChange={(e) => setZoom(e.target.value === "ajustar" ? "ajustar" : Number(e.target.value))}
            className={cn(SELECT_BARRA, "w-[5.5rem]")}
          >
            <option value="ajustar">
              {zoom === "ajustar" ? `${Math.round(escala * 100)}%` : "Ajustar"}
            </option>
            {ZOOMS.map((z) => (
              <option key={z} value={z}>
                {z}%
              </option>
            ))}
          </select>
          <Separador />
          <select
            aria-label="Estilo do parágrafo"
            value={estiloAtual(editor)}
            onChange={(e) => aplicarEstilo(editor, e.target.value as Estilo)}
            className={cn(SELECT_BARRA, "w-32")}
          >
            <option value="normal">Texto normal</option>
            <option value="titulo">Título</option>
            <option value="subtitulo">Subtítulo</option>
          </select>
          <Separador />
          <Botao rotulo="Negrito (Ctrl+B)" icon={Bold} onClick={() => ch().toggleBold().run()} ativo={editor.isActive("bold")} />
          <Botao rotulo="Itálico (Ctrl+I)" icon={Italic} onClick={() => ch().toggleItalic().run()} ativo={editor.isActive("italic")} />
          <Botao rotulo="Sublinhado (Ctrl+U)" icon={UnderlineIcon} onClick={() => ch().toggleUnderline().run()} ativo={editor.isActive("underline")} />
          <Botao rotulo="Tachado" icon={Strikethrough} onClick={() => ch().toggleStrike().run()} ativo={editor.isActive("strike")} />
          <Separador />
          <Botao rotulo="Inserir/editar link" icon={LinkIcon} onClick={onLink} ativo={editor.isActive("link")} />
          <Botao
            rotulo={uploading ? "Enviando imagem…" : "Inserir imagem"}
            icon={uploading ? Loader2 : ImageIcon}
            girando={uploading}
            onClick={onInserirImagem}
            desabilitado={uploading}
          />
          {emTabela ? (
            <>
              <Botao rotulo="Adicionar coluna" icon={Columns3} onClick={() => ch().addColumnAfter().run()} />
              <Botao rotulo="Adicionar linha" icon={Rows3} onClick={() => ch().addRowAfter().run()} />
              <Botao rotulo="Excluir tabela" icon={Trash2} onClick={() => ch().deleteTable().run()} />
            </>
          ) : (
            <Botao
              rotulo="Inserir tabela"
              icon={TableIcon}
              onClick={() => ch().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}
            />
          )}
          <Separador />
          <Botao rotulo="Alinhar à esquerda" icon={AlignLeft} onClick={() => ch().setTextAlign("left").run()} ativo={editor.isActive({ textAlign: "left" })} />
          <Botao rotulo="Centralizar" icon={AlignCenter} onClick={() => ch().setTextAlign("center").run()} ativo={editor.isActive({ textAlign: "center" })} />
          <Botao rotulo="Alinhar à direita" icon={AlignRight} onClick={() => ch().setTextAlign("right").run()} ativo={editor.isActive({ textAlign: "right" })} />
          <Botao rotulo="Justificar" icon={AlignJustify} onClick={() => ch().setTextAlign("justify").run()} ativo={editor.isActive({ textAlign: "justify" })} />
          <Separador />
          <Botao rotulo="Lista com marcadores" icon={List} onClick={() => ch().toggleBulletList().run()} ativo={editor.isActive("bulletList")} />
          <Botao rotulo="Lista numerada" icon={ListOrdered} onClick={() => ch().toggleOrderedList().run()} ativo={editor.isActive("orderedList")} />
          <Botao rotulo="Diminuir recuo (Ctrl+[)" icon={IndentDecrease} onClick={() => ch().mudarRecuoEsquerdo(-PASSO_RECUO_CM).run()} />
          <Botao rotulo="Aumentar recuo (Ctrl+])" icon={IndentIncrease} onClick={() => ch().mudarRecuoEsquerdo(PASSO_RECUO_CM).run()} />
          <Botao rotulo="Citação" icon={Quote} onClick={() => ch().toggleBlockquote().run()} ativo={editor.isActive("blockquote")} />
          <Botao rotulo="Linha horizontal" icon={SeparatorHorizontal} onClick={() => ch().setHorizontalRule().run()} />
          <Separador />
          <Botao
            rotulo="Limpar formatação"
            icon={RemoveFormatting}
            onClick={() =>
              ch().unsetAllMarks().clearNodes().definirRecuo({ recuoEsquerdo: 0, recuoDireito: 0, recuoPrimeiraLinha: 0 }).run()
            }
          />
          {opcoes.onAlternarPrevia && (
            <>
              <span className="ml-auto" />
              <Botao
                rotulo="Pré-visualização do PDF ao lado"
                icon={Eye}
                onClick={opcoes.onAlternarPrevia}
                ativo={opcoes.previaAberta}
              />
            </>
          )}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 border-t border-border">
        <div ref={telaRef} className="min-h-0 min-w-0 flex-1 overflow-auto bg-muted">
          {opcoes.aviso && <div className="mx-auto max-w-[21cm] px-4 pt-3">{opcoes.aviso}</div>}
          <div className="px-4 pb-10 pt-3" style={{ zoom: escala }}>
            {regua && (
              <div className="sticky top-0 z-sticky mb-3">
                <Regua editor={editor} />
              </div>
            )}
            {cssEscopado && <style>{cssEscopado}</style>}
            <div className="folha-doc editor-doc-folha">
              <div className="editor-doc-miolo">
                {opcoes.cabecalho}
                {conteudo}
              </div>
              {opcoes.rodape}
            </div>
          </div>
        </div>
        {opcoes.previaAberta && opcoes.previa && (
          <aside
            aria-label="Pré-visualização do PDF"
            className="hidden w-[min(40rem,45%)] shrink-0 flex-col border-l border-border bg-card p-3 lg:flex"
          >
            {opcoes.previa}
          </aside>
        )}
      </div>
    </div>
  );
}
