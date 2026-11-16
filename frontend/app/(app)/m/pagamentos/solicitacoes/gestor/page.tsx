"use client";

import { CheckCircle, Reply, Users } from "lucide-react";

import { FilaPorEtapa, type SecaoDaFila } from "@/components/pagamentos/FilaPorEtapa";

const SECOES: SecaoDaFila[] = [
  {
    situacao: "AGUARDANDO_GESTOR",
    titulo: "Aguardando sua decisão",
    rotuloKpi: "Aguardando decisão",
    icon: Users,
    acaoLabel: "Analisar",
  },
  {
    situacao: "AJUSTE_GESTOR",
    titulo: "Aguardando ajustes da unidade",
    rotuloKpi: "Aguardando ajustes",
    icon: Reply,
    acaoLabel: "Ver",
    intent: "warning",
  },
];

export default function GestorPage() {
  return (
    <FilaPorEtapa
      titulo="Fila do gestor"
      descricao="Solicitações que esperam a sua decisão como gestor da pasta."
      icon={Users}
      secoes={SECOES}
      vazio={{
        icon: CheckCircle,
        titulo: "Nenhuma solicitação aguardando sua ação",
        descricao: "A fila do gestor está em dia.",
      }}
    />
  );
}
