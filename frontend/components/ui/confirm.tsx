"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface ConfirmOptions {
  title?: string;
  message: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  intent?: "primary" | "danger";
  /**
   * Ação assíncrona executada AO confirmar, com o botão em loading e o
   * dialog aberto até terminar (fatia 2.3). Sucesso: fecha e o `confirm()`
   * resolve `true`. Erro: fecha e o `confirm()` REJEITA com o erro — o
   * caller trata (toast etc.) como trataria chamando a ação ele mesmo.
   */
  onConfirm?: () => Promise<void>;
}

interface PromptOptions {
  title?: string;
  message?: React.ReactNode;
  label: string;
  defaultValue?: string;
  placeholder?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  type?: "text" | "number";
  inputMode?: "text" | "numeric" | "decimal";
  required?: boolean;
}

interface ConfirmContextValue {
  confirm: (opts: ConfirmOptions) => Promise<boolean>;
  prompt: (opts: PromptOptions) => Promise<string | null>;
}

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

type Pending =
  | {
      kind: "confirm";
      opts: ConfirmOptions;
      resolve: (v: boolean) => void;
      reject: (e: unknown) => void;
    }
  | { kind: "prompt"; opts: PromptOptions; resolve: (v: string | null) => void };

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);
  const [promptValue, setPromptValue] = useState("");
  // true enquanto o onConfirm async está em voo — botão em loading, dialog
  // aberto, cliques repetidos ignorados.
  const [executando, setExecutando] = useState(false);

  const confirm = useCallback(
    (opts: ConfirmOptions) =>
      new Promise<boolean>((resolve, reject) => {
        setPending({ kind: "confirm", opts, resolve, reject });
      }),
    [],
  );

  const prompt = useCallback(
    (opts: PromptOptions) =>
      new Promise<string | null>((resolve) => {
        setPromptValue(opts.defaultValue ?? "");
        setPending({ kind: "prompt", opts, resolve });
      }),
    [],
  );

  const handleCancel = useCallback(() => {
    if (!pending || executando) return; // ação em voo não é cancelável daqui
    if (pending.kind === "confirm") pending.resolve(false);
    else pending.resolve(null);
    setPending(null);
  }, [pending, executando]);

  const handleConfirm = useCallback(async () => {
    if (!pending || executando) return;
    if (pending.kind === "confirm") {
      const { onConfirm } = pending.opts;
      if (onConfirm) {
        setExecutando(true);
        try {
          await onConfirm();
          pending.resolve(true);
        } catch (e) {
          pending.reject(e);
        } finally {
          setExecutando(false);
          setPending(null);
        }
        return;
      }
      pending.resolve(true);
    } else {
      if (pending.opts.required && promptValue.trim() === "") return;
      pending.resolve(promptValue);
    }
    setPending(null);
  }, [pending, promptValue, executando]);

  const value = useMemo<ConfirmContextValue>(
    () => ({ confirm, prompt }),
    [confirm, prompt],
  );

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      {pending && (
        <Dialog
          open
          onClose={handleCancel}
          title={
            pending.opts.title ??
            (pending.kind === "confirm" ? "Confirmar" : "Informar valor")
          }
          size="sm"
          footer={
            <>
              <Button variant="secondary" disabled={executando} onClick={handleCancel}>
                {pending.opts.cancelLabel ?? "Cancelar"}
              </Button>
              <Button
                variant={
                  pending.kind === "confirm" && pending.opts.intent === "danger"
                    ? "danger"
                    : "primary"
                }
                loading={executando}
                onClick={handleConfirm}
              >
                {pending.opts.confirmLabel ??
                  (pending.kind === "confirm" ? "Confirmar" : "OK")}
              </Button>
            </>
          }
        >
          {pending.kind === "confirm" ? (
            <div className="text-sm text-foreground">{pending.opts.message}</div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleConfirm();
              }}
              className="space-y-3"
            >
              {pending.opts.message && (
                <div className="text-sm text-muted-foreground">
                  {pending.opts.message}
                </div>
              )}
              <div>
                <Label htmlFor="prompt-input" required={pending.opts.required}>
                  {pending.opts.label}
                </Label>
                <Input
                  id="prompt-input"
                  type={pending.opts.type ?? "text"}
                  inputMode={pending.opts.inputMode}
                  placeholder={pending.opts.placeholder}
                  value={promptValue}
                  onChange={(e) => setPromptValue(e.target.value)}
                  autoFocus
                  required={pending.opts.required}
                />
              </div>
            </form>
          )}
        </Dialog>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm deve ser usado dentro de <ConfirmProvider>");
  return ctx.confirm;
}

export function usePrompt() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("usePrompt deve ser usado dentro de <ConfirmProvider>");
  return ctx.prompt;
}
