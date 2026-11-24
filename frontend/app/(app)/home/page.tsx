"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Banknote,
  Bus,
  CheckCheck,
  FileText,
  Home,
  type LucideIcon,
  PenLine,
  Star,
  Truck,
} from "lucide-react";
import Link from "next/link";

import { Panorama } from "@/components/home/Panorama";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api, notificacoesApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { hrefDaCaixa } from "@/lib/caixas-processos";
import { MENUS } from "@/lib/menus";
import { PERMS_LEITURA_PAGAMENTOS } from "@/lib/menus/pagamentos";
import { cn } from "@/lib/utils";

/**
 * Início — a tela que atravessa os módulos: o que pede a pessoa HOJE, em
 * todos os módulos que a prefeitura contratou e que ela alcança.
 *
 * Até 2026-11-05 a `/home` empurrava quem opera processos para o painel do
 * Protocolo (decisão de 2026-10-21, PR 142 do repositório). Na prática "Início" virou um
 * segundo link para "Painel de controle": clicado no painel, recarregava a
 * mesma tela; clicado em Pagamentos, jogava a pessoa no Protocolo. O painel
 * de cada módulo responde "como está a minha unidade NESTE módulo"; o Início
 * responde "o que precisa de mim agora, em qualquer lugar".
 *
 * Cada cartão só aparece se o módulo está contratado E a pessoa tem a
 * leitura dele — as mesmas regras do menu —, e cada número leva à lista que
 * o conta, na tela do próprio módulo. Número que não carregou diz isso, em
 * vez de mostrar zero.
 */

interface LinhaDef {
  rotulo: string;
  valor: number | undefined;
  href: string;
  /** Só pinta quando há algo: zero nunca é alarme. */
  tom?: "danger" | "warning";
}

