"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Clock, FileText, Paperclip } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ChecklistDocumentosCard } from "@/components/ChecklistDocumentosCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useRequireCidadao } from "@/lib/cidadao-auth";

function fmt(s: string | null | undefined) {
  if (!s) return "—";
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

export default function CidadaoProcessoDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const idValido = Number.isInteger(id) && id > 0;
  const { cidadao, loading } = useRequireCidadao();

  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({
    queryKey: ["cidadao-processo", id],
    queryFn: () => api.cidadao.getProcesso(id),
    enabled: !!cidadao && idValido,
  });
  const checklistQ = useQuery({
    queryKey: ["cidadao-checklist", id],
    queryFn: () => api.cidadao.checklistDocumentos(id),
    enabled: !!cidadao && idValido,
  });

  const [uploadKey, setUploadKey] = useState<string | null>(null);
  const [uploadNome, setUploadNome] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);

  const uploadM = useMutation({
    mutationFn: () => {
      if (!file || !uploadKey) throw new Error("Selecione um arquivo");
      return api.cidadao.uploadAnexo(id, file, file.name, uploadKey);
    },
    onSuccess: () => {
      toast.success("Documento anexado.");
      qc.invalidateQueries({ queryKey: ["cidadao-processo", id] });
      qc.invalidateQueries({ queryKey: ["cidadao-checklist", id] });
      setUploadKey(null);
      setFile(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (loading) return <p className="text-sm text-muted-foreground">Carregando...</p>;
  if (!cidadao) return null;

  if (!idValido) {
    return (
      <div className="space-y-3">
        <Link
          href="/cidadao/processos"
          className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar
        </Link>
        <div
          role="alert"
          className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
        >
          ID de processo inválido.
        </div>
      </div>
    );
  }

  if (q.isLoading)
    return <p className="text-sm text-muted-foreground">Carregando processo...</p>;
  if (q.error || !q.data) {
    return (
      <div className="space-y-3">
        <Link
          href="/cidadao/processos"
          className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar
        </Link>
        <div
          role="alert"
          className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
        >
          {q.error instanceof Error ? q.error.message : "Erro ao carregar"}
        </div>
      </div>
    );
  }

  const p = q.data;
  const identifier = p.nup ?? p.numero_processo;

  return (
    <div className="space-y-4">
      <Link
        href="/cidadao/processos"
        className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
      >
        <ArrowLeft className="h-4 w-4" />
        Voltar
      </Link>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <CardTitle className="font-mono">{identifier}</CardTitle>
            <span className="text-sm text-muted-foreground tabular-nums">
              aberto em {fmt(p.data_hora_abertura)}
            </span>
          </div>
          {p.nup && p.numero_processo && p.nup !== p.numero_processo && (
            <p className="mt-1 text-xs text-muted-foreground">
              Número interno:{" "}
              <span className="font-mono">{p.numero_processo}</span>
            </p>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {p.ativo ? (
              <Badge intent="success" icon={Clock}>
                Em andamento
              </Badge>
            ) : (
              <Badge intent="neutral" icon={CheckCircle2}>
                Encerrado
              </Badge>
            )}
            {p.especie_nome && (
              <Badge intent="neutral">{p.especie_nome}</Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                Assunto
              </dt>
              <dd>{p.assunto ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                Tipo de processo
              </dt>
              <dd>{p.tipo_processo ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                Local atual
              </dt>
              <dd>{p.local_atual ?? "—"}</dd>
            </div>
            {p.ccd_nome && (
              <div>
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                  Classificação documental
                </dt>
                <dd>
                  {p.ccd_codigo && (
                    <span className="font-mono text-xs text-muted-foreground">
                      {p.ccd_codigo}{" "}
                    </span>
                  )}
                  {p.ccd_nome}
                </dd>
              </div>
            )}
            {p.corpo && (
              <div className="md:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                  Descrição
                </dt>
                <dd className="whitespace-pre-wrap">{p.corpo}</dd>
              </div>
            )}
            {p.observacao && (
              <div className="md:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                  Observação
                </dt>
                <dd className="whitespace-pre-wrap">{p.observacao}</dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>

      <ChecklistDocumentosCard
        data={checklistQ.data}
        loading={checklistQ.isLoading}
        onAnexar={(key, nome) => {
          setUploadKey(key);
          setUploadNome(nome);
          setFile(null);
        }}
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Paperclip className="h-4 w-4" />
            Anexos ({p.anexos.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {p.anexos.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum anexo público.</p>
          ) : (
            <ul className="space-y-2">
              {p.anexos.map((a) => (
                <li
                  key={a.id}
                  className="flex items-center gap-3 rounded-md border border-border bg-muted/20 px-3 py-2"
                >
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm">
                      {a.descricao ?? a.e_doc ?? `Anexo ${a.id}`}
                    </div>
                    {a.qtd_paginas != null && (
                      <div className="text-xs text-muted-foreground">
                        {a.qtd_paginas} pág
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Histórico ({p.movimentacoes.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {p.movimentacoes.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhuma movimentação ainda.
            </p>
          ) : (
            <ol className="space-y-3">
              {p.movimentacoes.map((m) => (
                <li key={m.id} className="border-l-2 border-primary pl-4">
                  <div className="text-xs text-muted-foreground tabular-nums">
                    {fmt(m.data_hora_movimentacao)}
                  </div>
                  <div className="text-sm">
                    <span className="font-medium text-foreground">{m.acao}</span>
                    {m.unidade_responsavel && (
                      <span className="text-muted-foreground">
                        {" "}
                        em {m.unidade_responsavel}
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={uploadKey !== null}
        onClose={() => {
          if (!uploadM.isPending) {
            setUploadKey(null);
            setFile(null);
          }
        }}
        title={`Anexar: ${uploadNome}`}
        size="sm"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setUploadKey(null);
                setFile(null);
              }}
              disabled={uploadM.isPending}
            >
              Cancelar
            </Button>
            <Button
              onClick={() => uploadM.mutate()}
              disabled={!file || uploadM.isPending}
            >
              {uploadM.isPending ? "Enviando..." : "Enviar"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Selecione o arquivo correspondente a <strong>{uploadNome}</strong>.
          </p>
          <div>
            <Label htmlFor="checklist-file">Arquivo</Label>
            <input
              id="checklist-file"
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm"
            />
          </div>
        </div>
      </Dialog>
    </div>
  );
}
