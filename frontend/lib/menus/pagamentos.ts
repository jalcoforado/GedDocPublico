import {
  Banknote,
  BarChart3,
  BookOpen,
  Building2,
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
  raiz: "/pagamentos",
  grupos: [
    {
      title: "Pagamentos",
      defaultOpen: false,
      items: [
        { label: "Visão geral", href: "/pagamentos", icon: Inbox,
          anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar", "pagamento_cadastro"] },
        { label: "Dashboard", href: "/pagamentos/dashboard", icon: BarChart3,
          anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar", "pagamento_cadastro"] },
        { label: "Contas a pagar", href: "/pagamentos/contas-a-pagar", icon: ClipboardList,
          anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar"] },
        { label: "Autorizações", href: "/pagamentos/autorizacao", icon: ShieldCheck,
          anyOf: ["pagamento_autorizar"] },
        { label: "Tesouraria", href: "/pagamentos/tesouraria", icon: Banknote,
          perm: "pagamento_pagar" },
        { label: "Caixa", href: "/pagamentos/caixa", icon: Wallet, perm: "pagamento_cadastro" },
        // Leitura espelha o `_LEITURA` do router de conciliação; a escrita
        // (importar/baixar/conciliar) exige `pagamento_pagar`.
        { label: "Conciliação", href: "/pagamentos/conciliacao", icon: Landmark,
          anyOf: ["pagamento_pagar", "pagamento_autorizar", "pagamento_auditar", "pagamento_cadastro"] },
        {
          label: "Cadastros",
          href: "/pagamentos/cadastros/fornecedores",
          icon: FolderTree,
          perm: "pagamento_cadastro",
          children: [
            { label: "Fornecedores", href: "/pagamentos/cadastros/fornecedores", icon: UserCircle, perm: "pagamento_cadastro" },
            { label: "Naturezas", href: "/pagamentos/cadastros/naturezas", icon: Layers, perm: "pagamento_cadastro" },
            { label: "Fontes de recursos", href: "/pagamentos/cadastros/fontes", icon: BookOpen, perm: "pagamento_cadastro" },
            { label: "Contas bancárias", href: "/pagamentos/cadastros/contas", icon: Building2, perm: "pagamento_cadastro" },
            { label: "Contratos", href: "/pagamentos/cadastros/contratos", icon: FileText, perm: "pagamento_cadastro" },
            { label: "Alçadas", href: "/pagamentos/cadastros/alcadas", icon: Shield, perm: "pagamento_cadastro" },
            { label: "Checklist documental", href: "/pagamentos/cadastros/checklist", icon: ListChecks, perm: "pagamento_cadastro" },
          ],
        },
      ],
    },
  ],
};
