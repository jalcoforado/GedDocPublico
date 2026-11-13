"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Download, FileText, Lock, Pencil, Save, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useOpcoesDoRecorte } from "@/components/relatorios/opcoesDoRecorte";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Carregando } from "@/components/ui/carregando";
import { Checkbox } from "@/components/ui/checkbox";
import { Combobox } from "@/components/ui/combobox";
import { useConfirm, usePrompt } from "@/components/ui/confirm";
import { Input } from "@/components/ui/input";
import { KpiCard } from "@/components/ui/kpi-card";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import {
  NIVEL_SIGILO_LABEL,
  api,
  montadoCsvUrl,
  montadoPdfUrl,
  type AgruparPorMontado,
  type CatalogoMontado,
  type ColunaMontado,
  type DefinicaoMontado,
  type FiltrosMontado,
  type ModoUnidadeRelatorio,
  type OrdemMontado,
  type PeriodoMontado,
  type ResultadoMontado,
  type SituacaoRelatorio,
  type StatusDocFiltroMontado,
  type StatusPrazoRelatorio,
  type TipoPeriodoMontado,
} from "@/lib/api";
import {
  ROTA_RELATORIOS,
  ROTULO_MODO_UNIDADE,
  ROTULO_PRAZO,
  ROTULO_SITUACAO,
  ROTULO_TIPO_PERIODO,
  definicaoDaUrl,
  definicaoInicial,
  fmtValorMontado,
  urlDoMontador,
} from "@/lib/relatorios";

/**
 * Montar relatório (SI-35) — a pessoa escolhe colunas e filtros, vê o
 * resultado e salva o "seu" relatório para abrir de novo.
 *
 * O que está APLICADO mora na URL (`?d=` com a definição, `?salvo=` com o
 * relatório salvo): voltar do navegador e recarregar funcionam, e o CSV e o
 * PDF são links comuns com a mesma definição. O formulário edita um rascunho
 * e só aplica no "Gerar relatório".
 *
 * Quem decide o que a pessoa vê é o backend: o resultado roda com o sigilo de
 * quem abre, na hora em que abre — o salvo guarda a definição, não os dados.
 */

const ROTULO_DOC: Record<StatusDocFiltroMontado, string> = {
  pendente: "Pendentes",
  parcial: "Parciais",
  completo: "Completos",
  sem_documentos_exigidos: "Sem documento exigido",
};

function inteiro(v: string | null): number | null {
  return v && /^\d+$/.test(v) ? Number(v) : null;
}

/** O que impede de gerar, em texto, ou null. */
function problemaDe(d: DefinicaoMontado): string | null {
  if (!d.colunas.length) return "Escolha pelo menos uma coluna.";
  const p = d.periodo;
  if (p?.tipo === "fixo") {
    if (!p.desde && !p.ate) return "Informe a data inicial ou a final do período.";
    if (p.desde && p.ate && p.desde > p.ate) return "A data inicial do período é posterior à final.";
  }
  if (p?.tipo === "ultimos_dias" && !(p.dias && p.dias >= 1)) return "Informe quantos dias.";
  return null;
}

/** Tira o que não vale para o tipo de período e campos vazios — a URL e o
 * salvo ficam com só o que a pessoa escolheu. */
function limpar(d: DefinicaoMontado): DefinicaoMontado {
  const p = d.periodo ?? { tipo: "sem" };
  const periodo: PeriodoMontado =
    p.tipo === "fixo"
      ? { tipo: "fixo", desde: p.desde || null, ate: p.ate || null }
      : p.tipo === "ultimos_dias"
        ? { tipo: "ultimos_dias", dias: p.dias ?? null }
        : { tipo: p.tipo };
  const filtros = Object.fromEntries(
    Object.entries(d.filtros ?? {}).filter(([, v]) => v !== null && v !== undefined && v !== "" && v !== false),
  ) as FiltrosMontado;
  if (!filtros.id_unidade) delete filtros.modo_unidade;
  return {
    colunas: d.colunas,
    filtros,
    periodo,
    agrupar_por: d.agrupar_por ?? null,
    ordem: d.ordem ?? null,
    ordem_desc: d.ordem_desc ?? true,
  };
}

