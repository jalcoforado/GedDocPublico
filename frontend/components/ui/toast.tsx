"use client";

import { AlertCircle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
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

/** Máximo de toasts simultâneos — acima disso o mais antigo sai (fatia 2.2). */
const MAX_TOASTS = 3;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  // id → {timer, duration}: o timer é cancelável (pausa no hover/foco) e a
  // duração fica guardada para rearmar do zero ao sair — mais simples que
  // contabilizar tempo restante, e a diferença não é perceptível.
  const timers = useRef(new Map<string, { timer: number; duration: number }>());

  const dismiss = useCallback((id: string) => {
    const reg = timers.current.get(id);
    if (reg) {
      window.clearTimeout(reg.timer);
      timers.current.delete(id);
    }
    setToasts((cur) => cur.filter((t) => t.id !== id));
  }, []);

  const pausa = useCallback((id: string) => {
    const reg = timers.current.get(id);
    if (reg) window.clearTimeout(reg.timer);
  }, []);

  const retoma = useCallback(
    (id: string) => {
      const reg = timers.current.get(id);
      if (reg) reg.timer = window.setTimeout(() => dismiss(id), reg.duration);
    },
    [dismiss],
  );

  const toast = useCallback(
    ({ message, intent = "info", duration = 4000, action }: ToastInput) => {
      const id = Math.random().toString(36).slice(2, 9);
      setToasts((cur) => {
        const proximos = [...cur, { id, message, intent, action }];
        // Estourou a fila: derruba os mais antigos (e seus timers).
        const derrubados = proximos.slice(0, Math.max(0, proximos.length - MAX_TOASTS));
        for (const d of derrubados) {
          const reg = timers.current.get(d.id);
          if (reg) {
            window.clearTimeout(reg.timer);
            timers.current.delete(d.id);
          }
        }
        return proximos.slice(-MAX_TOASTS);
      });
      // Toasts com ação ficam por mais tempo (6s default) — undo precisa de janela maior
      const finalDuration =
        action && duration === 4000 ? 6000 : duration;
      if (finalDuration > 0) {
        const timer = window.setTimeout(() => dismiss(id), finalDuration);
        timers.current.set(id, { timer, duration: finalDuration });
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
      {/* Sem aria-live no container: cada toast anuncia pelo próprio role —
          erro é `alert` (assertive), o resto `status` (polite). Container com
          live region duplicaria o anúncio. */}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-toast flex flex-col items-center gap-2 px-4 pb-safe sm:bottom-6">
        {toasts.map((t) => {
          const Icon = ICONS[t.intent];
          return (
            <div
              key={t.id}
              role={t.intent === "error" ? "alert" : "status"}
              onMouseEnter={() => pausa(t.id)}
              onMouseLeave={() => retoma(t.id)}
              onFocus={() => pausa(t.id)}
              onBlur={(e) => {
                // Só rearma quando o foco SAIU do toast inteiro — mover o foco
                // entre a ação e o X não pode expirar a notificação no meio.
                if (!e.currentTarget.contains(e.relatedTarget as Node | null)) retoma(t.id);
              }}
              className={cn(
                "pointer-events-auto flex w-full max-w-md items-start gap-3 rounded-dropdown border border-border px-4 py-3 shadow-dropdown animate-slide-up",
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
                  className="rounded border border-current/30 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide transition-colors duration-fast hover:bg-black/10 active:bg-black/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current focus-visible:ring-offset-2"
                >
                  {t.action.label}
                </button>
              )}
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Fechar notificação"
                className="rounded p-0.5 transition-colors duration-fast hover:bg-black/10 active:bg-black/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current focus-visible:ring-offset-2"
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
