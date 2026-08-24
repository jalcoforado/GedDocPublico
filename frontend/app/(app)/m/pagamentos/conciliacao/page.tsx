"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCheck,
  CheckCircle2,
  FileUp,
  Landmark,
  Link2,
  ListChecks,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { BotaoExportarCsv } from "@/components/pagamentos/BotoesExportar";
import { fmtData, fmtDataHora, fmtMoeda } from "@/components/pagamentos/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type ExtratoBancario,
  type ImportarExtratoResultado,
  type LancamentoExtrato,
  type Movimentacao,
} from "@/lib/api";

const CHAVES_INVALIDAR = [
  ["pag-conc-extratos"],
  ["pag-conc-lancamentos"],
  ["pag-conc-sugestoes"],
  ["pag-caixa-painel"],
  ["pag-debitos"],
] as const;

/** Cabeçalho aceito pelo importador do backend (`_parse_csv`). */
const MODELO_CSV = "data;historico;documento;favorecido;valor;tipo";

type FormatoExtrato = "CSV" | "OFX" | "CNAB240";

const ACCEPT_POR_FORMATO: Record<FormatoExtrato, string> = {
  CSV: ".csv,text/csv,text/plain",
  OFX: ".ofx,text/plain,text/xml,application/xml",
  CNAB240: ".txt,.rem,.ret,text/plain",
};

interface FormImport {
  id_conta: number | null;
  formato: FormatoExtrato;
  nome_arquivo: string;
  conteudo: string;
}

function formVazio(): FormImport {
  return { id_conta: null, formato: "CSV", nome_arquivo: "", conteudo: "" };
}

