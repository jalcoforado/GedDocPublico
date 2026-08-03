import { BarChart3, Building2, Bus, Car, IdCard, ScrollText } from "lucide-react";

import type { MenuModulo } from "./tipos";

/** Menu do módulo transporte regulado, movido verbatim da Sidebar (linha 141). */
export const menuTransporte: MenuModulo = {
  slug: "transporte",
  raiz: "/transporte-regulado",
  grupos: [
    {
      title: "Transporte Regulado",
      defaultOpen: false,
      items: [
        { label: "Transporte Regulado", href: "/transporte-regulado", icon: Bus, perm: "transporte_regulado" },
        {
          label: "Permissionários",
          href: "/transporte-regulado/permissionarios",
          icon: IdCard,
          perm: "transporte_regulado",
        },
        {
          label: "Empresas",
          href: "/transporte-regulado/empresas",
          icon: Building2,
          perm: "transporte_regulado",
        },
        {
          label: "Veículos",
          href: "/transporte-regulado/veiculos",
          icon: Car,
          perm: "transporte_regulado",
        },
        {
          label: "Alvarás",
          href: "/transporte-regulado/alvaras",
          icon: ScrollText,
          perm: "transporte_regulado",
        },
        {
          label: "Relatórios",
          href: "/transporte-regulado/relatorio",
          icon: BarChart3,
          perm: "transporte_regulado",
        },
      ],
    },
  ],
};
