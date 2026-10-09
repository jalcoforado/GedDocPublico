"use client";

import { Palette, RotateCcw, Type } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  FONTES,
  corValida,
  cssDaFonte,
  derivarTema,
  hslParaHex,
  tokenParaHex,
} from "@/lib/tema-cores";
import { useModoTema } from "@/lib/modo-tema";


/** Os campos de COR. A fonte é o outro campo do tema, e não é uma cor. */
type CampoCor = "cor_primaria" | "cor_destaque" | "cor_lateral" | "cor_titulos";
type Campo = CampoCor | "fonte_titulos";

const CAMPOS: { campo: CampoCor; rotulo: string; ajuda: string; token: string }[] = [
  {
    campo: "cor_primaria",
    rotulo: "Cor primária",
    ajuda: "Botões, links e foco dos campos.",
    token: "--brand",
  },
  {
    campo: "cor_destaque",
    rotulo: "Cor de destaque",
    ajuda: "Realces e o painel da cidade na tela de entrada.",
    token: "--accent",
  },
  {
    campo: "cor_lateral",
    rotulo: "Cor da barra lateral",
    ajuda:
      "Fundo do menu. O texto clareia ou escurece sozinho para continuar legível. Em branco, acompanha a cor primária.",
    token: "--sidebar",
  },
  {
    campo: "cor_titulos",
    rotulo: "Cor dos títulos",
    ajuda:
      "Títulos das telas. Em branco, cada título mantém a cor padrão (texto ou cor primária).",
    token: "--titulo-destaque",
  },
];

interface CoresDoTemaProps {
  /** `""` = não definida (vale o padrão do sistema). */
  valores: Record<Campo, string>;
  onChange: (campo: Campo, valor: string) => void;
  disabled?: boolean;
}

/**
 * Editor do tema do município: três cores e uma pré-visualização ao vivo.
 *
 * A pré-visualização usa a MESMA derivação que o sistema aplica depois de
 * salvar (`derivarTema`), escopada ao próprio quadro por CSS custom properties
 * — o que se vê aqui é o que vai para a tela, inclusive o ajuste de contraste.
 */
