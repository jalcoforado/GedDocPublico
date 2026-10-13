"use client";

import { Ban, CheckCircle2, History, ThumbsDown, X } from "lucide-react";

import { FilaPorEtapa, type SecaoDaFila } from "@/components/pagamentos/FilaPorEtapa";

const SECOES: SecaoDaFila[] = [
  {
    situacao: "AUTORIZADA",
    titulo: "Autorizadas",
    rotuloKpi: "Autorizadas",
    icon: CheckCircle2,
    acaoLabel: "Ver",
    intent: "success",
  },
  {
    situacao: "REJEITADA_GESTOR",
    titulo: "Rejeitadas",
    rotuloKpi: "Rejeitadas",
    icon: X,
    acaoLabel: "Ver",
    intent: "danger",
  },
  {
    situacao: "INDEFERIDA_AUTORIDADE",
    titulo: "Indeferidas",
    rotuloKpi: "Indeferidas",
    icon: ThumbsDown,
    acaoLabel: "Ver",
    intent: "danger",
  },
  {
    situacao: "CANCELADA",
    titulo: "Canceladas",
    rotuloKpi: "Canceladas",
    icon: Ban,
    acaoLabel: "Ver",
  },
];

export default function ConcluidasPage() {
  return (
    <FilaPorEtapa
      titulo="Solicitações Concluídas"
      descricao="Histórico de solicitações já finalizadas"
      icon={History}
      secoes={SECOES}
      gradeKpi="grid grid-cols-2 gap-3 md:grid-cols-4"
      vazio={{
        icon: History,
        titulo: "Nenhuma solicitação concluída",
        descricao: "Solicitações autorizadas, rejeitadas, indeferidas ou canceladas aparecem aqui.",
      }}
    />
  );
}
