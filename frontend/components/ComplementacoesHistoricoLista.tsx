"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ComplementacaoOut, StatusComplementacao } from "@/lib/api";

const STATUS_LABEL: Record<StatusComplementacao, string> = {
  aberta: "Aberta",
  respondida: "Respondida",
  cancelada: "Cancelada",
};

const STATUS_INTENT: Record<
  StatusComplementacao,
  "warning" | "success" | "neutral"
> = {
  aberta: "warning",
  respondida: "success",
  cancelada: "neutral",
};

function fmt(s: string | null | undefined) {
  if (!s) return "—";
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

interface Props {
  data: ComplementacaoOut[];
  title?: string;
}

function ItemLinha({ c }: { c: ComplementacaoOut }) {
  const [expandido, setExpandido] = useState(false);
  const longa = c.mensagem.length > 140;
  const texto = expandido || !longa ? c.mensagem : c.mensagem.slice(0, 140) + "…";
  return (
    <li className="border-l-2 border-border pl-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-foreground-muted tabular-nums">
        <Badge intent={STATUS_INTENT[c.status]}>{STATUS_LABEL[c.status]}</Badge>
        <span>{fmt(c.criado_em)}</span>
        {c.nome_solicitante && <span>· {c.nome_solicitante}</span>}
      </div>
      <p className="mt-1 whitespace-pre-wrap text-sm">{texto}</p>
      {longa && (
        <button
          type="button"
          className="text-xs text-primary hover:underline"
          onClick={() => setExpandido((v) => !v)}
        >
          {expandido ? "Recolher" : "Mostrar mais"}
        </button>
      )}
    </li>
  );
}

export function ComplementacoesHistoricoLista({
  data,
  title = "Complementações anteriores",
}: Props) {
  if (data.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-3">
          {data.map((c) => (
            <ItemLinha key={c.id} c={c} />
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
