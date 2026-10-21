"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, LayoutGrid, PenLine } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { api, notificacoesApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

/** Para onde vai quem opera processos. O painel mora no módulo Protocolo
 * (decisão do produto, 2026-10-21); a tela inicial é só o caminho até ele. */
const ROTA_PAINEL = "/m/protocolo/painel";

/**
 * Tela inicial. Quem opera processos (transação `processo`) NUM TENANT QUE
 * CONTRATOU O PROTOCOLO é levado ao painel de controle do módulo, que é o que
 * ele abriria de qualquer jeito; os demais veem uma tela leve: saudação,
 * notificações não lidas e o caminho para os módulos e as assinaturas.
 *
 * A contratação entra na decisão porque `can()` sozinho não basta: ele
 * devolve `true` para todo super-usuário — e hoje todo grupo é SU —, então
 * num tenant só de Frota a `/home` empurraria todo mundo para um módulo que o
 * tenant não tem, com o menu do Protocolo e o painel negado pelo backend. E a
 * `/home` é o destino de "Início"/"Menu principal": não haveria saída.
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

  // Mesma queryKey do guard de módulo, do launcher e do switcher: o cache é
  // um só, e na maioria das vezes a resposta já está aqui.
  const modulosQ = useQuery({
    queryKey: ["modulos-me"],
    queryFn: api.modulos,
    enabled: operaProcessos,
  });
  // `undefined` enquanto carrega — distinto de `false`, que é "não contratou".
  const protocoloContratado = modulosQ.data
    ? modulosQ.data.itens.some((i) => i.slug === "protocolo")
    : undefined;
  const vaiAoPainel = operaProcessos && protocoloContratado === true;
  // Falha de `/modulos/me` não decide por ninguém: fica na tela simples, que
  // funciona em qualquer tenant. Empurrar para o painel no escuro poderia
  // levar a um módulo que o tenant não tem.
  const decidindo = operaProcessos && !modulosQ.isError && protocoloContratado === undefined;

  useEffect(() => {
    if (vaiAoPainel) router.replace(ROTA_PAINEL);
  }, [vaiAoPainel, router]);

  // Enquanto decide ou redireciona, nada: desenhar a tela simples faria ela
  // piscar antes do painel.
  if (decidindo || vaiAoPainel) return null;
  return <TelaInicialSimples />;
}

function TelaInicialSimples() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const primeiroNome = (user?.nome ?? "").split(/\s+/)[0] || "—";

  const notifQ = useQuery({
    // Sob `["notificacoes", "me"]`, o prefixo que o sino invalida: marcar
    // como lida lá atualiza esta lista, e vice-versa.
    queryKey: ["notificacoes", "me", "home-nao-lidas"],
    queryFn: () => notificacoesApi.listarMinhas({ apenas_nao_lidas: true, limit: 5 }),
    staleTime: 30_000,
  });
  const naoLidas = notifQ.data?.nao_lidas;
  const itens = notifQ.data?.items ?? [];
  const temAlgo = (naoLidas ?? 0) > 0;

  const recarregar = () => qc.invalidateQueries({ queryKey: ["notificacoes", "me"] });
  // Abrir a notificação é lê-la, como no sino: sem isso ela continuaria na
  // lista e no contador depois de aberta.
  const marcarLida = useMutation({
    mutationFn: (id: number) => notificacoesApi.marcarLida(id),
    onSuccess: recarregar,
  });
  const marcarTodas = useMutation({
    mutationFn: () => notificacoesApi.marcarTodasLidas(),
    onSuccess: recarregar,
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Início" description={`Olá, ${primeiroNome}.`} />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Não é link: não há tela que liste notificações — /perfil, para
            onde ia, só tem as preferências. A lista está logo abaixo. */}
        <KpiCard
          label="Notificações"
          value={naoLidas ?? "—"}
          hint="não lidas"
          icon={Bell}
          intent={temAlgo ? "danger" : "default"}
          className={cn("h-full", temAlgo && "border-l-4 border-l-danger")}
        />

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
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-base font-semibold text-foreground">
            Notificações não lidas
          </h2>
          {itens.length > 0 && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => marcarTodas.mutate()}
              disabled={marcarTodas.isPending}
            >
              <CheckCheck className="h-4 w-4" aria-hidden="true" />
              Marcar todas como lidas
            </Button>
          )}
        </div>
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
                  <Link
                    href={n.link_url}
                    onClick={() => marcarLida.mutate(n.id)}
                    className="font-medium text-foreground underline-offset-2 hover:underline"
                  >
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