export default function MontarRelatorioPage() {
  const router = useRouter();
  const sp = useSearchParams();
  const chaveD = sp.get("d");
  const idSalvo = inteiro(sp.get("salvo"));
  const aplicada = useMemo(() => definicaoDaUrl(new URLSearchParams(chaveD ? { d: chaveD } : {})), [chaveD]);
  const toast = useToast();
  const prompt = usePrompt();
  const confirm = useConfirm();
  const qc = useQueryClient();

  const catalogoQ = useQuery({ queryKey: ["montado-catalogo"], queryFn: () => api.relatorios.montadoCatalogo() });
  const salvoQ = useQuery({
    queryKey: ["relatorio-salvo", idSalvo],
    queryFn: () => api.relatorios.salvos.get(idSalvo as number),
    enabled: !!idSalvo,
    retry: false,
  });

  const [rascunho, setRascunho] = useState<DefinicaoMontado>(() => aplicada ?? definicaoInicial());
  // URL mudou por fora (voltar, link colado): o rascunho segue o aplicado.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (aplicada) setRascunho(aplicada); }, [chaveD]);
  // Abriu um salvo sem definição na URL: aplica a do salvo.
  useEffect(() => {
    if (salvoQ.data && !chaveD) router.replace(urlDoMontador(salvoQ.data.definicao, salvoQ.data.id), { scroll: false });
  }, [salvoQ.data, chaveD, router]);

  const resultadoQ = useQuery({
    queryKey: ["relatorio-montado", chaveD],
    queryFn: () => api.relatorios.montado(aplicada as DefinicaoMontado),
    enabled: !!aplicada,
    retry: false,
  });

  const limpo = limpar(rascunho);
  const problema = problemaDe(limpo);
  const pendente = !!aplicada && JSON.stringify(limpo) !== JSON.stringify(limpar(aplicada));
  const nomeSalvo = salvoQ.data?.nome;

  function aplicar(d: DefinicaoMontado, salvo: number | null = idSalvo) {
    router.replace(urlDoMontador(limpar(d), salvo), { scroll: false });
  }

  const salvarNovo = useMutation({
    mutationFn: (nome: string) => api.relatorios.salvos.create({ nome, definicao: limpo }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["relatorios-salvos"] });
      qc.setQueryData(["relatorio-salvo", r.id], r);
      toast.success(`Relatório "${r.nome}" salvo.`);
      aplicar(limpo, r.id);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Não foi possível salvar."),
  });
  const salvarAlteracoes = useMutation({
    mutationFn: (body: { nome?: string; definicao?: DefinicaoMontado }) =>
      api.relatorios.salvos.update(idSalvo as number, body),
    onSuccess: (r, body) => {
      qc.invalidateQueries({ queryKey: ["relatorios-salvos"] });
      qc.setQueryData(["relatorio-salvo", r.id], r);
      toast.success(body.nome ? `Renomeado para "${r.nome}".` : "Alterações salvas.");
      if (body.definicao) aplicar(body.definicao);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Não foi possível salvar."),
  });

  async function pedirNome(titulo: string, inicial = ""): Promise<string | null> {
    const nome = await prompt({
      title: titulo,
      label: "Nome do relatório",
      defaultValue: inicial,
      placeholder: "Ex.: Alvarás parados da minha unidade",
      confirmLabel: "Salvar",
      required: true,
    });
    return nome?.trim() ? nome.trim() : null;
  }

  async function excluir() {
    if (!idSalvo) return;
    const ok = await confirm({
      title: "Excluir relatório",
      message: `O relatório "${nomeSalvo}" sai dos seus relatórios. Os processos não mudam.`,
      confirmLabel: "Excluir",
      intent: "danger",
    }).catch(() => false);
    if (!ok) return;
    try {
      await api.relatorios.salvos.remove(idSalvo);
      qc.invalidateQueries({ queryKey: ["relatorios-salvos"] });
      toast.success("Relatório excluído.");
      router.push(ROTA_RELATORIOS);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Não foi possível excluir.");
    }
  }

  const exportavel = aplicada && !pendente ? limpar(aplicada) : null;
  const linkClasse =
    "inline-flex h-9 items-center gap-1.5 rounded-md px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[{ label: "Relatórios", href: ROTA_RELATORIOS }, { label: nomeSalvo ?? "Montar relatório" }]}
        title={nomeSalvo ?? "Montar relatório"}
        description="Escolha as colunas e os filtros, gere o resultado e salve para abrir de novo. Só você vê os relatórios que salvar."
        actions={
          <div className="flex flex-wrap gap-2">
            {exportavel ? (
              <>
                <a href={montadoCsvUrl(exportavel)} target="_blank" rel="noreferrer"
                  className={`${linkClasse} bg-muted text-foreground hover:bg-muted/70`}>
                  <Download className="h-4 w-4" aria-hidden="true" /> CSV
                </a>
                <a href={montadoPdfUrl(exportavel, nomeSalvo)} target="_blank" rel="noreferrer"
                  className={`${linkClasse} bg-muted text-foreground hover:bg-muted/70`}>
                  <FileText className="h-4 w-4" aria-hidden="true" /> PDF
                </a>
              </>
            ) : null}
            {idSalvo && salvoQ.data ? (
              <>
                <Button
                  size="sm"
                  disabled={!!problema || salvarAlteracoes.isPending}
                  onClick={() => salvarAlteracoes.mutate({ definicao: limpo })}
                >
                  <Save className="h-4 w-4" aria-hidden="true" /> Salvar alterações
                </Button>
                <Button size="sm" variant="secondary" disabled={!!problema || salvarNovo.isPending}
                  onClick={async () => { const n = await pedirNome("Salvar como novo relatório", `${nomeSalvo} (cópia)`); if (n) salvarNovo.mutate(n); }}>
                  Salvar como…
                </Button>
                <Button size="sm" variant="ghost" aria-label="Renomear"
                  onClick={async () => { const n = await pedirNome("Renomear relatório", nomeSalvo); if (n && n !== nomeSalvo) salvarAlteracoes.mutate({ nome: n }); }}>
                  <Pencil className="h-4 w-4" aria-hidden="true" />
                </Button>
                <Button size="sm" variant="ghost" aria-label="Excluir relatório" onClick={excluir}>
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </Button>
              </>
            ) : (
              <Button size="sm" disabled={!!problema || salvarNovo.isPending}
                onClick={async () => { const n = await pedirNome("Salvar relatório"); if (n) salvarNovo.mutate(n); }}>
                <Save className="h-4 w-4" aria-hidden="true" /> Salvar relatório
              </Button>
            )}
          </div>
        }
      />

      {salvoQ.error && (
        <Alert intent="danger" title="Não foi possível abrir o relatório salvo">
          {salvoQ.error instanceof Error ? salvoQ.error.message : "Relatório não encontrado."}{" "}
          <Link href={ROTA_RELATORIOS} className="underline">Voltar aos relatórios</Link>
        </Alert>
      )}
      {salvoQ.data?.avisos?.length ? (
        <Alert intent="warning" title="O relatório salvo mudou">
          <ul className="list-disc pl-4">{salvoQ.data.avisos.map((a) => <li key={a}>{a}</li>)}</ul>
        </Alert>
      ) : null}

      <form
        aria-label="Montar relatório"
        className="space-y-4"
        onSubmit={(e) => { e.preventDefault(); if (!problema) aplicar(rascunho); }}
      >
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <SecaoRecorte d={rascunho} onChange={setRascunho} />
          <SecaoFiltros d={rascunho} onChange={setRascunho} />
        </div>
        {catalogoQ.data ? (
          <SecaoColunas d={rascunho} onChange={setRascunho} catalogo={catalogoQ.data} />
        ) : (
          <Carregando />
        )}
        <div className="flex flex-wrap items-center justify-end gap-3">
          {problema ? (
            <p role="alert" className="text-sm text-danger">{problema}</p>
          ) : pendente ? (
            <p className="text-sm text-foreground-muted">Há mudanças ainda não aplicadas ao resultado.</p>
          ) : null}
          <Button type="button" variant="secondary" onClick={() => setRascunho(aplicada ?? definicaoInicial())}>
            Desfazer mudanças
          </Button>
          <Button type="submit" disabled={!!problema}>Gerar relatório</Button>
        </div>
      </form>

      {resultadoQ.isLoading && <Carregando />}
      {resultadoQ.error && (
        <Alert intent="danger" title="Não foi possível gerar o relatório">
          {resultadoQ.error instanceof Error ? resultadoQ.error.message : "Erro ao gerar."}
        </Alert>
      )}
      {resultadoQ.data && <Resultado r={resultadoQ.data} />}
    </div>
  );
}

