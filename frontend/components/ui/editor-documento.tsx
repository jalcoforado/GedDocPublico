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
import { useMemo, useState } from "react";

import { ActionsMenu, type ActionsMenuItem } from "@/components/ui/actions-menu";
import { cn } from "@/lib/utils";

/**
 * Editor de documento com cara de Google Docs (SI-67) — a moldura do
 * `RichTextEditor variante="documento"`: barra de menus (Arquivo, Editar, Ver,
 * Inserir, Formatar), barra de ferramentas, régua e a folha A4 sobre fundo
 * cinza, com o papel timbrado da prefeitura dentro da folha.
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

/** HTML de um documento inteiro (timbre + título + corpo), para imprimir. */
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

const ZOOMS = [50, 75, 90, 100, 125, 150];

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

/** Régua em centímetros: números a partir da margem esquerda, como no Google Docs. */
function Regua() {
  return (
    <div className="editor-doc-regua" aria-hidden="true">
      <span className="editor-doc-regua-margem" style={{ left: 0 }} />
      <span className="editor-doc-regua-margem" style={{ right: 0 }} />
      {Array.from({ length: 16 }, (_, i) => i + 1).map((n) => (
        <span key={n} className="editor-doc-regua-numero" style={{ left: `${2 + n}cm` }}>
          {n}
        </span>
      ))}
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

/** Barras + régua + folha. Recebe o editor já criado pelo `RichTextEditor`. */
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
  const [zoom, setZoom] = useState(100);
  const [regua, setRegua] = useState(true);
  const cssEscopado = useMemo(() => escoparCss(opcoes.css ?? ""), [opcoes.css]);
  const emTabela = editor.isActive("table");
  const ch = () => editor.chain().focus();

  const menus: { rotulo: string; itens: ActionsMenuItem[] }[] = [
    {
      rotulo: "Arquivo",
      itens: opcoes.menuArquivo ?? [],
    },
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
        { label: "Zoom 75%", onClick: () => setZoom(75) },
        { label: "Zoom 100%", onClick: () => setZoom(100) },
        { label: "Zoom 125%", onClick: () => setZoom(125) },
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
        {
          label: "Limpar formatação",
          icon: RemoveFormatting,
          onClick: () => ch().unsetAllMarks().clearNodes().run(),
        },
      ],
    },
  ];

  return (
    <div
      className={cn("flex min-h-0 flex-1 flex-col bg-surface-2", className)}
      onKeyDown={(e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && opcoes.onSalvar) {
          e.preventDefault();
          opcoes.onSalvar();
        }
      }}
    >
      <div className="shrink-0 space-y-1 border-b border-border bg-card px-3 pb-2 pt-1">
        <nav aria-label="Menus do documento" className="flex flex-wrap items-center">
          {menus.map((m) => (
            <ActionsMenu
              key={m.rotulo}
              label={m.rotulo}
              items={m.itens}
              variant="ghost"
              semSeta
              placement="bottom-start"
            />
          ))}
        </nav>
        <div
          role="toolbar"
          aria-label="Formatação do texto"
          className="flex items-center gap-0.5 overflow-x-auto rounded-full bg-surface-2 px-3 py-1"
        >
          <Botao rotulo="Desfazer (Ctrl+Z)" icon={Undo2} onClick={() => ch().undo().run()} desabilitado={!editor.can().undo()} />
          <Botao rotulo="Refazer (Ctrl+Y)" icon={Redo2} onClick={() => ch().redo().run()} desabilitado={!editor.can().redo()} />
          {opcoes.onImprimir && <Botao rotulo="Imprimir" icon={Printer} onClick={opcoes.onImprimir} />}
          <Separador />
          <select
            aria-label="Zoom"
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
            className={SELECT_BARRA}
          >
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
          <Botao rotulo="Citação" icon={Quote} onClick={() => ch().toggleBlockquote().run()} ativo={editor.isActive("blockquote")} />
          <Botao rotulo="Linha horizontal" icon={SeparatorHorizontal} onClick={() => ch().setHorizontalRule().run()} />
          <Separador />
          <Botao rotulo="Limpar formatação" icon={RemoveFormatting} onClick={() => ch().unsetAllMarks().clearNodes().run()} />
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

      <div className={cn("flex min-h-0 flex-1", opcoes.previaAberta && opcoes.previa && "gap-0")}>
        <div className="min-h-0 min-w-0 flex-1 overflow-auto bg-muted">
          {opcoes.aviso && <div className="mx-auto max-w-[21cm] px-4 pt-3">{opcoes.aviso}</div>}
          <div className="px-4 pb-10 pt-3" style={{ zoom: zoom / 100 }}>
            {regua && (
              <div className="sticky top-0 z-sticky mb-3">
                <Regua />
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
