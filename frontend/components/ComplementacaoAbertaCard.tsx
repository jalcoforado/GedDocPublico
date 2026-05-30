"use client";

import { AlertCircle, Check, FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  data: ComplementacaoOut;
  modo: "servidor" | "cidadao";
  /** Cidadão: clique em "Responder complementação". */
  onResponder?: () => void;
  /** Servidor: clique em "Cancelar complementação". */
  onCancelar?: () => void;
  /** Cidadão: clique em "Anexar" por item solicitado pendente. */
  onAnexar?: (key: string, nome: string) => void;
  respondendo?: boolean;
}

export function ComplementacaoAbertaCard({
  data,
  modo,
  onResponder,
  onCancelar,
  onAnexar,
  respondendo,
}: Props) {
  const isAberta = data.status === "aberta";
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-warning" />
            Complementação documental
          </CardTitle>
          <Badge intent={STATUS_INTENT[data.status]}>
            {STATUS_LABEL[data.status]}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-xs text-foreground-muted">
          Solicitada por <strong>{data.nome_solicitante ?? "—"}</strong>{" "}
          em <span className="tabular-nums">{fmt(data.criado_em)}</span>
        </div>
        <p className="whitespace-pre-wrap rounded-md bg-surface-1 px-3 py-2 text-sm">
          {data.mensagem}
        </p>
        {data.documentos_solicitados.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium text-foreground-muted">
              Documentos solicitados
            </p>
            <ul className="space-y-2">
              {data.documentos_solicitados.map((item) => (
                <li
                  key={item.key}
                  className="flex items-start gap-3 rounded-lg border border-border bg-surface-1 p-3 text-sm"
                >
                  <span
                    className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border"
                    aria-hidden="true"
                  >
                    {item.enviado ? (
                      <Check className="h-3.5 w-3.5 text-success" />
                    ) : (
                      <FileText className="h-3 w-3 text-foreground-subtle" />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{item.nome}</span>
                      {item.enviado ? (
                        <Badge intent="success">Enviado</Badge>
                      ) : (
                        <Badge intent="warning">Pendente</Badge>
                      )}
                    </div>
                    {item.descricao && (
                      <p className="mt-0.5 text-xs text-foreground-muted">
                        {item.descricao}
                      </p>
                    )}
                  </div>
                  {modo === "cidadao" && isAberta && onAnexar && !item.enviado && (
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => onAnexar(item.key, item.nome)}
                    >
                      Anexar
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {data.motivo_cancelamento && (
          <div className="rounded-md bg-surface-1 px-3 py-2 text-xs text-foreground-muted">
            <strong>Motivo do cancelamento:</strong> {data.motivo_cancelamento}
          </div>
        )}
        {isAberta && (modo === "cidadao" || modo === "servidor") && (
          <div className="flex flex-wrap justify-end gap-2 pt-1">
            {modo === "cidadao" && onResponder && (
              <Button
                type="button"
                onClick={onResponder}
                disabled={respondendo}
              >
                {respondendo ? "Enviando..." : "Responder complementação"}
              </Button>
            )}
            {modo === "servidor" && onCancelar && (
              <Button type="button" variant="secondary" onClick={onCancelar}>
                Cancelar complementação
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
