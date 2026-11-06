"use client";

import { FolderTree } from "lucide-react";

import { HubDoModulo } from "@/components/HubDoModulo";

/** Índice do Protocolo: o que saiu do menu lateral (ver `HubDoModulo`). */
export default function ProtocoloCadastrosPage() {
  return (
    <HubDoModulo
      slug="protocolo"
      titulo="Cadastros e configuração"
      descricao="Cadastros, gestão documental, fluxos e prazos do Protocolo — as telas de apoio que não ficam no menu."
      icone={FolderTree}
    />
  );
}