export function CoresDoTema({ valores, onChange, disabled }: CoresDoTemaProps) {
  const theme = useModoTema();
  // Cor atual de cada token, lida do CSS: é o valor inicial do seletor quando
  // o município ainda não definiu a cor (o `<input type="color">` exige hex).
  const [padroes, setPadroes] = useState<Record<string, string>>({});

  useEffect(() => {
    const css = getComputedStyle(document.documentElement);
    setPadroes(
      Object.fromEntries(
        CAMPOS.map(({ token }) => [token, tokenParaHex(css.getPropertyValue(token)) ?? ""]),
      ),
    );
  }, [theme]);

  // Cores E fonte: a pré-visualização tem de mostrar o título como ele vai
  // ficar, e a fonte é metade disso.
  const previa = useMemo(() => {
    const css = cssDaFonte(valores.fonte_titulos);
    return { ...derivarTema(valores, theme), ...(css ? { "--font-display": css } : {}) };
  }, [valores, theme]);
  const neutro = hslParaHex({ h: 0, s: 0, l: 50 });

  return (
    <div className="md:col-span-2">
      <div className="flex items-center gap-2">
        <Palette className="h-4 w-4 text-foreground-muted" aria-hidden="true" />
        <h3 className="text-sm font-semibold">Cores e fonte do sistema</h3>
      </div>
      <p className="mt-0.5 text-xs text-foreground-muted">
        Definem a aparência do sistema para todos os usuários do município. A
        tonalidade é ajustada quando necessário para manter os textos legíveis.
      </p>

      <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="space-y-3">
          {CAMPOS.map(({ campo, rotulo, ajuda, token }) => {
            const valor = valores[campo];
            const invalida = valor !== "" && !corValida(valor);
            return (
              <div key={campo}>
                <Label htmlFor={campo}>{rotulo}</Label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    aria-label={`${rotulo} — seletor`}
                    value={corValida(valor) ? valor : padroes[token] || neutro}
                    onChange={(e) => onChange(campo, e.target.value)}
                    disabled={disabled}
                    className="h-10 w-12 shrink-0 cursor-pointer rounded-md border border-border bg-card disabled:cursor-not-allowed disabled:opacity-50"
                  />
                  <Input
                    id={campo}
                    value={valor}
                    placeholder="Padrão do sistema"
                    maxLength={7}
                    onChange={(e) => onChange(campo, e.target.value.trim())}
                    disabled={disabled}
                    aria-invalid={invalida}
                    aria-describedby={`${campo}-ajuda`}
                    className="font-mono"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => onChange(campo, "")}
                    disabled={disabled || valor === ""}
                    aria-label={`Voltar ${rotulo.toLowerCase()} ao padrão`}
                  >
                    <RotateCcw className="h-4 w-4" aria-hidden="true" />
                  </Button>
                </div>
                <p id={`${campo}-ajuda`} className="mt-1 text-xs text-foreground-muted">
                  {invalida ? (
                    <span className="text-danger-soft-foreground">
                      Use o formato #RRGGBB, como {padroes[token] || neutro}.
                    </span>
                  ) : (
                    ajuda
                  )}
                </p>
              </div>
            );
          })}

          <div>
            <Label htmlFor="fonte_titulos">
              <Type className="mr-1 inline h-3.5 w-3.5 text-foreground-muted" aria-hidden="true" />
              Fonte dos títulos
            </Label>
            <Select
              id="fonte_titulos"
              value={valores.fonte_titulos}
              onChange={(e) => onChange("fonte_titulos", e.target.value)}
              disabled={disabled}
              aria-describedby="fonte_titulos-ajuda"
            >
              {/* A padrão é a opção VAZIA: gravar "montserrat" seria o mesmo
                  resultado, mas prenderia o município a ela se o padrão do
                  produto mudar. */}
              {FONTES.map((f) => (
                <option key={f.chave} value={f.css ? f.chave : ""}>
                  {f.rotulo}
                </option>
              ))}
            </Select>
            <p id="fonte_titulos-ajuda" className="mt-1 text-xs text-foreground-muted">
              Vale para os títulos. O texto corrido e as tabelas continuam na
              fonte padrão, que é a que lê bem em tamanho pequeno.
            </p>
          </div>
        </div>

        {/* Pré-visualização: os tokens derivados valem só dentro deste quadro. */}
        <div
          aria-label="Pré-visualização das cores e da fonte"
          role="img"
          className="flex overflow-hidden rounded-lg border border-border bg-background shadow-xs"
          style={previa as React.CSSProperties}
        >
          <div className="w-24 shrink-0 space-y-1.5 bg-sidebar p-2.5 text-[11px] text-sidebar-foreground">
            <div className="mb-2 font-semibold">Menu</div>
            <div className="rounded bg-sidebar-active px-2 py-1">Início</div>
            <div className="rounded px-2 py-1 text-sidebar-muted">Processos</div>
            <div className="rounded px-2 py-1 text-sidebar-muted">Frota</div>
          </div>
          <div className="min-w-0 flex-1 space-y-2.5 p-3">
            <div className="font-display text-sm font-semibold text-titulo-destaque">
              Título da tela
            </div>
            <div className="inline-flex rounded-md bg-brand px-3 py-1.5 text-xs font-medium text-primary-foreground">
              Botão principal
            </div>
            <div>
              <span className="inline-flex rounded-full bg-accent px-2 py-0.5 text-[11px] font-medium text-accent-foreground">
                Destaque
              </span>
            </div>
            <div className="text-xs text-brand underline">Link de exemplo</div>
          </div>
        </div>
      </div>
    </div>
  );
}
