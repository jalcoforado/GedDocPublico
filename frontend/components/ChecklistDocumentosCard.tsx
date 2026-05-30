"use client";

import { Check, FileText, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  ChecklistDocumentosResponse,
  StatusDocumental,
} from "@/lib/api";

const STATUS_LABEL: Record<StatusDocumental, string> = {
  sem_documentos_exigidos: "Sem documentos exigidos",
  pendente: "Pendente",
  parcial: "Parcial",
  completo: "Completo",
};

const STATUS_INTENT: Record<
  StatusDocumental,
  "neutral" | "warning" | "info" | "success"
> = {
  sem_documentos_exigidos: "neutral",
  pendente: "warning",
  parcial: "info",
  completo: "success",
};

interface Props {
  data: ChecklistDocumentosResponse | undefined;
  loading?: boolean;
  /** Citizen mode: clique em "Anexar" por item exigido. Read-only se omitido. */
  onAnexar?: (key: string, nome: string) => void;
}

export function ChecklistDocumentosCard({ data, loading, onAnexar }: Props) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle>Documentos exigidos</CardTitle>
          {data && (
            <Badge intent={STATUS_INTENT[data.status_documental]}>
              {STATUS_LABEL[data.status_documental]}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {loading && (
          <p className="text-sm text-muted-foreground">
            <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />
            Carregando…
          </p>
        )}

        {data && data.status_documental === "sem_documentos_exigidos" && (
          <p className="text-sm text-muted-foreground">
            Este processo não tem documentos exigidos.
          </p>
        )}

        {data && data.itens.length > 0 && (
          <>
            <p className="mb-2 text-xs text-foreground-muted">
              {data.obrigatorios_enviados}/{data.obrigatorios_total} obrigatórios enviados.
            </p>
            <ul className="space-y-2">
              {data.itens.map((item) => (
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
                      <span className="font-medium">
                        {item.nome}
                        {item.obrigatorio && (
                          <span className="text-danger" aria-label="obrigatório">
                            {" "}
                            *
                          </span>
                        )}
                      </span>
                      {item.enviado ? (
                        <Badge intent="success">Enviado</Badge>
                      ) : (
                        <Badge intent={item.obrigatorio ? "warning" : "neutral"}>
                          Pendente
                        </Badge>
                      )}
                      {!item.obrigatorio && (
                        <span className="text-xs text-foreground-subtle">opcional</span>
                      )}
                    </div>
                    {item.descricao && (
                      <p className="mt-0.5 text-xs text-foreground-muted">
                        {item.descricao}
                      </p>
                    )}
                    {item.anexos.length > 0 && (
                      <ul className="mt-1 list-inside list-disc text-xs text-foreground-muted">
                        {item.anexos.map((a) => (
                          <li key={a.id_anexo}>{a.descricao ?? `Anexo #${a.id_anexo}`}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                  {onAnexar && (
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
          </>
        )}
      </CardContent>
    </Card>
  );
}
