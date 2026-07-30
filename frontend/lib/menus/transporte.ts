import { Building2, Bus, Car, IdCard } from "lucide-react";

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
      ],
    },
  ],
};
