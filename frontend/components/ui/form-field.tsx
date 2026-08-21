"use client";

import * as React from "react";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface FormFieldProps {
  label: string;
  /** Texto auxiliar permanente sob o campo (formato esperado, exemplo etc.). */
  hint?: string;
  /** Mensagem de validação — liga `aria-invalid` e entra no `aria-describedby`. */
  error?: string;
  required?: boolean;
  className?: string;
  /** Um único controle (Input/Select/Textarea ou equivalente que aceite id/aria-*). */
  children: React.ReactElement<
    React.InputHTMLAttributes<HTMLInputElement> & { id?: string }
  >;
}

/**
 * Label + controle + hint + erro com a fiação ARIA completa (UX-02 fatia 2.4):
 * `htmlFor`/`id` gerados, `aria-describedby` apontando para hint e erro,
 * `aria-invalid` quando há erro. Cada tela montava esse conjunto à mão — e
 * quase nenhuma fazia a parte ARIA.
 *
 * O id respeita um `id` já passado ao controle (telas que precisam de âncora
 * estável); os demais atributos são mesclados, nunca sobrescrevem os do filho.
 */
export function FormField({ label, hint, error, required, className, children }: FormFieldProps) {
  const autoId = React.useId();
  const child = React.Children.only(children);
  const id = child.props.id ?? autoId;
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;

  const describedBy =
    [hint ? hintId : null, error ? errorId : null, child.props["aria-describedby"]]
      .filter(Boolean)
      .join(" ") || undefined;

  return (
    <div className={cn("space-y-1", className)}>
      <Label htmlFor={id} required={required}>
        {label}
      </Label>
      {React.cloneElement(child, {
        id,
        required: child.props.required ?? required,
        "aria-invalid": error ? true : child.props["aria-invalid"],
        "aria-describedby": describedBy,
      })}
      {hint && (
        <p id={hintId} className="text-xs text-foreground-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-xs font-medium text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

/**
 * Foca o primeiro controle inválido dentro do container (default: documento).
 * Chamar após a validação do submit — é a metade "foco no primeiro inválido"
 * da fatia 2.4, que não dá para resolver dentro de um FormField isolado.
 */
export function focarPrimeiroInvalido(container: ParentNode = document): void {
  const alvo = container.querySelector<HTMLElement>('[aria-invalid="true"]');
  alvo?.focus();
}
