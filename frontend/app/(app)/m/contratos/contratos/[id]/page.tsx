"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { type ReactNode, useState } from "react";

import {
  ErroFormulario,
  ROTA_CONTRATOS,
  SituacaoAditivoBadge,
  SituacaoContratoBadge,
  TRANSACAO_CONTRATO,
  VencimentoBadge,
  fmtPercentual,
  isoEmDias,
  nullify,
} from "@/components/contratos/comum";
import { fmtData, fmtMoeda } from "@/components/pagamentos/format";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { KpiCard } from "@/components/ui/kpi-card";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  CATEGORIA_CONTRATO_LABEL,
  TIPO_APOSTILA_LABEL,
  api,
  type ContratoAditivo,
  type ContratoDetalhe,
  type TipoAditivo,
  type TipoApostila,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Tipos de aditivo que alteram o prazo — os demais não levam nova data final. */
const ADITIVO_COM_PRAZO: ReadonlySet<TipoAditivo> = new Set(["AP", "PA", "PR", "RE"]);
const APOSTILA_COM_VALOR: ReadonlySet<TipoApostila> = new Set(["REAJUSTE", "REPACTUACAO"]);
const TIPOS_APOSTILA = Object.keys(TIPO_APOSTILA_LABEL) as TipoApostila[];

const NATUREZA_LABEL: Record<string, string> = {
  CONTINUO: "Contínuo",
  ESCOPO: "Escopo",
};

interface AditivoForm {
  numero: string;
  tipo: TipoAditivo;
  data_assinatura: string;
  valor: string;
  nova_vigencia_fim: string;
  justificativa: string;
}

const ADITIVO_VAZIO: AditivoForm = {
  numero: "",
  tipo: "AP",
  data_assinatura: "",
  valor: "",
  nova_vigencia_fim: "",
  justificativa: "",
};

interface ApostilaForm {
  tipo: TipoApostila;
  data: string;
  valor_delta: string;
  indice: string;
  descricao: string;
}

const APOSTILA_VAZIA: ApostilaForm = {
  tipo: "REAJUSTE",
  data: "",
  valor_delta: "",
  indice: "",
  descricao: "",
};

function Campo({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{rotulo}</dt>
      <dd className="text-sm text-foreground">{children}</dd>
    </div>
  );
}

