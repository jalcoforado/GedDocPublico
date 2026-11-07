"use client";

import { ChevronDown, Search, SlidersHorizontal, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import type { EscopoProcesso, ProcessoListFilters } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Busca e filtros da tela de Processos, no formato de barra: busca larga +
 * botão "Filtros" que abre o resto + chips do que está valendo.
 *
 * Antes era um cartão com oito controles sempre abertos, que empurrava a
 * lista para baixo da dobra (a 1280px a primeira linha da tabela caía perto
 * dos 560px) para servir, na maior parte das vezes, só à busca. O formato
 * veio da referência de mercado (SUITE/CE): a busca fica à mão, o resto sob
 * demanda, e os chips dizem por que a lista mostra o que mostra — inclusive o
 * "Só ativos", que é o padrão da tela e antes não aparecia em lugar nenhum.
 *
 * A URL continua sendo a fonte de verdade: este componente só monta o
 * rascunho e chama `aoAplicar`; a página serializa.
 */

export const ESCOPOS: EscopoProcesso[] = ["meus", "unidade", "unidade_e_subordinadas"];

export const ESCOPO_LABEL: Record<EscopoProcesso, string> = {
  meus: "Meus",
  unidade: "Da minha unidade",
  unidade_e_subordinadas: "Unidade e subordinadas",
};

interface Opcao {
  id: number;
  nome: string;
}

interface Props {
  filtros: ProcessoListFilters;
  aoAplicar: (f: ProcessoListFilters) => void;
  /** Limpa tudo, menos a caixa aberta — sair dela é pelas abas. */
  aoLimpar: () => void;
  assuntos: Opcao[];
  unidades: Opcao[];
  /** Total da lista com os filtros valendo; `undefined` enquanto carrega. */
  total: number | undefined;
}

function dataBr(iso: string | undefined): string {
  if (!iso) return "";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

/** Quantos filtros do painel "Filtros" estão valendo (o badge do botão). */
export function contarAvancados(f: ProcessoListFilters): number {
  return [f.id_assunto, f.id_unidade, f.desde, f.ate, f.favoritos].filter(Boolean).length;
}

export function FiltrosProcessos({ filtros, aoAplicar, aoLimpar, assuntos, unidades, total }: Props) {
  const [draft, setDraft] = useState<ProcessoListFilters>(filtros);
  const [aberto, setAberto] = useState(false);
  // Reaproxima o rascunho do que a URL diz (back/forward, chip removido).
  useEffect(() => {
    setDraft(filtros);
  }, [filtros]);

  const nAvancados = contarAvancados(filtros);

  function aplicar(e?: React.FormEvent) {
    e?.preventDefault();
    aoAplicar({ ...draft, apenas_ativos: draft.apenas_ativos ?? false });
  }

  const nomeAssunto = assuntos.find((a) => a.id === filtros.id_assunto)?.nome;
  const nomeUnidade = unidades.find((u) => u.id === filtros.id_unidade)?.nome;

  // Chips do que está valendo, cada um removível. A ordem segue a da leitura:
  // primeiro o que o usuário digitou, depois os recortes.
  const chips: { chave: string; rotulo: string; remover: ProcessoListFilters }[] = [];
  if (filtros.q) chips.push({ chave: "q", rotulo: `“${filtros.q}”`, remover: { ...filtros, q: undefined } });
  if (filtros.id_assunto)
    chips.push({
      chave: "assunto",
      rotulo: `Assunto: ${nomeAssunto ?? `#${filtros.id_assunto}`}`,
      remover: { ...filtros, id_assunto: undefined },
    });
  if (filtros.id_unidade)
    chips.push({
      chave: "unidade",
      rotulo: `Unidade: ${nomeUnidade ?? `#${filtros.id_unidade}`}`,
      remover: { ...filtros, id_unidade: undefined },
    });
  if (filtros.desde)
    chips.push({ chave: "desde", rotulo: `Aberto desde ${dataBr(filtros.desde)}`, remover: { ...filtros, desde: undefined } });
  if (filtros.ate)
    chips.push({ chave: "ate", rotulo: `Aberto até ${dataBr(filtros.ate)}`, remover: { ...filtros, ate: undefined } });
  if (filtros.situacao === "rascunho")
    chips.push({ chave: "situacao", rotulo: "Só rascunhos", remover: { ...filtros, situacao: undefined } });
  if (filtros.situacao === "todos")
    chips.push({ chave: "situacao", rotulo: "Com rascunhos", remover: { ...filtros, situacao: undefined } });
  if (filtros.favoritos)
    chips.push({ chave: "favoritos", rotulo: "Só favoritos", remover: { ...filtros, favoritos: undefined } });
  if (filtros.apenas_ativos)
    chips.push({ chave: "ativos", rotulo: "Só ativos", remover: { ...filtros, apenas_ativos: false } });

  return (
    <form onSubmit={aplicar} role="search" aria-label="Buscar processos" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[16rem] flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            id="q"
            aria-label="Busca por número, manifestante ou assunto"
            value={draft.q ?? ""}
            onChange={(e) => setDraft({ ...draft, q: e.target.value || undefined })}
            placeholder="Buscar por número, manifestante ou assunto — Enter para buscar"
            inputMode="search"
            className="pl-9"
          />
        </div>
        <Button
          type="button"
          variant="secondary"
          aria-expanded={aberto}
          aria-controls="filtros-processos-painel"
          onClick={() => setAberto((v) => !v)}
        >
          <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
          Filtros
          {nAvancados > 0 && (
            <span className="rounded-full bg-primary px-1.5 text-xs font-semibold tabular-nums text-primary-foreground">
              {nAvancados}
              <span className="sr-only"> {nAvancados === 1 ? "filtro ativo" : "filtros ativos"}</span>
            </span>
          )}
          <ChevronDown
            className={cn("h-4 w-4 transition-transform duration-fast", aberto && "rotate-180")}
            aria-hidden="true"
          />
        </Button>
        <Button type="submit">Buscar</Button>
      </div>

      <div
        id="filtros-processos-painel"
        hidden={!aberto}
        className="rounded-card border border-border bg-surface-1 p-4 shadow-xs"
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <Label htmlFor="assunto">Assunto</Label>
            <Select
              id="assunto"
              value={draft.id_assunto ?? ""}
              onChange={(e) => setDraft({ ...draft, id_assunto: e.target.value ? Number(e.target.value) : undefined })}
            >
              <option value="">Todos</option>
              {assuntos.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.nome.length > 60 ? a.nome.slice(0, 60) + "…" : a.nome}
                </option>
              ))}
            </Select>
          </div>
          <div className="lg:col-span-2">
            <Label htmlFor="unidade">Unidade (proprietária ou local atual)</Label>
            <Select
              id="unidade"
              value={draft.id_unidade ?? ""}
              onChange={(e) => setDraft({ ...draft, id_unidade: e.target.value ? Number(e.target.value) : undefined })}
            >
              <option value="">Todas</option>
              {unidades.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nome}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="desde">Aberto desde</Label>
            <Input
              id="desde"
              type="date"
              value={draft.desde?.slice(0, 10) ?? ""}
              onChange={(e) => setDraft({ ...draft, desde: e.target.value ? `${e.target.value}T00:00:00` : undefined })}
            />
          </div>
          <div>
            <Label htmlFor="ate">Aberto até</Label>
            <Input
              id="ate"
              type="date"
              value={draft.ate?.slice(0, 10) ?? ""}
              onChange={(e) => setDraft({ ...draft, ate: e.target.value ? `${e.target.value}T23:59:59` : undefined })}
            />
          </div>
          <div className="flex flex-col justify-end gap-2 pb-1">
            <label className="inline-flex items-center gap-2 text-sm">
              <Checkbox
                id="ativos"
                checked={!!draft.apenas_ativos}
                onChange={(e) => setDraft({ ...draft, apenas_ativos: e.target.checked })}
              />
              Apenas ativos
            </label>
            <label className="inline-flex items-center gap-2 text-sm">
              <Checkbox
                id="favoritos"
                checked={!!draft.favoritos}
                onChange={(e) => setDraft({ ...draft, favoritos: e.target.checked || undefined })}
              />
              Só favoritos
            </label>
          </div>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={aoLimpar}>
            Limpar
          </Button>
          <Button type="submit">Aplicar filtros</Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
          <span className="font-medium tabular-nums text-foreground" aria-live="polite">
            {total === undefined ? "Carregando…" : `${total} ${total === 1 ? "processo" : "processos"}`}
          </span>
          {chips.map((c) => (
            <button
              key={c.chave}
              type="button"
              onClick={() => aoAplicar(c.remover)}
              aria-label={`Remover filtro ${c.rotulo}`}
              className="inline-flex max-w-[18rem] items-center gap-1 rounded-full border border-border bg-muted px-2.5 py-0.5 text-xs text-foreground transition-colors duration-fast hover:border-border-strong hover:bg-surface-1"
            >
              <span className="truncate">{c.rotulo}</span>
              <X className="h-3 w-3 shrink-0" aria-hidden="true" />
            </button>
          ))}
          {chips.length > 1 && (
            <button
              type="button"
              onClick={aoLimpar}
              className="rounded text-xs font-medium text-primary underline-offset-2 hover:underline"
            >
              Limpar tudo
            </button>
          )}
        </div>

        {/* F2 — o recorte por responsabilidade. "Da minha unidade" INCLUI os
            processos sem responsável: são os que precisam que alguém os
            assuma. Fica à vista (não dentro de "Filtros") porque é a pergunta
            de todo dia: os meus, ou os da unidade? */}
        <div role="group" aria-label="Escopo" className="inline-flex rounded-button border border-border bg-surface-1 p-0.5">
          {([undefined, ...ESCOPOS] as (EscopoProcesso | undefined)[]).map((e) => {
            const ativo = filtros.escopo === e;
            return (
              <button
                key={e ?? "todos"}
                type="button"
                aria-pressed={ativo}
                onClick={() => aoAplicar({ ...filtros, escopo: e })}
                className={cn(
                  "rounded-sm px-2.5 py-1 text-xs font-medium transition-colors duration-fast",
                  ativo ? "bg-primary text-primary-foreground" : "text-foreground-muted hover:bg-muted hover:text-foreground",
                )}
              >
                {e ? ESCOPO_LABEL[e] : "Todos"}
              </button>
            );
          })}
        </div>
      </div>
    </form>
  );
}
