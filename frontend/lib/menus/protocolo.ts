import {
  BarChart3,
  BookOpen,
  CalendarClock,
  ClipboardList,
  FileText,
  FolderTree,
  GitBranch,
  Inbox,
  Layers,
  Map,
  MapPin,
  Paperclip,
  Tag,
  UserCircle,
} from "lucide-react";

import type { MenuModulo } from "./tipos";

/**
 * Menu do módulo protocolo — grupos Processos, Protocolo e Cadastros, movidos
 * verbatim da Sidebar (linhas 80, 90 e 115). Os catálogos de localização
 * (Cidades/Bairros/Endereços) vieram junto por §12: quem os consome é o
 * endereço do manifestante. Exceção: "Para assinar" (linha 84) NÃO ficou em
 * "Processos" — o apêndice §12 do spec trata assinatura como transversal
 * (`moduloDoPathname("/para-assinar")` é `null`, ver `lib/modulos.ts`), então
 * o item foi para `comum.ts`.
 */
export const menuProtocolo: MenuModulo = {
  slug: "protocolo",
  raiz: "/processos",
  grupos: [
    {
      title: "Processos",
      defaultOpen: true,
      items: [
        { label: "Processos", href: "/processos", icon: FileText, perm: "processo" },
        { label: "Workflows", href: "/workflow", icon: GitBranch },
        { label: "Relatórios", href: "/relatorios", icon: BarChart3, perm: "processo" },
      ],
    },
    {
      title: "Protocolo",
      defaultOpen: true,
      items: [
        { label: "Balcão", href: "/protocolo/balcao", icon: Inbox, perm: "processo" },
        {
          label: "Vencendo prazo",
          href: "/protocolo/vencendo-prazo",
          icon: CalendarClock,
          perm: "processo",
        },
        {
          label: "CCD (Classificação)",
          href: "/protocolo/ccd",
          icon: FolderTree,
          perm: "catalogo",
        },
        {
          label: "TTD (Temporalidade)",
          href: "/protocolo/ttd",
          icon: CalendarClock,
          perm: "catalogo",
        },
      ],
    },
    {
      title: "Cadastros",
      defaultOpen: false,
      items: [
        { label: "Manifestantes", href: "/manifestantes", icon: UserCircle, perm: "manifestante" },
        { label: "Tipos de Manifestante", href: "/tipos-manifestante", icon: Tag, perm: "manifestante" },
        { label: "Tipos de Processo", href: "/tipos-processo", icon: Layers, perm: "catalogo" },
        { label: "Assuntos", href: "/assuntos", icon: BookOpen, perm: "assunto" },
        { label: "Catálogo de Serviços", href: "/servicos", icon: ClipboardList, perm: "servico" },
        { label: "Tipos de Anexo", href: "/tipos-anexo", icon: Paperclip, perm: "catalogo" },
        { label: "Templates de documento", href: "/templates-documento", icon: FileText, perm: "minuta_template" },
        { label: "Cidades", href: "/cidades", icon: MapPin, perm: "cidade" },
        { label: "Bairros", href: "/bairros", icon: Map, perm: "endereco" },
        { label: "Endereços", href: "/enderecos", icon: MapPin, perm: "endereco" },
      ],
    },
  ],
};
