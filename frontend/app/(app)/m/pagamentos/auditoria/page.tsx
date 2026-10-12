"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ScrollText, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { fmtDataHora, fmtMoeda } from "@/components/pagamentos/format";
import { api, type AuditLogItem as AuditLogOut } from "@/lib/api";

/** Atos que o módulo grava na trilha, na ordem em que acontecem no rito. */
const ATOS_AUDITADOS: { acao: string; rotulo: string }[] = [
  { acao: "debito.ajuste_solicitado", rotulo: "Ajuste solicitado" },
  { acao: "debito.ajuste_respondido", rotulo: "Ajuste respondido" },
  { acao: "debito.versao_criada", rotulo: "Alteração material (nova versão)" },
  { acao: "debito.aprovacoes_invalidadas", rotulo: "Aprovações invalidadas" },
  { acao: "anexo_debito.incluido", rotulo: "Documento anexado" },
  { acao: "anexo_debito.removido", rotulo: "Documento removido" },
  { acao: "excecao_cronologica.autorizada", rotulo: "Exceção cronológica autorizada" },
  { acao: "pagamento.autorizado", rotulo: "Pagamento autorizado" },
  { acao: "pagamento.parcelas_liberadas", rotulo: "Parcelas liberadas" },
  { acao: "pagamento.liberacao_revogada", rotulo: "Liberação revogada" },
  { acao: "pagamento.lote_enviado", rotulo: "Lote enviado ao banco" },
  { acao: "pagamento.lote_retorno", rotulo: "Retorno de lote registrado" },
  { acao: "pagamento.parcela_paga", rotulo: "Parcela paga" },
  { acao: "pagamento.parcela_estornada", rotulo: "Pagamento estornado" },
  { acao: "pagamento.retencao_recolhida", rotulo: "Retenção recolhida" },
  { acao: "pagamento.conciliado", rotulo: "Lançamento conciliado" },
  { acao: "pagamento.conciliacao_desfeita", rotulo: "Conciliação desfeita" },
  { acao: "fornecedor.dados_bancarios_revelados", rotulo: "Dados bancários de fornecedor consultados" },
];
const ROTULO = new Map(ATOS_AUDITADOS.map((a) => [a.acao, a.rotulo]));

/** Débitos a que a linha se refere: o próprio registro, ou o que o ato guardou. */
function debitosDaLinha(l: AuditLogOut): number[] {
  const p = (l.payload ?? {}) as Record<string, unknown>;
  const ids = new Set<number>();
  if (l.entidade === "debito" && l.id_entidade) ids.add(l.id_entidade);
  for (const chave of ["id_debito", "debito_id"]) {
    if (typeof p[chave] === "number") ids.add(p[chave] as number);
  }
  if (Array.isArray(p.debito_ids)) {
    for (const v of p.debito_ids) if (typeof v === "number") ids.add(v);
  }
  return [...ids].sort((a, b) => a - b);
}

/** O que do ato vale ler sem abrir nada: valor e a justificativa, quando há. */
function resumoDaLinha(l: AuditLogOut): string {
  const p = (l.payload ?? {}) as Record<string, unknown>;
  const partes: string[] = [];
  const valor = p.valor ?? p.valor_total;
  if (typeof valor === "string" || typeof valor === "number") partes.push(fmtMoeda(String(valor)));
  if (typeof p.numero === "string") partes.push(p.numero);
  if (typeof p.forma_pagamento === "string") partes.push(p.forma_pagamento);
  if (p.excecao_saldo === true) partes.push("com exceção de saldo");
  if (typeof p.justificativa === "string" && p.justificativa) partes.push(`“${p.justificativa}”`);
  return partes.join(" · ");
}

interface Filtros {
  acao: string;
  desde: string;
  ate: string;
  id_usuario: number | null;
  nome_usuario: string | null;
  page: number;
}
const FILTROS_VAZIOS: Filtros = {
  acao: "", desde: "", ate: "", id_usuario: null, nome_usuario: null, page: 1,
};
const POR_PAGINA = 50;

/**
 * Trilha de auditoria de pagamentos: quem fez qual ato financeiro, e quando.
 * A trilha é gravada desde 2026-10-11 (PR 113); atos anteriores não aparecem aqui.
 */
