"use client";

import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { MENUS } from "@/lib/menus";
import { iconeDoModulo } from "@/lib/modulos";

/**
 * Corpo do launcher. Fica num componente separado do `export default` porque
 * precisa do próprio QueryClient (ver comentário em `Launcher`, abaixo).
 */
function LauncherContent() {
  const router = useRouter();
  const { user } = useAuth();
  const {
    data,
    isLoading,
    isError,
    refetch,
  } = useQuery({ queryKey: ["modulos-me"], queryFn: api.modulos });

  const itens = data?.itens ?? [];
  const ordenados = [...itens].sort((a, b) => a.ordem - b.ordem);
  // Só um módulo contratado/permitido: o launcher é porta, não pedágio —
  // não faz sentido obrigar a escolher entre um item só.
  const moduloUnico = !isLoading && !isError && ordenados.length === 1;

  useEffect(() => {
    if (!moduloUnico) return;
    const raiz = MENUS[ordenados[0].slug]?.raiz ?? "/home";
    router.replace(raiz);
    // Roda só quando o veredito "módulo único" muda — não a cada re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moduloUnico]);

  if (isLoading) {
    return <p className="text-foreground-muted">Carregando módulos...</p>;
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <p className="text-foreground-muted">
          Não foi possível carregar os módulos. Tente novamente em instantes.
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  if (ordenados.length === 0) {
    return (
      <div className="max-w-md text-center">
        <p className="text-lg font-medium text-foreground">
          Nenhum módulo disponível para o seu usuário.
        </p>
        <p className="mt-2 text-sm text-foreground-muted">
          Fale com o administrador do seu órgão para contratar um módulo ou
          liberar sua permissão de acesso.
        </p>
      </div>
    );
  }

  if (moduloUnico) {
    // Estado transitório: o useEffect acima já disparou o replace.
    return <p className="text-foreground-muted">Entrando...</p>;
  }

  return (
    <div className="w-full max-w-3xl">
      <h1 className="mb-1 text-2xl font-semibold text-foreground">
        {user?.nome ? `Bem-vindo(a), ${user.nome}` : "Escolha um módulo"}
      </h1>
      <p className="mb-6 text-sm text-foreground-muted">
        Selecione o módulo em que deseja trabalhar.
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
        {ordenados.map((m) => {
          const Icone = iconeDoModulo(m.icone);
          // Módulo cujo slug não está em MENUS não some da tela: cai em
          // /home com ícone genérico (fail-open desta camada, coerente com
          // D8) — evita que um módulo novo no catálogo desapareça do
          // launcher antes de a UI dele existir.
          const raiz = MENUS[m.slug]?.raiz ?? "/home";
          return (
            <Link
              key={m.slug}
              href={raiz}
              className="flex flex-col items-center gap-3 rounded-lg border border-border bg-card p-6 text-center transition hover:border-primary hover:shadow-sm"
            >
              <Icone className="h-8 w-8 text-primary" />
              <span className="font-medium text-foreground">{m.nome}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

/**
 * `export default` da rota `/modulos`. Cria seu próprio QueryClient em vez de
 * depender do `Providers` do layout: assim o componente é testável isolado
 * (`render(<Launcher />)`, sem precisar montar layout + providers) e, dentro
 * da app real, o client do layout segue existindo por fora sem conflito —
 * este aqui só é usado pela subárvore do launcher.
 */
export default function Launcher() {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  );
  return (
    <QueryClientProvider client={client}>
      <LauncherContent />
    </QueryClientProvider>
  );
}
