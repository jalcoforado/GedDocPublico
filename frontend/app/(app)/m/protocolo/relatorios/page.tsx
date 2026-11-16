"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  FileCheck,
  Inbox,
  LayoutDashboard,
  type LucideIcon,
  PenLine,
  Plus,
  Star,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Carregando } from "@/components/ui/carregando";
import { PageHeader } from "@/components/ui/page-header";
import { api } from "@/lib/api";
import {
  ROTA_LISTA_ASSINATURAS,
  ROTA_LISTA_DOCUMENTACAO,
  ROTA_LISTA_PROCESSOS,
  ROTA_LISTA_TRAMITACAO,
  ROTA_MONTAR,
  filtroParaUrl,
  fmtDataHora,
  urlDoMontador,
} from "@/lib/relatorios";

/**
 * Relatórios do protocolo — o índice (decisão de 2026-11-14).
 *
 * Até o SI-34 esta página era a "gerencial": filtro no topo e quatro grupos
 * de números. Os números foram para o Painel de controle (`PanoramaDoProtocolo`),
 * que é onde o servidor olha todo dia; aqui ficam os RELATÓRIOS: cada um
 * diz a pergunta que responde e quem o usa (a lista do SI-33), e abre a sua
 * lista, com CSV e PDF e o mesmo filtro de período, unidade, tipo, assunto e
 * serviço (`FiltrosDoRelatorio`). Embaixo, os relatórios que a pessoa montou
 * e salvou (SI-35).
 *
 * Esta página não consulta número nenhum de propósito: número mora no Painel
 * e nas listas, uma vez só.
 */

interface DefRelatorio {
  id: string;
  titulo: string;
  icon: LucideIcon;
  pergunta: string;
  quemUsa: string;
  mostra: string;
  href: string;
}

const RELATORIOS_PADRAO: DefRelatorio[] = [
  {
    id: "processos",
    titulo: "Processos",
    icon: Inbox,
    pergunta: "Quantos processos entraram, estão em andamento, pararam ou foram arquivados no período — e quais são?",
    quemUsa: "Protocolo geral, chefes de unidade e secretários.",
    mostra:
      "Entrada por canal, situação de hoje, parados, prazos do serviço, sigilo e origem; agrupa por tipo, unidade, assunto ou serviço.",
    href: ROTA_LISTA_PROCESSOS,
  },
  {
    id: "tramitacao",
    titulo: "Tramitação",
    icon: AlertTriangle,
    pergunta: "Por onde cada processo passou, quanto tempo ficou em cada unidade e onde atrasou?",
    quemUsa: "Chefes de unidade, gestão e controle interno.",
    mostra: "Etapas de cada processo, permanência e atrasos por unidade; filtro “só com atraso”.",
    href: `${ROTA_LISTA_TRAMITACAO}${filtroParaUrl({ data_base: "chegada" })}`,
  },
  {
    id: "documentacao",
    titulo: "Documentação",
    icon: FileCheck,
    pergunta: "Quais processos estão com documentos pendentes, e quais complementações aguardam o cidadão?",
    quemUsa: "Atendimento, protocolo e chefias.",
    mostra: "Situação dos documentos exigidos pelo serviço e os pedidos de complementação ao cidadão.",
    href: ROTA_LISTA_DOCUMENTACAO,
  },
  {
    id: "assinaturas",
    titulo: "Assinaturas",
    icon: PenLine,
    pergunta: "Quantas assinaturas foram pedidas, concluídas e canceladas no período, e em quanto tempo?",
    quemUsa: "Chefias e gestão documental.",
    mostra: "Pedidos por solicitante e assinante, pendências e tempo do pedido à conclusão.",
    href: `${ROTA_LISTA_ASSINATURAS}${filtroParaUrl({ data_base: "pedido" })}`,
  },
];

