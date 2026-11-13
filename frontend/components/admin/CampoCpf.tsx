"use client";

import * as React from "react";

import { Input } from "@/components/ui/input";
import { aplicarMascara, soDigitos } from "@/lib/mascaras";

type CampoCpfProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange"> & {
  /** Só os dígitos — é assim que o backend guarda e recebe o CPF. */
  value: string;
  onValor: (digitos: string) => void;
};

/**
 * CPF com a máscara aparecendo enquanto se digita ("123.456.789-01"), mas o
 * valor que sai daqui continua só com os 11 dígitos: a máscara é da tela, o
 * payload não muda. Quem cola "123.456.789-01" de outro sistema também
 * acerta, porque pontos e traço são descartados na entrada.
 */
export const CampoCpf = React.forwardRef<HTMLInputElement, CampoCpfProps>(
  ({ value, onValor, ...props }, ref) => (
    <Input
      ref={ref}
      {...props}
      type="text"
      inputMode="numeric"
      autoComplete="off"
      placeholder={props.placeholder ?? "000.000.000-00"}
      maxLength={14}
      className="tabular-nums"
      value={aplicarMascara("cpf", value).valor}
      onChange={(e) => onValor(soDigitos(e.target.value).slice(0, 11))}
    />
  ),
);
CampoCpf.displayName = "CampoCpf";
