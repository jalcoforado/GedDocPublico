import {
  Banknote,
  BarChart3,
  BookOpen,
  Building2,
  CheckCircle,
  ClipboardList,
  FileText,
  FolderTree,
  Inbox,
  Landmark,
  Layers,
  ListChecks,
  Shield,
  ShieldCheck,
  UserCircle,
  Wallet,
} from "lucide-react";

import type { MenuModulo } from "./tipos";

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
          anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar", "pagamento_cadastro"] },
        { label: "Dashboard", href: "/m/pagamentos/dashboard", icon: BarChart3,
          anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar", "pagamento_cadastro"] },
        { label: "Solicitações", href: "/m/pagamentos/solicitacoes", icon: ClipboardList,
          anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar"] },
        { label: "Aguardando Gestor", href: "/m/pagamentos/solicitacoes/gestor", icon: CheckCircle,
          perm: "pagamento_gerir" },
        { label: "Aguardando Validação", href: "/m/pagamentos/solicitacoes/validacao", icon: CheckCircle,
          perm: "pagamento_validar" },
        { label: "Aguardando Autoridade", href: "/m/pagamentos/solicitacoes/autoridade", icon: CheckCircle,
          perm: "pagamento_autorizar" },
        { label: "Concluídas", href: "/m/pagamentos/solicitacoes/concluidas", icon: CheckCircle,
          anyOf: ["pagamento_solicitar", "pagamento_gerir", "pagamento_validar", "pagamento_autorizar"] },
        { label: "Contas a pagar", href: "/m/pagamentos/contas-a-pagar", icon: ClipboardList,
          anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar"] },
        { label: "Autorizações", href: "/m/pagamentos/autorizacao", icon: ShieldCheck,
          anyOf: ["pagamento_autorizar"] },
        { label: "Tesouraria", href: "/m/pagamentos/tesouraria", icon: Banknote,
          perm: "pagamento_pagar" },
        { label: "Caixa", href: "/m/pagamentos/caixa", icon: Wallet, perm: "pagamento_cadastro" },
        // Leitura espelha o `_LEITURA` do router de conciliação; a escrita
        // (importar/baixar/conciliar) exige `pagamento_pagar`.
        { label: "Conciliação", href: "/m/pagamentos/conciliacao", icon: Landmark,
          anyOf: ["pagamento_pagar", "pagamento_autorizar", "pagamento_auditar", "pagamento_cadastro"] },
        {
          label: "Cadastros",
          href: "/m/pagamentos/cadastros/fornecedores",
          icon: FolderTree,
          perm: "pagamento_cadastro",
          children: [
            { label: "Fornecedores", href: "/m/pagamentos/cadastros/fornecedores", icon: UserCircle, perm: "pagamento_cadastro" },
            { label: "Naturezas", href: "/m/pagamentos/cadastros/naturezas", icon: Layers, perm: "pagamento_cadastro" },
            { label: "Fontes de recursos", href: "/m/pagamentos/cadastros/fontes", icon: BookOpen, perm: "pagamento_cadastro" },
            { label: "Contas bancárias", href: "/m/pagamentos/cadastros/contas", icon: Building2, perm: "pagamento_cadastro" },
            { label: "Contratos", href: "/m/pagamentos/cadastros/contratos", icon: FileText, perm: "pagamento_cadastro" },
            { label: "Alçadas", href: "/m/pagamentos/cadastros/alcadas", icon: Shield, perm: "pagamento_cadastro" },
            { label: "Checklist documental", href: "/m/pagamentos/cadastros/checklist", icon: ListChecks, perm: "pagamento_cadastro" },
          ],
        },
      ],
    },
  ],
};
