"use client";

import * as React from "react";

import { focarPrimeiroInvalido } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { aceitaLetras, aplicarMascara, type Mascara } from "@/lib/mascaras";
import { cn } from "@/lib/utils";

/**
 * Peças comuns dos formulários do transporte regulado. Todos são diálogos
 * montados à mão (não `CrudPage`), e cada um repetia a validação "primeiro
 * erro no topo e para" — que escondia o segundo problema até o primeiro ser
 * consertado e nunca dizia em qual campo estava.
 */

type Erros<C extends string> = Partial<Record<C, string | null | undefined>>;

/**
 * Erro só depois da tentativa (padrão de formulário, regra 4): o campo mostra
 * o seu erro depois que a pessoa sai dele ou tenta enviar — nunca ao abrir.
 *
 * `erros` é recalculado a cada render pelo chamador (função pura do form);
 * o hook só decide QUANDO mostrar. `conferir()` no envio marca a tentativa e,
 * havendo erro, leva o foco ao primeiro campo inválido.
 */
export function useValidacao<C extends string>(erros: Erros<C>) {
  const [tocados, setTocados] = React.useState<ReadonlySet<string>>(() => new Set());
  const [tentativas, setTentativas] = React.useState(0);
  const ref = React.useRef<HTMLDivElement>(null);

  // O foco espera o render que liga `aria-invalid` nos campos.
  React.useEffect(() => {
    if (tentativas > 0) focarPrimeiroInvalido(ref.current ?? document);
  }, [tentativas]);

  const valido = Object.values(erros).every((e) => !e);

  return {
    /** Vai no contêiner dos campos: o foco procura o inválido só ali dentro. */
    ref,
    valido,
    erro(campo: C): string | undefined {
      return tentativas > 0 || tocados.has(campo) ? (erros[campo] ?? undefined) : undefined;
    },
    /** `onBlur` do campo. */
    sair(campo: C) {
      return () => setTocados((s) => (s.has(campo) ? s : new Set(s).add(campo)));
    },
    /** No envio: `true` libera; `false` mostra todos os erros e foca o primeiro. */
    conferir(): boolean {
      if (valido) return true;
      setTentativas((t) => t + 1);
      return false;
    },
    reiniciar() {
      setTocados(new Set());
      setTentativas(0);
    },
  };
}

/**
 * Input com máscara de documento/telefone. O valor guardado no form é o
 * formatado; o backend do transporte normaliza CPF e CNPJ para só dígitos
 * (`schemas/transporte_regulado.py`), então a máscara é só da tela.
 */
export const InputMascarado = React.forwardRef<
  HTMLInputElement,
  Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange"> & {
    mascara: Mascara;
    value: string;
    onValueChange: (v: string) => void;
  }
>(({ mascara, value, onValueChange, ...props }, ref) => (
  <Input
    ref={ref}
    {...props}
    inputMode={aceitaLetras(mascara) ? "text" : "numeric"}
    autoComplete="off"
    className={cn("font-mono tabular-nums", props.className)}
    value={aplicarMascara(mascara, value).valor}
    onChange={(e) => onValueChange(aplicarMascara(mascara, e.target.value).valor)}
  />
));
InputMascarado.displayName = "InputMascarado";

/** Campo preenchido com documento completo? (`000.000.000-00` inteiro.) */
export function mascaraCompleta(m: Mascara, v: string): boolean {
  return aplicarMascara(m, v).completo;
}

// Mesma forma que o backend do transporte aceita (`EMAIL_PATTERN`): a tela
// não reprova o que o servidor passaria.
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** Erro do e-mail opcional (vazio passa). */
export function erroEmail(v: string): string | undefined {
  return v.trim() !== "" && !EMAIL.test(v.trim())
    ? "E-mail inválido: use o formato nome@provedor.com."
    : undefined;
}

/**
 * Grupo de campos dentro de um diálogo longo ("Dados pessoais", "CNH"). Não
 * é `SectionCard` — cartão dentro de diálogo vira caixa dentro de caixa —,
 * só um subtítulo e um fio separando do grupo anterior.
 */
