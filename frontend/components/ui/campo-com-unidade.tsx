import * as React from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface CampoComUnidadeProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Antes do valor: "R$". */
  prefixo?: string;
  /** Depois do valor: "km", "L", "%", "dias". */
  sufixo?: string;
}

/**
 * Input com a unidade grudada no campo ("R$ 1.200,00", "45 km"). A unidade
 * fora do rótulo deixa o rótulo curto ("Valor total", não "Valor total
 * (R$)") e mostra o formato enquanto se digita. A unidade é decorativa para
 * o leitor de tela: quem precisa dela é o rótulo ou o `aria-describedby`.
 */
export const CampoComUnidade = React.forwardRef<HTMLInputElement, CampoComUnidadeProps>(
  ({ prefixo, sufixo, className, ...props }, ref) => (
    <div className="relative">
      {prefixo && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-foreground-subtle"
        >
          {prefixo}
        </span>
      )}
      <Input
        ref={ref}
        className={cn(
          "tabular-nums",
          prefixo && (prefixo.length > 2 ? "pl-12" : "pl-10"),
          sufixo && (sufixo.length > 2 ? "pr-14" : "pr-10"),
          className,
        )}
        {...props}
      />
      {sufixo && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-foreground-subtle"
        >
          {sufixo}
        </span>
      )}
    </div>
  ),
);
CampoComUnidade.displayName = "CampoComUnidade";
