import {
  AlertOctagon,
  BarChart3,
  Building2,
  Car,
  IdCard,
  MapPin,
  RefreshCw,
  Route,
  ScrollText,
} from "lucide-react";
import type React from "react";

export interface HubCard {
  href?: string;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  desc: string;
  ready?: boolean;
}

/**
 * Cards do hub do transporte regulado — dado, não JSX, para que as invariantes
 * possam ser testadas sem renderizar a página.
 *
 * Card `ready` sem `href` é o defeito que deixou P1–P4 invisíveis: tela
 * entregue, sem caminho até ela. `__tests__/transporte-hub.test.tsx` trava isso.
 *
 * Documentos, vistorias e avaliações NÃO aparecem aqui de propósito: no backend
 * só existem aninhados sob um veículo (`/veiculos/{id}/vistorias`), sem listagem
 * transversal, e no frontend são seções do detalhe do veículo. Não são destinos.
 */
export const CARDS: HubCard[] = [
  {
    href: "/m/transporte/permissionarios",
    icon: IdCard,
    title: "Permissionários",
    desc: "Cadastro de permissionários: dados pessoais, CNH, tipo de serviço, permissão e situação.",
    ready: true,
  },
  {
    href: "/m/transporte/empresas",
    icon: Building2,
    title: "Empresas",
    desc: "Empresas e operadoras reguladas: dados cadastrais, endereço, autorização e situação.",
    ready: true,
  },
  {
    href: "/m/transporte/veiculos",
    icon: Car,
    title: "Veículos",
    desc: "Veículos regulados, com documentos, avaliações e vistorias no detalhe de cada um.",
    ready: true,
  },
  {
    href: "/m/transporte/alvaras",
    icon: ScrollText,
    title: "Alvarás",
    desc: "Alvarás e autorizações de operação, com documentos, responsáveis e renovação.",
    ready: true,
  },
  {
    href: "/m/transporte/relatorio",
    icon: BarChart3,
    title: "Relatórios",
    desc: "KPIs e análise de alvarás regulados, com exportação.",
    ready: true,
  },
  {
    href: "/m/transporte/recadastramento",
    icon: RefreshCw,
    title: "Recadastramento",
    desc: "Ciclos de recadastramento: convoca os regulados ativos e escalona o prazo de cada um.",
    ready: true,
  },
  {
    href: "/m/transporte/pontos",
    icon: MapPin,
    title: "Pontos e Vagas",
    desc: "Pontos de estacionamento regulados, com vagas numeradas e o histórico de quem ocupou cada uma.",
    ready: true,
  },
  {
    href: "/m/transporte/linhas",
    icon: Route,
    title: "Linhas e Itinerários",
    desc: "Linhas distritais e escolares, com itinerário e horários.",
    ready: true,
  },
  {
    href: "/m/transporte/ocorrencias",
    icon: AlertOctagon,
    title: "Ocorrências",
    desc: "Ocorrências regulatórias e fiscalização: apuração de denúncias e fiscalizações contra permissionários e empresas.",
    ready: true,
  },
];
