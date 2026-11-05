"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { ArrowRight } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { api, type ModuloOut } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { primeiraRotaVisivel } from "@/lib/menus";
import { descricaoDoModulo, iconeDoModulo } from "@/lib/modulos";
import { cn } from "@/lib/utils";

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
  const { can, user } = useAuth();
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
    router.replace(primeiraRotaVisivel(ordenados[0].slug, can));
    // Roda só quando o veredito "módulo único" muda — não a cada re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moduloUnico]);

  if (isLoading) return <LauncherCarregando />;

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
    // Estado transitório: o useEffect acima já disparou o replace. A moldura
    // de carregamento, e não um "Entrando..." solto, para não piscar texto.
    return <LauncherCarregando />;
  }

  // Administração é configurar o órgão, não trabalho do dia: fica num grupo
  // próprio, depois, para os módulos de operação abrirem a tela.
  const trabalho = ordenados.filter((m) => !SLUGS_CONFIGURACAO.has(m.slug));
  const configuracao = ordenados.filter((m) => SLUGS_CONFIGURACAO.has(m.slug));
  const primeiroNome = (user?.nome ?? "").split(/\s+/)[0];

  return (
    <div className="animate-fade-in motion-reduce:animate-none">
      <h1 className="font-display text-2xl font-semibold tracking-tight text-titulo">
        {primeiroNome ? `Olá, ${primeiroNome}` : "Meus módulos"}
      </h1>
      <p className="mt-1 text-sm text-foreground-muted">Escolha onde você vai trabalhar agora.</p>

      <Grupo titulo="Módulos" modulos={trabalho} can={can} />
      {configuracao.length > 0 && (
        <nav aria-label="Configuração" className="mt-6 border-t border-border pt-4">
          {configuracao.map((m) => (
            <LinhaConfiguracao key={m.slug} modulo={m} href={primeiraRotaVisivel(m.slug, can)} />
          ))}
        </nav>
      )}
    </div>
  );
}

/**
 * Administração em destaque baixo: uma linha, não um cartão. É configuração
 * do órgão — quem a usa sabe onde está —, e como cartão disputava o olhar com
 * os módulos de trabalho do dia.
 */
function LinhaConfiguracao({ modulo: m, href }: { modulo: ModuloItem; href: string }) {
  const Icone = iconeDoModulo(m.icone);
  return (
    <Link
      href={href}
      className="group inline-flex max-w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-sm text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Icone className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="font-medium text-foreground">{m.nome}</span>
      <span className="hidden truncate sm:inline">— {descricaoDoModulo(m.slug)}</span>
      <ArrowRight
        className="h-3.5 w-3.5 shrink-0 transition-transform duration-fast group-hover:translate-x-0.5 motion-reduce:group-hover:translate-x-0"
        aria-hidden="true"
      />
    </Link>
  );
}

const SLUGS_CONFIGURACAO = new Set(["administracao"]);

type ModuloItem = ModuloOut;

function Grupo({
  titulo,
  modulos,
  can,
}: {
  titulo: string;
  modulos: ModuloItem[];
  can: (codigo: string) => boolean;
}) {
  if (modulos.length === 0) return null;
  return (
    <section aria-label={titulo} className="mt-6">
      {/* Sem rótulo visível: é o único grupo de cartões da tela, e "Módulos"
          em cima de módulos não informava nada. Quatro em três colunas
          deixava um cartão sozinho na segunda linha; com quatro, 2×2. */}
      <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-2", modulos.length !== 4 && "xl:grid-cols-3")}>
        {modulos.map((m) => (
          <CartaoModulo key={m.slug} modulo={m} href={primeiraRotaVisivel(m.slug, can)} />
        ))}
      </div>
    </section>
  );
}

/**
 * Cartão de um módulo. Módulo cujo slug não está em MENUS não some da tela:
 * cai em /home com ícone genérico (fail-open desta camada, coerente com D8) —
 * evita que um módulo novo no catálogo desapareça do launcher antes de a UI
 * dele existir. Dentre os que existem, vai para o primeiro item que o usuário
 * PODE ver, não a raiz fixa do módulo (item 1.0.9 do backlog).
 *
 * Desenho: cartão de superfície com borda, ícone num ladrilho de tom suave da
 * marca (o disco em gradiente com brilho pesava mais que o nome do módulo),
 * nome e descrição com a altura alinhada entre os cartões. O passar do mouse
 * muda borda e sombra e acende o ladrilho — nunca só a cor do texto.
 */
function CartaoModulo({ modulo: m, href }: { modulo: ModuloItem; href: string }) {
  const Icone = iconeDoModulo(m.icone);
  return (
    <Link
      href={href}
      className="group flex h-full items-start gap-4 rounded-card border border-border bg-surface-1 p-5 shadow-xs transition-[border-color,box-shadow,transform] duration-fast hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background motion-reduce:hover:translate-y-0"
    >
      <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-brand/10 text-brand transition-colors duration-fast group-hover:bg-brand group-hover:text-primary-foreground">
        <Icone className="h-5 w-5" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center justify-between gap-2">
          <span className="font-display text-base font-semibold text-foreground">{m.nome}</span>
          <ArrowRight
            className="h-4 w-4 shrink-0 text-foreground-subtle transition-transform duration-fast group-hover:translate-x-0.5 group-hover:text-brand motion-reduce:group-hover:translate-x-0"
            aria-hidden="true"
          />
        </span>
        <span className="mt-1 block text-sm leading-relaxed text-foreground-muted">
          {descricaoDoModulo(m.slug)}
        </span>
      </span>
    </Link>
  );
}

/** Mesma geometria da tela pronta: título e quatro cartões em 2×2. */
function LauncherCarregando() {
  return (
    <div role="status" aria-label="Carregando módulos" className="animate-aparece-depois motion-reduce:animate-none">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="mt-2 h-4 w-72 max-w-full" />
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex gap-4 rounded-card border border-border bg-surface-1 p-5">
            <Skeleton className="h-11 w-11 rounded-lg" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-2/3" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