export default function ConciliacaoPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [contaFiltro, setContaFiltro] = useState<number | null>(null);
  const [extratoSel, setExtratoSel] = useState<ExtratoBancario | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [form, setForm] = useState<FormImport>(formVazio());
  const [erroImport, setErroImport] = useState<string | null>(null);
  const [relatoImport, setRelatoImport] = useState<ImportarExtratoResultado | null>(null);
  const [manual, setManual] = useState<LancamentoExtrato | null>(null);
  const [movEscolhida, setMovEscolhida] = useState<number | null>(null);
  const arquivoRef = useRef<HTMLInputElement>(null);

  const contasQ = useQuery({
    queryKey: ["pag-caixa-painel"],
    queryFn: () => api.pagamentos.caixa.painel(),
  });

  const extratosQ = useQuery({
    queryKey: ["pag-conc-extratos", contaFiltro],
    queryFn: () => api.pagamentos.conciliacao.extratos(contaFiltro ?? undefined),
  });

  const lancamentosQ = useQuery({
    queryKey: ["pag-conc-lancamentos", extratoSel?.id],
    queryFn: () => api.pagamentos.conciliacao.lancamentos(extratoSel!.id),
    enabled: !!extratoSel,
  });

  const sugestoesQ = useQuery({
    queryKey: ["pag-conc-sugestoes", extratoSel?.id],
    queryFn: () => api.pagamentos.conciliacao.sugestoes(extratoSel!.id),
    enabled: !!extratoSel,
  });

  // Movimentações da conta do extrato — base da conciliação manual. O backend
  // recusa as já conciliadas (RN-14); aqui só filtramos pelo que pode casar:
  // saídas de pagamento.
  const movimentacoesQ = useQuery({
    queryKey: ["pag-caixa-extrato", extratoSel?.id_conta],
    queryFn: () => api.pagamentos.caixa.extrato(extratoSel!.id_conta),
    enabled: !!extratoSel,
  });

  const contas = contasQ.data ?? [];
  const extratos = extratosQ.data ?? [];
  const lancamentos = lancamentosQ.data ?? [];
  const sugestoes = sugestoesQ.data ?? [];

  const nomeConta = (id: number) =>
    contas.find((c) => c.id_conta === id)?.nome ?? `Conta ${id}`;

  const exatas = useMemo(
    () => sugestoes.filter((s) => s.tipo_correspondencia === "EXATA").length,
    [sugestoes],
  );

  const pendentes = useMemo(
    () => lancamentos.filter((l) => !l.conciliado).length,
    [lancamentos],
  );

  const movsPagamento = useMemo(
    () =>
      (movimentacoesQ.data ?? []).filter(
        (m: Movimentacao) => m.tipo === "SAIDA" && m.origem === "PAGAMENTO",
      ),
    [movimentacoesQ.data],
  );

  function invalidar() {
    for (const k of CHAVES_INVALIDAR) qc.invalidateQueries({ queryKey: [...k] });
  }

  const importar = useMutation({
    mutationFn: () =>
      api.pagamentos.conciliacao.importar({
        id_conta: form.id_conta!,
        nome_arquivo: form.nome_arquivo.trim(),
        formato: form.formato,
        conteudo: form.conteudo,
      }),
    onSuccess: (res) => {
      setErroImport(null);
      setRelatoImport(res);
      invalidar();
      toast.success(`Extrato importado — ${res.importados} lançamento(s).`);
    },
    onError: (e: unknown) =>
      setErroImport(e instanceof Error ? e.message : "Falha ao importar o extrato."),
  });

  const baixaAuto = useMutation({
    mutationFn: () => api.pagamentos.conciliacao.baixaAutomatica(extratoSel!.id),
    onSuccess: (r) => {
      invalidar();
      toast.success(
        r.baixas === 0
          ? "Nenhuma correspondência exata para baixar."
          : `${r.baixas} baixa(s) conciliada(s).`,
      );
    },
    onError: (e: unknown) =>
      toast.error(e instanceof Error ? e.message : "Falha na baixa automática."),
  });

  const conciliar = useMutation({
    mutationFn: (v: { id_lancamento: number; id_movimentacao: number }) =>
      api.pagamentos.conciliacao.conciliar(v),
    onSuccess: () => {
      setManual(null);
      setMovEscolhida(null);
      invalidar();
      toast.success("Lançamento conciliado.");
    },
    onError: (e: unknown) =>
      toast.error(e instanceof Error ? e.message : "Falha ao conciliar."),
  });

  function lerArquivo(f: File) {
    const leitor = new FileReader();
    leitor.onload = () => {
      const texto = typeof leitor.result === "string" ? leitor.result : "";
      setForm((s) => ({ ...s, conteudo: texto, nome_arquivo: s.nome_arquivo || f.name }));
    };
    leitor.onerror = () => setErroImport("Não foi possível ler o arquivo selecionado.");
    leitor.readAsText(f);
  }

  function fecharDialogoImport() {
    setImportOpen(false);
    setForm(formVazio());
    setErroImport(null);
    setRelatoImport(null);
  }

  function verExtratoImportado() {
    if (relatoImport) setExtratoSel(relatoImport.extrato);
    fecharDialogoImport();
  }

  async function confirmarBaixaAuto() {
    const ok = await confirm({
      title: "Baixa automática",
      message:
        `Conciliar de uma vez as ${exatas} correspondência(s) EXATA(S) deste extrato? ` +
        "Correspondências prováveis não são tocadas — essas continuam exigindo conferência.",
      confirmLabel: "Conciliar exatas",
    });
    if (ok) baixaAuto.mutate();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Landmark}
        breadcrumbs={[{ label: "Pagamentos", href: "/m/pagamentos" }, { label: "Conciliação" }]}
        title="Conciliação bancária"
        description="Importe o extrato da conta e case cada lançamento com o pagamento correspondente. Quando todas as movimentações de um débito pago ficam conciliadas, ele passa a CONCILIADO automaticamente."
        actions={
          <Button
            onClick={() => {
              setForm(formVazio());
              setErroImport(null);
              setRelatoImport(null);
              setImportOpen(true);
            }}
          >
            <FileUp className="mr-2 h-4 w-4" />
            Importar extrato
          </Button>
        }
      />

      <SectionCard title="Extratos importados">
        <div className="mb-4 flex items-center gap-3">
          <Label htmlFor="filtro-conta" className="whitespace-nowrap text-sm">
            Conta
          </Label>
          <Select
            id="filtro-conta"
            className="max-w-xs"
            value={contaFiltro ?? ""}
            onChange={(e) => {
              const v = e.target.value;
              setContaFiltro(v === "" ? null : Number(v));
              setExtratoSel(null);
            }}
          >
            <option value="">Todas</option>
            {contas.map((c) => (
              <option key={c.id_conta} value={c.id_conta}>
                {c.nome}
              </option>
            ))}
          </Select>
        </div>

        {extratosQ.isLoading ? (
          <p className="text-sm text-muted">Carregando…</p>
        ) : extratos.length === 0 ? (
          <EmptyState
            icon={FileUp}
            title="Nenhum extrato importado"
            description="Importe um CSV do banco para começar a conciliar os pagamentos desta conta."
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Arquivo</TH>
                <TH>Conta</TH>
                <TH>Período</TH>
                <TH className="text-right">Lançamentos</TH>
                <TH>Importado em</TH>
              </TR>
            </THead>
            <TBody>
              {extratos.map((e) => (
                <TR
                  key={e.id}
                  onClick={() => setExtratoSel(e)}
                  className={
                    extratoSel?.id === e.id
                      ? "cursor-pointer bg-surface-2"
                      : "cursor-pointer hover:bg-surface-2"
                  }
                >
                  <TD className="font-medium">{e.nome_arquivo}</TD>
                  <TD>{nomeConta(e.id_conta)}</TD>
                  <TD>
                    {fmtData(e.periodo_inicio)} — {fmtData(e.periodo_fim)}
                  </TD>
                  <TD className="text-right tabular-nums">{e.qtd_lancamentos}</TD>
                  <TD>{fmtDataHora(e.importado_em)}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </SectionCard>

      {extratoSel && (
        <>
          <SectionCard
            title="Sugestões de baixa"
            description="EXATA = mesmo valor e mesma data. PROVÁVEL = mesmo valor, até 3 dias de diferença — confira antes de conciliar."
          >
            {exatas > 0 && (
              <div className="mb-4 flex justify-end">
                <Button
                  variant="secondary"
                  onClick={confirmarBaixaAuto}
                  disabled={baixaAuto.isPending}
                >
                  <CheckCheck className="mr-2 h-4 w-4" />
                  Baixar {exatas} exata{exatas > 1 ? "s" : ""}
                </Button>
              </div>
            )}
            {sugestoesQ.isLoading ? (
              <p className="text-sm text-muted">Carregando…</p>
            ) : sugestoes.length === 0 ? (
              <EmptyState
                icon={ListChecks}
                title="Nenhuma correspondência encontrada"
                description={
                  pendentes === 0
                    ? "Todos os lançamentos deste extrato já estão conciliados."
                    : "Os lançamentos pendentes não casaram com nenhum pagamento em aberto desta conta. Use a conciliação manual abaixo."
                }
              />
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>Lançamento do extrato</TH>
                    <TH className="text-right">Valor</TH>
                    <TH>Pagamento correspondente</TH>
                    <TH>Correspondência</TH>
                    <TH />
                  </TR>
                </THead>
                <TBody>
                  {sugestoes.map((s) => (
                    <TR key={s.id_lancamento}>
                      <TD>
                        <div className="font-medium">{s.lancamento_historico}</div>
                        <div className="text-xs text-muted">{fmtData(s.lancamento_data)}</div>
                      </TD>
                      <TD className="text-right tabular-nums">{fmtMoeda(s.lancamento_valor)}</TD>
                      <TD>
                        <div>{s.nome_fornecedor ?? "—"}</div>
                        <div className="text-xs text-muted">
                          {fmtData(s.movimentacao_data)}
                          {s.id_debito ? ` · débito #${s.id_debito}` : ""}
                        </div>
                      </TD>
                      <TD>
                        <Badge intent={s.tipo_correspondencia === "EXATA" ? "success" : "warning"}>
                          {s.tipo_correspondencia === "EXATA" ? "Exata" : "Provável"}
                        </Badge>
                      </TD>
                      <TD className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={conciliar.isPending}
                          onClick={() =>
                            conciliar.mutate({
                              id_lancamento: s.id_lancamento,
                              id_movimentacao: s.id_movimentacao,
                            })
                          }
                        >
                          <Link2 className="mr-1 h-3.5 w-3.5" />
                          Conciliar
                        </Button>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </SectionCard>

          <SectionCard
            title="Lançamentos do extrato"
            description={`${pendentes} pendente(s) de ${lancamentos.length}.`}
          >
            {/* Export (C1.3). Dentro do card, e não no header dele, porque
                `SectionCard` não tem slot de ação — mexer no componente
                compartilhado por causa de um botão teria raio de alcance
                maior que o da fatia. */}
            {extratoSel && (
              <div className="flex justify-end">
                <BotaoExportarCsv
                  csvUrl={api.pagamentos.conciliacao.lancamentosCsvUrl(extratoSel.id)}
                  rotulo="lançamentos do extrato"
                />
              </div>
            )}
            {lancamentosQ.isLoading ? (
              <p className="text-sm text-muted">Carregando…</p>
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>Data</TH>
                    <TH>Histórico</TH>
                    <TH>Documento</TH>
                    <TH>Favorecido</TH>
                    <TH className="text-right">Valor</TH>
                    <TH>Tipo</TH>
                    <TH>Situação</TH>
                    <TH />
                  </TR>
                </THead>
                <TBody>
                  {lancamentos.map((l) => (
                    <TR key={l.id}>
                      <TD>{fmtData(l.data)}</TD>
                      <TD className="font-medium">{l.historico}</TD>
                      <TD>{l.documento ?? "—"}</TD>
                      <TD>{l.favorecido ?? "—"}</TD>
                      <TD className="text-right tabular-nums">{fmtMoeda(l.valor)}</TD>
                      <TD>{l.tipo === "DEBITO" ? "Débito" : "Crédito"}</TD>
                      <TD>
                        <Badge intent={l.conciliado ? "success" : "neutral"}>
                          {l.conciliado ? "Conciliado" : "Pendente"}
                        </Badge>
                      </TD>
                      <TD className="text-right">
                        {!l.conciliado && l.tipo === "DEBITO" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setManual(l);
                              setMovEscolhida(null);
                            }}
                          >
                            Conciliar manualmente
                          </Button>
                        )}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </SectionCard>
        </>
      )}

      <Dialog
        open={importOpen}
        onClose={fecharDialogoImport}
        title={relatoImport ? "Extrato importado" : "Importar extrato bancário"}
        footer={
          relatoImport ? (
            <Button onClick={verExtratoImportado}>
              <Link2 className="mr-2 h-4 w-4" />
              Ver extrato
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={fecharDialogoImport}>
                Cancelar
              </Button>
              <Button
                onClick={() => importar.mutate()}
                disabled={
                  importar.isPending ||
                  !form.id_conta ||
                  !form.nome_arquivo.trim() ||
                  !form.conteudo.trim()
                }
              >
                Importar
              </Button>
            </>
          )
        }
      >
        {relatoImport ? (
          <div className="space-y-4" data-testid="relato-importacao">
            <div className="flex items-start gap-3 rounded-card border border-success/30 bg-success-soft p-3 text-sm text-success-soft-foreground">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                {relatoImport.total_no_arquivo} linha(s) no arquivo — {relatoImport.importados}{" "}
                importado(s).
              </p>
            </div>

            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-card border border-border bg-surface-1 p-3">
                <dt className="text-xs text-muted">Ignorados por ID externo</dt>
                <dd className="text-lg font-semibold tabular-nums">
                  {relatoImport.ignorados_por_id_externo} ignorado(s)
                </dd>
              </div>
              <div className="rounded-card border border-border bg-surface-1 p-3">
                <dt className="text-xs text-muted">Possíveis duplicatas</dt>
                <dd className="text-lg font-semibold tabular-nums">
                  {relatoImport.possiveis_duplicatas} possível duplicata(s)
                </dd>
              </div>
            </dl>

            {relatoImport.possiveis_duplicatas > 0 && (
              <div className="flex items-start gap-2 rounded-card border border-warning/30 bg-warning-soft p-3 text-xs text-warning-soft-foreground">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <p>
                  Possível duplicata: já existe lançamento com a mesma data, valor e tipo
                  nesta conta. Elas <strong>não foram puladas</strong> — dois pagamentos
                  iguais no mesmo dia podem ser legítimos. Confira antes de conciliar.
                </p>
              </div>
            )}

            {relatoImport.ignorados_por_id_externo > 0 && (
              <p className="text-xs text-muted">
                Linhas ignoradas por ID externo já tinham o mesmo identificador do banco
                (FITID/documento) importado antes nesta conta — não foram duplicadas.
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <Label htmlFor="imp-conta">Conta</Label>
              <Select
                id="imp-conta"
                value={form.id_conta ?? ""}
                onChange={(e) =>
                  setForm((s) => ({
                    ...s,
                    id_conta: e.target.value === "" ? null : Number(e.target.value),
                  }))
                }
              >
                <option value="">Selecione…</option>
                {contas.map((c) => (
                  <option key={c.id_conta} value={c.id_conta}>
                    {c.nome}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <Label htmlFor="imp-formato">Formato do arquivo</Label>
              <Select
                id="imp-formato"
                value={form.formato}
                onChange={(e) => {
                  const formato = e.target.value as FormatoExtrato;
                  setForm((s) => ({ ...s, formato, conteudo: "", nome_arquivo: "" }));
                  if (arquivoRef.current) arquivoRef.current.value = "";
                }}
              >
                <option value="CSV">CSV</option>
                <option value="OFX">OFX</option>
                <option value="CNAB240">CNAB240</option>
              </Select>
            </div>

            <div>
              <Label htmlFor="imp-arquivo">Arquivo</Label>
              <Input
                id="imp-arquivo"
                ref={arquivoRef}
                type="file"
                accept={ACCEPT_POR_FORMATO[form.formato]}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) lerArquivo(f);
                }}
              />
              {form.formato === "CSV" && (
                <p className="mt-1 text-xs text-muted">
                  Colunas: <code>{MODELO_CSV}</code>. Separador <code>;</code> ou{" "}
                  <code>,</code>; cabeçalho opcional; tipo <code>CREDITO</code> ou{" "}
                  <code>DEBITO</code>.
                </p>
              )}
              {form.formato === "OFX" && (
                <p className="mt-1 text-xs text-muted">Extrato OFX (versão 1.x SGML ou 2.x XML).</p>
              )}
              {form.formato === "CNAB240" && (
                <p className="mt-1 text-xs text-muted">
                  Retorno CNAB240 (layout FEBRABAN, registros de 240 posições).
                </p>
              )}
            </div>

            <div>
              <Label htmlFor="imp-nome">Nome do arquivo</Label>
              <Input
                id="imp-nome"
                value={form.nome_arquivo}
                onChange={(e) => setForm((s) => ({ ...s, nome_arquivo: e.target.value }))}
                placeholder="extrato-julho.csv"
              />
            </div>

            {form.formato === "CSV" && (
              <div>
                <Label htmlFor="imp-conteudo">Conteúdo</Label>
                <Textarea
                  id="imp-conteudo"
                  rows={8}
                  className="font-mono text-xs"
                  value={form.conteudo}
                  onChange={(e) => setForm((s) => ({ ...s, conteudo: e.target.value }))}
                  placeholder={`${MODELO_CSV}\n01/07/2026;PAGAMENTO FORNECEDOR;DOC123;ACME LTDA;1234,56;DEBITO`}
                />
                <p className="mt-1 text-xs text-muted">
                  Também pode colar o conteúdo aqui em vez de escolher um arquivo.
                </p>
              </div>
            )}

            <p className="text-xs text-muted">
              Reimportar o mesmo arquivo na mesma conta é recusado — a checagem é por hash
              do conteúdo.
            </p>

            {erroImport && (
              <p className="text-sm text-danger" role="alert">
                {erroImport}
              </p>
            )}
          </div>
        )}
      </Dialog>

      <Dialog
        open={!!manual}
        onClose={() => setManual(null)}
        title="Conciliação manual"
        footer={
          <>
            <Button variant="ghost" onClick={() => setManual(null)}>
              Cancelar
            </Button>
            <Button
              disabled={!movEscolhida || conciliar.isPending}
              onClick={() =>
                manual &&
                conciliar.mutate({
                  id_lancamento: manual.id,
                  id_movimentacao: movEscolhida!,
                })
              }
            >
              Conciliar
            </Button>
          </>
        }
      >
        {manual && (
          <div className="space-y-4">
            <div className="rounded-card border border-border bg-surface-1 p-3 text-sm">
              <div className="font-medium">{manual.historico}</div>
              <div className="text-muted">
                {fmtData(manual.data)} · {fmtMoeda(manual.valor)}
                {manual.favorecido ? ` · ${manual.favorecido}` : ""}
              </div>
            </div>

            <div>
              <Label htmlFor="mov-alvo">Pagamento a vincular</Label>
              <Select
                id="mov-alvo"
                value={movEscolhida ?? ""}
                onChange={(e) =>
                  setMovEscolhida(e.target.value === "" ? null : Number(e.target.value))
                }
              >
                <option value="">Selecione…</option>
                {movsPagamento.map((m) => (
                  <option key={m.id} value={m.id}>
                    {fmtData(m.data)} — {fmtMoeda(m.valor)}
                    {m.descricao ? ` — ${m.descricao}` : ""}
                  </option>
                ))}
              </Select>
              <p className="mt-1 text-xs text-muted">
                Só saídas de pagamento desta conta. As já conciliadas são recusadas pelo
                servidor.
              </p>
            </div>

          </div>
        )}
      </Dialog>
    </div>
  );
}
