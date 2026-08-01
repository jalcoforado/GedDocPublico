import { Car, ClipboardList, IdCard, Truck } from "lucide-react";

import type { MenuModulo } from "./tipos";

/** Menu do módulo frota, movido verbatim da Sidebar (linha 131). */
export const menuFrota: MenuModulo = {
  slug: "frota",
  raiz: "/frotas",
  grupos: [
    {
      title: "Frota",
      defaultOpen: false,
      items: [
        { label: "Frota Pública", href: "/frotas", icon: Truck, perm: "frota" },
        { label: "Veículos", href: "/frotas/veiculos", icon: Car, perm: "frota" },
        { label: "Motoristas", href: "/frotas/motoristas", icon: IdCard, perm: "frota" },
        { label: "Solicitações", href: "/frotas/solicitacoes", icon: ClipboardList, perm: "frota" },
      ],
    },
  ],
};
