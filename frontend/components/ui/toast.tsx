"use client";

import { AlertCircle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

import { cn } from "@/lib/utils";

type Intent = "success" | "error" | "info" | "warning";

interface ToastAction {
  label: string;
  /** Ao clicar, executa e dispensa o toast. */
  onClick: () => void;
}

interface Toast {
  id: string;
  message: string;
  intent: Intent;
  action?: ToastAction;
}

interface ToastInput {
  message: string;
  intent?: Intent;
  duration?: number;
  action?: ToastAction;
}

interface ToastContextValue {
  toast: (input: ToastInput) => void;
  success: (message: string, opts?: { action?: ToastAction; duration?: number }) => void;
  error: (message: string) => void;
  info: (message: string) => void;
  warning: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const ICONS = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
  warning: AlertCircle,
} as const;

const STYLES: Record<Intent, string> = {
  success: "bg-success-soft text-success-soft-foreground",
  error: "bg-danger-soft text-danger-soft-foreground",
  info: "bg-info-soft text-info-soft-foreground",
  warning: "bg-warning-soft text-warning-soft-foreground",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((cur) => cur.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    ({ message, intent = "info", duration = 4000, action }: ToastInput) => {
      const id = Math.random().toString(36).slice(2, 9);
      setToasts((cur) => [...cur, { id, message, intent, action }]);
      // Toasts com ação ficam por mais tempo (6s default) — undo precisa de janela maior
      const finalDuration =
        action && duration === 4000 ? 6000 : duration;
      if (finalDuration > 0) {
        window.setTimeout(() => dismiss(id), finalDuration);
      }
    },
    [dismiss],
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      toast,
      success: (m, opts) =>
        toast({
          message: m,
          intent: "success",
          action: opts?.action,
          duration: opts?.duration,
        }),
      error: (m) => toast({ message: m, intent: "error", duration: 6000 }),
      info: (m) => toast({ message: m, intent: "info" }),
      warning: (m) => toast({ message: m, intent: "warning" }),
    }),
    [toast],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4 pb-safe sm:bottom-6"
      >
        {toasts.map((t) => {
          const Icon = ICONS[t.intent];
          return (
            <div
              key={t.id}
              role="status"
              className={cn(
                "pointer-events-auto flex w-full max-w-md items-start gap-3 rounded-md border border-border px-4 py-3 shadow-lg animate-slide-up",
                STYLES[t.intent],
              )}
            >
              <Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
              <p className="flex-1 text-sm">{t.message}</p>
              {t.action && (
                <button
                  type="button"
                  onClick={() => {
                    t.action!.onClick();
                    dismiss(t.id);
                  }}
                  className="rounded border border-current/30 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide transition-colors hover:bg-black/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current"
                >
                  {t.action.label}
                </button>
              )}
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Fechar notificação"
                className="rounded p-0.5 transition-colors hover:bg-black/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast deve ser usado dentro de <ToastProvider>");
  return ctx;
}
