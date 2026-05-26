"use client";

import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  Bold,
  Heading2,
  Heading3,
  Italic,
  Link as LinkIcon,
  List,
  ListOrdered,
  Quote,
  Redo2,
  Strikethrough,
  Undo2,
} from "lucide-react";
import { useCallback, useEffect } from "react";

import { cn } from "@/lib/utils";

interface ToolbarButtonProps {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

function ToolbarButton({ onClick, active, disabled, label, icon: Icon }: ToolbarButtonProps) {
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
        "hover:bg-muted hover:text-foreground",
        "disabled:cursor-not-allowed disabled:opacity-40",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "bg-brand/10 text-brand"
          : "text-foreground-muted",
      )}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
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
}

export function RichTextEditor({
  value,
  onChange,
  placeholder = "Escreva aqui…",
  minHeight = 180,
  className,
  ariaLabel,
}: RichTextEditorProps) {
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

  if (!editor) {
    return (
      <div
        className={cn(
          "rounded-md border border-input bg-card",
          className,
        )}
        style={{ minHeight: minHeight + 40 }}
        aria-busy="true"
      />
    );
  }

  return (
    <div
      className={cn(
        "group rounded-md border border-input bg-card transition-colors",
        "focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30",
        className,
      )}
    >
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
        <Divider />
        <ToolbarButton
          label="Inserir/editar link"
          icon={LinkIcon}
          onClick={() => promptLink(editor)}
          active={editor.isActive("link")}
        />
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
