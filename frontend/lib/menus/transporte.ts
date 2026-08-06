import { BarChart3, Building2, Bus, Car, IdCard, MapPin, RefreshCw, ScrollText } from "lucide-react";

import type { MenuModulo } from "./tipos";

/** Menu do módulo transporte regulado, movido verbatim da Sidebar (linha 141). */
export const menuTransporte: MenuModulo = {
  slug: "transporte",
  raiz: "/m/transporte",
  grupos: [
    {
      title: "Transporte Regulado",
      defaultOpen: false,
      items: [
        { label: "Transporte Regulado", href: "/m/transporte", icon: Bus, perm: "transporte_regulado" },
        {
          label: "Permissionários",
          href: "/m/transporte/permissionarios",
          icon: IdCard,
          perm: "transporte_regulado",
        },
        {
          label: "Empresas",
          href: "/m/transporte/empresas",
          icon: Building2,
          perm: "transporte_regulado",
        },
        {
          label: "Veículos",
          href: "/m/transporte/veiculos",
          icon: Car,
          perm: "transporte_regulado",
        },
        {
          label: "Alvarás",
          href: "/m/transporte/alvaras",
          icon: ScrollText,
          perm: "transporte_regulado",
        },
        {
          label: "Pontos e Vagas",
          href: "/m/transporte/pontos",
          icon: MapPin,
          perm: "transporte_regulado",
        },
        {
          label: "Recadastramento",
          href: "/m/transporte/recadastramento",
          icon: RefreshCw,
          perm: "transporte_regulado",
        },
        {
          label: "Relatórios",
          href: "/m/transporte/relatorio",
          icon: BarChart3,
          perm: "transporte_regulado",
        },
      ],
    },
  ],
};
