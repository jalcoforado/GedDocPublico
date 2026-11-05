"use client";

import { useParams } from "next/navigation";

import { FormularioProcesso } from "@/components/protocolo/FormularioProcesso";

/**
 * Edição do rascunho (SI-16): o mesmo formulário da abertura, carregado com o
 * rascunho. Só o autor chega aqui com sucesso — para os outros o servidor
 * responde 404, e o formulário diz isso.
 */
export default function EditarRascunhoPage() {
  const { id } = useParams<{ id: string }>();
  return <FormularioProcesso rascunhoId={Number(id)} />;
}
