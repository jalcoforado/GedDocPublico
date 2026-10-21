"use client";

import { useQuery } from "@tanstack/react-query";
import { Bell, LayoutGrid, PenLine } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { notificacoesApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

/** Para onde vai quem opera processos. O painel mora no módulo Protocolo
 * (decisão do produto, 2026-10-21); a tela inicial é só o caminho até ele. */
const ROTA_PAINEL = "/m/protocolo/painel";

/**
 * Tela inicial. Quem opera processos (transação `processo`) é levado ao
 * painel de controle do protocolo, que é o que ele abriria de qualquer jeito;
 * quem não opera vê uma tela leve: saudação, notificações não lidas e o
 * caminho para os módulos e as assinaturas.
 *
 * `replace`, e não `push`: a `/home` não fica no histórico, senão o "voltar"
 * do painel cairia aqui e seria empurrado de novo para o painel.
 */
export default function HomePage() {
  const { can } = useAuth();
  const router = useRouter();
  // O shell só desenha a página depois de `/auth/me`, que traz usuário e
  // permissões juntos: aqui `can` já é a resposta final, não um "ainda não
  // sei" que viraria `false` por um instante.
  const operaProcessos = can("processo");

  useEffect(() => {
    if (operaProcessos) router.replace(ROTA_PAINEL);
  }, [operaProcessos, router]);

  // Enquanto o redirecionamento acontece, nada: desenhar a tela simples
  // faria ela piscar antes do painel.
  if (operaProcessos) return null;
  return <TelaInicialSimples />;
}

function TelaInicialSimples() {
  const { user } = useAuth();
  const primeiroNome = (user?.nome ?? "").split(/\s+/)[0] || "—";

  const notifQ = useQuery({
    queryKey: ["home-notificacoes-nao-lidas"],
    queryFn: () => notificacoesApi.listarMinhas({ apenas_nao_lidas: true, limit: 5 }),
    staleTime: 30_000,
  });
  const naoLidas = notifQ.data?.nao_lidas;
  const itens = notifQ.data?.items ?? [];
  const temAlgo = (naoLidas ?? 0) > 0;

  return (
    <div className="space-y-6">
      <PageHeader title="Início" description={`Olá, ${primeiroNome}.`} />

      <div className="grid gap-4 lg:grid-cols-3">
        <Link
          href="/perfil"
          className="block rounded-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          <KpiCard
            label="Notificações"
            value={naoLidas ?? "—"}
            hint="não lidas"
            icon={Bell}
            intent={temAlgo ? "danger" : "default"}
            className={cn("h-full", temAlgo && "border-l-4 border-l-danger")}
          />
        </Link>

        <SectionCard title="Atalhos" className="lg:col-span-2">
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="secondary">
              <Link href="/modulos">
                <LayoutGrid className="mr-1.5 h-4 w-4" aria-hidden="true" />
                Meus módulos
              </Link>
            </Button>
            <Button asChild variant="secondary">
              <Link href="/para-assinar">
                <PenLine className="mr-1.5 h-4 w-4" aria-hidden="true" />
                Para assinar
              </Link>
            </Button>
          </div>
        </SectionCard>
      </div>

      <section aria-label="Notificações não lidas" className="space-y-2">
        <h2 className="font-display text-base font-semibold text-foreground">
          Notificações não lidas
        </h2>
        {notifQ.isError ? (
          <p role="alert" className="text-sm text-danger-soft-foreground">
            Não foi possível carregar as notificações.
          </p>
        ) : !notifQ.data ? (
          <p className="text-sm text-foreground-muted">Carregando…</p>
        ) : itens.length === 0 ? (
          <p className="text-sm text-foreground-muted">Nenhuma notificação nova.</p>
        ) : (
          <ul className="divide-y divide-border rounded-card border border-border bg-surface-1">
            {itens.map((n) => (
              <li key={n.id} className="px-4 py-3 text-sm">
                {n.link_url ? (
                  <Link href={n.link_url} className="font-medium text-foreground underline-offset-2 hover:underline">
                    {n.titulo}
                  </Link>
                ) : (
                  <span className="font-medium text-foreground">{n.titulo}</span>
                )}
                <p className="mt-0.5 text-foreground-muted">{n.mensagem}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
