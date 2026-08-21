"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Popover } from "@/components/ui/popover";
import { api, type ModuloOut } from "@/lib/api";
import { MENUS } from "@/lib/menus";
import { iconeDoModulo, moduloDoPathname } from "@/lib/modulos";
import { cn } from "@/lib/utils";

/**
 * Switcher de módulo no Header. Consome a MESMA queryKey `modulos-me` do
 * launcher (`app/(launcher)/modulos/page.tsx`) e herda o `QueryClient` do
 * `Providers` da árvore em vez de criar um próprio (já foi bug nesta
 * fatia) — mas isso NÃO significa cache compartilhado com o launcher: os
 * dois vivem em grupos de rota irmãos (`(app)` e `(launcher)`), cada um com
 * seu próprio `<Providers>`/`QueryClient`, então trocar entre eles sempre
 * desmonta um e monta o outro (ver comentário completo no launcher). Herdar
 * do layout continua certo pela consistência de config (`staleTime`,
 * `retry`), só não elimina o refetch ao cruzar de um grupo para o outro.
 *
 * Propriedade de desenho: trocar de módulo vai direto para a raiz dele
 * (`router.push`), sem passar pela tela `/modulos` — o launcher é porta de
 * entrada, não pedágio.
 */
export function ModuloSwitcher() {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const { data, isLoading, isError, refetch, isRefetching } = useQuery({
    queryKey: ["modulos-me"],
    queryFn: api.modulos,
  });

  // Clique-fora/ESC agora são do Popover (fatia 3.4); ao fechar por ESC ou
  // clique fora, o foco volta ao botão para não cair no body.
  const fechar = () => {
    setOpen(false);
    triggerRef.current?.focus();
  };

  // Carregando: estado transitório e curto (dado cacheado sob a mesma
  // queryKey do launcher) — não vale a pena um esqueleto só para isso.
  if (isLoading) return null;

  // Erro fica À MOSTRA e recuperável, diferente de "só tem um módulo": sem
  // isso, o switcher some tanto por falha de rede quanto por não ter para
  // onde trocar, e o usuário não consegue diferenciar os dois estados nem
  // sair do primeiro sem recarregar a página (retry:1 e sem refetch
  // automático no `Providers`). O launcher trata o mesmo dado com tela de
  // erro + "Tentar novamente"; aqui é a versão compacta da mesma ideia.
  if (isError) {
    return (
      <button
        type="button"
        onClick={() => refetch()}
        disabled={isRefetching}
        aria-label="Não foi possível carregar os módulos. Tentar novamente."
        title="Não foi possível carregar os módulos. Tentar novamente."
        className={cn(
          "inline-flex h-10 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium text-danger",
          "transition-colors duration-fast hover:bg-danger-soft disabled:opacity-60",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <AlertTriangle className="h-4 w-4" aria-hidden="true" />
        <span className="hidden sm:inline">
          {isRefetching ? "Tentando novamente…" : "Módulos indisponíveis"}
        </span>
      </button>
    );
  }

  const itens = data?.itens ?? [];
  const ordenados = [...itens].sort((a, b) => a.ordem - b.ordem);

  // Com 0 módulos não há nada para mostrar nem para onde trocar — some. Com 1
  // módulo o switcher continua útil: é o único caminho de volta a ele a
  // partir de uma rota transversal (ex.: /home), já que não há entrada
  // equivalente na Sidebar nem no AvatarDropdown.
  if (ordenados.length === 0) return null;

  const slugAtual = moduloDoPathname(pathname);
  const atual = ordenados.find((m) => m.slug === slugAtual) ?? null;
  // Rota transversal (ex.: /home) ou módulo que a API não devolveu: não pode
  // parecer que o usuário está num módulo em que não está — rótulo genérico.
  const IconeAtual = iconeDoModulo(atual?.icone);
  const rotuloAtual = atual?.nome ?? "Módulos";
  const rotuloAcessivel = atual
    ? `Módulo atual: ${atual.nome}. Trocar de módulo.`
    : "Selecionar módulo.";

  function irPara(slug: string) {
    setOpen(false);
    router.push(MENUS[slug]?.raiz ?? "/home");
  }

  function irParaLauncher() {
    setOpen(false);
    router.push("/modulos");
  }

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={rotuloAcessivel}
        className={cn(
          "inline-flex h-10 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium text-foreground",
          "transition-colors duration-fast hover:bg-muted",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <IconeAtual className="h-4 w-4 text-foreground-muted" aria-hidden="true" />
        <span className="hidden sm:inline">{rotuloAtual}</span>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 text-foreground-muted transition-transform duration-fast",
            open && "rotate-180",
          )}
          aria-hidden="true"
        />
      </button>

      <Popover open={open} anchorRef={triggerRef} onClose={fechar} className="w-64">
        <div role="menu" aria-label="Trocar de módulo">
          <div className="py-1">
            {ordenados.map((m) => (
              <ItemModulo
                key={m.slug}
                modulo={m}
                ativo={m.slug === atual?.slug}
                onClick={() => irPara(m.slug)}
              />
            ))}
          </div>
          {/* Com 1 módulo só, "Todos os módulos" bateria e voltaria na hora:
              o launcher com módulo único faz auto-redirect de volta para cá
              (requisito de produto, não mexido aqui). Item some para não
              prometer uma navegação que não acontece. */}
          {ordenados.length > 1 && (
            <div className="border-t border-border py-1">
              <button
                type="button"
                role="menuitem"
                onClick={irParaLauncher}
                className="
                  flex w-full items-center px-3 py-2 text-sm text-foreground-muted
                  transition-colors duration-fast hover:bg-muted hover:text-foreground
                "
              >
                Todos os módulos
              </button>
            </div>
          )}
        </div>
      </Popover>
    </div>
  );
}

function ItemModulo({
  modulo,
  ativo,
  onClick,
}: {
  modulo: ModuloOut;
  ativo: boolean;
  onClick: () => void;
}) {
  const Icone = iconeDoModulo(modulo.icone);
  return (
    <button
      type="button"
      role="menuitem"
      aria-current={ativo || undefined}
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors duration-fast",
        ativo
          ? "bg-primary/5 font-medium text-foreground"
          : "text-foreground hover:bg-muted",
      )}
    >
      <Icone className="h-4 w-4 text-foreground-muted" aria-hidden="true" />
      {modulo.nome}
    </button>
  );
}
