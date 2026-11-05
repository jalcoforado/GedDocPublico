import {
  BarChart3,
  BookOpen,
  CalendarClock,
  ClipboardList,
  FileText,
  FolderTree,
  GitBranch,
  Inbox,
  LayoutDashboard,
  Layers,
  Map,
  MapPin,
  Paperclip,
  Rows3,
  Tag,
  UserCircle,
  Workflow,
} from "lucide-react";

import { ROTA_PROCESSOS } from "@/lib/caixas-processos";

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
  // A raiz é o painel, como no SEI: quem entra no módulo cai nos números da
  // unidade. O launcher e o switcher vão para o primeiro item VISÍVEL (que é
  // o painel, para quem tem `processo`); a raiz fica para a trilha do shell
  // e para quem não vê item nenhum — e o painel, sem `processo`, ainda
  // mostra a saudação e as notificações em vez de uma tela vazia.
  raiz: "/m/protocolo/painel",
  grupos: [
    {
      title: "Processos",
      defaultOpen: true,
      items: [
        // O menu lista TELAS. As caixas de trabalho (entrada, saída, análise…)
        // são recortes de uma tela só, e moram nela, como abas com contador
        // (`components/protocolo/AbasCaixas.tsx`). Chegaram a ser oito itens
        // aqui, todos apontando para o mesmo caminho: o menu virava o filtro
        // de uma tela e empurrava as outras telas do módulo para baixo da dobra.
        // O painel abre o grupo: é a porta do módulo (ver `raiz` acima).
        { label: "Painel de controle", href: "/m/protocolo/painel", icon: LayoutDashboard, perm: "processo" },
        { label: "Caixas de trabalho", href: ROTA_PROCESSOS, icon: Rows3, perm: "processo" },
        // Mapa do caminho de um processo, com as quantidades das caixas.
        // "Workflows", logo abaixo, é outra coisa: o desenho de fluxos BPM.
        { label: "Fluxo do processo", href: "/m/protocolo/fluxo", icon: Workflow, perm: "processo" },
        { label: "Workflows", href: "/m/protocolo/workflow", icon: GitBranch },
        { label: "Relatórios", href: "/m/protocolo/relatorios", icon: BarChart3, perm: "processo" },
      ],
    },
    {
      title: "Protocolo",
      defaultOpen: true,
      items: [
        { label: "Balcão", href: "/m/protocolo/protocolo/balcao", icon: Inbox, perm: "processo" },
        {
          label: "Vencendo prazo",
          href: "/m/protocolo/protocolo/vencendo-prazo",
          icon: CalendarClock,
          perm: "processo",
        },
        {
          label: "CCD (Classificação)",
          href: "/m/protocolo/protocolo/ccd",
          icon: FolderTree,
          perm: "catalogo",
        },
        {
          label: "TTD (Temporalidade)",
          href: "/m/protocolo/protocolo/ttd",
          icon: CalendarClock,
          perm: "catalogo",
        },
      ],
    },
    {
      title: "Cadastros",
      defaultOpen: false,
      items: [
        { label: "Manifestantes", href: "/m/protocolo/manifestantes", icon: UserCircle, perm: "manifestante" },
        { label: "Tipos de Manifestante", href: "/m/protocolo/tipos-manifestante", icon: Tag, perm: "manifestante" },
        { label: "Tipos de Processo", href: "/m/protocolo/tipos-processo", icon: Layers, perm: "catalogo" },
        { label: "Assuntos", href: "/m/protocolo/assuntos", icon: BookOpen, perm: "assunto" },
        { label: "Catálogo de Serviços", href: "/m/protocolo/servicos", icon: ClipboardList, perm: "servico" },
        { label: "Tipos de Anexo", href: "/m/protocolo/tipos-anexo", icon: Paperclip, perm: "catalogo" },
        { label: "Templates de documento", href: "/m/protocolo/templates-documento", icon: FileText, perm: "minuta_template" },
        { label: "Cidades", href: "/m/protocolo/cidades", icon: MapPin, perm: "cidade" },
        { label: "Bairros", href: "/m/protocolo/bairros", icon: Map, perm: "endereco" },
        { label: "Endereços", href: "/m/protocolo/enderecos", icon: MapPin, perm: "endereco" },
      ],
    },
  ],
};