// ------------------------------------------------------------- seções

type Edita = { d: DefinicaoMontado; onChange: (d: DefinicaoMontado) => void };

function SecaoRecorte({ d, onChange }: Edita) {
  const f = d.filtros ?? {};
  const p = d.periodo ?? { tipo: "sem" };
  const op = useOpcoesDoRecorte(f.id_tipo_processo);
  const setF = (patch: Partial<FiltrosMontado>) => onChange({ ...d, filtros: { ...f, ...patch } });
  const setP = (patch: Partial<PeriodoMontado>) => onChange({ ...d, periodo: { ...p, ...patch } });
  const num = (v: number | string | null) => (typeof v === "number" ? v : null);

  return (
    <Card>
      <CardHeader><CardTitle>Período e recorte</CardTitle></CardHeader>
      <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div>
          <Label htmlFor="mon-periodo">Período</Label>
          <Select id="mon-periodo" value={p.tipo}
            onChange={(e) => onChange({ ...d, periodo: { tipo: e.target.value as TipoPeriodoMontado, dias: 30 } })}>
            {(Object.keys(ROTULO_TIPO_PERIODO) as TipoPeriodoMontado[]).map((t) => (
              <option key={t} value={t}>{ROTULO_TIPO_PERIODO[t]}</option>
            ))}
          </Select>
          <p className="mt-1 text-xs text-foreground-muted">
            {p.tipo === "fixo" || p.tipo === "sem"
              ? "O mesmo período toda vez que abrir."
              : "Relativo: recalculado no dia em que o relatório abre."}
          </p>
        </div>
        <div>
          <Label htmlFor="mon-data-base">Contar pela data de</Label>
          <Select id="mon-data-base" value={f.data_base ?? "abertura"}
            onChange={(e) => setF({ data_base: e.target.value as "abertura" | "arquivamento" })}>
            <option value="abertura">abertura</option>
            <option value="arquivamento">arquivamento</option>
          </Select>
        </div>
        {p.tipo === "fixo" && (
          <>
            <div>
              <Label htmlFor="mon-desde">De</Label>
              <Input id="mon-desde" type="date" value={p.desde ?? ""} onChange={(e) => setP({ desde: e.target.value || null })} />
            </div>
            <div>
              <Label htmlFor="mon-ate">Até</Label>
              <Input id="mon-ate" type="date" value={p.ate ?? ""} onChange={(e) => setP({ ate: e.target.value || null })} />
            </div>
          </>
        )}
        {p.tipo === "ultimos_dias" && (
          <div>
            <Label htmlFor="mon-dias">Quantos dias</Label>
            <Input id="mon-dias" type="number" min={1} max={3650} inputMode="numeric" value={p.dias ?? ""}
              onChange={(e) => setP({ dias: e.target.value ? Number(e.target.value) : null })} />
          </div>
        )}
        <div className="md:col-span-2">
          <Label htmlFor="mon-unidade">Unidade</Label>
          <Combobox id="mon-unidade" options={op.unidades} value={f.id_unidade ?? null}
            onChange={(v) => setF({ id_unidade: num(v) })} placeholder="Todas as unidades"
            searchPlaceholder="Nome ou sigla da unidade…" loading={op.carregando.unidades} />
        </div>
        {f.id_unidade ? (
          <div className="md:col-span-2">
            <Label htmlFor="mon-modo">Contar processos da unidade que é</Label>
            <Select id="mon-modo" value={f.modo_unidade ?? "envolvida"}
              onChange={(e) => setF({ modo_unidade: e.target.value as ModoUnidadeRelatorio })}>
              {(Object.keys(ROTULO_MODO_UNIDADE) as ModoUnidadeRelatorio[]).map((m) => (
                <option key={m} value={m}>{ROTULO_MODO_UNIDADE[m]}</option>
              ))}
            </Select>
          </div>
        ) : null}
        <div>
          <Label htmlFor="mon-tipo">Tipo de processo</Label>
          <Combobox id="mon-tipo" options={op.tipos} value={f.id_tipo_processo ?? null}
            onChange={(v) => {
              const id = num(v) ?? undefined;
              setF({ id_tipo_processo: id ?? null, id_assunto: op.assuntoCombina(f.id_assunto, id) ? f.id_assunto : null });
            }}
            placeholder="Todos" loading={op.carregando.tipos} />
        </div>
        <div>
          <Label htmlFor="mon-assunto">Assunto</Label>
          <Combobox id="mon-assunto" options={op.assuntos} value={f.id_assunto ?? null}
            onChange={(v) => setF({ id_assunto: num(v) })} placeholder="Todos" loading={op.carregando.assuntos} />
        </div>
        <div className="md:col-span-2">
          <Label htmlFor="mon-servico">Serviço</Label>
          <Combobox id="mon-servico" options={op.servicos} value={f.id_servico ?? null}
            onChange={(v) => setF({ id_servico: num(v) })} placeholder="Todos"
            searchPlaceholder="Nome do serviço…" loading={op.carregando.servicos} />
        </div>
      </CardContent>
    </Card>
  );
}

