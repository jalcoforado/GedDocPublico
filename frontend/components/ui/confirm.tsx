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
  | { kind: "confirm"; opts: ConfirmOptions; resolve: (v: boolean) => void }
  | { kind: "prompt"; opts: PromptOptions; resolve: (v: string | null) => void };

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);
  const [promptValue, setPromptValue] = useState("");

  const confirm = useCallback(
    (opts: ConfirmOptions) =>
      new Promise<boolean>((resolve) => {
        setPending({ kind: "confirm", opts, resolve });
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
    if (!pending) return;
    if (pending.kind === "confirm") pending.resolve(false);
    else pending.resolve(null);
    setPending(null);
  }, [pending]);

  const handleConfirm = useCallback(() => {
    if (!pending) return;
    if (pending.kind === "confirm") {
      pending.resolve(true);
    } else {
      if (pending.opts.required && promptValue.trim() === "") return;
      pending.resolve(promptValue);
    }
    setPending(null);
  }, [pending, promptValue]);

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
              <Button variant="secondary" onClick={handleCancel}>
                {pending.opts.cancelLabel ?? "Cancelar"}
              </Button>
              <Button
                variant={
                  pending.kind === "confirm" && pending.opts.intent === "danger"
                    ? "danger"
                    : "primary"
                }
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
