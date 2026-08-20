"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { ArrowRight } from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { MENUS } from "@/lib/menus";
import { descricaoDoModulo, iconeDoModulo } from "@/lib/modulos";

/**
 * Tela de seleção de módulos (`/modulos`). Herda o `QueryClient` do
 * `Providers` em `app/(launcher)/layout.tsx` em vez de criar um próprio —
 * mesma configuração (`staleTime`, `retry`, `refetchOnWindowFocus`) do resto
 * do app.
 *
 * O que isso NÃO dá: cache compartilhado com o switcher do Header
 * (`ModuloSwitcher`, em `components/ModuloSwitcher.tsx`). `(app)` e
 * `(launcher)` são grupos de rota IRMÃOS, cada um monta o próprio
 * `<Providers>`, e `Providers` cria o `QueryClient` num `useState` — ir de
 * `/m/frota` para `/modulos` desmonta um layout e monta o outro, então o
 * client (e o cache de `modulos-me`) é sempre novo. Herdar do layout
 * continua certo pela consistência de config, só não pela consistência de
 * cache entre os dois grupos.
 */
export default function Launcher() {
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

  const hoje = new Intl.DateTimeFormat("pt-BR", { dateStyle: "full" }).format(new Date());

  return (
    <div className="w-full max-w-4xl animate-fade-in">
      <p className="mb-1 text-sm capitalize text-foreground-subtle">{hoje}</p>
      <h1 className="mb-1 text-3xl font-semibold tracking-tight text-foreground">
        {user?.nome ? `Bem-vindo(a), ${user.nome}` : "Escolha um módulo"}
      </h1>
      <p className="mb-8 text-md text-foreground-muted">
        Selecione o módulo em que deseja trabalhar.
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
              className="group flex flex-col gap-4 rounded-2xl border border-border bg-card p-6 shadow-xs transition-all duration-base hover:-translate-y-0.5 hover:border-brand/50 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <div className="flex items-start justify-between">
                <span className="inline-flex h-12 w-12 items-center justify-center rounded-lg bg-brand-gradient text-white shadow-brand">
                  <Icone className="h-6 w-6" aria-hidden="true" />
                </span>
                <ArrowRight
                  className="h-4 w-4 translate-x-0 text-foreground-subtle opacity-0 transition-all duration-fast group-hover:translate-x-1 group-hover:text-brand group-hover:opacity-100"
                  aria-hidden="true"
                />
              </div>
              <div>
                <div className="text-md font-semibold text-foreground">{m.nome}</div>
                <p className="mt-1 text-sm leading-relaxed text-foreground-muted">
                  {descricaoDoModulo(m.slug)}
                </p>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
