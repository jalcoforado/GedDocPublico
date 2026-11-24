"use client";

import { useQuery } from "@tanstack/react-query";
import { Shield } from "lucide-react";

import { CrudPage, type CrudField } from "@/components/CrudPage";
import { fmtMoeda } from "@/components/pagamentos/format";
import { api, type Alcada, type Usuario } from "@/lib/api";

/**
 * Todos os usuários, página a página: a API devolve no máximo 100 por vez, e
 * parar na primeira página esconderia em silêncio quem vem depois na ordem
 * alfabética — justamente quem não daria para escolher.
 */
async function todosOsUsuarios(): Promise<Usuario[]> {
  const primeira = await api.usuarios.list({ page: 1, page_size: 100 });
  const paginas = Math.ceil(primeira.total / 100);
  if (paginas <= 1) return primeira.items;
  const resto = await Promise.all(
    Array.from({ length: paginas - 1 }, (_, i) => api.usuarios.list({ page: i + 2, page_size: 100 })),
  );
  return [...primeira.items, ...resto.flatMap((p) => p.items)];
}

export default function AlcadasPage() {
  const naturezasQ = useQuery({
    queryKey: ["pag-naturezas-select"],
    queryFn: () => api.pagamentos.cadastros.naturezas.list(),
  });
  const usuariosQ = useQuery({
    queryKey: ["usuarios-todos"],
    queryFn: todosOsUsuarios,
    retry: false,
  });
  const nomeUsuario = (id: number) => usuariosQ.data?.find((u) => u.id === id)?.nome;

  // Sem acesso à lista de usuários (permissão de outro módulo), o campo volta
  // a ser o número do usuário — pior, mas ainda dá para cadastrar.
  const campoUsuario: CrudField<Alcada> = usuariosQ.isError
    ? {
        name: "id_usuario",
        label: "Usuário (número)",
        type: "number",
        required: true,
        colSpan: 2,
        dica: "Número do usuário em Administração › Usuários.",
      }
    : {
        name: "id_usuario",
        label: "Usuário",
        type: "select",
        required: true,
        colSpan: 2,
        options: usuariosQ.data?.map((u) => ({ value: u.id, label: `${u.nome} — ${u.email}` })),
        dica: "Quem pode aprovar solicitações até o valor máximo abaixo.",
      };

  return (
    <CrudPage<Alcada>
      title="Alçadas de aprovação"
      icon={Shield}
      description="Até quanto cada usuário pode aprovar, por natureza de despesa."
      novoLabel="Nova alçada"
      queryKey={["pag-alcadas"]}
      fetchList={() => api.pagamentos.cadastros.alcadas.list()}
      createFn={api.pagamentos.cadastros.alcadas.create}
      updateFn={api.pagamentos.cadastros.alcadas.update}
      deleteFn={api.pagamentos.cadastros.alcadas.remove}
      emptyForm={{ id_usuario: null, id_natureza: null, valor_maximo: null }}
      columns={[
        { header: "Usuário", render: (r) => nomeUsuario(r.id_usuario) ?? `Usuário ${r.id_usuario}` },
        {
          header: "Natureza",
          render: (r) =>
            r.id_natureza
              ? naturezasQ.data?.find((n) => n.id === r.id_natureza)?.descricao ?? r.id_natureza
              : "Todas",
        },
        {
          header: "Valor máximo",
          render: (r) => fmtMoeda(r.valor_maximo),
          className: "text-right tabular-nums",
        },
      ]}
      fields={[
        campoUsuario,
        {
          name: "id_natureza",
          label: "Natureza",
          type: "select",
          options: naturezasQ.data?.map((n) => ({ value: n.id, label: n.descricao })),
          dica: "Em branco, a alçada vale para todas as naturezas.",
        },
        {
          name: "valor_maximo",
          label: "Valor máximo",
          type: "number",
          required: true,
          prefixo: "R$",
          placeholder: "0,00",
          dica: "O maior valor que este usuário pode aprovar.",
        },
      ]}
    />
  );
}
