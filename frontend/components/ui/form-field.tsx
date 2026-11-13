"use client";

import { AlertCircle } from "lucide-react";
import * as React from "react";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface FormFieldProps {
  label: string;
  /** Texto auxiliar permanente sob o campo (formato esperado, exemplo etc.). */
  hint?: React.ReactNode;
  /** Mensagem de validação — liga `aria-invalid` e entra no `aria-describedby`. */
  error?: string;
  required?: boolean;
  /**
   * Marca "opcional" ao lado do rótulo. Use quando o campo está num grupo de
   * obrigatórios e alguém poderia achar que precisa preencher — o asterisco
   * diz o que é obrigatório; "opcional" tira a dúvida do resto.
   */
  opcional?: boolean;
  /**
   * Atalho à direita do rótulo ("Cadastrar novo", "Usar modelo") — fica junto
   * do campo que ele ajuda a preencher, em vez de perdido no fim do formulário.
   */
  acao?: React.ReactNode;
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
export function FormField({
  label,
  hint,
  error,
  required,
  opcional,
  acao,
  className,
  children,
}: FormFieldProps) {
  const autoId = React.useId();
  const child = React.Children.only(children);
  const id = child.props.id ?? autoId;
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy =
    [hint ? hintId : null, error ? errorId : null, child.props["aria-describedby"]]
      .filter(Boolean)
      .join(" ") || undefined;

  const rotulo = (
    <Label htmlFor={id} required={required} className={acao ? "mb-0" : undefined}>
      {label}
      {opcional && !required && (
        <span className="ml-1.5 text-xs font-normal text-foreground-subtle">opcional</span>
      )}
    </Label>
  );

  return (
    <div className={cn("space-y-1", className)}>
      {acao ? (
        <div className="mb-1 flex flex-wrap items-end justify-between gap-x-3 gap-y-1">
          {rotulo}
          <div className="text-xs">{acao}</div>
        </div>
      ) : (
        rotulo
      )}
      {React.cloneElement(child, {
        id,
        required: child.props.required ?? required,
        "aria-invalid": error ? true : child.props["aria-invalid"],
        "aria-describedby": describedBy,
      })}
      {/* Com erro, a dica cede o lugar: duas linhas de texto miúdo sob o campo
          se leem como uma só, e a que importa naquela hora é o erro. A dica
          continua no aria-describedby. */}
      {hint && (
        <p id={hintId} className={cn("text-xs text-foreground-muted", error && "sr-only")}>
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="flex items-start gap-1 text-xs font-medium text-danger-soft-foreground">
          <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
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

/**
 * Grade de campos. Formulário lê-se de cima para baixo: uma coluna por
 * padrão; duas só para pares que andam juntos (cidade + UF, início + fim).
 */
export function GradeCampos({
  colunas = 2,
  className,
  children,
}: {
  colunas?: 1 | 2 | 3;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "grid gap-4",
        colunas === 2 && "sm:grid-cols-2",
        colunas === 3 && "sm:grid-cols-2 lg:grid-cols-3",
        className,
      )}
    >
      {children}
    </div>
  );
}
