"use client";

import { FolderTree } from "lucide-react";

import { HubDoModulo } from "@/components/HubDoModulo";

/** Índice de Pagamentos: o que saiu do menu lateral (ver `HubDoModulo`). */
export default function PagamentosCadastrosPage() {
  return (
    <HubDoModulo
      slug="pagamentos"
      titulo="Cadastros e controle"
      descricao="Cadastros, caixa, ordem cronológica, exceções, auditoria e export contábil — as telas de apoio que não ficam no menu."
      icone={FolderTree}
    />
  );
}
