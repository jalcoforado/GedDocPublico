import { redirect } from "next/navigation";

/**
 * Relatórios abrem na pergunta que eles respondem melhor: "onde o processo
 * para?" (Tramitação). A lista de processos para exportar, que repetia as
 * Caixas de trabalho com CSV/PDF, virou a última aba (`/relatorios/processos`).
 * Este endereço continua valendo — é o do menu e dos links antigos.
 */
export default function RelatoriosPage() {
  redirect("/m/protocolo/relatorios/tramitacao");
}
