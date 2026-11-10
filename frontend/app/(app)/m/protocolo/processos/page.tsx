"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, FileText, Lock, Pause, Pencil, Plus, SearchX } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ACOES_POR_CAIXA, AcoesEmLote } from "@/components/AcoesEmLote";
import { MarcadoresDaLinha } from "@/components/EtiquetaMarcador";
import { FavoritoStar } from "@/components/FavoritoStar";
import { AbasCaixas } from "@/components/protocolo/AbasCaixas";
import { ESCOPOS, FiltrosProcessos } from "@/components/protocolo/FiltrosProcessos";
import { TabelaCaixaProcessos } from "@/components/TabelaCaixaProcessos";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import type { EscopoProcesso } from "@/lib/api";
import {
  api,
  NIVEL_SIGILO_LABEL,
  type ColunaProcesso,
  type ProcessoListFilters,
} from "@/lib/api";
import { caixaDaUrl, rotuloDaCaixa } from "@/lib/caixas-processos";
import { useAssuntosAll } from "@/lib/assuntos";
import { useAuth } from "@/lib/auth";
import { decorridoDesde } from "@/lib/duracao";
import { estadoDaColuna, proximaOrdenacao, type Ordenacao } from "@/lib/ordenacao";

const PAGE_SIZE = 20;

// Filtros ↔ URL: a URL é a fonte de verdade, para que recarregar, compartilhar
// e back/forward preservem a listagem. `ativos` ausente cai no default da
// página (apenas ativos); links externos como `?id_unidade=` da home herdam
// esse default sem precisar declará-lo. Os recortes de escopo (F2) e a barra
// de busca/filtros moram em `components/protocolo/FiltrosProcessos.tsx`.

const COLUNAS: ColunaProcesso[] = [
  "numero",
  "abertura",
  "manifestante",
  "assunto",
  "local_atual",
  "responsavel",
  "parado",
];

function filtrosDaUrl(sp: URLSearchParams): ProcessoListFilters {
  const num = (k: string) => {
    const n = Number(sp.get(k));
    return Number.isFinite(n) && n > 0 ? n : undefined;
  };
  const desde = sp.get("desde");
  const ate = sp.get("ate");
  return {
    q: sp.get("q") ?? undefined,
    id_assunto: num("id_assunto"),
    id_unidade: num("id_unidade"),
    desde: desde ? `${desde}T00:00:00` : undefined,
    ate: ate ? `${ate}T23:59:59` : undefined,
    apenas_ativos: sp.has("ativos") ? sp.get("ativos") === "1" : true,
    // F2 — só aceita valor do enum. Um `escopo` inventado na URL vira
    // `undefined` (sem recorte) em vez de ir ao backend e tomar 422: a URL é
    // editável pelo usuário, e travar a tela por causa disso seria hostil.
    escopo: ESCOPOS.includes(sp.get("escopo") as EscopoProcesso)
      ? (sp.get("escopo") as EscopoProcesso)
      : undefined,
    favoritos: sp.get("favoritos") === "1" ? true : undefined,
    // E3 — ausente = exclui rascunho (default do backend). Mesmo cuidado do
    // `escopo` acima: valor fora do enum vira `undefined`, não 422.
    situacao: ["rascunho", "protocolado", "todos"].includes(sp.get("situacao") ?? "")
      ? (sp.get("situacao") as ProcessoListFilters["situacao"])
      : undefined,
    // Caixa — mesmo cuidado: valor fora da lista vira `undefined`, não 422.
    caixa: caixaDaUrl(sp.get("caixa")),
    // SI-19 — idem: coluna fora da lista é ignorada, não vai ao servidor.
    ordenar: COLUNAS.includes(sp.get("ordenar") as ColunaProcesso)
      ? (sp.get("ordenar") as ColunaProcesso)
      : undefined,
    direcao: sp.get("direcao") === "desc" ? "desc" : undefined,
  };
}

