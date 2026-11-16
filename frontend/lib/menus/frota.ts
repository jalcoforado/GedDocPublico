import { Car, ClipboardList, IdCard, MapPinned, Truck, Workflow } from "lucide-react";

import type { MenuModulo } from "./tipos";

/** Menu do módulo frota, movido verbatim da Sidebar (linha 131). */
export const menuFrota: MenuModulo = {
  slug: "frota",
  raiz: "/m/frota",
  grupos: [
    {
      title: "Frota",
      defaultOpen: false,
      items: [
        // Índice do módulo: os cartões dela levam ao que não está na barra.
        { label: "Visão geral", href: "/m/frota", icon: Truck, perm: "frota" },
        { label: "Veículos", href: "/m/frota/veiculos", icon: Car, perm: "frota" },
        { label: "Motoristas", href: "/m/frota/motoristas", icon: IdCard, perm: "frota", lugar: "hub" },
        { label: "Solicitações", href: "/m/frota/solicitacoes", icon: ClipboardList, perm: "frota" },
        // Mapa do caminho de uma solicitação de veículo, do pedido ao retorno.
        { label: "Fluxo do processo", href: "/m/frota/fluxo", icon: Workflow, perm: "frota", lugar: "hub" },
        { label: "Mapa da frota", href: "/m/frota/mapa", icon: MapPinned, perm: "frota", lugar: "hub" },
      ],
    },
  ],
};
