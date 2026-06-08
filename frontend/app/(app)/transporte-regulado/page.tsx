"use client";

import {
  Bus,
  Building2,
  Car,
  CalendarClock,
  ClipboardCheck,
  FileText,
  IdCard,
  Map,
  RefreshCw,
  Route,
  ScrollText,
  AlertOctagon,
} from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/ui/page-header";

interface HubCard {
  href?: string;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  desc: string;
  ready?: boolean;
}

const CARDS: HubCard[] = [
  {
    href: "/transporte-regulado/permissionarios",
    icon: IdCard,
    title: "Permissionários",
    desc: "Cadastro de permissionários: dados pessoais, CNH, tipo de serviço, permissão e situação.",
    ready: true,
  },
  {
    href: "/transporte-regulado/empresas",
    icon: Building2,
    title: "Empresas",
    desc: "Empresas e operadoras reguladas: dados cadastrais, endereço, autorização e situação.",
    ready: true,
  },
  {
    href: "/transporte-regulado/veiculos",
    icon: Car,
    title: "Veículos",
    desc: "Veículos regulados vinculados a permissionários ou empresas autorizadas.",
    ready: true,
  },
  { icon: FileText, title: "Documentos", desc: "Documentos exigidos e avaliação documental." },
  { icon: ClipboardCheck, title: "Vistorias", desc: "Vistorias regulatórias dos veículos." },
  { icon: ScrollText, title: "Alvarás", desc: "Alvarás e autorizações de operação." },
  { icon: RefreshCw, title: "Recadastramento", desc: "Campanhas e ciclos de recadastramento." },
  { icon: Route, title: "Rotas e Linhas", desc: "Rotas, linhas e localidades atendidas." },
  { icon: AlertOctagon, title: "Ocorrências", desc: "Ocorrências regulatórias e fiscalização." },
  { icon: Map, title: "Relatórios", desc: "Relatórios e impressões do transporte regulado." },
];

export default function TransporteReguladoHubPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        icon={Bus}
        title="Transporte Regulado"
        description="Gestão de permissionários e do transporte público regulado do município."
      />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {CARDS.map((c) => {
          const Icon = c.icon;
          const content = (
            <>
              <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-md bg-brand/12 text-brand">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </div>
              <div className="flex items-center gap-2">
                <h2 className="font-semibold text-foreground">{c.title}</h2>
                {!c.ready && (
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                    em estruturação
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-foreground-muted">{c.desc}</p>
            </>
          );
          return c.ready && c.href ? (
            <Link
              key={c.title}
              href={c.href}
              className="group rounded-lg border border-border bg-surface-1 p-4 transition-colors hover:border-brand hover:bg-sidebar-accent"
            >
              {content}
            </Link>
          ) : (
            <div
              key={c.title}
              aria-disabled="true"
              className="cursor-not-allowed rounded-lg border border-dashed border-border bg-surface-1 p-4 opacity-70"
            >
              {content}
            </div>
          );
        })}
      </div>
    </div>
  );
}