export default function ContratoDetalhePage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const { can } = useAuth();
  const podeInserir = can(TRANSACAO_CONTRATO, "inserir");
  const podeAtualizar = can(TRANSACAO_CONTRATO, "atualizar");
  const podeExcluir = can(TRANSACAO_CONTRATO, "excluir");

  const [aditivoAberto, setAditivoAberto] = useState(false);
  const [aditivo, setAditivo] = useState<AditivoForm>(ADITIVO_VAZIO);
  const [aditivoErr, setAditivoErr] = useState<string | null>(null);

  const [apostilaAberta, setApostilaAberta] = useState(false);
  const [apostila, setApostila] = useState<ApostilaForm>(APOSTILA_VAZIA);
  const [apostilaErr, setApostilaErr] = useState<string | null>(null);

  // Encerrar e rescindir dividem o diálogo: a diferença é o motivo obrigatório.
  const [fim, setFim] = useState<null | "encerrar" | "rescindir">(null);
  const [fimData, setFimData] = useState("");
  const [fimMotivo, setFimMotivo] = useState("");
  const [fimErr, setFimErr] = useState<string | null>(null);

  const [anulando, setAnulando] = useState<ContratoAditivo | null>(null);
  const [anularMotivo, setAnularMotivo] = useState("");
  const [anularErr, setAnularErr] = useState<string | null>(null);

  const contratoQ = useQuery({
    queryKey: ["contrato", id],
    queryFn: () => api.contratos.get(id),
    enabled: Number.isFinite(id),
  });
  const catalogosQ = useQuery({
    queryKey: ["contratos-catalogos"],
    queryFn: api.contratos.catalogos,
  });

  function recarregar() {
    qc.invalidateQueries({ queryKey: ["contrato", id] });
    qc.invalidateQueries({ queryKey: ["contratos-lista"] });
    qc.invalidateQueries({ queryKey: ["contratos-painel"] });
    qc.invalidateQueries({ queryKey: ["contratos-vencendo"] });
  }

  const erroToast = (e: Error) => toast.error(e.message);

  const assinarM = useMutation({
    mutationFn: () => api.contratos.assinar(id),
    onSuccess: () => {
      recarregar();
      toast.success("Contrato assinado. Valor e vigência originais estão congelados.");
    },
    onError: erroToast,
  });

  const excluirM = useMutation({
    mutationFn: () => api.contratos.remove(id),
    onSuccess: () => {
      recarregar();
      toast.success("Rascunho excluído.");
      router.push(ROTA_CONTRATOS);
    },
    onError: erroToast,
  });

  const fimM = useMutation({
    mutationFn: () =>
      fim === "rescindir"
        ? api.contratos.rescindir(id, { data_encerramento: fimData, motivo: fimMotivo.trim() })
        : api.contratos.encerrar(id, { data_encerramento: fimData }),
    onSuccess: () => {
      recarregar();
      toast.success(fim === "rescindir" ? "Contrato rescindido." : "Contrato encerrado.");
      setFim(null);
    },
    onError: (e: Error) => setFimErr(e.message),
  });

  const criarAditivoM = useMutation({
    mutationFn: () =>
      api.contratos.aditivos.create(id, {
        numero: aditivo.numero.trim(),
        tipo: aditivo.tipo,
        data_assinatura: aditivo.data_assinatura,
        // Aditivo só de prazo vai com zero — é a regra do SIM e do backend.
        valor: aditivo.tipo === "AP" ? "0" : aditivo.valor,
        nova_vigencia_fim: ADITIVO_COM_PRAZO.has(aditivo.tipo)
          ? nullify(aditivo.nova_vigencia_fim)
          : null,
        justificativa: nullify(aditivo.justificativa),
      }),
    onSuccess: () => {
      recarregar();
      toast.success("Aditivo registrado em rascunho. Assine para ele passar a valer.");
      setAditivoAberto(false);
      setAditivo(ADITIVO_VAZIO);
    },
    onError: (e: Error) => setAditivoErr(e.message),
  });

  const assinarAditivoM = useMutation({
    mutationFn: (aditivoId: number) => api.contratos.aditivos.assinar(id, aditivoId),
    onSuccess: () => {
      recarregar();
      toast.success("Aditivo assinado.");
    },
    onError: erroToast,
  });

  const excluirAditivoM = useMutation({
    mutationFn: (aditivoId: number) => api.contratos.aditivos.remove(id, aditivoId),
    onSuccess: () => {
      recarregar();
      toast.success("Aditivo excluído.");
    },
    onError: erroToast,
  });

  const anularM = useMutation({
    mutationFn: () =>
      api.contratos.aditivos.anular(id, anulando!.id, { motivo: anularMotivo.trim() }),
    onSuccess: () => {
      recarregar();
      toast.success("Aditivo anulado.");
      setAnulando(null);
      setAnularMotivo("");
    },
    onError: (e: Error) => setAnularErr(e.message),
  });

  const criarApostilaM = useMutation({
    mutationFn: () =>
      api.contratos.apostilas.create(id, {
        tipo: apostila.tipo,
        data: apostila.data,
        valor_delta: APOSTILA_COM_VALOR.has(apostila.tipo) ? nullify(apostila.valor_delta) : null,
        indice: APOSTILA_COM_VALOR.has(apostila.tipo) ? nullify(apostila.indice) : null,
        descricao: apostila.descricao.trim(),
      }),
    onSuccess: () => {
      recarregar();
      toast.success("Apostila registrada.");
      setApostilaAberta(false);
      setApostila(APOSTILA_VAZIA);
    },
    onError: (e: Error) => setApostilaErr(e.message),
  });

  const excluirApostilaM = useMutation({
    mutationFn: (apostilaId: number) => api.contratos.apostilas.remove(id, apostilaId),
    onSuccess: () => {
      recarregar();
      toast.success("Apostila excluída.");
    },
    onError: erroToast,
  });

  function salvarAditivo() {
    setAditivoErr(null);
    const comPrazo = ADITIVO_COM_PRAZO.has(aditivo.tipo);
    if (!aditivo.numero.trim() || !aditivo.data_assinatura) {
      setAditivoErr("Informe o número e a data de assinatura.");
      return;
    }
    if (aditivo.tipo !== "AP" && !(Number(aditivo.valor) > 0)) {
      setAditivoErr("Informe o valor: a diferença, sempre positiva — inclusive em redução.");
      return;
    }
    if (comPrazo && !aditivo.nova_vigencia_fim) {
      setAditivoErr("Este tipo de aditivo altera o prazo: informe a nova data final.");
      return;
    }
    criarAditivoM.mutate();
  }

  function salvarApostila() {
    setApostilaErr(null);
    if (!apostila.data || apostila.descricao.trim().length < 3) {
      setApostilaErr("Informe a data e a descrição.");
      return;
    }
    if (APOSTILA_COM_VALOR.has(apostila.tipo) && apostila.valor_delta === "") {
      setApostilaErr("Reajuste e repactuação exigem o valor da variação.");
      return;
    }
    criarApostilaM.mutate();
  }

  function salvarFim() {
    setFimErr(null);
    if (!fimData) {
      setFimErr("Informe a data.");
      return;
    }
    if (fim === "rescindir" && fimMotivo.trim().length < 5) {
      setFimErr("Informe o motivo da rescisão.");
      return;
    }
    fimM.mutate();
  }

  if (contratoQ.isLoading) {
    return <div className="py-8 text-center text-muted-foreground">Carregando...</div>;
  }
  if (contratoQ.isError || !contratoQ.data) {
    return (
      <Alert intent="danger" title="Contrato não encontrado">
        {(contratoQ.error as Error | null)?.message ?? "O contrato não existe ou foi excluído."}
      </Alert>
    );
  }

  const c: ContratoDetalhe = contratoQ.data;
  const calc = c.calculo;
  const rotuloTipoObjeto =
    catalogosQ.data?.tipos_objeto.find((t) => t.codigo === c.tipo_objeto)?.rotulo ?? c.tipo_objeto;
  const rotuloAditivo = (tipo: string) =>
    catalogosQ.data?.tipos_aditivo.find((t) => t.codigo === tipo)?.rotulo ?? tipo;
  const rascunho = c.situacao === "RASCUNHO";
  const vigente = c.situacao === "VIGENTE";

  return (
    <div className="space-y-6">
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            <span>Contrato {c.numero}</span>
            <SituacaoContratoBadge situacao={c.situacao} />
            <VencimentoBadge dias={calc.dias_para_vencer} />
          </span>
        }
        description={c.fornecedor_nome ?? undefined}
        breadcrumbs={[
          { label: "Contratos e Convênios", href: "/m/contratos" },
          { label: "Contratos", href: ROTA_CONTRATOS },
          { label: c.numero },
        ]}
        actions={
          <div className="flex flex-wrap gap-2">
            {rascunho && podeAtualizar && (
              <Button
                loading={assinarM.isPending}
                onClick={async () => {
                  const ok = await confirm({
                    title: "Assinar contrato",
                    message:
                      "Depois de assinado, número, objeto, valor e vigência só mudam por aditivo ou apostila. Assinar agora?",
                  });
                  if (ok) assinarM.mutate();
                }}
              >
                Assinar
              </Button>
            )}
            {rascunho && podeExcluir && (
              <Button
                variant="danger"
                loading={excluirM.isPending}
                onClick={async () => {
                  const ok = await confirm({
                    title: "Excluir rascunho",
                    message: `Excluir o rascunho do contrato "${c.numero}"?`,
                  });
                  if (ok) excluirM.mutate();
                }}
              >
                Excluir rascunho
              </Button>
            )}
            {vigente && podeAtualizar && (
              <>
                <Button
                  variant="secondary"
                  onClick={() => {
                    setFim("encerrar");
                    setFimData(isoEmDias(0));
                    setFimMotivo("");
                    setFimErr(null);
                  }}
                >
                  Encerrar
                </Button>
                <Button
                  variant="danger"
                  onClick={() => {
                    setFim("rescindir");
                    setFimData(isoEmDias(0));
                    setFimMotivo("");
                    setFimErr(null);
                  }}
                >
                  Rescindir
                </Button>
              </>
            )}
          </div>
        }
      />

      {rascunho && (
        <Alert intent="info" title="Contrato em rascunho">
          Ainda não vale como contrato. Para assinar são exigidos a data de celebração, o tipo
          de objeto, a natureza da duração e um número de até 15 caracteres.
        </Alert>
      )}
      {calc.acima_do_limite && (
        <Alert intent="warning" title="Acima do limite do art. 125 da Lei 14.133">
          Acréscimos em {fmtPercentual(calc.percentual_acrescimo)} (limite{" "}
          {fmtPercentual(calc.limite_acrescimo)}) e supressões em{" "}
          {fmtPercentual(calc.percentual_supressao)} (limite{" "}
          {fmtPercentual(calc.limite_supressao)}), sobre o valor inicial atualizado. O sistema
          sinaliza; a justificativa está no aditivo.
        </Alert>
      )}
      {c.situacao === "RESCINDIDO" && c.motivo_rescisao && (
        <Alert intent="danger" title={`Rescindido em ${fmtData(c.data_encerramento)}`}>
          {c.motivo_rescisao}
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard
          label="Valor atualizado"
          value={fmtMoeda(calc.valor_atualizado)}
          hint={`Original: ${fmtMoeda(calc.valor_inicial)}`}
        />
        <KpiCard
          label="Vigência até"
          value={fmtData(calc.vigencia_fim_atual)}
          hint={`Original: ${fmtData(c.vigencia_fim)}`}
        />
        <KpiCard
          label="Acréscimos"
          value={fmtPercentual(calc.percentual_acrescimo)}
          hint={`${fmtMoeda(calc.acrescimos)} · limite ${fmtPercentual(calc.limite_acrescimo)}`}
          intent={
            Number(calc.percentual_acrescimo) > Number(calc.limite_acrescimo) ? "warning" : "default"
          }
        />
        <KpiCard
          label="Supressões"
          value={fmtPercentual(calc.percentual_supressao)}
          hint={`${fmtMoeda(calc.supressoes)} · limite ${fmtPercentual(calc.limite_supressao)}`}
          intent={
            Number(calc.percentual_supressao) > Number(calc.limite_supressao) ? "warning" : "default"
          }
        />
      </div>

      <section className="space-y-3 rounded-lg border border-border bg-surface-1 p-4">
        <h2 className="text-sm font-semibold text-foreground">Dados do contrato</h2>
        <p className="text-sm text-foreground">{c.objeto}</p>
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Campo rotulo="Contratado">{c.fornecedor_nome ?? "—"}</Campo>
          <Campo rotulo="Unidade contratante">{c.unidade_nome ?? "—"}</Campo>
          <Campo rotulo="Exercício">{c.exercicio}</Campo>
          <Campo rotulo="Celebração">{fmtData(c.data_celebracao)}</Campo>
          <Campo rotulo="Vigência original">
            {fmtData(c.vigencia_inicio)} a {fmtData(c.vigencia_fim)}
          </Campo>
          <Campo rotulo="Valor original">{fmtMoeda(c.valor_total)}</Campo>
          <Campo rotulo="Tipo de objeto (SIM)">{rotuloTipoObjeto ?? "—"}</Campo>
          <Campo rotulo="Natureza da duração">
            {c.natureza_duracao ? NATUREZA_LABEL[c.natureza_duracao] : "—"}
            {c.reforma ? " · reforma" : ""}
          </Campo>
          <Campo rotulo="Categoria (fila de pagamentos)">
            {c.categoria ? CATEGORIA_CONTRATO_LABEL[c.categoria] : "—"}
          </Campo>
          <Campo rotulo="Processo de contratação">
            {c.processo_numero ?? "—"}
            {c.processo_data_autuacao ? ` · ${fmtData(c.processo_data_autuacao)}` : ""}
          </Campo>
          <Campo rotulo="PNCP">{c.pncp_id ?? "Não informado"}</Campo>
          <Campo rotulo="Publicado no PNCP em">{fmtData(c.pncp_publicado_em)}</Campo>
        </dl>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-foreground">Aditivos</h2>
          {vigente && podeInserir && (
            <Button
              size="sm"
              onClick={() => {
                setAditivo(ADITIVO_VAZIO);
                setAditivoErr(null);
                setAditivoAberto(true);
              }}
            >
              <Plus className="mr-1 h-4 w-4" />
              Novo aditivo
            </Button>
          )}
        </div>
        {c.aditivos.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhum aditivo registrado.</p>
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Nº</TH>
                <TH>Número</TH>
                <TH>Tipo</TH>
                <TH>Assinatura</TH>
                <TH className="text-right">Valor</TH>
                <TH>Nova vigência</TH>
                <TH>Situação</TH>
                <TH className="text-right">Ações</TH>
              </TR>
            </THead>
            <TBody>
              {c.aditivos.map((a) => (
                <TR key={a.id}>
                  <TD>{a.sequencial}º</TD>
                  <TD className="font-mono">{a.numero}</TD>
                  <TD>{rotuloAditivo(a.tipo)}</TD>
                  <TD>{fmtData(a.data_assinatura)}</TD>
                  <TD className="text-right tabular-nums">
                    {a.tipo === "AP" ? "—" : fmtMoeda(a.valor)}
                  </TD>
                  <TD>{fmtData(a.nova_vigencia_fim)}</TD>
                  <TD>
                    <SituacaoAditivoBadge situacao={a.situacao} />
                  </TD>
                  <TD className="text-right">
                    <div className="flex justify-end gap-2">
                      {a.situacao === "RASCUNHO" && vigente && podeAtualizar && (
                        <Button
                          size="sm"
                          disabled={assinarAditivoM.isPending}
                          onClick={() => assinarAditivoM.mutate(a.id)}
                        >
                          Assinar
                        </Button>
                      )}
                      {a.situacao === "RASCUNHO" && podeExcluir && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={async () => {
                            const ok = await confirm({
                              title: "Excluir aditivo",
                              message: `Excluir o rascunho do aditivo "${a.numero}"?`,
                            });
                            if (ok) excluirAditivoM.mutate(a.id);
                          }}
                        >
                          Excluir
                        </Button>
                      )}
                      {a.situacao === "VIGENTE" && podeAtualizar && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setAnulando(a);
                            setAnularMotivo("");
                            setAnularErr(null);
                          }}
                        >
                          Anular
                        </Button>
                      )}
                    </div>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-foreground">Apostilas</h2>
          {vigente && podeInserir && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setApostila(APOSTILA_VAZIA);
                setApostilaErr(null);
                setApostilaAberta(true);
              }}
            >
              <Plus className="mr-1 h-4 w-4" />
              Nova apostila
            </Button>
          )}
        </div>
        {c.apostilas.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma apostila registrada.</p>
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Nº</TH>
                <TH>Tipo</TH>
                <TH>Data</TH>
                <TH className="text-right">Variação</TH>
                <TH>Índice</TH>
                <TH>Descrição</TH>
                <TH className="text-right">Ações</TH>
              </TR>
            </THead>
            <TBody>
              {c.apostilas.map((p) => (
                <TR key={p.id}>
                  <TD>{p.sequencial}ª</TD>
                  <TD>{TIPO_APOSTILA_LABEL[p.tipo]}</TD>
                  <TD>{fmtData(p.data)}</TD>
                  <TD className="text-right tabular-nums">
                    {p.valor_delta === null ? "—" : fmtMoeda(p.valor_delta)}
                  </TD>
                  <TD>{p.indice ?? "—"}</TD>
                  <TD className="max-w-xs truncate text-sm" title={p.descricao}>
                    {p.descricao}
                  </TD>
                  <TD className="text-right">
                    {podeExcluir && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={async () => {
                          const ok = await confirm({
                            title: "Excluir apostila",
                            message: `Excluir a ${p.sequencial}ª apostila? O valor do contrato é recalculado.`,
                          });
                          if (ok) excluirApostilaM.mutate(p.id);
                        }}
                      >
                        Excluir
                      </Button>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </section>

      <Dialog
        open={aditivoAberto}
        onClose={() => setAditivoAberto(false)}
        title="Novo aditivo"
        description="O aditivo nasce em rascunho e só passa a valer depois de assinado."
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setAditivoAberto(false)}>
              Cancelar
            </Button>
            <Button onClick={salvarAditivo} loading={criarAditivoM.isPending}>
              Registrar
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <ErroFormulario mensagem={aditivoErr} />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="ad_tipo" required>
                Tipo
              </Label>
              <Select
                id="ad_tipo"
                value={aditivo.tipo}
                onChange={(e) => setAditivo((f) => ({ ...f, tipo: e.target.value as TipoAditivo }))}
              >
                {(catalogosQ.data?.tipos_aditivo ?? []).map((t) => (
                  <option key={t.codigo} value={t.codigo}>
                    {t.rotulo}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="ad_numero" required>
                Número
              </Label>
              <Input
                id="ad_numero"
                maxLength={15}
                value={aditivo.numero}
                onChange={(e) => setAditivo((f) => ({ ...f, numero: e.target.value }))}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Não pode repetir número de contrato do mesmo ano: no SIM os dois dividem a
                numeração.
              </p>
            </div>
            <div>
              <Label htmlFor="ad_data" required>
                Data de assinatura
              </Label>
              <Input
                id="ad_data"
                type="date"
                value={aditivo.data_assinatura}
                onChange={(e) => setAditivo((f) => ({ ...f, data_assinatura: e.target.value }))}
              />
            </div>
            {aditivo.tipo !== "AP" && (
              <div>
                <Label htmlFor="ad_valor" required>
                  Valor da diferença (R$)
                </Label>
                <Input
                  id="ad_valor"
                  type="number"
                  min="0"
                  step="0.01"
                  value={aditivo.valor}
                  onChange={(e) => setAditivo((f) => ({ ...f, valor: e.target.value }))}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  Sempre positivo — inclusive em redução.
                </p>
              </div>
            )}
            {ADITIVO_COM_PRAZO.has(aditivo.tipo) && (
              <div>
                <Label htmlFor="ad_vig" required>
                  Nova data final da vigência
                </Label>
                <Input
                  id="ad_vig"
                  type="date"
                  value={aditivo.nova_vigencia_fim}
                  onChange={(e) =>
                    setAditivo((f) => ({ ...f, nova_vigencia_fim: e.target.value }))
                  }
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  Vigência atual: {fmtData(calc.vigencia_fim_atual)}.
                </p>
              </div>
            )}
          </div>
          <div>
            <Label htmlFor="ad_just">Justificativa</Label>
            <Textarea
              id="ad_just"
              rows={3}
              maxLength={1000}
              value={aditivo.justificativa}
              onChange={(e) => setAditivo((f) => ({ ...f, justificativa: e.target.value }))}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Obrigatória para assinar quando o acumulado passa do limite do art. 125.
            </p>
          </div>
        </div>
      </Dialog>

      <Dialog
        open={apostilaAberta}
        onClose={() => setApostilaAberta(false)}
        title="Nova apostila"
        description="Para o que o art. 136 da Lei 14.133 dispensa de termo aditivo."
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setApostilaAberta(false)}>
              Cancelar
            </Button>
            <Button onClick={salvarApostila} loading={criarApostilaM.isPending}>
              Registrar
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <ErroFormulario mensagem={apostilaErr} />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="ap_tipo" required>
                Tipo
              </Label>
              <Select
                id="ap_tipo"
                value={apostila.tipo}
                onChange={(e) =>
                  setApostila((f) => ({ ...f, tipo: e.target.value as TipoApostila }))
                }
              >
                {TIPOS_APOSTILA.map((t) => (
                  <option key={t} value={t}>
                    {TIPO_APOSTILA_LABEL[t]}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="ap_data" required>
                Data
              </Label>
              <Input
                id="ap_data"
                type="date"
                value={apostila.data}
                onChange={(e) => setApostila((f) => ({ ...f, data: e.target.value }))}
              />
            </div>
            {APOSTILA_COM_VALOR.has(apostila.tipo) && (
              <>
                <div>
                  <Label htmlFor="ap_valor" required>
                    Variação do valor (R$)
                  </Label>
                  <Input
                    id="ap_valor"
                    type="number"
                    step="0.01"
                    value={apostila.valor_delta}
                    onChange={(e) => setApostila((f) => ({ ...f, valor_delta: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="ap_indice">Índice aplicado</Label>
                  <Input
                    id="ap_indice"
                    maxLength={60}
                    value={apostila.indice}
                    onChange={(e) => setApostila((f) => ({ ...f, indice: e.target.value }))}
                    placeholder="IPCA 12 meses 4,83%"
                  />
                </div>
              </>
            )}
          </div>
          <div>
            <Label htmlFor="ap_desc" required>
              Descrição
            </Label>
            <Textarea
              id="ap_desc"
              rows={3}
              maxLength={1000}
              value={apostila.descricao}
              onChange={(e) => setApostila((f) => ({ ...f, descricao: e.target.value }))}
            />
          </div>
        </div>
      </Dialog>

      <Dialog
        open={fim !== null}
        onClose={() => setFim(null)}
        title={fim === "rescindir" ? "Rescindir contrato" : "Encerrar contrato"}
        description="Situação final: depois disto o contrato não recebe mais aditivo nem apostila."
        footer={
          <>
            <Button variant="secondary" onClick={() => setFim(null)}>
              Cancelar
            </Button>
            <Button
              variant={fim === "rescindir" ? "danger" : "primary"}
              onClick={salvarFim}
              loading={fimM.isPending}
            >
              {fim === "rescindir" ? "Rescindir" : "Encerrar"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <ErroFormulario mensagem={fimErr} />
          <div>
            <Label htmlFor="fim_data" required>
              Data
            </Label>
            <Input
              id="fim_data"
              type="date"
              value={fimData}
              onChange={(e) => setFimData(e.target.value)}
            />
          </div>
          {fim === "rescindir" && (
            <div>
              <Label htmlFor="fim_motivo" required>
                Motivo
              </Label>
              <Textarea
                id="fim_motivo"
                rows={3}
                maxLength={500}
                value={fimMotivo}
                onChange={(e) => setFimMotivo(e.target.value)}
              />
            </div>
          )}
        </div>
      </Dialog>

      <Dialog
        open={anulando !== null}
        onClose={() => setAnulando(null)}
        title={anulando ? `Anular aditivo ${anulando.numero}` : "Anular aditivo"}
        description="O aditivo deixa de contar no valor e na vigência, e o registro permanece."
        footer={
          <>
            <Button variant="secondary" onClick={() => setAnulando(null)}>
              Cancelar
            </Button>
            <Button
              variant="danger"
              loading={anularM.isPending}
              onClick={() => {
                setAnularErr(null);
                if (anularMotivo.trim().length < 5) {
                  setAnularErr("Informe o motivo da anulação.");
                  return;
                }
                anularM.mutate();
              }}
            >
              Anular
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <ErroFormulario mensagem={anularErr} />
          <div>
            <Label htmlFor="anular_motivo" required>
              Motivo
            </Label>
            <Textarea
              id="anular_motivo"
              rows={3}
              maxLength={500}
              value={anularMotivo}
              onChange={(e) => setAnularMotivo(e.target.value)}
            />
          </div>
        </div>
      </Dialog>
    </div>
  );
}
