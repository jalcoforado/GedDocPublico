"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { filtroParaUrl, type FiltroDaUrl } from "@/lib/relatorios";

import { CamposDoRecorte } from "./CamposDoRecorte";

/**
 * Barra do recorte comum dos relatórios (SI-34): período, unidade no sentido
 * escolhido, tipo, assunto e serviço. A mesma em todas as listas, para que o
 * filtro de uma seja o da outra; os campos vêm de `CamposDoRecorte`, que o
 * montador também usa.
 *
 * Edita um rascunho e só aplica no botão: cada mudança de filtro dispara
 * consultas pesadas, e aplicar a cada tecla de data martelaria o servidor com
 * períodos pela metade.
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

  const periodoInvertido = !!(rascunho.desde && rascunho.ate && rascunho.desde > rascunho.ate);

  return (
    <form
      className="space-y-3 rounded-card border border-border bg-card p-4 shadow-card"
      onSubmit={(e) => {
        e.preventDefault();
        if (!periodoInvertido) onAplicar(rascunho);
      }}
      aria-label="Filtros do relatório"
    >
      <CamposDoRecorte valor={rascunho} onChange={setRascunho} periodoInvertido={periodoInvertido} />

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
