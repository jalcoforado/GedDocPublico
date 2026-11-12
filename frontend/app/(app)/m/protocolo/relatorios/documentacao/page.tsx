"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, Lock } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { FiltrosDoRelatorio } from "@/components/relatorios/FiltrosDoRelatorio";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Carregando } from "@/components/ui/carregando";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import {
  NIVEL_SIGILO_LABEL,
  api,
  documentacaoCsvUrl,
  type DocumentacaoProcessoRow,
  type StatusDocumental,
  type VisaoDocumentacao,
} from "@/lib/api";
import {
  ROTA_RELATORIOS,
  VISOES_DOCUMENTACAO,
  consultaDaDocumentacao,
  filtroDaUrl,
  filtroParaUrl,
  fmtData,
  fmtDataHora,
  recorteComum,
  visaoDocDe,
  type FiltroDaUrl,
} from "@/lib/relatorios";

/**
 * Documentação (SI-34) — o "ver documentação" do grupo Documentação da página
 * de relatórios. Uma linha por processo: a situação dos documentos que o
 * serviço exige (a mesma da tela do processo) e o pedido de complementação
 * mais recente. O "Mostrar" escolhe qual número do grupo ver; cada opção é a
 * consulta que produziu o número (`relatorios_documentacao.py`).
 *
 * A mensagem do pedido ao cidadão não aparece aqui de propósito: é texto
 * livre e pode trazer dado pessoal. Ela fica no processo.
 */

const DOC: Record<StatusDocumental, { rotulo: string; intent: "neutral" | "warning" | "info" | "success" }> = {
  sem_documentos_exigidos: { rotulo: "Sem exigência", intent: "neutral" },
  pendente: { rotulo: "Pendente", intent: "warning" },
  parcial: { rotulo: "Parcial", intent: "info" },
  completo: { rotulo: "Completo", intent: "success" },
};

const COMPL: Record<NonNullable<DocumentacaoProcessoRow["complementacao_status"]>, { rotulo: string; intent: "warning" | "success" | "neutral" }> = {
  aberta: { rotulo: "Aguardando o cidadão", intent: "warning" },
  respondida: { rotulo: "Respondida", intent: "success" },
  cancelada: { rotulo: "Cancelada", intent: "neutral" },
};

