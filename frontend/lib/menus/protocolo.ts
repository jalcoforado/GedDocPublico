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
        { label: "Balcão", href: "/m/protocolo/protocolo/balcao", icon: Inbox, perm: "processo" },
        { label: "Relatórios", href: "/m/protocolo/relatorios", icon: BarChart3, perm: "processo" },
        // Índice do resto do módulo (`/m/protocolo/cadastros`): os três grupos
        // abaixo moram lá, não na barra. Sem `perm`: cada cartão da tela é
        // podado pela permissão do próprio item.
        { label: "Cadastros e configuração", href: "/m/protocolo/cadastros", icon: FolderTree },
      ],
    },
    {
      title: "Fluxo e prazos",
      items: [
        // Mapa do caminho de um processo, com as quantidades das caixas.
        // "Workflows" é outra coisa: o desenho de fluxos BPM.
        { label: "Fluxo do processo", href: "/m/protocolo/fluxo", icon: Workflow, perm: "processo", lugar: "hub" },
        { label: "Workflows", href: "/m/protocolo/workflow", icon: GitBranch, lugar: "hub" },
        {
          label: "Vencendo prazo",
          href: "/m/protocolo/protocolo/vencendo-prazo",
          icon: CalendarClock,
          perm: "processo",
          lugar: "hub",
        },
      ],
    },
    {
      title: "Gestão documental",
      items: [
        {
          label: "CCD (Classificação)",
          href: "/m/protocolo/protocolo/ccd",
          icon: FolderTree,
          perm: "catalogo",
          lugar: "hub",
        },
        {
          label: "TTD (Temporalidade)",
          href: "/m/protocolo/protocolo/ttd",
          icon: CalendarClock,
          perm: "catalogo",
          lugar: "hub",
        },
        { label: "Templates de documento", href: "/m/protocolo/templates-documento", icon: FileText, perm: "minuta_template", lugar: "hub" },
        { label: "Tipos de Anexo", href: "/m/protocolo/tipos-anexo", icon: Paperclip, perm: "catalogo", lugar: "hub" },
      ],
    },
    {
      title: "Cadastros",
      items: [
        { label: "Manifestantes", href: "/m/protocolo/manifestantes", icon: UserCircle, perm: "manifestante", lugar: "hub" },
        { label: "Tipos de Manifestante", href: "/m/protocolo/tipos-manifestante", icon: Tag, perm: "manifestante", lugar: "hub" },
        { label: "Tipos de Processo", href: "/m/protocolo/tipos-processo", icon: Layers, perm: "catalogo", lugar: "hub" },
        { label: "Assuntos", href: "/m/protocolo/assuntos", icon: BookOpen, perm: "assunto", lugar: "hub" },
        { label: "Catálogo de Serviços", href: "/m/protocolo/servicos", icon: ClipboardList, perm: "servico", lugar: "hub" },
        { label: "Cidades", href: "/m/protocolo/cidades", icon: MapPin, perm: "cidade", lugar: "hub" },
        { label: "Bairros", href: "/m/protocolo/bairros", icon: Map, perm: "endereco", lugar: "hub" },
        { label: "Endereços", href: "/m/protocolo/enderecos", icon: MapPin, perm: "endereco", lugar: "hub" },
      ],
    },
  ],
};
