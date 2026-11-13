"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, SearchX } from "lucide-react";
import { use, useState } from "react";

import { fmtData } from "@/components/pagamentos/format";
import { CamposAlvo } from "@/components/transporte/campos-alvo";
import { useValidacao } from "@/components/transporte/formulario";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField } from "@/components/ui/form-field";
import { PageHeader } from "@/components/ui/page-header";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { dataHoraParaExibir } from "@/components/transporte/rotulos";
import { WorkflowTimeline } from "@/components/transporte/WorkflowTimeline";
import {
  api,
  type OcorrenciaDecidirInput,
  type OcorrenciaOrigem,
  type OcorrenciaSituacao,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface PageParams {
  params: Promise<{ id: string }>;
}

const ORIGEM_LABEL: Record<OcorrenciaOrigem, string> = {
  fiscalizacao: "Fiscalização",
  denuncia: "Denúncia",
  outro: "Outro",
};

const SITUACAO_LABEL: Record<OcorrenciaSituacao, string> = {
  registrada: "Registrada",
  em_apuracao: "Em apuração",
  procedente: "Procedente",
  improcedente: "Improcedente",
  arquivada: "Arquivada",
};

const SITUACAO_INTENT: Record<OcorrenciaSituacao, "neutral" | "warning" | "danger"> = {
  registrada: "neutral",
  em_apuracao: "warning",
  procedente: "danger",
  improcedente: "neutral",
  arquivada: "neutral",
};

// Rótulos de ato da trilha — fixados no brief da Tarefa 7.
const ATO_LABEL: Record<string, string> = {
  registro: "Registro",
  inicio_apuracao: "Início da apuração",
  anotacao: "Anotação",
  vinculo_alvo: "Vínculo de alvo",
  decisao: "Decisão",
};

// A descrição é a consequência da escolha, dita sob o grupo ao decidir.
const RESULTADOS: { value: OcorrenciaDecidirInput["resultado"]; label: string; descricao: string }[] = [
  { value: "procedente", label: "Procedente", descricao: "A infração fica confirmada contra o alvo." },
  { value: "improcedente", label: "Improcedente", descricao: "Encerra a ocorrência: não houve infração." },
  { value: "arquivada", label: "Arquivada", descricao: "Encerra a ocorrência sem julgar o mérito." },
];

// Data e hora sem os segundos do `toLocaleString` puro.
const formatarData = dataHoraParaExibir;

export default function OcorrenciaDetalhePage({ params }: PageParams) {
  const { id } = use(params);
  const ocorrenciaId = Number(id);

  const { can } = useAuth();
  const canEdit = can("transporte_regulado", "atualizar");
  const qc = useQueryClient();
  const toast = useToast();

  const q = useQuery({
    queryKey: ["tr-ocorrencia", ocorrenciaId],
    queryFn: () => api.ocorrenciasTransporte.get(ocorrenciaId),
  });

  function invalidar() {
    qc.invalidateQueries({ queryKey: ["tr-ocorrencia", ocorrenciaId] });
    qc.invalidateQueries({ queryKey: ["tr-ocorrencias"] });
  }

  // --- Apurar -----------------------------------------------------------
  const apurarM = useMutation({
    mutationFn: () => api.ocorrenciasTransporte.apurar(ocorrenciaId),
    onSuccess: () => {
      toast.success("Apuração iniciada.");
      invalidar();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // --- Anotar -------------------------------------------------------------
  const [anotarOpen, setAnotarOpen] = useState(false);
  const [parecerAnotacao, setParecerAnotacao] = useState("");
  const [erroAnotar, setErroAnotar] = useState<string | null>(null);
  const valAnotar = useValidacao<"parecer">({
    parecer: parecerAnotacao.trim() === "" ? "Escreva a anotação." : undefined,
  });

  const anotarM = useMutation({
    mutationFn: (parecer: string) => api.ocorrenciasTransporte.anotar(ocorrenciaId, { parecer }),
    onSuccess: () => {
      toast.success("Anotação registrada.");
      setAnotarOpen(false);
      setParecerAnotacao("");
      invalidar();
    },
    onError: (e: Error) => setErroAnotar(e.message),
  });

  function abrirAnotar() {
    setParecerAnotacao("");
    setErroAnotar(null);
    valAnotar.reiniciar();
    setAnotarOpen(true);
  }

  function submeterAnotar() {
    setErroAnotar(null);
    if (!valAnotar.conferir()) return;
    anotarM.mutate(parecerAnotacao.trim());
  }

  // --- Vincular alvo ------------------------------------------------------
  // A busca (no servidor, com debounce) mora em `CamposAlvo`.
  const [vincularOpen, setVincularOpen] = useState(false);
  const [vIdEmpresa, setVIdEmpresa] = useState<number | null>(null);
  const [vIdPermissionario, setVIdPermissionario] = useState<number | null>(null);
  const [vIdVeiculo, setVIdVeiculo] = useState<number | null>(null);
  const [erroVincular, setErroVincular] = useState<string | null>(null);
  const valVincular = useValidacao<"alvo">({
    alvo:
      vIdEmpresa === null && vIdPermissionario === null && vIdVeiculo === null
        ? "Escolha ao menos um alvo: permissionário, empresa ou veículo."
        : undefined,
  });

  const vincularM = useMutation({
    mutationFn: () =>
      api.ocorrenciasTransporte.vincularAlvo(ocorrenciaId, {
        id_empresa: vIdEmpresa,
        id_permissionario: vIdPermissionario,
        id_veiculo: vIdVeiculo,
      }),
    onSuccess: () => {
      toast.success("Alvo vinculado.");
      setVincularOpen(false);
      invalidar();
    },
    onError: (e: Error) => setErroVincular(e.message),
  });

  function abrirVincular() {
    setVIdEmpresa(ocorrencia?.id_empresa ?? null);
    setVIdPermissionario(ocorrencia?.id_permissionario ?? null);
    setVIdVeiculo(ocorrencia?.id_veiculo ?? null);
    setErroVincular(null);
    valVincular.reiniciar();
    setVincularOpen(true);
  }

  function submeterVincular() {
    setErroVincular(null);
    if (!valVincular.conferir()) return;
    vincularM.mutate();
  }

  // --- Decidir --------------------------------------------------------
  const [decidirOpen, setDecidirOpen] = useState(false);
  const [resultado, setResultado] = useState<OcorrenciaDecidirInput["resultado"]>("procedente");
  const [parecerDecisao, setParecerDecisao] = useState("");
  const [erroDecidir, setErroDecidir] = useState<string | null>(null);
  const valDecidir = useValidacao<"parecer">({
    parecer:
      parecerDecisao.trim() === "" ? "Escreva o parecer: ele fundamenta a decisão." : undefined,
  });

  const decidirM = useMutation({
    mutationFn: (data: OcorrenciaDecidirInput) => api.ocorrenciasTransporte.decidir(ocorrenciaId, data),
    onSuccess: () => {
      toast.success("Ocorrência decidida.");
      setDecidirOpen(false);
      invalidar();
    },
    onError: (e: Error) => setErroDecidir(e.message),
  });

  function abrirDecidir() {
    setResultado("procedente");
    setParecerDecisao("");
    setErroDecidir(null);
    valDecidir.reiniciar();
    setDecidirOpen(true);
  }

  function submeterDecidir() {
    setErroDecidir(null);
    if (!valDecidir.conferir()) return;
    decidirM.mutate({ resultado, parecer: parecerDecisao.trim() });
  }
  const ocorrencia = q.data;
  const andamentos = [...(ocorrencia?.andamentos ?? [])].sort(
    (a, b) =>
      new Date(a.criado_em).getTime() - new Date(b.criado_em).getTime() ||
      a.id - b.id,
  );

  return (
    <div className="space-y-4">
      <PageHeader
        icon={AlertTriangle}
        title={ocorrencia ? `Ocorrência #${ocorrencia.id}` : "Ocorrência"}
        description={ocorrencia?.tipo_nome ?? "Detalhe da ocorrência."}
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Ocorrências", href: "/m/transporte/ocorrencias" },
          { label: ocorrencia ? `#${ocorrencia.id}` : "Ocorrência" },
        ]}
      />

      {q.isLoading ? (
        <Carregando className="py-8 text-center text-muted-foreground" />
      ) : !ocorrencia ? (
        <EmptyState
          icon={SearchX}
          title="Ocorrência não encontrada"
          description="Ela pode ter sido excluída. Volte para a lista de ocorrências."
        />
      ) : (
        <>
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Dados</CardTitle>
              <Badge intent={SITUACAO_INTENT[ocorrencia.situacao]}>
                {SITUACAO_LABEL[ocorrencia.situacao]}
              </Badge>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <div>
                <div className="text-xs text-muted-foreground">Tipo</div>
                <div>{ocorrencia.tipo_nome ?? "—"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Origem</div>
                <div>{ORIGEM_LABEL[ocorrencia.origem]}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Data do fato</div>
                <div className="tabular-nums">{fmtData(ocorrencia.data_fato)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Alvo</div>
                <div>{ocorrencia.alvo_resumo ?? ocorrencia.referencia_alvo ?? "—"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Registrada em</div>
                <div>{formatarData(ocorrencia.criado_em)}</div>
              </div>
              {ocorrencia.atualizado_em && (
                <div>
                  <div className="text-xs text-muted-foreground">Última atualização</div>
                  <div>{formatarData(ocorrencia.atualizado_em)}</div>
                </div>
              )}
              <div className="col-span-2 sm:col-span-3">
                <div className="text-xs text-muted-foreground">Descrição</div>
                <div>{ocorrencia.descricao}</div>
              </div>
              {ocorrencia.observacoes && (
                <div className="col-span-2 sm:col-span-3">
                  <div className="text-xs text-muted-foreground">Observações</div>
                  <div>{ocorrencia.observacoes}</div>
                </div>
              )}
            </CardContent>
          </Card>

          {canEdit && (
            <Card>
              <CardHeader>
                <CardTitle>Ações</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {ocorrencia.situacao === "registrada" && (
                  <>
                    <Button onClick={() => apurarM.mutate()} disabled={apurarM.isPending}>
                      {apurarM.isPending ? "Apurando..." : "Apurar"}
                    </Button>
                    <Button variant="secondary" onClick={abrirAnotar}>
                      Anotar
                    </Button>
                    <Button variant="secondary" onClick={abrirVincular}>
                      Vincular alvo
                    </Button>
                  </>
                )}
                {ocorrencia.situacao === "em_apuracao" && (
                  <>
                    <Button variant="secondary" onClick={abrirAnotar}>
                      Anotar
                    </Button>
                    <Button variant="secondary" onClick={abrirVincular}>
                      Vincular alvo
                    </Button>
                    <Button onClick={abrirDecidir}>Decidir</Button>
                  </>
                )}
                {ocorrencia.situacao !== "registrada" && ocorrencia.situacao !== "em_apuracao" && (
                  <p className="text-sm text-muted-foreground">
                    Situação final — somente leitura.
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          <WorkflowTimeline entidadeTipo="ocorrencia" entidadeId={ocorrencia.id} />

          <Card>
            <CardHeader>
              <CardTitle>Trilha</CardTitle>
            </CardHeader>
            <CardContent>
              {andamentos.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nenhum andamento registrado.</p>
              ) : (
                <ol className="space-y-3">
                  {andamentos.map((a) => (
                    <li
                      key={a.id}
                      className="rounded-md border border-border bg-surface-1 px-3 py-2"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium">{ATO_LABEL[a.ato] ?? a.ato}</span>
                        <span className="text-xs text-muted-foreground">
                          {formatarData(a.criado_em)}
                        </span>
                      </div>
                      {a.parecer && <p className="mt-1 text-sm">{a.parecer}</p>}
                      <div className="mt-1 text-xs text-muted-foreground">
                        {a.usuario_nome ?? "—"}
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        </>
      )}

      <Dialog
        open={anotarOpen}
        onClose={() => setAnotarOpen(false)}
        title="Anotar na ocorrência"
        description="A anotação entra na trilha da ocorrência, com seu nome e a data."
        footer={
          <>
            <Button variant="ghost" onClick={() => setAnotarOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={submeterAnotar} loading={anotarM.isPending}>
              Registrar anotação
            </Button>
          </>
        }
      >
        <div ref={valAnotar.ref} className="space-y-4">
          <FormField label="Anotação" required error={valAnotar.erro("parecer")}>
            <Textarea
              id="parecerAnotacao"
              rows={4}
              value={parecerAnotacao}
              onChange={(e) => setParecerAnotacao(e.target.value)}
              onBlur={valAnotar.sair("parecer")}
              placeholder="Ex.: permissionário notificado por telefone; prazo de 5 dias para defesa."
            />
          </FormField>
          {erroAnotar && <Alert intent="danger">{erroAnotar}</Alert>}
        </div>
      </Dialog>

      <Dialog
        open={vincularOpen}
        onClose={() => setVincularOpen(false)}
        title="Vincular alvo"
        description="Acrescenta ou troca o alvo. Deixar um campo vazio não remove o vínculo que já existe."
        footer={
          <>
            <Button variant="ghost" onClick={() => setVincularOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={submeterVincular} loading={vincularM.isPending}>
              Vincular alvo
            </Button>
          </>
        }
      >
        <div ref={valVincular.ref} className="space-y-4">
          <CamposAlvo
            ativo={vincularOpen}
            idPermissionario={vIdPermissionario}
            idEmpresa={vIdEmpresa}
            idVeiculo={vIdVeiculo}
            onPermissionario={setVIdPermissionario}
            onEmpresa={setVIdEmpresa}
            onVeiculo={setVIdVeiculo}
            erro={valVincular.erro("alvo")}
          />
          {erroVincular && <Alert intent="danger">{erroVincular}</Alert>}
        </div>
      </Dialog>

      <Dialog
        open={decidirOpen}
        onClose={() => setDecidirOpen(false)}
        title="Decidir ocorrência"
        description="A decisão encerra a apuração."
        footer={
          <>
            <Button variant="ghost" onClick={() => setDecidirOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={submeterDecidir} loading={decidirM.isPending}>
              Registrar decisão
            </Button>
          </>
        }
      >
        <div ref={valDecidir.ref} className="space-y-4">
          <EscolhaSegmentada<OcorrenciaDecidirInput["resultado"]>
            nome="resultado"
            titulo="Resultado"
            valor={resultado}
            onChange={setResultado}
            opcoes={RESULTADOS.map((r) => ({ valor: r.value, rotulo: r.label, descricao: r.descricao }))}
          />
          <FormField
            label="Parecer"
            required
            error={valDecidir.erro("parecer")}
            hint="Os fatos e o fundamento da decisão."
          >
            <Textarea
              id="parecerDecisao"
              rows={4}
              value={parecerDecisao}
              onChange={(e) => setParecerDecisao(e.target.value)}
              onBlur={valDecidir.sair("parecer")}
              placeholder="Ex.: constatado o transporte sem alvará válido, conforme auto de infração nº 1234."
            />
          </FormField>
          {erroDecidir && <Alert intent="danger">{erroDecidir}</Alert>}
        </div>
      </Dialog>
    </div>
  );
}
