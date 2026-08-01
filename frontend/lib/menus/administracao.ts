import { Building2, Cog, Settings, Shield, Users } from "lucide-react";

import type { MenuModulo } from "./tipos";

/**
 * Menu do módulo administração, movido verbatim da Sidebar (linha 202).
 * Organograma entrou aqui vindo do grupo "Geral" (linha 71): §12 trata
 * estrutura organizacional como matéria de administração, não item comum.
 */
export const menuAdministracao: MenuModulo = {
  slug: "administracao",
  raiz: "/usuarios",
  grupos: [
    {
      title: "Administração",
      defaultOpen: false,
      items: [
        { label: "Usuários", href: "/usuarios", icon: Users, perm: "usuario" },
        { label: "Unidades", href: "/unidades-trabalho", icon: Building2, perm: "unidadeTrabalho" },
        { label: "Organograma", href: "/organograma", icon: Building2 },
        { label: "Grupos & Permissões", href: "/grupos", icon: Shield },
        { label: "Configurações", href: "/configuracoes", icon: Settings, perm: "usuario" },
        { label: "Auditoria", href: "/auditoria", icon: Shield },
        { label: "Jobs em background", href: "/jobs", icon: Cog },
      ],
    },
  ],
};
