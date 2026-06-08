"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  AlertTriangle,
  BarChart3,
  Car,
  ClipboardCheck,
  ClipboardList,
  Fuel,
  IdCard,
  Truck,
  Wrench,
} from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/ui/page-header";
import { api } from "@/lib/api";

const CARDS = [
  {
    href: "/frotas/veiculos",
    icon: Car,
    title: "Veículos",
    desc: "Cadastro da frota própria: placa, documentação, situação, posse e unidade responsável.",
  },
  {
    href: "/frotas/motoristas",
    icon: IdCard,
    title: "Motoristas",
    desc: "Cadastro de condutores: CPF, CNH (categoria e validade), lotação e situação.",
  },
  {
    href: "/frotas/solicitacoes",
    icon: ClipboardList,
    title: "Solicitações de Veículo",
    desc: "Pedidos de uso de veículo: finalidade, destino, datas previstas e fluxo de aprovação.",
  },
  {
    href: "/frotas/manutencoes",
    icon: Wrench,
    title: "Manutenções",
    desc: "Manutenções preventivas e corretivas: abertura, andamento, conclusão e custos.",
  },
  {
    href: "/frotas/abastecimentos",
    icon: Fuel,
    title: "Abastecimentos",
    desc: "Registro de abastecimentos: litros, valor, quilometragem, posto e indicadores.",
  },
  {
    href: "/frotas/vistorias",
    icon: ClipboardCheck,
    title: "Vistorias",
    desc: "Checklist interno de vistoria: saída, retorno e periódica, com resultado e itens.",
  },
  {
    href: "/frotas/ocorrencias",
    icon: AlertOctagon,
    title: "Ocorrências",
    desc: "Avarias, multas, sinistros e uso indevido: gravidade, tratamento e resolução.",
  },
  {
    href: "/frotas/relatorios",
    icon: BarChart3,
    title: "Visão gerencial",
    desc: "Indicadores consolidados: veículos, solicitações, pendências e abastecimentos.",
  },
];

export default function FrotaHubPage() {
  const alertasQ = useQuery({
    queryKey: ["frota-documentos-alertas"],
    queryFn: () => api.documentosVeiculo.alertas(30),
  });
  const vencidos = alertasQ.data?.vencidos.length ?? 0;
  const aVencer = alertasQ.data?.a_vencer.length ?? 0;
  const temAlerta = vencidos + aVencer > 0;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Truck}
        title="Frota Pública"
        description="Gestão da frota própria do município."
      />

      {temAlerta && (
        <Link
          href="/frotas/veiculos"
          className="flex items-center gap-3 rounded-lg border border-warning-soft bg-warning-soft px-4 py-3 text-sm text-warning-soft-foreground transition-opacity hover:opacity-90"
        >
          <AlertTriangle className="h-5 w-5 shrink-0" aria-hidden="true" />
          <span>
            <strong>{vencidos}</strong> documento(s) vencido(s) e{" "}
            <strong>{aVencer}</strong> a vencer nos próximos 30 dias. Acesse os veículos
            para regularizar.
          </span>
        </Link>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {CARDS.map((c) => {
          const Icon = c.icon;
          return (
            <Link
              key={c.href}
              href={c.href}
              className="group rounded-lg border border-border bg-surface-1 p-4 transition-colors hover:border-brand hover:bg-sidebar-accent"
            >
              <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-md bg-brand/12 text-brand">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </div>
              <h2 className="font-semibold text-foreground">{c.title}</h2>
              <p className="mt-1 text-sm text-foreground-muted">{c.desc}</p>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
