"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { use, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
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

const RESULTADOS: { value: OcorrenciaDecidirInput["resultado"]; label: string }[] = [
  { value: "procedente", label: "Procedente" },
  { value: "improcedente", label: "Improcedente" },
  { value: "arquivada", label: "Arquivada" },
];

function formatarData(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pt-BR");
}

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
    setAnotarOpen(true);
  }

  function submeterAnotar(e: React.FormEvent) {
    e.preventDefault();
    setErroAnotar(null);
    anotarM.mutate(parecerAnotacao.trim());
  }

  // --- Vincular alvo ------------------------------------------------------
  // Busca NO SERVIDOR com debounce, mesmo padrão do seletor de operador em
  // linhas/page.tsx. O alvo veículo fica de fora: não há endpoint de
  // veículos do transporte regulado com busca `q` — mesma decisão do
  // dialog de registro (ver relatório da Tarefa 7).
  const [vincularOpen, setVincularOpen] = useState(false);
  const [vIdEmpresa, setVIdEmpresa] = useState<number | null>(null);
  const [vIdPermissionario, setVIdPermissionario] = useState<number | null>(null);
  const [erroVincular, setErroVincular] = useState<string | null>(null);

  const [buscaEmpresa, setBuscaEmpresa] = useState("");
  const [buscaEmpresaAplicada, setBuscaEmpresaAplicada] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBuscaEmpresaAplicada(buscaEmpresa.trim()), 300);
    return () => clearTimeout(t);
  }, [buscaEmpresa]);

  const [buscaPerm, setBuscaPerm] = useState("");
  const [buscaPermAplicada, setBuscaPermAplicada] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBuscaPermAplicada(buscaPerm.trim()), 300);
    return () => clearTimeout(t);
  }, [buscaPerm]);

  const empresasQ = useQuery({
    queryKey: ["tr-empresas-busca", buscaEmpresaAplicada],
    queryFn: () => api.empresas.list({ q: buscaEmpresaAplicada || undefined }),
    enabled: vincularOpen,
  });
  const permsQ = useQuery({
    queryKey: ["tr-perms-busca", buscaPermAplicada],
    queryFn: () => api.permissionarios.list({ q: buscaPermAplicada || undefined }),
    enabled: vincularOpen,
  });
  const empresaSelecionadaQ = useQuery({
    queryKey: ["tr-empresa-selecionada", vIdEmpresa],
    queryFn: () => api.empresas.get(vIdEmpresa as number),
    enabled: vIdEmpresa !== null,
  });
  const permSelecionadoQ = useQuery({
    queryKey: ["tr-perm-selecionado", vIdPermissionario],
    queryFn: () => api.permissionarios.get(vIdPermissionario as number),
    enabled: vIdPermissionario !== null,
  });

  const vincularM = useMutation({
    mutationFn: () =>
      api.ocorrenciasTransporte.vincularAlvo(ocorrenciaId, {
        id_empresa: vIdEmpresa,
        id_permissionario: vIdPermissionario,
      }),
    onSuccess: () => {
      toast.success("Alvo vinculado.");
      setVincularOpen(false);
      invalidar();
    },
    onError: (e: Error) => setErroVincular(e.message),
  });

  function abrirVincular() {
    setVIdEmpresa(null);
    setVIdPermissionario(null);
    setBuscaEmpresa("");
    setBuscaPerm("");
    setErroVincular(null);
    setVincularOpen(true);
  }

  function submeterVincular(e: React.FormEvent) {
    e.preventDefault();
    setErroVincular(null);
    if (vIdEmpresa === null && vIdPermissionario === null) {
      setErroVincular("Selecione ao menos um alvo: empresa ou permissionário.");
      return;
    }
    vincularM.mutate();
  }

  // --- Decidir --------------------------------------------------------
  const [decidirOpen, setDecidirOpen] = useState(false);
  const [resultado, setResultado] = useState<OcorrenciaDecidirInput["resultado"]>("procedente");
  const [parecerDecisao, setParecerDecisao] = useState("");
  const [erroDecidir, setErroDecidir] = useState<string | null>(null);

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
    setDecidirOpen(true);
  }

  function submeterDecidir(e: React.FormEvent) {
    e.preventDefault();
    setErroDecidir(null);
    const parecer = parecerDecisao.trim();
    if (!parecer) {
      setErroDecidir("O parecer é obrigatório para decidir a ocorrência.");
      return;
    }
    decidirM.mutate({ resultado, parecer });
  }

  const ocorrencia = q.data;
  const andamentos = [...(ocorrencia?.andamentos ?? [])].sort(
    (a, b) => new Date(a.criado_em).getTime() - new Date(b.criado_em).getTime(),
  );

  const empresaSelecionadaNome = empresaSelecionadaQ.data
    ? empresaSelecionadaQ.data.nome_fantasia ?? empresaSelecionadaQ.data.razao_social
    : vIdEmpresa !== null
      ? `Empresa #${vIdEmpresa}`
      : null;
  const permSelecionadoNome = permSelecionadoQ.data
    ? permSelecionadoQ.data.nome
    : vIdPermissionario !== null
      ? `Permissionário #${vIdPermissionario}`
      : null;

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
        <div className="py-8 text-center text-muted-foreground">Carregando...</div>
      ) : !ocorrencia ? (
        <div className="py-8 text-center text-muted-foreground">Ocorrência não encontrada.</div>
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
                <div>{ocorrencia.data_fato}</div>
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

      <Dialog open={anotarOpen} onClose={() => setAnotarOpen(false)} title="Anotar">
        <form className="space-y-3" onSubmit={submeterAnotar}>
          {erroAnotar && (
            <div className="rounded-md border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
              {erroAnotar}
            </div>
          )}
          <div>
            <Label htmlFor="parecerAnotacao">Parecer</Label>
            <Textarea
              id="parecerAnotacao"
              required
              rows={3}
              value={parecerAnotacao}
              onChange={(e) => setParecerAnotacao(e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setAnotarOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={anotarM.isPending}>
              {anotarM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </div>
        </form>
      </Dialog>

      <Dialog open={vincularOpen} onClose={() => setVincularOpen(false)} title="Vincular alvo">
        <form className="space-y-3" onSubmit={submeterVincular}>
          {erroVincular && (
            <div className="rounded-md border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
              {erroVincular}
            </div>
          )}
          <div>
            <Label htmlFor="vBuscaEmpresa">Empresa</Label>
            {vIdEmpresa !== null ? (
              <div className="flex h-11 items-center justify-between rounded-input border border-input bg-card px-3 text-sm">
                <span className="truncate">{empresaSelecionadaNome}</span>
                <Button type="button" variant="ghost" size="sm" onClick={() => setVIdEmpresa(null)}>
                  Limpar
                </Button>
              </div>
            ) : (
              <>
                <Input
                  id="vBuscaEmpresa"
                  placeholder="Buscar por razão social/CNPJ..."
                  value={buscaEmpresa}
                  onChange={(e) => setBuscaEmpresa(e.target.value)}
                />
                <div className="mt-1 max-h-40 overflow-y-auto rounded-md border border-border">
                  {empresasQ.isLoading ? (
                    <div className="p-2 text-xs text-muted-foreground">Carregando...</div>
                  ) : (empresasQ.data?.items ?? []).length === 0 ? (
                    <div className="p-2 text-xs text-muted-foreground">
                      Nenhuma empresa encontrada.
                    </div>
                  ) : (
                    (empresasQ.data?.items ?? []).map((emp) => (
                      <button
                        key={emp.id}
                        type="button"
                        className="block w-full truncate px-3 py-2 text-left text-sm hover:bg-muted"
                        onClick={() => setVIdEmpresa(emp.id)}
                      >
                        {emp.nome_fantasia ?? emp.razao_social}
                        <span className="ml-2 text-xs text-muted-foreground">{emp.cnpj}</span>
                      </button>
                    ))
                  )}
                </div>
              </>
            )}
          </div>
          <div>
            <Label htmlFor="vBuscaPerm">Permissionário</Label>
            {vIdPermissionario !== null ? (
              <div className="flex h-11 items-center justify-between rounded-input border border-input bg-card px-3 text-sm">
                <span className="truncate">{permSelecionadoNome}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setVIdPermissionario(null)}
                >
                  Limpar
                </Button>
              </div>
            ) : (
              <>
                <Input
                  id="vBuscaPerm"
                  placeholder="Buscar por nome/CPF..."
                  value={buscaPerm}
                  onChange={(e) => setBuscaPerm(e.target.value)}
                />
                <div className="mt-1 max-h-40 overflow-y-auto rounded-md border border-border">
                  {permsQ.isLoading ? (
                    <div className="p-2 text-xs text-muted-foreground">Carregando...</div>
                  ) : (permsQ.data?.items ?? []).length === 0 ? (
                    <div className="p-2 text-xs text-muted-foreground">
                      Nenhum permissionário encontrado.
                    </div>
                  ) : (
                    (permsQ.data?.items ?? []).map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        className="block w-full truncate px-3 py-2 text-left text-sm hover:bg-muted"
                        onClick={() => setVIdPermissionario(p.id)}
                      >
                        {p.nome}
                        <span className="ml-2 text-xs text-muted-foreground">{p.cpf}</span>
                      </button>
                    ))
                  )}
                </div>
              </>
            )}
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setVincularOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={vincularM.isPending}>
              {vincularM.isPending ? "Vinculando..." : "Vincular"}
            </Button>
          </div>
        </form>
      </Dialog>

      <Dialog open={decidirOpen} onClose={() => setDecidirOpen(false)} title="Decidir ocorrência">
        <form className="space-y-3" onSubmit={submeterDecidir}>
          {erroDecidir && (
            <div className="rounded-md border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
              {erroDecidir}
            </div>
          )}
          <div>
            <Label htmlFor="resultado">Resultado</Label>
            <Select
              id="resultado"
              value={resultado}
              onChange={(e) => setResultado(e.target.value as OcorrenciaDecidirInput["resultado"])}
            >
              {RESULTADOS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="parecerDecisao">Parecer</Label>
            <Textarea
              id="parecerDecisao"
              required
              rows={3}
              value={parecerDecisao}
              onChange={(e) => setParecerDecisao(e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setDecidirOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={decidirM.isPending}>
              {decidirM.isPending ? "Salvando..." : "Decidir"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