function saudacao(agora: Date): string {
  const h = agora.getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

export default function HomePage() {
  const { user, can } = useAuth();
  const primeiroNome = (user?.nome ?? "").split(/\s+/)[0] || "";
  const agora = new Date();
  const data = agora.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  const hoje = data.charAt(0).toUpperCase() + data.slice(1);

  // Mesma queryKey do guard de módulo e do menu lateral.
  const modulosQ = useQuery({ queryKey: ["modulos-me"], queryFn: api.modulos });
  const contratado = (slug: string) => !!modulosQ.data?.itens.some((i) => i.slug === slug);

  const veProtocolo = contratado("protocolo") && can("processo");
  const vePagamentos = contratado("pagamentos") && PERMS_LEITURA_PAGAMENTOS.some((p) => can(p));
  const veFrota = contratado("frota") && can("frota");
  const veTransporte = contratado("transporte") && can("transporte_regulado");

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Home}
        title="Início"
        description={
          <>
            {saudacao(agora)}
            {primeiroNome && `, ${primeiroNome}`} — {hoje}.
          </>
        }
        actions={
          // A lista de módulos mora no menu lateral, que desde o menu único
          // também aparece aqui.
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="secondary">
              <Link href="/para-assinar">
                <PenLine className="h-4 w-4" aria-hidden="true" />
                Para assinar
              </Link>
            </Button>
          </div>
        }
      />

      <section aria-labelledby="pendencias-titulo" className="space-y-4">
        <h2 id="pendencias-titulo" className="font-display text-base font-semibold text-foreground">
          O que precisa de você hoje
        </h2>
        {modulosQ.isError ? (
          <p role="alert" className="text-sm text-danger-soft-foreground">
            Não foi possível saber quais módulos a prefeitura contratou, então os resumos não
            aparecem. As notificações abaixo continuam valendo.
          </p>
        ) : !modulosQ.data ? (
          <div role="status" className="grid gap-4 animate-aparece-depois motion-reduce:animate-none lg:grid-cols-2">
            <span className="sr-only">Carregando…</span>
            <Skeleton aria-hidden="true" role="presentation" className="h-44 rounded-card" variant="shimmer" />
            <Skeleton aria-hidden="true" role="presentation" className="h-44 rounded-card" variant="shimmer" />
          </div>
        ) : !veProtocolo && !vePagamentos && !veFrota && !veTransporte ? (
          <EmptyState
            icon={CheckCheck}
            title="Nenhum módulo com pendências para o seu perfil"
            description="Os módulos que você alcança estão no menu ao lado."
          />
        ) : (
          (() => {
            // Um módulo só vira faixa de largura inteira: um cartão sozinho
            // ocupava meia tela e deixava a outra metade em branco.
            const faixa = [veProtocolo, vePagamentos, veFrota, veTransporte].filter(Boolean).length === 1;
            return (
              <div className={cn("grid gap-5", !faixa && "lg:grid-cols-2 2xl:grid-cols-4")}>
                {veProtocolo && <CartaoProtocolo faixa={faixa} />}
                {vePagamentos && <CartaoPagamentos faixa={faixa} />}
                {veFrota && <CartaoFrota faixa={faixa} />}
                {veTransporte && <CartaoTransporte faixa={faixa} />}
              </div>
            );
          })()
        )}
      </section>

      {modulosQ.data && (
        <Panorama
          acesso={{
            // O panorama do Protocolo vem do dashboard executivo, que tem
            // permissão própria (`dashboard`) além da de processos.
            protocolo: contratado("protocolo") && can("dashboard"),
            pagamentos: vePagamentos,
            frota: veFrota,
            transporte: veTransporte,
          }}
        />
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Notificacoes />
        {veProtocolo && <Acompanhando />}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ cartões ---- */

function Cartao({
  titulo,
  icone: Icone,
  href,
  linhas,
  carregando,
  erro,
  faixa = false,
}: {
  titulo: string;
  icone: LucideIcon;
  href: string;
  linhas: LinhaDef[];
  carregando: boolean;
  erro: boolean;
  /** Largura inteira: as linhas viram blocos lado a lado (número em destaque). */
  faixa?: boolean;
}) {
  return (
    <section
      aria-label={titulo}
      className="flex flex-col rounded-card border border-border bg-surface-1 shadow-card"
    >
      <div className="flex items-center justify-between gap-2 border-b border-border px-5 py-4">
        <h3 className="inline-flex items-center gap-2 font-display text-sm font-semibold text-foreground">
          <Icone className="h-4 w-4 text-primary" aria-hidden="true" />
          {titulo}
        </h3>
        <Link
          href={href}
          className="-mx-1.5 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
        >
          Abrir módulo
          <ArrowRight className="h-3 w-3" aria-hidden="true" />
        </Link>
      </div>
      {erro ? (
        <p className="px-5 py-4 text-sm text-danger-soft-foreground">
          Não foi possível carregar os números deste módulo agora.
        </p>
      ) : faixa ? (
        <ul className="grid grid-cols-2 divide-border lg:grid-cols-4 lg:divide-x">
          {linhas.map((l) => {
            const ativo = !carregando && l.valor !== undefined && l.valor > 0;
            const conteudo = (
              <>
                <span
                  className={cn(
                    "text-xs uppercase tracking-wide text-foreground-subtle",
                    ativo && l.tom === "danger" && "font-medium text-danger-soft-foreground",
                    ativo && l.tom === "warning" && "font-medium text-warning-soft-foreground",
                  )}
                >
                  {l.rotulo}
                </span>
                <span
                  className={cn(
                    "font-display text-2xl tabular-nums",
                    !ativo && "text-foreground-subtle",
                    ativo && "font-semibold",
                    ativo && l.tom === "danger" && "text-danger-soft-foreground",
                    ativo && l.tom === "warning" && "text-warning-soft-foreground",
                    ativo && !l.tom && "text-foreground",
                  )}
                >
                  {carregando || l.valor === undefined ? "…" : l.valor}
                </span>
              </>
            );
            return (
              <li key={l.rotulo}>
                {ativo ? (
                  <Link
                    href={l.href}
                    aria-label={`${l.rotulo}: ${l.valor} — abrir a lista`}
                    className="flex h-full flex-col gap-1.5 px-5 py-4 transition-colors duration-fast hover:bg-muted/60 focus-visible:bg-muted/60"
                  >
                    {conteudo}
                  </Link>
                ) : (
                  <div className="flex flex-col gap-1.5 px-5 py-4">{conteudo}</div>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <ul className="divide-y divide-border">
          {linhas.map((l) => {
            const pronto = !carregando && l.valor !== undefined;
            // O rótulo fica neutro: a cor do alerta vai só na contagem. Rótulo
            // e número tingidos juntos, em âmbar e vermelho, viravam uma
            // coluna colorida que brigava com o resto da tela.
            const conteudo = (
              <>
                <span className="text-foreground">{l.rotulo}</span>
                {!pronto ? (
                  <span className="text-foreground-subtle">…</span>
                ) : (
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className={cn(
                        "min-w-8 rounded-full px-2 text-center tabular-nums",
                        l.valor! > 0 && "font-semibold",
                        l.valor! > 0 && l.tom === "danger" && "bg-danger-soft text-danger-soft-foreground",
                        l.valor! > 0 && l.tom === "warning" && "bg-warning-soft text-warning-soft-foreground",
                        l.valor! > 0 && !l.tom && "bg-muted text-foreground",
                        l.valor === 0 && "text-foreground-subtle",
                      )}
                    >
                      {l.valor}
                    </span>
                    {l.valor! > 0 && (
                      <ArrowRight
                        className="h-3.5 w-3.5 text-foreground-subtle transition-transform duration-fast group-hover:translate-x-0.5 group-hover:text-foreground"
                        aria-hidden="true"
                      />
                    )}
                  </span>
                )}
              </>
            );
            return (
              <li key={l.rotulo}>
                {pronto && l.valor! > 0 ? (
                  // A linha inteira é o alvo do clique (antes só o número, um
                  // alvo de 30px num cartão de 600px).
                  <Link
                    href={l.href}
                    aria-label={`${l.rotulo}: ${l.valor} — abrir a lista`}
                    className="group flex items-center justify-between gap-3 px-5 py-3.5 text-sm transition-colors duration-fast hover:bg-muted/60 focus-visible:bg-muted/60"
                  >
                    {conteudo}
                  </Link>
                ) : (
                  // Zero não leva a lugar nenhum: não há lista para abrir.
                  <div className="flex items-center justify-between gap-3 px-5 py-3.5 text-sm">{conteudo}</div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function CartaoProtocolo({ faixa }: { faixa: boolean }) {
  // Sob `protocolo-painel`, a mesma chave do painel: o cache é um só, e trocar
  // de unidade ativa invalida os dois juntos.
  const q = useQuery({ queryKey: ["protocolo-painel"], queryFn: () => api.processos.painel(), staleTime: 60_000 });
  const p = q.data;
  return (
    <Cartao
      titulo="Protocolo"
      icone={FileText}
      href={MENUS.protocolo.raiz}
      carregando={q.isLoading}
      erro={q.isError}
      faixa={faixa}
      linhas={[
        { rotulo: "A receber na unidade", valor: p?.caixas.entrada, href: hrefDaCaixa("entrada"), tom: "warning" },
        { rotulo: "Na mesa da unidade", valor: p?.caixas.analise, href: hrefDaCaixa("analise") },
        { rotulo: "Com prazo vencido", valor: p?.prazos.vencidos, href: hrefDaCaixa("analise"), tom: "danger" },
        { rotulo: "Esperando a sua assinatura", valor: p?.caixas.aguardando_assinatura, href: "/para-assinar", tom: "warning" },
      ]}
    />
  );
}

function CartaoPagamentos({ faixa }: { faixa: boolean }) {
  const q = useQuery({
    // A mesma chave do dashboard financeiro (com 12 meses, o padrão dele).
    queryKey: ["pag-dashboard", 12],
    queryFn: () => api.pagamentos.dashboard(12),
    staleTime: 60_000,
  });
  const k = q.data?.kpis;
  return (
    <Cartao
      titulo="Pagamentos"
      icone={Banknote}
      href={MENUS.pagamentos.raiz}
      carregando={q.isLoading}
      erro={q.isError}
      faixa={faixa}
      linhas={[
        // Os mesmos destinos do dashboard financeiro ("ver fila →").
        { rotulo: "Aguardando aprovação", valor: k?.aguardando_aprovacao_qtd, href: "/m/pagamentos", tom: "warning" },
        { rotulo: "Aguardando autorização", valor: k?.aguardando_autorizacao_qtd, href: "/m/pagamentos", tom: "warning" },
        { rotulo: "Parcelas vencidas", valor: k?.vencidas_qtd, href: "/m/pagamentos/dashboard", tom: "danger" },
      ]}
    />
  );
}

function CartaoFrota({ faixa }: { faixa: boolean }) {
  // A lista de solicitações não tem contagem própria nem filtro por situação
  // no backend; é a mesma consulta da tela de Solicitações (cache comum).
  const q = useQuery({ queryKey: ["frota-solicitacoes"], queryFn: () => api.solicitacoes.listAll(), staleTime: 60_000 });
  const aguardando = q.data?.filter((s) => s.status === "solicitada").length;
  return (
    <Cartao
      titulo="Frota"
      icone={Truck}
      href={MENUS.frota.raiz}
      carregando={q.isLoading}
      erro={q.isError}
      faixa={faixa}
      linhas={[
        { rotulo: "Solicitações aguardando aprovação", valor: aguardando, href: "/m/frota/solicitacoes", tom: "warning" },
      ]}
    />
  );
}

function CartaoTransporte({ faixa }: { faixa: boolean }) {
  const q = useQuery({
    queryKey: ["/transporte-regulado/alvaras/relatorio/kpis"],
    queryFn: () => api.alvaras.relatorio.kpis(),
    staleTime: 60_000,
  });
  const k = q.data;
  return (
    <Cartao
      titulo="Transporte Regulado"
      icone={Bus}
      href={MENUS.transporte.raiz}
      carregando={q.isLoading}
      erro={q.isError}
      faixa={faixa}
      linhas={[
        { rotulo: "Alvarás vencidos", valor: k?.vencidos, href: "/m/transporte/relatorio", tom: "danger" },
        { rotulo: "Alvarás a renovar em 30 dias", valor: k?.a_renovar_30d, href: "/m/transporte/relatorio", tom: "warning" },
      ]}
    />
  );
}

/* ------------------------------------------------------ notificações ---- */

function Notificacoes() {
  const qc = useQueryClient();
  const notifQ = useQuery({
    // Sob `["notificacoes", "me"]`, o prefixo que o sino invalida: marcar
    // como lida lá atualiza esta lista, e vice-versa.
    queryKey: ["notificacoes", "me", "home-nao-lidas"],
    queryFn: () => notificacoesApi.listarMinhas({ apenas_nao_lidas: true, limit: 5 }),
    staleTime: 30_000,
  });
  const naoLidas = notifQ.data?.nao_lidas ?? 0;
  const itens = notifQ.data?.items ?? [];

  const recarregar = () => qc.invalidateQueries({ queryKey: ["notificacoes", "me"] });
  // Abrir a notificação é lê-la, como no sino.
  const marcarLida = useMutation({
    mutationFn: (id: number) => notificacoesApi.marcarLida(id),
    onSuccess: recarregar,
  });
  const marcarTodas = useMutation({
    mutationFn: () => notificacoesApi.marcarTodasLidas(),
    onSuccess: recarregar,
  });

  return (
    <section aria-label="Notificações não lidas" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-base font-semibold text-foreground">
          Notificações não lidas
          {naoLidas > 0 && (
            <Badge intent="danger" className="ml-2 tabular-nums">
              {naoLidas}
            </Badge>
          )}
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
        <Carregando className="text-sm text-foreground-muted" />
      ) : itens.length === 0 ? (
        <p className="rounded-card border border-border bg-surface-1 px-5 py-4 text-sm text-foreground-muted">
          Nenhuma notificação nova.
        </p>
      ) : (
        <ul className="divide-y divide-border rounded-card border border-border bg-surface-1">
          {itens.map((n) => (
            <li key={n.id} className="px-5 py-3.5 text-sm">
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
  );
}

/* ------------------------------------------------------ acompanhando ---- */

/** Quantos favoritos aparecem; o resto está na lista filtrada. */
const QUANTOS_ACOMPANHANDO = 5;

/**
 * Os processos que a pessoa marcou com estrela, e onde cada um está AGORA —
 * inclusive os que já saíram da unidade dela. É o "Favoritos" do SUITE (CE):
 * acompanhar sem precisar abrir um por um.
 */
function Acompanhando() {
  const q = useQuery({
    queryKey: ["processos", "home-favoritos"],
    queryFn: () =>
      api.processos.list({ favoritos: true, apenas_ativos: false, page: 1, page_size: QUANTOS_ACOMPANHANDO }),
    staleTime: 60_000,
  });
  const itens = q.data?.items ?? [];
  const total = q.data?.total ?? 0;

  return (
    <section aria-labelledby="acompanhando-titulo" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="acompanhando-titulo" className="font-display text-base font-semibold text-foreground">
          Processos que você acompanha
        </h2>
        {total > QUANTOS_ACOMPANHANDO && (
          <Link
            href="/m/protocolo/processos?favoritos=1&ativos=0"
            className="inline-flex items-center gap-1 rounded text-sm font-medium text-foreground underline underline-offset-2 hover:no-underline"
          >
            Ver todos ({total})
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        )}
      </div>
      {q.isError ? (
        <p role="alert" className="text-sm text-danger-soft-foreground">
          Não foi possível carregar os processos acompanhados.
        </p>
      ) : !q.data ? (
        <Carregando className="text-sm text-foreground-muted" />
      ) : itens.length === 0 ? (
        <p className="rounded-card border border-border bg-surface-1 px-5 py-4 text-sm text-foreground-muted">
          <Star className="mr-1.5 inline h-4 w-4 align-[-3px]" aria-hidden="true" />
          Nenhum processo acompanhado. Marque a estrela de um processo — na lista ou no detalhe — para
          ver aqui onde ele está.
        </p>
      ) : (
        // A Table já é um cartão (borda, fundo, sombra): sem casca em volta.
        <Table>
          <THead>
            <TR>
              <TH>Processo</TH>
              <TH>Assunto</TH>
              <TH>Onde está agora</TH>
            </TR>
          </THead>
          <TBody>
            {itens.map((p) => (
              <TR key={p.id}>
                <TD className="font-mono text-xs tabular-nums">
                  <Link
                    href={`/m/protocolo/processos/${p.id}`}
                    className="font-medium text-primary underline-offset-2 hover:underline"
                  >
                    {p.nup ?? p.numero_processo}
                  </Link>
                </TD>
                <TD>
                  <div className="line-clamp-1 text-sm">{p.assunto ?? "—"}</div>
                </TD>
                <TD className="text-sm">
                  {p.local_atual ?? <span className="text-foreground-muted">sem unidade registrada</span>}
                  {!p.ativo && <span className="ml-1 text-xs text-foreground-muted">(inativo)</span>}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </section>
  );
}