function urlDosFiltros(f: ProcessoListFilters, page: number): string {
  const sp = new URLSearchParams();
  if (f.q) sp.set("q", f.q);
  if (f.id_assunto) sp.set("id_assunto", String(f.id_assunto));
  if (f.escopo) sp.set("escopo", f.escopo);
  if (f.id_unidade) sp.set("id_unidade", String(f.id_unidade));
  if (f.desde) sp.set("desde", f.desde.slice(0, 10));
  if (f.ate) sp.set("ate", f.ate.slice(0, 10));
  sp.set("ativos", f.apenas_ativos ? "1" : "0");
  if (f.favoritos) sp.set("favoritos", "1");
  if (f.situacao) sp.set("situacao", f.situacao);
  if (f.caixa) sp.set("caixa", f.caixa);
  if (f.ordenar) {
    sp.set("ordenar", f.ordenar);
    if (f.direcao === "desc") sp.set("direcao", "desc");
  }
  if (page > 1) sp.set("page", String(page));
  return sp.toString();
}

/**
 * SI-17 — situação em um clique. Até aqui era um seletor no meio dos filtros,
 * que só valia depois de "Filtrar": na weekly ninguém achou os rascunhos.
 */
const SITUACOES: { valor: ProcessoListFilters["situacao"]; rotulo: string }[] = [
  { valor: undefined, rotulo: "Protocolados" },
  { valor: "rascunho", rotulo: "Meus rascunhos" },
  { valor: "todos", rotulo: "Todos" },
];

