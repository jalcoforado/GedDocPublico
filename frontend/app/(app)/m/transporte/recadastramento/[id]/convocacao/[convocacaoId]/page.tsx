"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Ban,
  CarFront,
  CheckCircle2,
  ClipboardCheck,
  Inbox,
  RotateCcw,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, type RecadastramentoChecklistItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { WorkflowTimeline } from "@/components/transporte/WorkflowTimeline";

interface PageParams {
  params: Promise<{ id: string; convocacaoId: string }>;
}

type Ato = "deferir" | "indeferir" | "reabrir" | "suspender" | "reativar";

const ATO_TITULO: Record<Ato, string> = {
  deferir: "Deferir recadastramento",
  indeferir: "Indeferir recadastramento",
  reabrir: "Reabrir recadastramento",
  suspender: "Suspender por falta de recadastramento",
  reativar: "Reativar recadastramento",
};

const SITUACAO_INTENT: Record<string, "neutral" | "success" | "danger" | "info"> = {
  convocado: "neutral",
  em_analise: "info",
  deferido: "success",
  indeferido: "danger",
  suspenso: "danger",
};

const DECISAO_INTENT: Record<string, "success" | "danger" | "warning"> = {
  deferimento: "success",
  indeferimento: "danger",
  reabertura: "warning",
};

