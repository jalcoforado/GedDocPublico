"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef } from "react";

import { cn } from "@/lib/utils";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
}

const SIZES = {
  sm: "max-w-md",
  md: "max-w-xl",
  lg: "max-w-3xl",
  xl: "max-w-5xl",
};

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Dialog({ open, onClose, title, children, footer, size = "md" }: DialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const previouslyFocused = useRef<HTMLElement | null>(null);

  // Destino de retorno do foco: o PRIMEIRO evento de foco que cruza a
  // fronteira "fora → dentro" do dialog carrega em `relatedTarget` o
  // elemento que perdeu o foco — o trigger. Isso cobre inclusive o
  // `autoFocus` de filho, que dispara no commit, ANTES de qualquer efeito
  // do pai (efeitos, mesmo de layout, rodam filho-primeiro): o evento é a
  // única testemunha do trigger nesse instante. Movimentação de foco
  // interna tem relatedTarget dentro do dialog e não sobrescreve; o ciclo
  // zera no fechamento, então reabrir captura o novo trigger.
  function capturaRetorno(e: React.FocusEvent) {
    if (previouslyFocused.current) return; // primeiro ingresso vence o ciclo
    const origem = e.relatedTarget;
    if (
      origem instanceof HTMLElement &&
      origem !== document.body &&
      !dialogRef.current?.contains(origem)
    ) {
      previouslyFocused.current = origem;
    }
  }

  // `onClose` costuma ser um arrow function inline no call-site — nova
  // referência a cada render do pai (ex.: a cada letra digitada num campo
  // controlado fora do dialog). Guardar num ref evita que o efeito abaixo
  // rode de novo nesses casos e roube o foco de volta pro primeiro elemento
  // focável a cada re-render do pai.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;

    // Foco inicial. O botão "Fechar" mora no header, antes do conteúdo no
    // DOM — como primeiro focável, ele capturava o foco de TODO dialog. A
    // regra aqui: (1) `autoFocus` de um filho já focou algo durante o commit
    // (antes deste efeito) → preservar; (2) senão, primeiro focável que não
    // seja o Fechar (campo do conteúdo ou 1ª ação do footer); (3) só Fechar
    // existe → Fechar. Ele continua na ordem de tabulação normal (trap).
    const root = dialogRef.current;
    if (root && !root.contains(document.activeElement)) {
      // Fallback defensivo da captura de retorno: neste ponto a árvore já
      // foi commitada e nada dentro do dialog recebeu foco — quem está
      // focado AGORA é o elemento externo anterior. (O caminho principal é
      // o evento de foco em `capturaRetorno`; este cobre ambiente sem
      // relatedTarget.)
      const ativo = document.activeElement;
      if (
        !previouslyFocused.current &&
        ativo instanceof HTMLElement &&
        ativo !== document.body
      ) {
        previouslyFocused.current = ativo;
      }
      const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
      const alvo = items.find((el) => el !== closeRef.current) ?? items[0];
      alvo?.focus();
    }

    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const cur = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (!cur || cur.length === 0) return;
      const first = cur[0];
      const last = cur[cur.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    }
    window.addEventListener("keydown", onKey);

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      // Lido no CLEANUP (não no corpo do efeito): a captura pode acontecer
      // depois do efeito rodar (evento de foco do autoFocus/StrictMode).
      const previous = previouslyFocused.current;
      previouslyFocused.current = null; // cada abertura é um novo ciclo
      if (previous?.isConnected) previous.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 animate-fade-in sm:items-center sm:p-4"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onFocus={capturaRetorno}
        className={cn(
          "w-full rounded-t-dialog bg-card text-card-foreground shadow-dialog animate-slide-up",
          "sm:rounded-dialog sm:animate-scale-in",
          SIZES[size],
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-border px-5 py-3">
          <h2 id={titleId} className="text-md font-semibold text-primary">
            {title}
          </h2>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className="inline-flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground transition-colors duration-fast hover:bg-muted hover:text-foreground active:bg-muted/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </header>
        <div className="max-h-[70vh] overflow-y-auto p-5">{children}</div>
        {footer && (
          <footer className="flex flex-wrap justify-end gap-2 border-t border-border px-5 py-3 pb-safe">
            {footer}
          </footer>
        )}
      </div>
    </div>
  );
}