export function GrupoCampos({
  titulo,
  descricao,
  children,
  className,
}: {
  titulo: string;
  descricao?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const id = React.useId();
  return (
    <section
      aria-labelledby={id}
      className={cn("space-y-4 border-t border-border pt-5 first:border-t-0 first:pt-0", className)}
    >
      <div>
        <h3 id={id} className="text-xs font-semibold uppercase tracking-wide text-foreground-subtle">
          {titulo}
        </h3>
        {descricao && <p className="mt-0.5 text-xs text-foreground-muted">{descricao}</p>}
      </div>
      {children}
    </section>
  );
}

// ---------------------------------------------------------------- datas ----
// Datas do formulário são `YYYY-MM-DD` (input date). Contas em UTC puro para
// não escorregar um dia em UTC-3; "hoje" é o dia LOCAL de quem preenche.

export function hojeISO(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function paraUTC(iso: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  return m ? Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;
}

/** `2026-11-10` → `10/11/2026`. */
export function dataBR(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return y && m && d ? `${d}/${m}/${y}` : iso;
}

/** Soma meses a uma data ISO (31/01 + 1 mês = 28 ou 29/02, não 03/03). */
export function somarMeses(iso: string, meses: number): string {
  const t = paraUTC(iso);
  if (t === null) return iso;
  const d = new Date(t);
  const dia = d.getUTCDate();
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() + meses);
  const ultimo = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
  d.setUTCDate(Math.min(dia, ultimo));
  return d.toISOString().slice(0, 10);
}

/** Dias corridos de `de` até `ate` (negativo se `ate` vem antes). */
export function diasEntre(de: string, ate: string): number | null {
  const a = paraUTC(de);
  const b = paraUTC(ate);
  return a === null || b === null ? null : Math.round((b - a) / 86_400_000);
}

function plural(n: number, um: string, varios: string): string {
  return `${n} ${n === 1 ? um : varios}`;
}

/**
 * "1 ano e 6 meses", "45 dias" — a duração de uma vigência, para a pessoa
 * conferir de relance se digitou o ano certo na validade.
 */
export function duracaoLegivel(inicio: string, fim: string): string | null {
  const dias = diasEntre(inicio, fim);
  if (dias === null || dias < 0) return null;
  const [ai, mi, di] = inicio.split("-").map(Number);
  const [af, mf, df] = fim.split("-").map(Number);
  let meses = (af - ai) * 12 + (mf - mi) - (df < di ? 1 : 0);
  if (meses < 1) return plural(dias, "dia", "dias");
  const anos = Math.floor(meses / 12);
  meses %= 12;
  const partes = [anos ? plural(anos, "ano", "anos") : null, meses ? plural(meses, "mês", "meses") : null];
  return partes.filter(Boolean).join(" e ");
}

/** "vence hoje", "vence em 12 dias", "venceu há 3 dias" — a partir de hoje. */
export function prazoAteHoje(iso: string): string | null {
  const d = diasEntre(hojeISO(), iso);
  if (d === null) return null;
  if (d === 0) return "vence hoje";
  return d > 0 ? `vence em ${plural(d, "dia", "dias")}` : `venceu há ${plural(-d, "dia", "dias")}`;
}

/**
 * Dica da data de validade: a vigência e o prazo ("Vigência de 2 anos —
 * vence em 730 dias."). Sem datas suficientes, a dica fixa.
 */
export function dicaVigencia(inicio: string, validade: string, padrao: string): string {
  if (!validade) return padrao;
  const prazo = prazoAteHoje(validade);
  const dur = inicio ? duracaoLegivel(inicio, validade) : null;
  if (dur && prazo) return `Vigência de ${dur} — ${prazo}.`;
  return prazo ? `${prazo[0].toUpperCase()}${prazo.slice(1)}.` : padrao;
}

/**
 * Atalhos de prazo na validade ("1 ano · 2 anos · 5 anos"): a validade quase
 * sempre é o início mais um prazo redondo, e digitar a data à mão é onde
 * entra o ano errado. Conta a partir do início (ou de hoje, sem início).
 */
export function AtalhosPrazo({
  inicio,
  onEscolher,
  meses = [12, 24, 60],
}: {
  inicio: string;
  onEscolher: (validade: string) => void;
  meses?: number[];
}) {
  const base = inicio || hojeISO();
  return (
    <span className="flex flex-wrap items-center gap-x-1 text-foreground-muted">
      {meses.map((m, i) => (
        <React.Fragment key={m}>
          {i > 0 && <span aria-hidden="true">·</span>}
          <button
            type="button"
            onClick={() => onEscolher(somarMeses(base, m))}
            className="rounded text-primary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={`Validade de ${rotuloMeses(m)} a partir do início`}
          >
            {rotuloMeses(m)}
          </button>
        </React.Fragment>
      ))}
    </span>
  );
}

function rotuloMeses(m: number): string {
  return m % 12 === 0 ? plural(m / 12, "ano", "anos") : plural(m, "mês", "meses");
}

/** Erro de validade antes do início (espelha a regra do backend). */
export function erroValidade(inicio: string, validade: string): string | undefined {
  return inicio && validade && validade < inicio
    ? "A validade não pode ser antes do início. Confira o ano."
    : undefined;
}
