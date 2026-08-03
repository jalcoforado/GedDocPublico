"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { use, useEffect } from "react";

import { api } from "@/lib/api";
import { SLUGS_MODULO } from "@/lib/modulos";

/**
 * Guard de módulo das rotas `/m/<slug>/…` (F3).
 *
 * **É UX, não segurança, e a distinção é literal.** A barreira real está no
 * backend: `require_modulo` nega o GET e o gate de contratação em
 * `auth/perms.py` nega a transação — inclusive para super-usuário do tenant,
 * de propósito. Este componente existe para que o usuário sem o módulo veja o
 * launcher em vez de uma tela vazia com 403 no console. Nenhum teste deve
 * afirmar que ele protege dado; se o backend falhar, isto não salva nada.
 *
 * Não monta Sidebar nem Header: quem faz isso é `app/(app)/layout.tsx`, que já
 * resolve o módulo ativo por `moduloDoPathname` — e desde a F3 esse resolvedor
 * entende a forma canônica `/m/<slug>`. Duplicar o shell aqui daria duas
 * Sidebars aninhadas.
 */
export default function ModuloLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  // Next 15: `params` é Promise em Client Component; `use()` a desembrulha.
  params: Promise<{ modulo: string }>;
}) {
  const { modulo } = use(params);
  const router = useRouter();

  // Slug inexistente no catálogo do frontend nem chega a consultar a API.
  const slugConhecido = SLUGS_MODULO.has(modulo);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["modulos-me"],
    queryFn: api.modulos,
    enabled: slugConhecido,
  });

  // `undefined` enquanto carrega — distinto de `false`. Sem essa distinção o
  // primeiro render devolveria todo mundo ao launcher antes da resposta
  // chegar, e o módulo contratado piscaria para fora.
  const liberado = data ? data.itens.some((i) => i.slug === modulo) : undefined;

  useEffect(() => {
    if (!slugConhecido || liberado === false) router.replace("/modulos");
  }, [slugConhecido, liberado, router]);

  if (!slugConhecido) return null;

  // Erro de rede NÃO expulsa: devolver ao launcher aqui transformaria uma
  // falha temporária de `/modulos/me` em "você perdeu o módulo". Deixa passar
  // e o backend nega o que tiver de negar — que é a barreira que vale.
  if (isLoading && !isError) {
    return (
      <div className="text-foreground-muted">Carregando módulo…</div>
    );
  }
  if (liberado === false) return null;

  return <>{children}</>;
}