export default function AuditoriaPagamentosPage() {
  const [f, setF] = useState<Filtros>(FILTROS_VAZIOS);

  const q = useQuery({
    queryKey: ["pag-auditoria", f.acao, f.desde, f.ate, f.id_usuario, f.page],
    queryFn: () =>
      api.pagamentos.auditoria({
        acao: f.acao || undefined,
        // `<input type="date">` devolve só o dia; o período inclui os dois extremos.
        desde: f.desde ? `${f.desde}T00:00:00` : undefined,
        ate: f.ate ? `${f.ate}T23:59:59` : undefined,
        id_usuario: f.id_usuario ?? undefined,
        page: f.page,
        page_size: POR_PAGINA,
      }),
  });

  const data = q.data;
  const paginas = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const filtrando = !!(f.acao || f.desde || f.ate || f.id_usuario);

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[{ label: "Pagamentos", href: "/m/pagamentos" }]}
        title="Trilha de auditoria"
        description="Quem autorizou, liberou, pagou, estornou ou conciliou — e quando. O registro não pode ser alterado."
        icon={ScrollText}
      />

      <div className="grid gap-3 rounded-card border border-border bg-card p-4 sm:grid-cols-2 lg:grid-cols-4">
        <FormField label="Ato">
          <Select value={f.acao} onChange={(e) => setF({ ...f, acao: e.target.value, page: 1 })}>
            <option value="">Todos os atos</option>
            {ATOS_AUDITADOS.map((a) => (
              <option key={a.acao} value={a.acao}>{a.rotulo}</option>
            ))}
          </Select>
        </FormField>
        <FormField label="De">
          <Input type="date" value={f.desde} onChange={(e) => setF({ ...f, desde: e.target.value, page: 1 })} />
        </FormField>
        <FormField label="Até">
          <Input type="date" value={f.ate} onChange={(e) => setF({ ...f, ate: e.target.value, page: 1 })} />
        </FormField>
        <div className="flex items-end">
          <Button variant="ghost" onClick={() => setF(FILTROS_VAZIOS)} disabled={!filtrando}>
            Limpar filtros
          </Button>
        </div>
        {f.id_usuario && (
          <div className="sm:col-span-2 lg:col-span-4">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setF({ ...f, id_usuario: null, nome_usuario: null, page: 1 })}
              aria-label={`Remover filtro por ${f.nome_usuario ?? "pessoa"}`}
            >
              Só atos de {f.nome_usuario ?? `usuário #${f.id_usuario}`}
              <X className="ml-1 h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        )}
      </div>

      {q.isError ? (
        <EmptyState
          icon={ScrollText}
          title="Não foi possível carregar a trilha"
          description="Tente de novo em instantes. Se persistir, avise o suporte."
        />
      ) : !q.isLoading && data && data.total === 0 ? (
        <EmptyState
          icon={ScrollText}
          title={filtrando ? "Nenhum ato com esses filtros" : "Nenhum ato registrado ainda"}
          description={
            filtrando
              ? "Amplie o período ou limpe os filtros."
              : "Os atos financeiros passam a aparecer aqui conforme forem praticados."
          }
        />
      ) : (
        <>
          <p className="text-sm text-foreground-muted" role="status">
            {data ? (data.total === 1 ? "1 ato" : `${data.total} atos`) : "Carregando…"}
          </p>
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>Quando</TH>
                  <TH>Quem</TH>
                  <TH>Ato</TH>
                  <TH>Solicitação</TH>
                  <TH>Detalhe</TH>
                </TR>
              </THead>
              <TBody>
                {q.isLoading && <SkeletonRow cols={5} />}
                {data?.items.map((l) => {
                  const debitos = debitosDaLinha(l);
                  return (
                    <TR key={l.id}>
                      <TD className="whitespace-nowrap">{fmtDataHora(l.criado_em)}</TD>
                      <TD>
                        {l.id_usuario ? (
                          <button
                            type="button"
                            className="rounded text-left text-primary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            title="Ver só os atos desta pessoa"
                            onClick={() =>
                              setF({ ...f, id_usuario: l.id_usuario, nome_usuario: l.nome_usuario, page: 1 })
                            }
                          >
                            {l.nome_usuario ?? `Usuário #${l.id_usuario}`}
                          </button>
                        ) : (
                          <span className="text-foreground-muted">Sistema</span>
                        )}
                      </TD>
                      <TD className="font-medium">{ROTULO.get(l.acao) ?? l.acao}</TD>
                      <TD>
                        {debitos.length === 0
                          ? "—"
                          : debitos.map((id, i) => (
                              <span key={id}>
                                {i > 0 && ", "}
                                <Link
                                  href={`/m/pagamentos/solicitacoes/${id}`}
                                  className="text-primary underline-offset-2 hover:underline"
                                >
                                  #{id}
                                </Link>
                              </span>
                            ))}
                      </TD>
                      <TD className="max-w-[28rem] text-foreground-muted">{resumoDaLinha(l) || "—"}</TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          </div>
          {paginas > 1 && (
            <div className="flex items-center justify-end gap-2">
              <Button
                variant="secondary"
                size="sm"
                aria-label="Página anterior"
                disabled={f.page <= 1}
                onClick={() => setF({ ...f, page: f.page - 1 })}
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              </Button>
              <span className="text-sm text-foreground-muted">
                Página {f.page} de {paginas}
              </span>
              <Button
                variant="secondary"
                size="sm"
                aria-label="Próxima página"
                disabled={f.page >= paginas}
                onClick={() => setF({ ...f, page: f.page + 1 })}
              >
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