function CartaoRelatorio({ r }: { r: DefRelatorio }) {
  const Icon = r.icon;
  return (
    <Link
      href={r.href}
      aria-label={`Abrir relatório ${r.titulo}`}
      className="group flex min-w-0 flex-col gap-3 rounded-card border border-border bg-card p-5 shadow-card transition-[box-shadow,border-color,transform] duration-fast ease-out hover:-translate-y-0.5 hover:border-border-strong hover:shadow-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring motion-reduce:transition-none motion-reduce:hover:translate-y-0"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand/10 text-brand">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h3 className="font-display text-lg font-semibold text-foreground">{r.titulo}</h3>
          <p className="text-sm text-foreground">{r.pergunta}</p>
        </div>
      </div>
      <dl className="grid gap-1 text-xs text-foreground-muted">
        <div className="flex gap-1">
          <dt className="shrink-0 font-medium">Quem usa:</dt>
          <dd>{r.quemUsa}</dd>
        </div>
        <div className="flex gap-1">
          <dt className="shrink-0 font-medium">Mostra:</dt>
          <dd>{r.mostra}</dd>
        </div>
      </dl>
      <span className="mt-auto inline-flex items-center gap-1 text-xs font-medium text-foreground-subtle transition-colors duration-fast group-hover:text-primary">
        Abrir relatório
        <ArrowRight className="h-3 w-3 transition-transform duration-fast group-hover:translate-x-0.5" aria-hidden="true" />
      </span>
    </Link>
  );
}

/**
 * Meus relatórios (SI-35): os que a pessoa montou e salvou. Só ela vê — o
 * backend devolve só os dela. Cada um tem o seu período e os seus filtros.
 */
function MeusRelatorios() {
  const q = useQuery({ queryKey: ["relatorios-salvos"], queryFn: () => api.relatorios.salvos.list() });
  return (
    <section aria-labelledby="meus-relatorios-titulo" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="meus-relatorios-titulo" className="flex items-center gap-2 font-display text-base font-semibold text-foreground">
            <Star className="h-4 w-4 text-brand" aria-hidden="true" /> Meus relatórios
          </h2>
          <p className="text-sm text-foreground-muted">
            Os que você montou e salvou, com as suas colunas e filtros. Só você vê.
          </p>
        </div>
        <Button asChild size="sm">
          <Link href={ROTA_MONTAR}>
            <Plus className="h-4 w-4" aria-hidden="true" /> Montar relatório
          </Link>
        </Button>
      </div>
      {q.isLoading ? (
        <Carregando />
      ) : q.error ? (
        <p role="alert" className="text-sm text-danger">
          Não foi possível carregar os seus relatórios.
        </p>
      ) : !q.data?.length ? (
        <p className="rounded-card border border-dashed border-border p-4 text-sm text-foreground-muted">
          Você ainda não salvou nenhum. Monte um com as colunas e os filtros que usa sempre, e ele fica aqui.
        </p>
      ) : (
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3" aria-label="Relatórios salvos">
          {q.data.map((r) => (
            <li key={r.id}>
              <Link
                href={urlDoMontador(null, r.id)}
                className="block rounded-md border border-border bg-card px-3 py-2 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="block truncate text-sm font-medium text-foreground">{r.nome}</span>
                <span className="block text-xs text-foreground-muted">alterado em {fmtDataHora(r.atualizado_em)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function RelatoriosPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        icon={BarChart3}
        title="Relatórios"
        description="Cada relatório responde a uma pergunta e abre a sua lista, com CSV e PDF e o mesmo filtro de período, unidade, tipo, assunto e serviço. Os números do dia a dia e o panorama do período ficam no Painel de controle."
        actions={
          <Button asChild variant="secondary" size="sm">
            <Link href="/m/protocolo/painel">
              <LayoutDashboard className="h-4 w-4" aria-hidden="true" /> Painel de controle
            </Link>
          </Button>
        }
      />

      <section aria-labelledby="relatorios-padrao-titulo" className="space-y-3">
        <h2 id="relatorios-padrao-titulo" className="font-display text-base font-semibold text-foreground">
          Relatórios padrão
        </h2>
        <div className="grid gap-4 lg:grid-cols-2">
          {RELATORIOS_PADRAO.map((r) => (
            <CartaoRelatorio key={r.id} r={r} />
          ))}
        </div>
      </section>

      <MeusRelatorios />
    </div>
  );
}
