import { FileSignature, LayoutDashboard } from "lucide-react";

import type { MenuModulo } from "./tipos";

/**
 * Menu do módulo Contratos e Convênios (G1). Nasceu depois da F3: todas as
 * telas já moram em `/m/contratos/…` e não existe URL legada a redirecionar.
 *
 * As fatias seguintes acrescentam aqui: fiscalização (G2), contratações (G3),
 * convênios (G5). Item novo entra também em `PERMISSOES_ESPERADAS`
 * (`__tests__/menus.test.tsx`).
 */
export const menuContratos: MenuModulo = {
  slug: "contratos",
  raiz: "/m/contratos",
  grupos: [
    {
      title: "Contratos",
      defaultOpen: true,
      items: [
        { label: "Painel", href: "/m/contratos", icon: LayoutDashboard, perm: "contrato" },
        {
          label: "Contratos",
          href: "/m/contratos/contratos",
          icon: FileSignature,
          perm: "contrato",
        },
      ],
    },
  ],
};
