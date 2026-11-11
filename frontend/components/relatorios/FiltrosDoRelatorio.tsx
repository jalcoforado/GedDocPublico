"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { api, organogramaApi, type ModoUnidadeRelatorio } from "@/lib/api";
import { useAssuntosAll } from "@/lib/assuntos";
import { ROTULO_MODO_UNIDADE, filtroParaUrl, type FiltroDaUrl } from "@/lib/relatorios";

/**
 * Barra do recorte comum dos relatórios (SI-34): período, unidade no sentido
 * escolhido, assunto e tipo. A mesma na página gerencial e nas listas, para
 * que o filtro de uma seja o da outra.
 *
 * Edita um rascunho e só aplica no botão: cada mudança de filtro dispara
 * consultas de cinco seções, e aplicar a cada tecla de data martelaria o
 * servidor com períodos pela metade.
 */

function hojeLocal(): Date {
  return new Date();
}

function iso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${dia}`;
}

function atalhos(): { rotulo: string; desde: string; ate: string }[] {
  const h = hojeLocal();
  const inicioMes = new Date(h.getFullYear(), h.getMonth(), 1);
  const inicioMesPassado = new Date(h.getFullYear(), h.getMonth() - 1, 1);
  const fimMesPassado = new Date(h.getFullYear(), h.getMonth(), 0);
  const trintaDias = new Date(h.getFullYear(), h.getMonth(), h.getDate() - 29);
  return [
    { rotulo: "Este mês", desde: iso(inicioMes), ate: iso(h) },
    { rotulo: "Mês passado", desde: iso(inicioMesPassado), ate: iso(fimMesPassado) },
    { rotulo: "Últimos 30 dias", desde: iso(trintaDias), ate: iso(h) },
  ];
}

export function FiltrosDoRelatorio({
  valor,
  onAplicar,
}: {
  valor: FiltroDaUrl;
  onAplicar: (f: FiltroDaUrl) => void;
}) {
  const [rascunho, setRascunho] = useState<FiltroDaUrl>(valor);
  // URL mudou por fora (voltar do navegador, link colado): o rascunho segue.
  // Pelo CONTEÚDO, não pela referência — a página recria o objeto a cada
  // render, e seguir a referência apagaria o que a pessoa está digitando.
  const chave = filtroParaUrl(valor);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => setRascunho(valor), [chave]);

  const organogramaQ = useQuery({ queryKey: ["organograma"], queryFn: () => organogramaApi.tree() });
  const tiposQ = useQuery({ queryKey: ["tipos-processo"], queryFn: () => api.tiposProcesso.list() });
  const assuntosQ = useAssuntosAll();

  const unidades = useMemo<ComboboxOption[]>(
    () =>
      (organogramaQ.data ?? [])
        .map((u) => ({ value: u.id, label: u.unidade_trabalho, hint: u.sigla ?? undefined }))
        .sort((a, b) => a.label.localeCompare(b.label, "pt-BR")),
    [organogramaQ.data],
  );
  const tipos = useMemo<ComboboxOption[]>(
    () => (tiposQ.data ?? []).map((t) => ({ value: t.id, label: t.tipo_processo })),
    [tiposQ.data],
  );
  const assuntos = useMemo<ComboboxOption[]>(
    () =>
      (assuntosQ.data ?? [])
        .filter((a) => !rascunho.id_tipo_processo || a.id_tipo_processo === rascunho.id_tipo_processo)
        .map((a) => ({ value: a.id, label: a.assunto })),
    [assuntosQ.data, rascunho.id_tipo_processo],
  );

  const periodoInvertido = !!(rascunho.desde && rascunho.ate && rascunho.desde > rascunho.ate);
  const num = (v: number | string | null) => (typeof v === "number" ? v : undefined);

  return (
    <form
      className="space-y-3 rounded-card border border-border bg-card p-4 shadow-card"
      onSubmit={(e) => {
        e.preventDefault();
        if (!periodoInvertido) onAplicar(rascunho);
      }}
      aria-label="Filtros do relatório"
    >
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div>
          <Label htmlFor="rel-desde">De</Label>
          <Input
            id="rel-desde"
            type="date"
            value={rascunho.desde ?? ""}
            onChange={(e) => setRascunho({ ...rascunho, desde: e.target.value || undefined })}
          />
        </div>
        <div>
          <Label htmlFor="rel-ate">Até</Label>
          <Input
            id="rel-ate"
            type="date"
            value={rascunho.ate ?? ""}
            onChange={(e) => setRascunho({ ...rascunho, ate: e.target.value || undefined })}
            aria-invalid={periodoInvertido || undefined}
            aria-describedby={periodoInvertido ? "rel-periodo-erro" : undefined}
          />
        </div>
        <div>
          <Label htmlFor="rel-tipo">Tipo de processo</Label>
          <Combobox
            id="rel-tipo"
            options={tipos}
            value={rascunho.id_tipo_processo ?? null}
            onChange={(v) => {
              const id_tipo_processo = num(v);
              // Assunto de outro tipo não combina com o tipo novo.
              const assuntoFica = assuntosQ.data?.find((a) => a.id === rascunho.id_assunto)
                ?.id_tipo_processo === id_tipo_processo;
              setRascunho({
                ...rascunho,
                id_tipo_processo,
                id_assunto: !id_tipo_processo || assuntoFica ? rascunho.id_assunto : undefined,
              });
            }}
            placeholder="Todos"
            loading={tiposQ.isLoading}
          />
        </div>
        <div>
          <Label htmlFor="rel-assunto">Assunto</Label>
          <Combobox
            id="rel-assunto"
            options={assuntos}
            value={rascunho.id_assunto ?? null}
            onChange={(v) => setRascunho({ ...rascunho, id_assunto: num(v) })}
            placeholder="Todos"
            loading={assuntosQ.isLoading}
          />
        </div>
        <div className="md:col-span-2">
          <Label htmlFor="rel-unidade">Unidade</Label>
          <Combobox
            id="rel-unidade"
            options={unidades}
            value={rascunho.id_unidade ?? null}
            onChange={(v) => setRascunho({ ...rascunho, id_unidade: num(v) })}
            placeholder="Todas as unidades"
            searchPlaceholder="Nome ou sigla da unidade…"
            loading={organogramaQ.isLoading}
          />
        </div>
        {rascunho.id_unidade ? (
          <div className="md:col-span-2">
            <Label htmlFor="rel-modo">Contar processos da unidade que é</Label>
            <Select
              id="rel-modo"
              value={rascunho.modo_unidade ?? "envolvida"}
              onChange={(e) =>
                setRascunho({ ...rascunho, modo_unidade: e.target.value as ModoUnidadeRelatorio })
              }
            >
              {(Object.keys(ROTULO_MODO_UNIDADE) as ModoUnidadeRelatorio[]).map((m) => (
                <option key={m} value={m}>
                  {ROTULO_MODO_UNIDADE[m]}
                </option>
              ))}
            </Select>
          </div>
        ) : null}
      </div>

      {periodoInvertido && (
        <p id="rel-periodo-erro" role="alert" className="text-sm text-danger">
          A data &ldquo;De&rdquo; é posterior à data &ldquo;Até&rdquo;.
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1" aria-label="Atalhos de período">
          {atalhos().map((a) => (
            <Button
              key={a.rotulo}
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setRascunho({ ...rascunho, desde: a.desde, ate: a.ate })}
            >
              {a.rotulo}
            </Button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setRascunho({});
              onAplicar({});
            }}
          >
            Limpar
          </Button>
          <Button type="submit" disabled={periodoInvertido}>
            Aplicar filtros
          </Button>
        </div>
      </div>
    </form>
  );
}