export default function AtendimentoRecadastramentoPage({ params }: PageParams) {
  const { id, convocacaoId } = use(params);
  const cicloId = Number(id);
  const convId = Number(convocacaoId);

  const { can } = useAuth();
  const canEdit = can("transporte_regulado", "atualizar");
  const qc = useQueryClient();
  const toast = useToast();

  const [ato, setAto] = useState<Ato | null>(null);
  const [parecer, setParecer] = useState("");
  const [atoErr, setAtoErr] = useState<string | null>(null);
  const [obs, setObs] = useState<Record<number, string>>({});

  const fichaQ = useQuery({
    queryKey: ["tr-recad-atendimento", convId],
    queryFn: () => api.recadastramento.atendimento.get(convId),
    enabled: Number.isFinite(convId),
  });

  const decisoesQ = useQuery({
    queryKey: ["tr-recad-decisoes", convId],
    queryFn: () => api.recadastramento.atendimento.decisoes(convId),
    enabled: Number.isFinite(convId),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["tr-recad-atendimento", convId] });
    qc.invalidateQueries({ queryKey: ["tr-recad-decisoes", convId] });
    qc.invalidateQueries({ queryKey: ["tr-recad-convocacoes", cicloId] });
  };

  const marcarM = useMutation({
    mutationFn: ({
      itemId,
      marcado,
      observacao,
    }: {
      itemId: number;
      marcado: boolean;
      observacao?: string | null;
    }) =>
      api.recadastramento.atendimento.marcar(convId, itemId, {
        marcado,
        observacao: observacao?.trim() ? observacao.trim() : null,
      }),
    // A resposta JÁ é a ficha atualizada; ainda assim invalidamos, porque o
    // histórico e a lista do ciclo mudam junto.
    onSuccess: (ficha) => {
      qc.setQueryData(["tr-recad-atendimento", convId], ficha);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const atoM = useMutation({
    mutationFn: () => {
      const dados = { parecer: parecer.trim() };
      if (ato === "deferir") return api.recadastramento.atendimento.deferir(convId, dados);
      if (ato === "indeferir")
        return api.recadastramento.atendimento.indeferir(convId, dados);
      if (ato === "suspender")
        return api.recadastramento.atendimento.suspender(convId, dados);
      if (ato === "reativar")
        return api.recadastramento.atendimento.reativar(convId, dados);
      return api.recadastramento.atendimento.reabrir(convId, dados);
    },
    onSuccess: () => {
      invalidate();
      toast.success("Registrado.");
      fecharAto();
    },
    onError: (e: Error) => setAtoErr(e.message),
  });

  function abrirAto(qual: Ato) {
    setAto(qual);
    setParecer("");
    setAtoErr(null);
  }

  function fecharAto() {
    setAto(null);
    setParecer("");
    setAtoErr(null);
  }

  function submeterAto() {
    setAtoErr(null);
    // Parecer obrigatório também no formulário: descobrir a regra por mensagem
    // de erro depois de digitar tudo é pior do que saber antes.
    if (parecer.trim().length < 5) {
      setAtoErr("O parecer é obrigatório (mínimo de 5 caracteres).");
      return;
    }
    atoM.mutate();
  }

  const ficha = fichaQ.data;

  if (fichaQ.isLoading) {
    return <div className="text-center text-muted-foreground py-8">Carregando...</div>;
  }
  if (fichaQ.isError || !ficha) {
    return (
      <EmptyState
        icon={Inbox}
        title="Convocação não encontrada"
        description="Ela pode ter sido excluída ou pertence a outro município."
      />
    );
  }

  const decidida = ficha.situacao === "deferido" || ficha.situacao === "indeferido";
  const suspensa = ficha.situacao === "suspenso";
  // Quem decide o atraso é o SERVIDOR (`em_atraso` na ficha). Recalcular aqui
  // com a data do navegador faria o botão aparecer ou sumir conforme o relógio
  // da máquina do atendente.
  const vencida = ficha.em_atraso;
  const vist = ficha.vistorias;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={ClipboardCheck}
        title={ficha.nome_regulado}
        description={
          ficha.tipo_regulado === "empresa"
            ? "Empresa regulada — conferência de documentos e vistorias."
            : "Permissionário — conferência de documentos e vistorias."
        }
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Recadastramento", href: "/m/transporte/recadastramento" },
          { label: "Convocados", href: `/m/transporte/recadastramento/${cicloId}` },
          { label: ficha.nome_regulado },
        ]}
        actions={
          canEdit ? (
            <div className="flex flex-wrap gap-2">
              {/* Suspensa tem UMA saída, e não duas: reativar. Oferecer
                  "Reabrir" aqui deixaria a trilha ambígua — uma suspensão
                  desfeita por reabertura não se distingue de um indeferimento
                  desfeito. O backend recusa, e a tela não deve nem sugerir. */}
              {suspensa ? (
                <Button variant="secondary" onClick={() => abrirAto("reativar")}>
                  <RotateCcw className="mr-1 h-4 w-4" />
                  Reativar
                </Button>
              ) : decidida ? (
                <Button variant="secondary" onClick={() => abrirAto("reabrir")}>
                  <RotateCcw className="mr-1 h-4 w-4" />
                  Reabrir
                </Button>
              ) : (
                <>
                  <Button
                    onClick={() => abrirAto("deferir")}
                    disabled={!ficha.pode_deferir}
                    title={
                      ficha.pode_deferir
                        ? undefined
                        : "Faltam itens obrigatórios ou vistorias"
                    }
                  >
                    <CheckCircle2 className="mr-1 h-4 w-4" />
                    Deferir
                  </Button>
                  {/* Indeferir NUNCA desabilita: indeferir por falta de
                      documento é justamente o caso real do balcão. */}
                  <Button variant="danger" onClick={() => abrirAto("indeferir")}>
                    <XCircle className="mr-1 h-4 w-4" />
                    Indeferir
                  </Button>
                  {/* Só aparece com o prazo vencido: o backend devolve 409
                      para suspensão prematura, e botão que só serve para
                      receber erro é armadilha. */}
                  {vencida && (
                    <Button
                      variant="danger"
                      onClick={() => abrirAto("suspender")}
                    >
                      <Ban className="mr-1 h-4 w-4" />
                      Suspender
                    </Button>
                  )}
                </>
              )}
            </div>
          ) : undefined
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <Badge intent={SITUACAO_INTENT[ficha.situacao] ?? "neutral"}>
          {ficha.situacao.replace("_", " ")}
        </Badge>
        {!decidida && !ficha.pode_deferir && (
          <span className="text-sm text-muted-foreground">
            Deferimento bloqueado:{" "}
            {ficha.itens_obrigatorios_pendentes.length > 0 &&
              `falta ${ficha.itens_obrigatorios_pendentes.join(", ")}`}
            {ficha.itens_obrigatorios_pendentes.length > 0 &&
              !vist.satisfeita &&
              " · "}
            {!vist.satisfeita && `${vist.pendentes.length} veículo(s) sem vistoria válida`}
          </span>
        )}
      </div>

      {/* ---------------------------------------------------------- checklist */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-muted-foreground">
          Documentos exigidos
        </h2>
        {ficha.itens.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="Nenhum item no catálogo"
            description="Sem itens cadastrados, não há o que conferir — qualquer convocação pode ser deferida direto."
            action={
              <Button variant="secondary" asChild>
                <Link href="/m/transporte/recadastramento/itens">Cadastrar itens</Link>
              </Button>
            }
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Documento</TH>
                <TH>Situação</TH>
                <TH>Observação</TH>
                <TH className="text-right">Ações</TH>
              </TR>
            </THead>
            <TBody>
              {ficha.itens.map((i: RecadastramentoChecklistItem) => (
                <TR key={i.id_item}>
                  <TD className="font-medium">
                    <div className="flex flex-wrap items-center gap-2">
                      {i.descricao}
                      {i.obrigatorio && <Badge intent="warning">obrigatório</Badge>}
                    </div>
                  </TD>
                  <TD>
                    {/* Três estados, não dois: `null` é "ninguém olhou", que
                        não é a mesma coisa que "olhou e não está em ordem". */}
                    {i.marcado === null ? (
                      <Badge intent="neutral">não conferido</Badge>
                    ) : i.marcado ? (
                      <Badge intent="success">em ordem</Badge>
                    ) : (
                      <Badge intent="danger">não apresentado</Badge>
                    )}
                  </TD>
                  <TD className="text-sm text-muted-foreground">
                    {i.observacao ?? "—"}
                  </TD>
                  <TD className="text-right">
                    {canEdit && !decidida && (
                      <div className="inline-flex flex-wrap justify-end items-center gap-2">
                        <Input
                          className="w-44"
                          placeholder="Observação"
                          value={obs[i.id_item] ?? ""}
                          onChange={(e) =>
                            setObs({ ...obs, [i.id_item]: e.target.value })
                          }
                        />
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={marcarM.isPending}
                          onClick={() =>
                            marcarM.mutate({
                              itemId: i.id_item,
                              marcado: true,
                              observacao: obs[i.id_item],
                            })
                          }
                        >
                          Em ordem
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={marcarM.isPending}
                          onClick={() =>
                            marcarM.mutate({
                              itemId: i.id_item,
                              marcado: false,
                              observacao: obs[i.id_item],
                            })
                          }
                        >
                          Não apresentado
                        </Button>
                      </div>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </section>

      {/* --------------------------------------------------------- vistorias */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-muted-foreground">
          Vistoria dos veículos
        </h2>
        {/* TRÊS estados distintos, e não um selo verde para dois deles.
            "Nenhum veículo cadastrado" satisfaz a regra por vacuidade, mas
            não é a mesma coisa que "todos em dia" — colapsar os dois
            esconderia cadastro incompleto. */}
        {vist.total_veiculos_ativos === 0 ? (
          <div className="flex items-start gap-2 rounded-md border border-dashed p-3 text-sm">
            <CarFront className="mt-0.5 h-4 w-4 text-muted-foreground" aria-hidden="true" />
            <div>
              <div className="font-medium">Nenhum veículo ativo cadastrado</div>
              <p className="text-muted-foreground">
                A exigência de vistoria não se aplica. Confira se o cadastro está
                completo antes de deferir.
              </p>
            </div>
          </div>
        ) : vist.satisfeita ? (
          <div className="flex items-start gap-2 rounded-md border p-3 text-sm">
            <CheckCircle2 className="mt-0.5 h-4 w-4 text-success" aria-hidden="true" />
            <div>
              <div className="font-medium">
                {vist.total_veiculos_ativos} veículo(s) com vistoria aprovada válida
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-2 rounded-md border border-warning p-3 text-sm">
            <div className="flex items-center gap-2 font-medium">
              <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" />
              {vist.pendentes.length} de {vist.total_veiculos_ativos} veículo(s)
              sem vistoria aprovada válida
            </div>
            <ul className="ml-6 list-disc text-muted-foreground">
              {vist.pendentes.map((v) => (
                <li key={v.id_veiculo}>
                  <span className="font-mono">{v.placa}</span> — {v.motivo}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {/* ---------------------------------------------------------- workflow */}
      <WorkflowTimeline entidadeTipo="convocacao" entidadeId={convId} />

      {/* --------------------------------------------------------- histórico */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-muted-foreground">
          Histórico de decisões
        </h2>
        {(decisoesQ.data?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma decisão registrada.</p>
        ) : (
          <ul className="space-y-2">
            {decisoesQ.data?.map((d) => (
              <li key={d.id} className="rounded-md border p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge intent={DECISAO_INTENT[d.tipo] ?? "neutral"}>{d.tipo}</Badge>
                  <span className="text-muted-foreground">
                    {new Date(d.criado_em).toLocaleString("pt-BR")}
                  </span>
                </div>
                <p className="mt-1 whitespace-pre-wrap">{d.parecer}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Dialog
        open={ato !== null}
        onClose={fecharAto}
        title={ato ? ATO_TITULO[ato] : ""}
        footer={
          <>
            <Button variant="secondary" onClick={fecharAto}>
              Cancelar
            </Button>
            <Button
              onClick={submeterAto}
              disabled={atoM.isPending}
              variant={ato === "indeferir" ? "danger" : "primary"}
            >
              {atoM.isPending ? "Registrando..." : "Confirmar"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          {atoErr && <div className="text-sm text-danger">{atoErr}</div>}
          {ato === "suspender" && (
            <p className="text-sm text-muted-foreground">
              A suspensão vale para <strong>esta convocação</strong>: não altera a
              situação do cadastro do regulado nem os alvarás. Enquanto suspensa,
              a ficha não aceita marcação nem decisão.
            </p>
          )}
          {ato === "reativar" && (
            <p className="text-sm text-muted-foreground">
              Reativar devolve a convocação para atendimento. As marcações já
              feitas continuam valendo, e a suspensão permanece no histórico.
            </p>
          )}
          {ato === "reabrir" && (
            <p className="text-sm text-muted-foreground">
              A decisão anterior permanece no histórico. Reabrir devolve a convocação
              para análise.
            </p>
          )}
          <div>
            <Label htmlFor="parecer">Parecer</Label>
            <Textarea
              id="parecer"
              rows={4}
              value={parecer}
              onChange={(e) => setParecer(e.target.value)}
              placeholder="Fundamente a decisão."
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Obrigatório. Fica registrado com autor e data.
            </p>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