function SecaoFiltros({ d, onChange }: Edita) {
  const f = d.filtros ?? {};
  const setF = (patch: Partial<FiltrosMontado>) => onChange({ ...d, filtros: { ...f, ...patch } });
  return (
    <Card>
      <CardHeader><CardTitle>Filtros</CardTitle></CardHeader>
      <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div>
          <Label htmlFor="mon-situacao">Situação hoje</Label>
          <Select id="mon-situacao" value={f.situacao ?? ""}
            onChange={(e) => setF({ situacao: (e.target.value || null) as SituacaoRelatorio | null })}>
            <option value="">Todas</option>
            {(Object.keys(ROTULO_SITUACAO) as SituacaoRelatorio[]).map((s) => (
              <option key={s} value={s}>{ROTULO_SITUACAO[s]}</option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="mon-prazo">Prazo do serviço</Label>
          <Select id="mon-prazo" value={f.prazo ?? ""}
            onChange={(e) => setF({ prazo: (e.target.value || null) as StatusPrazoRelatorio | null })}>
            <option value="">Todos</option>
            {(Object.keys(ROTULO_PRAZO) as StatusPrazoRelatorio[]).map((s) => (
              <option key={s} value={s}>{ROTULO_PRAZO[s]}</option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="mon-sigilo">Sigilo</Label>
          <Select id="mon-sigilo" value={f.sigilo ?? ""}
            onChange={(e) => setF({ sigilo: (e.target.value || null) as FiltrosMontado["sigilo"] })}>
            <option value="">Todos que você pode ver</option>
            <option value="ostensivo">Só ostensivos (públicos)</option>
            <option value="sigiloso">Só sigilosos</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="mon-origem">Origem</Label>
          <Select id="mon-origem" value={f.origem ?? ""}
            onChange={(e) => setF({ origem: (e.target.value || null) as FiltrosMontado["origem"] })}>
            <option value="">Internos e externos</option>
            <option value="interna">Só internos</option>
            <option value="externa">Só externos</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="mon-doc">Documentos exigidos</Label>
          <Select id="mon-doc" value={f.documentacao ?? ""}
            onChange={(e) => setF({ documentacao: (e.target.value || null) as StatusDocFiltroMontado | null })}>
            <option value="">Todos</option>
            {(Object.keys(ROTULO_DOC) as StatusDocFiltroMontado[]).map((s) => (
              <option key={s} value={s}>{ROTULO_DOC[s]}</option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="mon-parado">Parados há pelo menos (dias)</Label>
          <Input id="mon-parado" type="number" min={1} max={3650} inputMode="numeric" value={f.parado_ha_dias ?? ""}
            placeholder="Qualquer"
            onChange={(e) => setF({ parado_ha_dias: e.target.value ? Number(e.target.value) : null })} />
        </div>
        <fieldset className="space-y-2 md:col-span-2">
          <legend className="text-sm font-medium text-foreground">Só processos</legend>
          {([
            ["complementacao_aberta", "com complementação aguardando o cidadão"],
            ["com_atraso", "com etapa atrasada na tramitação"],
            ["assinatura_pendente", "com assinatura pendente"],
          ] as const).map(([chave, rotulo]) => (
            <label key={chave} className="flex items-center gap-2 text-sm">
              <Checkbox checked={!!f[chave]} onChange={(e) => setF({ [chave]: e.target.checked })} />
              {rotulo}
            </label>
          ))}
        </fieldset>
      </CardContent>
    </Card>
  );
}

function SecaoColunas({ d, onChange, catalogo }: Edita & { catalogo: CatalogoMontado }) {
  const info = useMemo(() => new Map(catalogo.colunas.map((c) => [c.chave, c])), [catalogo]);
  const grupos = [...new Set(catalogo.colunas.map((c) => c.grupo))];
  const escolhidas = d.colunas;
  const cheio = escolhidas.length >= catalogo.max_colunas;

  function alternar(c: ColunaMontado, marcar: boolean) {
    onChange({ ...d, colunas: marcar ? [...escolhidas, c] : escolhidas.filter((x) => x !== c) });
  }
  function mover(i: number, delta: number) {
    const novo = [...escolhidas];
    const [c] = novo.splice(i, 1);
    novo.splice(i + delta, 0, c);
    onChange({ ...d, colunas: novo });
  }

  return (
    <Card>
      <CardHeader><CardTitle>Colunas, ordem e agrupamento</CardTitle></CardHeader>
      <CardContent className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {grupos.map((g) => (
            <fieldset key={g} className="space-y-1.5">
              <legend className="mb-1 text-sm font-semibold text-foreground">{g}</legend>
              {catalogo.colunas.filter((c) => c.grupo === g).map((c) => {
                const marcada = escolhidas.includes(c.chave);
                return (
                  <label key={c.chave} className="flex items-center gap-2 text-sm">
                    <Checkbox checked={marcada} disabled={!marcada && cheio}
                      onChange={(e) => alternar(c.chave, e.target.checked)} />
                    {c.rotulo}
                  </label>
                );
              })}
            </fieldset>
          ))}
        </div>
        <div className="space-y-4">
          <div>
            <p className="text-sm font-semibold text-foreground">Na ordem do relatório</p>
            <p className="text-xs text-foreground-muted">O número do processo vem sempre primeiro.</p>
            <ol className="mt-2 space-y-1" aria-label="Colunas escolhidas">
              {escolhidas.map((c, i) => (
                <li key={c} className="flex items-center justify-between gap-2 rounded-md border border-border py-0.5 pl-2 pr-1 text-sm">
                  <span>{info.get(c)?.rotulo ?? c}</span>
                  <span className="flex gap-0.5">
                    <Button type="button" size="icon" variant="ghost" className="h-7 w-7" aria-label={`Subir ${info.get(c)?.rotulo}`}
                      disabled={i === 0} onClick={() => mover(i, -1)}><ArrowUp className="h-4 w-4" /></Button>
                    <Button type="button" size="icon" variant="ghost" className="h-7 w-7" aria-label={`Descer ${info.get(c)?.rotulo}`}
                      disabled={i === escolhidas.length - 1} onClick={() => mover(i, 1)}><ArrowDown className="h-4 w-4" /></Button>
                    <Button type="button" size="icon" variant="ghost" className="h-7 w-7" aria-label={`Tirar ${info.get(c)?.rotulo}`}
                      onClick={() => alternar(c, false)}><X className="h-4 w-4" /></Button>
                  </span>
                </li>
              ))}
            </ol>
          </div>
          <div>
            <Label htmlFor="mon-ordem">Ordenar por</Label>
            <div className="flex gap-2">
              <Select id="mon-ordem" value={d.ordem ?? ""}
                onChange={(e) => onChange({ ...d, ordem: (e.target.value || null) as OrdemMontado | null })}>
                <option value="">Data do período (mais recente primeiro)</option>
                {(Object.entries(catalogo.ordens) as [OrdemMontado, string][]).map(([k, r]) => (
                  <option key={k} value={k}>{r}</option>
                ))}
              </Select>
              {d.ordem ? (
                <Select aria-label="Direção da ordem" className="w-36" value={d.ordem_desc === false ? "asc" : "desc"}
                  onChange={(e) => onChange({ ...d, ordem_desc: e.target.value === "desc" })}>
                  <option value="desc">decrescente</option>
                  <option value="asc">crescente</option>
                </Select>
              ) : null}
            </div>
          </div>
          <div>
            <Label htmlFor="mon-agrupar">Agrupar por</Label>
            <Select id="mon-agrupar" value={d.agrupar_por ?? ""}
              onChange={(e) => onChange({ ...d, agrupar_por: (e.target.value || null) as AgruparPorMontado | null })}>
              <option value="">Não agrupar</option>
              {(Object.entries(catalogo.agrupamentos) as [AgruparPorMontado, string][]).map(([k, r]) => (
                <option key={k} value={k}>{r}</option>
              ))}
            </Select>
            <p className="mt-1 text-xs text-foreground-muted">Mostra quantos processos há em cada um, acima da lista.</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function Resultado({ r }: { r: ResultadoMontado }) {
  return (
    <section aria-label="Resultado" className="space-y-4">
      {r.avisos.length ? (
        <Alert intent="warning"><ul className="list-disc pl-4">{r.avisos.map((a) => <li key={a}>{a}</li>)}</ul></Alert>
      ) : null}
      <ul className="space-y-0.5 text-xs text-foreground-muted" aria-label="Recorte do relatório">
        {r.descricao_filtros.map((l) => <li key={l}>{l}</li>)}
      </ul>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiCard label="Processos" value={r.totais.total} />
        <KpiCard label="Em andamento" value={r.totais.em_andamento} />
        <KpiCard label="Em trânsito" value={r.totais.em_transito} />
        <KpiCard label="Arquivados" value={r.totais.arquivados} />
      </div>

      {r.agrupamento && (
        <Card>
          <CardHeader><CardTitle>Por {r.rotulo_agrupamento?.toLowerCase()}</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <THead><TR><TH>{r.rotulo_agrupamento}</TH><TH className="w-28 text-right">Processos</TH><TH className="w-20 text-right">%</TH></TR></THead>
              <TBody>
                {r.agrupamento.map((g) => (
                  <TR key={g.label}>
                    <TD>{g.label}</TD>
                    <TD className="text-right tabular-nums">{g.count}</TD>
                    <TD className="text-right tabular-nums">{g.pct.toLocaleString("pt-BR")}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>
            {r.cortado ? `Processos (os ${r.linhas.length} primeiros de ${r.totais.total})` : `Processos (${r.linhas.length})`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {r.cortado && (
            <p className="mb-3 text-sm text-foreground-muted">
              A lista na tela tem limite; os totais acima contam o recorte inteiro. Para todos, use o CSV.
            </p>
          )}
          <Table>
            <THead>
              <TR>
                <TH>Número</TH>
                {r.colunas.map((c) => (
                  <TH key={c.chave} className={"whitespace-nowrap" + (c.tipo === "numero" ? " text-right" : "")}>{c.rotulo}</TH>
                ))}
              </TR>
            </THead>
            <TBody>
              {r.linhas.length === 0 && (
                <TR><TD colSpan={r.colunas.length + 1} className="text-center text-foreground-muted">Nenhum processo no recorte.</TD></TR>
              )}
              {r.linhas.map((ln) => (
                <TR key={ln.id}>
                  <TD>
                    <div className="flex flex-wrap items-center gap-1">
                      <Link href={`/m/protocolo/processos/${ln.id}`} className="whitespace-nowrap font-mono text-xs text-primary hover:underline">
                        {ln.numero_processo}
                      </Link>
                      {ln.nivel_sigilo !== "ostensivo" && (
                        <Badge intent="warning" icon={Lock}>{NIVEL_SIGILO_LABEL[ln.nivel_sigilo]}</Badge>
                      )}
                    </div>
                  </TD>
                  {r.colunas.map((c) => (
                    <TD key={c.chave} className={c.tipo === "texto" ? "whitespace-nowrap text-sm" : "whitespace-nowrap text-xs tabular-nums" + (c.tipo === "numero" ? " text-right" : "")}>
                      {fmtValorMontado(ln.valores[c.chave], c.tipo)}
                    </TD>
                  ))}
                </TR>
              ))}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </section>
  );
}
