"use client";

import { Car, ClipboardList, IdCard, Truck } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/ui/page-header";

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
];

export default function FrotaHubPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        icon={Truck}
        title="Frota Pública"
        description="Gestão da frota própria do município."
      />
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
