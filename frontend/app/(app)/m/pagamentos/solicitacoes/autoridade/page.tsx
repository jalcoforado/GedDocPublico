"use client";

import { CheckCircle, Gavel, Reply } from "lucide-react";

import { FilaPorEtapa, type SecaoDaFila } from "@/components/pagamentos/FilaPorEtapa";

const SECOES: SecaoDaFila[] = [
  {
    situacao: "AGUARDANDO_AUTORIDADE",
    titulo: "Aguardando sua aprovação",
    rotuloKpi: "Aguardando aprovação",
    icon: Gavel,
    acaoLabel: "Aprovar",
  },
  {
    situacao: "AJUSTE_AUTORIDADE",
    titulo: "Aguardando ajustes da unidade",
    rotuloKpi: "Aguardando ajustes",
    icon: Reply,
    acaoLabel: "Ver",
    intent: "warning",
  },
];

export default function AutoridadePage() {
  return (
    <FilaPorEtapa
      titulo="Fila da Autoridade"
      descricao="Solicitações aguardando aprovação final"
      icon={Gavel}
      secoes={SECOES}
      vazio={{
        icon: CheckCircle,
        titulo: "Nenhuma solicitação aguardando sua aprovação",
        descricao: "A fila da autoridade está em dia.",
      }}
    />
  );
}
