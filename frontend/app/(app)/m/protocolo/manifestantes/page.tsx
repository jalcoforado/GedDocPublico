"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { UserCircle } from "lucide-react";

import { CrudPage } from "@/components/CrudPage";
import { BadgeAtivo } from "@/components/protocolo/BadgeAtivo";
import { api, type Manifestante } from "@/lib/api";
import { aplicarMascara } from "@/lib/mascaras";

export default function ManifestantesPage() {
  const [q, setQ] = useState("");
  const tiposQ = useQuery({
    queryKey: ["tipos-manifestante"],
    queryFn: () => api.tiposManifestante.list(),
  });

  // Pessoa jurídica pelo tipo escolhido (`natureza`); sem tipo, física.
  const juridica = (form: { id_tipo_manifestante?: number | null }) =>
    tiposQ.data?.find((t) => t.id === form.id_tipo_manifestante)?.natureza === "J";
  const tipoPadrao =
    tiposQ.data?.find((t) => t.natureza === "F" && t.ativo) ?? tiposQ.data?.[0];

  return (
    <CrudPage<Manifestante>
      title="Manifestantes"
      icon={UserCircle}
      description="Pessoas e organizações que abrem ou acompanham processos."
      novoLabel="Novo manifestante"
      queryKey={["manifestantes", q]}
      fetchList={({ page }) => api.manifestantes.list({ q: q || undefined, page, page_size: 50 })}
      createFn={api.manifestantes.create}
      updateFn={api.manifestantes.update}
      deleteFn={api.manifestantes.remove}
      searchable
      onSearchChange={setQ}
      dialogSize="lg"
      emptyForm={{
        id_tipo_manifestante: tipoPadrao?.id ?? null,
        cpf_cnpj: "",
        nome: "",
        organizacao: "",
        telefone_celular: "",
        email: "",
        ativo: true,
      }}
      columns={[
        { header: "Nome", render: (r) => r.nome ?? "—" },
        {
          header: "CPF/CNPJ",
          render: (r) =>
            r.cpf_cnpj
              ? aplicarMascara(r.cpf_cnpj.length > 11 ? "cnpj" : "cpf", r.cpf_cnpj).valor
              : "—",
        },
        {
          header: "Tipo",
          render: (r) =>
            tiposQ.data?.find((t) => t.id === r.id_tipo_manifestante)
              ?.tipo_manifestante ?? "—",
        },
        { header: "Email", render: (r) => r.email ?? "—" },
        { header: "Situação", render: (r) => <BadgeAtivo ativo={r.ativo} />, className: "w-24" },
      ]}
      fields={[
        // Tipo e Situação na mesma linha: o Ativo ficava no fim do formulário,
        // visível só rolando o popup.
        {
          name: "id_tipo_manifestante",
          label: "Tipo",
          type: "select",
          required: true,
          options: tiposQ.data?.map((t) => ({ value: t.id, label: t.tipo_manifestante })),
        },
        { name: "ativo", label: "Situação", type: "checkbox", textoAoLado: "Ativo" },
        {
          name: "nome",
          label: (f) => (juridica(f) ? "Razão social" : "Nome"),
          type: "text",
          required: true,
          colSpan: 2,
        },
        {
          name: "cpf_cnpj",
          label: (f) => (juridica(f) ? "CNPJ" : "CPF"),
          type: "text",
          required: true,
          mascara: (f) => (juridica(f) ? "cnpj" : "cpf"),
        },
        {
          name: "email",
          label: "E-mail",
          type: "email",
          placeholder: "nome@exemplo.com.br",
        },
        { name: "telefone_celular", label: "Celular", type: "text", required: true, mascara: "celular" },
        { name: "telefone_residencial", label: "Residencial", type: "text", mascara: "telefone" },
        { name: "telefone_comercial", label: "Comercial", type: "text", mascara: "telefone" },
        { name: "organizacao", label: "Organização", type: "text" },
        { name: "responsavel", label: "Responsável", type: "text", colSpan: 2 },
        { name: "observacao", label: "Observação", type: "textarea", colSpan: 2 },
      ]}
    />
  );
}
