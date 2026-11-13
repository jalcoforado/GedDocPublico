import type { TipoServico } from "@/lib/api";
import { aplicarMascara } from "@/lib/mascaras";

/**
 * Rótulos dos tipos de serviço do transporte regulado. O backend devolve o
 * enum cru (`transporte_escolar`); a tela mostra o nome de gente. Cada tela
 * tinha a sua cópia desta lista, e a do relatório nem chegava a usar a dela
 * na tabela — por isso mora aqui.
 */
export const TIPOS_SERVICO: { value: TipoServico; label: string }[] = [
  { value: "taxi", label: "Táxi" },
  { value: "mototaxi", label: "Mototáxi" },
  { value: "transporte_escolar", label: "Transporte escolar" },
  { value: "motofrete", label: "Motofrete" },
  { value: "transporte_distrital", label: "Transporte distrital" },
  { value: "aplicativo", label: "Aplicativo" },
  { value: "outro", label: "Outro" },
];

const TIPO_LABEL: Record<string, string> = Object.fromEntries(
  TIPOS_SERVICO.map((t) => [t.value, t.label]),
);

/** Rótulo do tipo de serviço; valor desconhecido passa como veio. */
export function rotuloTipoServico(tipo: string | null | undefined): string {
  if (!tipo) return "—";
  return TIPO_LABEL[tipo] ?? tipo;
}

/**
 * CPF/CNPJ gravados só com dígitos (`99744455566`) → `997.444.555-66`. O
 * backend guarda sem máscara; a máscara é só da tela. Valor fora do formato
 * volta como está.
 */
export function documentoParaExibir(v: string | null | undefined): string {
  if (!v) return "—";
  if (/^\d{11}$/.test(v)) return aplicarMascara("cpf", v).valor;
  if (/^[0-9A-Z]{12}\d{2}$/.test(v)) return aplicarMascara("cnpj", v).valor;
  return v;
}

/**
 * Data e hora de evento (trilha, auditoria): `10/11/2026 14:32`, sem os
 * segundos que o `toLocaleString` puro traz.
 */
export function dataHoraParaExibir(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const data = d.toLocaleDateString("pt-BR");
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${data} ${hora}`;
}

/**
 * Situação da convocação de recadastramento. A lista do ciclo mostrava o
 * enum cru (`em_analise`) e o atendimento fazia `replace("_", " ")`; os dois
 * leem daqui agora, com a mesma cor.
 */
export const SITUACAO_CONVOCACAO: Record<
  string,
  { label: string; intent: "neutral" | "success" | "danger" | "info" }
> = {
  convocado: { label: "Convocado", intent: "neutral" },
  em_analise: { label: "Em análise", intent: "info" },
  deferido: { label: "Deferido", intent: "success" },
  indeferido: { label: "Indeferido", intent: "danger" },
  suspenso: { label: "Suspenso", intent: "danger" },
};
