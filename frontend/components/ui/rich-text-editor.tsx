"use client";

import Image from "@tiptap/extension-image";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { Table } from "@tiptap/extension-table";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import TableRow from "@tiptap/extension-table-row";
import TextAlign from "@tiptap/extension-text-align";
import Underline from "@tiptap/extension-underline";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Bold,
  Columns3,
  Heading2,
  Heading3,
  Image as ImageIcon,
  Italic,
  Link as LinkIcon,
  List,
  ListOrdered,
  Loader2,
  Quote,
  Redo2,
  Rows3,
  SeparatorHorizontal,
  Strikethrough,
  Table as TableIcon,
  Trash2,
  Underline as UnderlineIcon,
  Undo2,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

interface ToolbarButtonProps {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  spinning?: boolean;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

function ToolbarButton({ onClick, active, disabled, spinning, label, icon: Icon }: ToolbarButtonProps) {
  return (
    <button
      type="button"
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      aria-pressed={active}
      className={cn(
        "inline-flex h-8 w-8 items-center justify-center rounded-md text-sm transition-colors duration-fast",
        "hover:bg-muted hover:text-foreground active:bg-muted/80",
        "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
        active
          ? "bg-brand/10 text-brand"
          : "text-foreground-muted",
      )}
    >
      <Icon className={cn("h-4 w-4", spinning && "animate-spin")} aria-hidden="true" />
    </button>
  );
}

function Divider() {
  return <span className="mx-1 h-5 w-px bg-border" aria-hidden="true" />;
}

interface RichTextEditorProps {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  minHeight?: number;
  className?: string;
  ariaLabel?: string;
  /** Sem isso, "inserir imagem" pede uma URL em vez de fazer upload. */
  onUploadImage?: (file: File) => Promise<string>;
}

export function RichTextEditor({
  value,
  onChange,
  placeholder = "Escreva aqui…",
  minHeight = 180,
  className,
  ariaLabel,
  onUploadImage,
}: RichTextEditorProps) {
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3] },
        bulletList: { keepMarks: true, keepAttributes: false },
        orderedList: { keepMarks: true, keepAttributes: false },
      }),
      Link.configure({
        openOnClick: false,
        autolink: true,
        HTMLAttributes: { rel: "noopener noreferrer", target: "_blank" },
      }),
      Placeholder.configure({ placeholder }),
      Underline,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Image.configure({ inline: true, HTMLAttributes: { class: "max-w-full" } }),
      Table.configure({ resizable: false }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    content: value || "",
    editorProps: {
      attributes: {
        class: cn(
          "prose-tiptap focus:outline-none",
          "px-3 py-2.5 text-sm leading-relaxed text-foreground",
        ),
        role: "textbox",
        "aria-multiline": "true",
        "aria-label": ariaLabel ?? "Editor de texto",
        style: `min-height:${minHeight}px`,
      },
    },
    onUpdate({ editor }) {
      const html = editor.getHTML();
      // Tiptap returns "<p></p>" for empty content; normalize to ""
      onChange(html === "<p></p>" ? "" : html);
    },
  });

  // Sync external value changes (e.g. localStorage hydrate) into editor
  useEffect(() => {
    if (!editor) return;
    const current = editor.getHTML();
    const normalized = value || "";
    const currentNormalized = current === "<p></p>" ? "" : current;
    if (normalized !== currentNormalized) {
      editor.commands.setContent(normalized, { emitUpdate: false });
    }
  }, [value, editor]);

  const promptLink = useCallback(
    (ed: Editor) => {
      const prev = ed.getAttributes("link").href as string | undefined;
      const url = window.prompt("URL do link:", prev ?? "https://");
      if (url === null) return;
      if (url === "") {
        ed.chain().focus().extendMarkRange("link").unsetLink().run();
        return;
      }
      ed.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
    },
    [],
  );

  const insertImage = useCallback(
    (ed: Editor) => {
      if (!onUploadImage) {
        const url = window.prompt("URL da imagem:", "https://");
        if (url) ed.chain().focus().setImage({ src: url }).run();
        return;
      }
      fileInputRef.current?.click();
    },
    [onUploadImage],
  );

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // permite selecionar o mesmo arquivo de novo
    if (!file || !editor || !onUploadImage) return;
    setUploading(true);
    try {
      const url = await onUploadImage(file);
      editor.chain().focus().setImage({ src: url }).run();
    } catch (err: any) {
      window.alert(err?.message || "Erro ao enviar imagem.");
    } finally {
      setUploading(false);
    }
  }

  if (!editor) {
    return (
      <div
        className={cn(
          "rounded-input border border-input bg-card shadow-input",
          className,
        )}
        style={{ minHeight: minHeight + 40 }}
        aria-busy="true"
      />
    );
  }

  const emTabela = editor.isActive("table");

  return (
    <div
      className={cn(
        "group rounded-input border border-input bg-card shadow-input transition-colors duration-fast",
        "hover:border-border-strong",
        "focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30",
        className,
      )}
    >
      {onUploadImage && (
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          className="hidden"
          onChange={handleFileSelected}
        />
      )}
      <div
        className="flex flex-wrap items-center gap-0.5 border-b border-border bg-surface-2/40 px-1.5 py-1"
        role="toolbar"
        aria-label="Formatação do texto"
      >
        <ToolbarButton
          label="Negrito (Ctrl+B)"
          icon={Bold}
          onClick={() => editor.chain().focus().toggleBold().run()}
          active={editor.isActive("bold")}
        />
        <ToolbarButton
          label="Itálico (Ctrl+I)"
          icon={Italic}
          onClick={() => editor.chain().focus().toggleItalic().run()}
          active={editor.isActive("italic")}
        />
        <ToolbarButton
          label="Sublinhado (Ctrl+U)"
          icon={UnderlineIcon}
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          active={editor.isActive("underline")}
        />
        <ToolbarButton
          label="Tachado"
          icon={Strikethrough}
          onClick={() => editor.chain().focus().toggleStrike().run()}
          active={editor.isActive("strike")}
        />
        <Divider />
        <ToolbarButton
          label="Título nível 2"
          icon={Heading2}
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          active={editor.isActive("heading", { level: 2 })}
        />
        <ToolbarButton
          label="Título nível 3"
          icon={Heading3}
          onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
          active={editor.isActive("heading", { level: 3 })}
        />
        <Divider />
        <ToolbarButton
          label="Alinhar à esquerda"
          icon={AlignLeft}
          onClick={() => editor.chain().focus().setTextAlign("left").run()}
          active={editor.isActive({ textAlign: "left" })}
        />
        <ToolbarButton
          label="Centralizar"
          icon={AlignCenter}
          onClick={() => editor.chain().focus().setTextAlign("center").run()}
          active={editor.isActive({ textAlign: "center" })}
        />
        <ToolbarButton
          label="Alinhar à direita"
          icon={AlignRight}
          onClick={() => editor.chain().focus().setTextAlign("right").run()}
          active={editor.isActive({ textAlign: "right" })}
        />
        <ToolbarButton
          label="Justificar"
          icon={AlignJustify}
          onClick={() => editor.chain().focus().setTextAlign("justify").run()}
          active={editor.isActive({ textAlign: "justify" })}
        />
        <Divider />
        <ToolbarButton
          label="Lista com marcadores"
          icon={List}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          active={editor.isActive("bulletList")}
        />
        <ToolbarButton
          label="Lista numerada"
          icon={ListOrdered}
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          active={editor.isActive("orderedList")}
        />
        <ToolbarButton
          label="Citação"
          icon={Quote}
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
          active={editor.isActive("blockquote")}
        />
        <ToolbarButton
          label="Linha horizontal"
          icon={SeparatorHorizontal}
          onClick={() => editor.chain().focus().setHorizontalRule().run()}
        />
        <Divider />
        <ToolbarButton
          label="Inserir/editar link"
          icon={LinkIcon}
          onClick={() => promptLink(editor)}
          active={editor.isActive("link")}
        />
        <ToolbarButton
          label={uploading ? "Enviando imagem…" : "Inserir imagem"}
          icon={uploading ? Loader2 : ImageIcon}
          spinning={uploading}
          onClick={() => insertImage(editor)}
          disabled={uploading}
        />
        {!emTabela && (
          <ToolbarButton
            label="Inserir tabela"
            icon={TableIcon}
            onClick={() =>
              editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
            }
          />
        )}
        {emTabela && (
          <>
            <ToolbarButton
              label="Adicionar coluna"
              icon={Columns3}
              onClick={() => editor.chain().focus().addColumnAfter().run()}
            />
            <ToolbarButton
              label="Adicionar linha"
              icon={Rows3}
              onClick={() => editor.chain().focus().addRowAfter().run()}
            />
            <ToolbarButton
              label="Excluir tabela"
              icon={Trash2}
              onClick={() => editor.chain().focus().deleteTable().run()}
            />
          </>
        )}
        <div className="ml-auto flex items-center gap-0.5">
          <ToolbarButton
            label="Desfazer (Ctrl+Z)"
            icon={Undo2}
            onClick={() => editor.chain().focus().undo().run()}
            disabled={!editor.can().undo()}
          />
          <ToolbarButton
            label="Refazer (Ctrl+Y)"
            icon={Redo2}
            onClick={() => editor.chain().focus().redo().run()}
            disabled={!editor.can().redo()}
          />
        </div>
      </div>
      <EditorContent editor={editor} />
    </div>
  );
}

/**
 * Read-only renderer for content produced by RichTextEditor.
 * Uses dangerouslySetInnerHTML — content originates from authenticated
 * back-office users; if untrusted input enters, sanitize before saving.
 */
export function RichTextView({
  html,
  className,
}: {
  html: string;
  className?: string;
}) {
  if (!html || html === "<p></p>") {
    return (
      <p className={cn("text-sm italic text-foreground-subtle", className)}>
        Sem conteúdo.
      </p>
    );
  }
  return (
    <div
      className={cn("prose-tiptap text-sm text-foreground", className)}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