export default function RelatorioDocumentacaoPage() {
  const router = useRouter();
  const pathname = usePathname();
  const busca = useSearchParams().toString();
  const filtro = useMemo(() => filtroDaUrl(new URLSearchParams(busca)), [busca]);
  const visao = visaoDocDe(filtro);
  const consulta = consultaDaDocumentacao(filtro);
  const grupos = [...new Set(VISOES_DOCUMENTACAO.map((v) => v.grupo))];

  const q = useQuery({
    queryKey: ["relatorio-documentacao", busca],
    queryFn: () => api.relatorios.documentacao(consulta),
  });

  function irPara(f: FiltroDaUrl) {
    router.replace(`${pathname}${filtroParaUrl(f)}`, { scroll: false });
  }

  const r = q.data;
  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[
          { label: "Relatórios", href: `${ROTA_RELATORIOS}${filtroParaUrl(recorteComum(filtro))}` },
          { label: "Documentação" },
        ]}
        title="Documentação dos processos"
        description="Documentos que o serviço exige e pedidos de complementação ao cidadão, processo a processo."
        actions={
          <a
            href={documentacaoCsvUrl(consulta)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-muted px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Download className="h-4 w-4" aria-hidden="true" /> CSV
          </a>
        }
      />

      <FiltrosDoRelatorio valor={recorteComum(filtro)} onAplicar={(f) => irPara({ ...f, visao: filtro.visao })} />

      <div
        role="group"
        aria-label="Filtros desta lista"
        className="flex flex-wrap items-center gap-x-5 gap-y-3 rounded-card border border-border bg-card p-3 text-sm shadow-card"
      >
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="rel-visao-doc" className="font-medium text-foreground">
            Mostrar
          </label>
          <Select
            id="rel-visao-doc"
            className="h-9 w-80"
            value={visao.id}
            onChange={(e) => irPara({ ...filtro, visao: e.target.value as VisaoDocumentacao })}
          >
            {grupos.map((g) => (
              <optgroup key={g} label={g}>
                {VISOES_DOCUMENTACAO.filter((v) => v.grupo === g).map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.rotulo}
                  </option>
                ))}
              </optgroup>
            ))}
          </Select>
        </div>
        <p className="basis-full text-xs text-foreground-muted">
          {visao.hoje
            ? "Situação de hoje: o período do filtro não se aplica (unidade, tipo, assunto e serviço, sim)."
            : `No período do filtro, pela data de ${visao.data}. A situação dos documentos é a de hoje.`}
        </p>
      </div>

      {q.isLoading && <Carregando />}
      {q.error && (
        <div role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
          {q.error instanceof Error ? q.error.message : "Não foi possível gerar o relatório."}
        </div>
      )}

      {r && (
        <>
          <ul className="space-y-0.5 text-xs text-foreground-muted" aria-label="Recorte do relatório">
            {r.descricao_filtros.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <KpiCard label="Processos" value={r.totais.total} />
            <KpiCard label="Pendentes" value={r.totais.pendentes} intent="warning" />
            <KpiCard label="Parciais" value={r.totais.parciais} />
            <KpiCard label="Completos" value={r.totais.completos} />
            <KpiCard label="Aguardando o cidadão" value={r.totais.aguardando_cidadao} intent="warning" />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>
                {r.cortado
                  ? `Processos (os ${r.processos.length} mais recentes de ${r.totais.total})`
                  : `Processos (${r.processos.length})`}
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
                    <TH>Aberto em</TH>
                    <TH>Serviço</TH>
                    <TH>Documentos</TH>
                    <TH>Complementação</TH>
                    <TH>Onde está</TH>
                  </TR>
                </THead>
                <TBody>
                  {r.processos.length === 0 && (
                    <TR>
                      <TD colSpan={6} className="text-center text-foreground-muted">
                        Nenhum processo no recorte.
                      </TD>
                    </TR>
                  )}
                  {r.processos.map((p) => (
                    <TR key={p.id}>
                      <TD>
                        <div className="flex flex-wrap items-center gap-1">
                          <Link
                            href={`/m/protocolo/processos/${p.id}`}
                            className="font-mono text-xs text-primary hover:underline"
                          >
                            {p.numero_processo}
                          </Link>
                          {p.nivel_sigilo !== "ostensivo" && (
                            <Badge intent="warning" icon={Lock}>
                              {NIVEL_SIGILO_LABEL[p.nivel_sigilo]}
                            </Badge>
                          )}
                        </div>
                      </TD>
                      <TD className="text-xs tabular-nums">{fmtDataHora(p.data_hora_abertura)}</TD>
                      <TD className="text-sm">{p.servico ?? "—"}</TD>
                      <TD>
                        <Badge intent={DOC[p.status_documental].intent}>{DOC[p.status_documental].rotulo}</Badge>
                        {p.obrigatorios_total > 0 && (
                          <div className="mt-0.5 text-xs text-foreground-muted">
                            {p.obrigatorios_enviados} de {p.obrigatorios_total} obrigatórios
                          </div>
                        )}
                      </TD>
                      <TD>
                        {p.complementacao_status ? (
                          <>
                            <Badge intent={COMPL[p.complementacao_status].intent}>
                              {COMPL[p.complementacao_status].rotulo}
                            </Badge>
                            <div className="mt-0.5 text-xs text-foreground-muted">
                              pedida {fmtData(p.complementacao_pedida_em)}
                              {p.complementacao_respondida_em
                                ? ` · respondida ${fmtData(p.complementacao_respondida_em)}`
                                : ""}
                            </div>
                          </>
                        ) : (
                          <span className="text-xs text-foreground-muted">—</span>
                        )}
                      </TD>
                      <TD className="text-sm">{p.local_atual ?? "—"}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
