import {
  BarChart3,
  Banknote,
  BookOpen,
  Building2,
  CheckCircle,
  ClipboardList,
  FileSpreadsheet,
  FileText,
  FolderTree,
  Inbox,
  KeyRound,
  Landmark,
  Layers,
  ListChecks,
  ListOrdered,
  ScrollText,
  Shield,
  ShieldAlert,
  ShieldCheck,
  UserCircle,
  Wallet,
  Workflow,
} from "lucide-react";

import type { MenuModulo } from "./tipos";

/**
 * Quem lê o módulo — espelha `PERMS_LEITURA` do router
 * (`pagamentos_debitos.py`), que gateia `GET /pagamentos/minha-fila` e
 * `GET /pagamentos/dashboard`.
 *
 * Até 2026-10-11 "Visão geral" e "Dashboard" listavam `pagamento_aprovar`,
 * transação que não existe mais no backend, e deixavam de fora gestor,
 * validador e auditor: os três tinham o dado liberado e não viam a porta.
 */
export const PERMS_LEITURA_PAGAMENTOS = [
  "pagamento_solicitar", "pagamento_gerir", "pagamento_validar",
  "pagamento_autorizar", "pagamento_pagar", "pagamento_auditar",
  "pagamento_cadastro",
];

/** Menu do módulo pagamentos, movido verbatim da Sidebar (linha 166). */
export const menuPagamentos: MenuModulo = {
  slug: "pagamentos",
  raiz: "/m/pagamentos",
  grupos: [
    {
      title: "Pagamentos",
      defaultOpen: false,
      items: [
        { label: "Visão geral", href: "/m/pagamentos", icon: Inbox,
          anyOf: PERMS_LEITURA_PAGAMENTOS },
        { label: "Dashboard", href: "/m/pagamentos/dashboard", icon: BarChart3,
          anyOf: PERMS_LEITURA_PAGAMENTOS },
        // Mapa do processo inteiro, para quem opera entender o antes e o
        // depois da própria mesa. As quantidades vêm de endpoints de leitura
        // do módulo, daí o mesmo conjunto.
        { label: "Solicitações", href: "/m/pagamentos/solicitacoes", icon: ClipboardList,
          anyOf: ["pagamento_solicitar", "pagamento_gerir", "pagamento_validar", "pagamento_autorizar"] },
        // As etapas são abas de Solicitações (`components/pagamentos/AbasSolicitacoes`),
        // não itens da barra: eram quatro entradas para recortes da mesma lista.
        { label: "Aguardando Gestor", href: "/m/pagamentos/solicitacoes/gestor", icon: CheckCircle,
          perm: "pagamento_gerir", lugar: "aba" },
        { label: "Aguardando Validação", href: "/m/pagamentos/solicitacoes/validacao", icon: CheckCircle,
          perm: "pagamento_validar", lugar: "aba" },
        { label: "Aguardando Autoridade", href: "/m/pagamentos/solicitacoes/autoridade", icon: CheckCircle,
          perm: "pagamento_autorizar", lugar: "aba" },
        { label: "Concluídas", href: "/m/pagamentos/solicitacoes/concluidas", icon: CheckCircle,
          anyOf: ["pagamento_solicitar", "pagamento_gerir", "pagamento_validar", "pagamento_autorizar"],
          lugar: "aba" },
        // Cobre os dois atos do ordenador (Lei 4.320/64): autorizar a despesa
        // (gera OP) e liberar o pagamento pra tesouraria — abas da mesma tela.
        { label: "Autorizações", href: "/m/pagamentos/autorizacao", icon: ShieldCheck,
          perm: "pagamento_autorizar" },
        { label: "Tesouraria", href: "/m/pagamentos/tesouraria", icon: Banknote,
          perm: "pagamento_pagar" },
        // Leitura espelha o `_LEITURA` do router de conciliação; a escrita
        // (importar/baixar/conciliar) exige `pagamento_pagar`.
        { label: "Conciliação", href: "/m/pagamentos/conciliacao", icon: Landmark,
          anyOf: ["pagamento_pagar", "pagamento_autorizar", "pagamento_auditar", "pagamento_cadastro"] },
        // Índice do resto do módulo (`/m/pagamentos/cadastros`): os grupos
        // "Controle" e "Cadastros" abaixo moram lá, não na barra.
        { label: "Cadastros e controle", href: "/m/pagamentos/cadastros", icon: FolderTree,
          anyOf: PERMS_LEITURA_PAGAMENTOS },
      ],
    },
    {
      title: "Controle",
      items: [
        // Mapa do processo inteiro, para quem opera entender o antes e o
        // depois da própria mesa. As quantidades vêm de endpoints de leitura
        // do módulo, daí o mesmo conjunto.
        { label: "Fluxo do processo", href: "/m/pagamentos/fluxo", icon: Workflow,
          anyOf: PERMS_LEITURA_PAGAMENTOS, lugar: "hub" },
        // Leitura espelha `PERMS_LEITURA` do router (`pagamentos_debitos.py`)
        // — o mesmo conjunto que gateia `GET /pagamentos/fila-cronologica`.
        { label: "Ordem cronológica", href: "/m/pagamentos/fila", icon: ListOrdered,
          anyOf: PERMS_LEITURA_PAGAMENTOS, lugar: "hub" },
        // Saldos, extrato e bloqueios por conta. Todo o router
        // (`pagamentos_caixa.py`) exige `pagamento_cadastro`.
        { label: "Caixa", href: "/m/pagamentos/caixa", icon: Wallet,
          perm: "pagamento_cadastro", lugar: "hub" },
        // Relatório de exceções: leitura ampla de propósito no router — quem
        // audita não é necessariamente quem autoriza ou paga.
        { label: "Exceções", href: "/m/pagamentos/excecoes", icon: ShieldAlert,
          anyOf: PERMS_LEITURA_PAGAMENTOS, lugar: "hub" },
        // Mesmo gate do router (`pagamentos_auditoria.py`): só quem audita.
        { label: "Trilha de auditoria", href: "/m/pagamentos/auditoria", icon: ScrollText,
          perm: "pagamento_auditar", lugar: "hub" },
        // Leitura e geração exigem `pagamento_cadastro`, mesmo gate do router
        // (`pagamentos_contabil.py`): POST pede action "inserir", GETs só a
        // transação.
        { label: "Export contábil", href: "/m/pagamentos/contabil", icon: FileSpreadsheet,
          perm: "pagamento_cadastro", lugar: "hub" },
      ],
    },
    {
      title: "Cadastros",
      items: [
        { label: "Fornecedores", href: "/m/pagamentos/cadastros/fornecedores", icon: UserCircle, perm: "pagamento_cadastro", lugar: "hub" },
        { label: "Naturezas", href: "/m/pagamentos/cadastros/naturezas", icon: Layers, perm: "pagamento_cadastro", lugar: "hub" },
        { label: "Fontes de recursos", href: "/m/pagamentos/cadastros/fontes", icon: BookOpen, perm: "pagamento_cadastro", lugar: "hub" },
        { label: "Contas bancárias", href: "/m/pagamentos/cadastros/contas", icon: Building2, perm: "pagamento_cadastro", lugar: "hub" },
        { label: "Contratos", href: "/m/pagamentos/cadastros/contratos", icon: FileText, perm: "pagamento_cadastro", lugar: "hub" },
        { label: "Alçadas", href: "/m/pagamentos/cadastros/alcadas", icon: Shield, perm: "pagamento_cadastro", lugar: "hub" },
        { label: "Checklist documental", href: "/m/pagamentos/cadastros/checklist", icon: ListChecks, perm: "pagamento_cadastro", lugar: "hub" },
        { label: "Sistemas integrados", href: "/m/pagamentos/cadastros/integracoes", icon: KeyRound, perm: "pagamento_cadastro", lugar: "hub" },
      ],
    },
  ],
};
