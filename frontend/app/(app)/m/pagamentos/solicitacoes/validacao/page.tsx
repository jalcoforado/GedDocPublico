"use client";

import { CheckCircle, Reply, ShieldCheck } from "lucide-react";

import { FilaPorEtapa, type SecaoDaFila } from "@/components/pagamentos/FilaPorEtapa";

const SECOES: SecaoDaFila[] = [
  {
    situacao: "AGUARDANDO_VALIDACAO",
    titulo: "Aguardando validação",
    rotuloKpi: "Aguardando validação",
    icon: ShieldCheck,
    acaoLabel: "Validar",
  },
  {
    situacao: "AJUSTE_VALIDACAO",
    titulo: "Aguardando ajustes da unidade",
    rotuloKpi: "Aguardando ajustes",
    icon: Reply,
    acaoLabel: "Ver",
    intent: "warning",
  },
];

export default function ValidacaoPage() {
  return (
    <FilaPorEtapa
      titulo="Fila de Validação"
      descricao="Solicitações aguardando validação financeira"
      icon={ShieldCheck}
      secoes={SECOES}
      vazio={{
        icon: CheckCircle,
        titulo: "Nenhuma solicitação aguardando validação",
        descricao: "A fila de validação está em dia.",
      }}
    />
  );
}