function fmtDate(s: string) {
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

export default function ProcessosPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const filters = useMemo(() => filtrosDaUrl(searchParams), [searchParams]);

  const { user } = useAuth();
  // Seleção para ações em lote. Vale para a página e a caixa abertas: trocar
  // de página, de caixa ou de filtro a zera, para nunca agir sobre um
  // processo que já não está na tela.
  const [selecionados, setSelecionados] = useState<Set<number>>(new Set());
  useEffect(() => {
    setSelecionados(new Set());
  }, [filters, page]);
  const comLote = !!filters.caixa && (ACOES_POR_CAIXA[filters.caixa]?.length ?? 0) > 0;

  const assuntosQ = useAssuntosAll();
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });

  const processosQ = useQuery({
    queryKey: ["processos", page, filters],
    queryFn: () =>
      api.processos.list({
        ...filters,
        // Caixa de trabalho abre pelo que espera há mais tempo; a lista geral
        // mantém a ordem de sempre (abertura, do mais novo).
        ordem: filters.caixa ? "parados" : undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  });

  function navigate(f: ProcessoListFilters, p: number) {
    const q = urlDosFiltros(f, p);
    router.push(q ? `${pathname}?${q}` : pathname, { scroll: false });
  }

  // SI-19 — a ordenação vive na URL, como os filtros: a seta de voltar e o
  // recarregar a preservam. Trocar a ordem volta para a página 1.
  const ordenacao: Ordenacao<ColunaProcesso> | undefined = filters.ordenar
    ? { campo: filters.ordenar, direcao: filters.direcao ?? "asc" }
    : undefined;
  function ordenarPor(campo: ColunaProcesso) {
    const nova = proximaOrdenacao(ordenacao, campo);
    navigate({ ...filters, ordenar: nova.campo, direcao: nova.direcao }, 1);
  }
  const colunaOrdenavel = (campo: ColunaProcesso) => ({
    sortable: true,
    sortState: estadoDaColuna(ordenacao, campo),
    onSortToggle: () => ordenarPor(campo),
  });

  function clearFilters() {
    // Limpa os filtros DENTRO da caixa aberta — sair dela é pelas abas.
    navigate({ apenas_ativos: false, caixa: filters.caixa }, 1);
  }

  const totalPages = processosQ.data
    ? Math.max(1, Math.ceil(processosQ.data.total / PAGE_SIZE))
    : 1;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={FileText}
        title={filters.caixa ? `Caixas de trabalho — ${rotuloDaCaixa(filters.caixa)}` : "Caixas de trabalho"}
        description="Escolha a caixa nas abas abaixo; filtre dentro dela e abra o processo. Tecle / para busca global."
        actions={
          <Button asChild>
            <Link href="/m/protocolo/processos/novo">
              <Plus className="h-4 w-4" aria-hidden="true" />
              Novo processo
            </Link>
          </Button>
        }
      />

      <AbasCaixas caixa={filters.caixa} />

      {/* SI-17 — a situação vale na hora, sem "Filtrar". Fora das caixas:
          dentro de uma, quem decide o recorte é a caixa. */}
      {!filters.caixa && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <div role="group" aria-label="Situação" className="inline-flex rounded-lg border border-border bg-surface-1 p-0.5">
            {SITUACOES.map((s) => {
              const ativo = filters.situacao === s.valor;
              return (
                <button
                  key={s.rotulo}
                  type="button"
                  aria-pressed={ativo}
                  onClick={() => navigate({ ...filters, situacao: s.valor }, 1)}
                  className={
                    "rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring " +
                    (ativo
                      ? "bg-brand text-primary-foreground shadow-xs"
                      : "text-foreground-muted hover:bg-muted hover:text-foreground")
                  }
                >
                  {s.rotulo}
                </button>
              );
            })}
          </div>
          <span className="text-xs text-foreground-subtle">
            Encaminhamentos recusados ficam na caixa{" "}
            <Link href="/m/protocolo/processos?caixa=recusados" className="text-brand hover:underline">
              Recusados
            </Link>
            .
          </span>
        </div>
      )}

      <FiltrosProcessos
        filtros={filters}
        aoAplicar={(f) => navigate(f, 1)}
        aoLimpar={clearFilters}
        assuntos={(assuntosQ.data ?? []).map((a) => ({ id: a.id, nome: a.assunto }))}
        unidades={(unidadesQ.data?.items ?? []).map((u) => ({ id: u.id, nome: u.unidade_trabalho }))}
        total={processosQ.data?.total}
      />

      {filters.caixa && comLote && (
        <AcoesEmLote
          caixa={filters.caixa}
          selecionados={(processosQ.data?.items ?? []).filter((p) => selecionados.has(p.id))}
          idUsuario={user?.id}
          onConcluido={() => setSelecionados(new Set())}
        />
      )}

      {filters.caixa ? (
        <TabelaCaixaProcessos
          itens={processosQ.data?.items}
          carregando={processosQ.isLoading}
          colunaOrdenavel={colunaOrdenavel}
          selecao={
            comLote
              ? {
                  ids: selecionados,
                  alternar: (id) =>
                    setSelecionados((atual) => {
                      const novo = new Set(atual);
                      if (novo.has(id)) novo.delete(id);
                      else novo.add(id);
                      return novo;
                    }),
                  alternarPagina: (marcar) =>
                    setSelecionados(
                      marcar
                        ? new Set((processosQ.data?.items ?? []).map((p) => p.id))
                        : new Set(),
                    ),
                }
              : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH {...colunaOrdenavel("numero")}>Número</TH>
              <TH {...colunaOrdenavel("abertura")}>Aberto em</TH>
              <TH {...colunaOrdenavel("manifestante")}>Manifestante</TH>
              <TH {...colunaOrdenavel("assunto")}>Assunto</TH>
              <TH {...colunaOrdenavel("local_atual")}>Local atual</TH>
              <TH {...colunaOrdenavel("responsavel")}>Responsável</TH>
              <TH>Status</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {processosQ.isLoading &&
              Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} cols={7} />)}
            {!processosQ.isLoading && (processosQ.data?.items.length ?? 0) === 0 && (
              <TR>
                <TD colSpan={8} className="p-0">
                  <EmptyState
                    icon={SearchX}
                    title={filters.caixa ? "Nenhum processo nesta caixa" : "Nenhum processo encontrado"}
                    description={
                      filters.caixa
                        ? "Quando houver, eles aparecem aqui."
                        : "Ajuste os filtros ou crie um novo processo."
                    }
                    className="border-0 bg-transparent"
                  />
                </TD>
              </TR>
            )}
            {processosQ.data?.items.map((p) => (
              <TR key={p.id}>
                <TD className="font-mono text-xs tabular-nums">
                  <div className="flex items-center gap-1">
                    <FavoritoStar processo={p} size="sm" />
                    {/* O número é link para o processo, em text-primary como nas
                        outras tabelas (antes só o "Abrir" da ponta levava). */}
                    <Link
                      href={`/m/protocolo/processos/${p.id}`}
                      className="rounded text-primary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {p.situacao === "rascunho" ? (
                        <span className="font-sans italic text-muted-foreground">
                          Rascunho
                        </span>
                      ) : p.nup ? (
                        <>
                          <div>{p.nup}</div>
                          <div className="text-[10px] text-foreground-muted">
                            {p.numero_processo}
                          </div>
                        </>
                      ) : (
                        p.numero_processo
                      )}
                    </Link>
                  </div>
                  <MarcadoresDaLinha marcadores={p.marcadores} />
                </TD>
                <TD className="text-xs tabular-nums">
                  {fmtDate(p.data_hora_abertura)}
                  {/* F1 — a data sozinha obriga quem lê a fazer a conta de
                      cabeça para saber se o processo é de ontem ou do ano
                      passado. O decorrido é calculado no cliente: a lista não
                      carrega o bloco de permanência, que só existe no detalhe. */}
                  <span className="block text-muted-foreground">
                    {decorridoDesde(p.data_hora_abertura)}
                  </span>
                </TD>
                <TD>
                  <div className="text-sm text-foreground">{p.manifestante ?? "—"}</div>
                  <div className="text-xs text-muted-foreground">
                    {p.manifestante_cpf_cnpj ?? ""}
                  </div>
                </TD>
                <TD>
                  <div className="line-clamp-1 text-sm">{p.assunto ?? "—"}</div>
                  <div className="text-xs text-muted-foreground">{p.tipo_processo ?? ""}</div>
                </TD>
                <TD className="text-sm">{p.local_atual ?? "—"}</TD>
                <TD className="text-sm">
                  {p.responsavel ?? (
                    // Não é "—": sem responsável é um ESTADO, e a tela tem de
                    // dizer qual. Travessão leria como "dado faltando".
                    <span className="text-warning-soft-foreground">
                      Sem responsável
                    </span>
                  )}
                </TD>
                <TD>
                  <div className="flex flex-wrap gap-1">
                    {p.situacao === "rascunho" && (
                      <Badge intent="warning" icon={Pencil}>
                        Rascunho
                      </Badge>
                    )}
                    {p.ativo ? (
                      <Badge intent="success" icon={CheckCircle2}>
                        Ativo
                      </Badge>
                    ) : (
                      <Badge intent="neutral" icon={Pause}>
                        Inativo
                      </Badge>
                    )}
                    {!p.publico && (
                      <Badge intent="warning" icon={Lock}>
                        {NIVEL_SIGILO_LABEL[p.nivel_sigilo]}
                      </Badge>
                    )}
                  </div>
                </TD>
                <TD className="text-right">
                  <Link
                    href={`/m/protocolo/processos/${p.id}`}
                    className="inline-flex h-9 items-center rounded-md border border-transparent px-3 text-xs font-medium text-primary transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    Abrir →
                  </Link>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      {processosQ.data && processosQ.data.total > 0 && (
        <div className="flex flex-col items-start justify-between gap-2 text-sm text-muted-foreground sm:flex-row sm:items-center">
          <span className="tabular-nums">
            {processosQ.data.total} processos — página {page} de {totalPages}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={page === 1}
              onClick={() => navigate(filters, page - 1)}
            >
              Anterior
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => navigate(filters, page + 1)}
            >
              Próxima
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
