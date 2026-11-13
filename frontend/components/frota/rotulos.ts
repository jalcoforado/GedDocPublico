// Rótulos, cores de situação e formatação compartilhados pelas telas da Frota.
// A mesma situação tem a mesma cor em todas as telas do módulo: aguardando
// alguém agir = warning; em andamento = info; concluída/ok = success;
// negada/reprovada = danger; cancelada/inativa = neutral.

import type { VeiculoSituacao } from "@/lib/api";

export type IntentStatus = "neutral" | "success" | "danger" | "warning" | "info";

/** O backend guarda o combustível em minúsculas sem acento; a tela mostra o nome. */
export const COMBUSTIVEIS: { value: string; label: string }[] = [
  { value: "gasolina", label: "Gasolina" },
  { value: "etanol", label: "Etanol" },
  { value: "flex", label: "Flex" },
  { value: "diesel", label: "Diesel" },
  { value: "gnv", label: "GNV" },
  { value: "eletrico", label: "Elétrico" },
  { value: "hibrido", label: "Híbrido" },
];

export const SITUACOES_VEICULO: { value: VeiculoSituacao; label: string; intent: IntentStatus }[] = [
  { value: "disponivel", label: "Disponível", intent: "success" },
  { value: "em_uso", label: "Em uso", intent: "info" },
  { value: "manutencao", label: "Manutenção", intent: "warning" },
  { value: "inativo", label: "Inativo", intent: "neutral" },
  { value: "baixado", label: "Baixado", intent: "neutral" },
];

/**
 * dd/mm/aaaa hh:mm — sem os segundos, que o `toLocaleString` puro mostrava e
 * só esticavam a coluna.
 */
export function fmtDataHora(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  const data = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${data} ${hora}`;
}

/** Litros com até duas casas: "1.234,5 L". */
export function fmtLitros(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} L`;
}
