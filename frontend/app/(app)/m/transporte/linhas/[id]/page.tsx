"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Plus, Route, X } from "lucide-react";
import { use, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type LinhaParada,
  type LinhaSituacao,
  type LinhaTransporte,
  type LinhaTransporteCreate,
  type TipoServico,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface PageParams {
  params: Promise<{ id: string }>;
}

const TIPOS: { value: TipoServico; label: string }[] = [
  { value: "transporte_distrital", label: "Transporte distrital" },
  { value: "transporte_escolar", label: "Transporte escolar" },
  { value: "outro", label: "Outro" },
];
const TIPO_LABEL: Record<string, string> = Object.fromEntries(
  TIPOS.map((t) => [t.value, t.label]),
);

// dia_semana: 0=segunda … 6=domingo.
const DIAS = [
  "Segunda",
  "Terça",
  "Quarta",
  "Quinta",
  "Sexta",
  "Sábado",
  "Domingo",
];

interface LinhaForm {
  nome: string;
  codigo: string;
  tipo_servico: TipoServico;
  origem: string;
  destino: string;
  situacao: LinhaSituacao;
  observacoes: string;
  id_empresa: number | null;
  id_permissionario: number | null;
}

function limpo(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

function paraPayload(f: LinhaForm): LinhaTransporteCreate {
  return {
    nome: f.nome.trim(),
    codigo: limpo(f.codigo),
    tipo_servico: f.tipo_servico,
    origem: f.origem.trim(),
    destino: f.destino.trim(),
    situacao: f.situacao,
    observacoes: limpo(f.observacoes),
    id_empresa: f.id_empresa,
    id_permissionario: f.id_permissionario,
  };
}

function paraForm(l: LinhaTransporte): LinhaForm {
  return {
    nome: l.nome,
    codigo: l.codigo ?? "",
    tipo_servico: l.tipo_servico,
    origem: l.origem,
    destino: l.destino,
    situacao: l.situacao,
    observacoes: l.observacoes ?? "",
    id_empresa: l.id_empresa,
    id_permissionario: l.id_permissionario,
  };
}

export default function LinhaDetalhePage({ params }: PageParams) {
  const { id } = use(params);
  const linhaId = Number(id);

  const { can } = useAuth();
  const canEdit = can("transporte_regulado", "atualizar");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const q = useQuery({
    queryKey: ["tr-linha", linhaId],
    queryFn: () => api.linhasTransporte.get(linhaId),
  });

  function invalidar() {
    qc.invalidateQueries({ queryKey: ["tr-linha", linhaId] });
  }

  // --- Dados / edição -------------------------------------------------
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<LinhaForm | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // Seletor de operador — busca NO SERVIDOR com debounce, mesmo padrão do
  // seletor de ocupante da P6 (pontos/[id]/page.tsx): filtrar no cliente
  // sobre a primeira página repete o bug "só enxerga os 50 primeiros".
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
    enabled: dialogOpen,
  });
  const permsQ = useQuery({
    queryKey: ["tr-perms-busca", buscaPermAplicada],
    queryFn: () => api.permissionarios.list({ q: buscaPermAplicada || undefined }),
    enabled: dialogOpen,
  });

  // Nome do operador já selecionado — busca dedicada por id, independente
  // do texto de busca atual (o selecionado pode não estar entre os
  // resultados da busca corrente).
  const idEmpresaForm = form?.id_empresa ?? null;
  const idPermissionarioForm = form?.id_permissionario ?? null;
  const empresaSelecionadaQ = useQuery({
    queryKey: ["tr-empresa-selecionada", idEmpresaForm],
    queryFn: () => api.empresas.get(idEmpresaForm as number),
    enabled: idEmpresaForm !== null,
  });
  const permSelecionadoQ = useQuery({
    queryKey: ["tr-perm-selecionado", idPermissionarioForm],
    queryFn: () => api.permissionarios.get(idPermissionarioForm as number),
    enabled: idPermissionarioForm !== null,
  });

  const salvarM = useMutation({
    mutationFn: (f: LinhaForm) => api.linhasTransporte.update(linhaId, paraPayload(f)),
    onSuccess: () => {
      toast.success("Linha atualizada.");
      setDialogOpen(false);
      invalidar();
    },
    onError: (e: Error) => setErr(e.message),
  });

  function abrirEdicao() {
    if (!q.data) return;
    setForm(paraForm(q.data));
    setErr(null);
    setBuscaEmpresa("");
    setBuscaPerm("");
    setDialogOpen(true);
  }

  function set<K extends keyof LinhaForm>(k: K, v: LinhaForm[K]) {
    setForm((f) => (f ? { ...f, [k]: v } : f));
  }

  function submeterEdicao(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setErr(null);
    if (form.id_empresa === null && form.id_permissionario === null) {
      setErr("Informe ao menos um operador: empresa ou permissionário.");
      return;
    }
    salvarM.mutate(form);
  }

  // --- Itinerário (paradas) -------------------------------------------
  const [paradaDialogOpen, setParadaDialogOpen] = useState(false);
  const [paradaEditando, setParadaEditando] = useState<LinhaParada | null>(null);
  const [paradaDescricao, setParadaDescricao] = useState("");
  const [paradaObs, setParadaObs] = useState("");
  const [erroParada, setErroParada] = useState<string | null>(null);

  const paradas = [...(q.data?.paradas ?? [])].sort((a, b) => a.ordem - b.ordem);

  const addParadaM = useMutation({
    mutationFn: (v: { descricao: string; observacoes: string | null }) =>
      api.linhasTransporte.addParada(linhaId, v),
    onSuccess: () => {
      toast.success("Parada adicionada.");
      fecharDialogParada();
      invalidar();
    },
    onError: (e: Error) => setErroParada(e.message),
  });

  const updateParadaM = useMutation({
    mutationFn: (v: { id: number; descricao: string; observacoes: string | null }) =>
      api.linhasTransporte.updateParada(linhaId, v.id, {
        descricao: v.descricao,
        observacoes: v.observacoes,
      }),
    onSuccess: () => {
      toast.success("Parada atualizada.");
      fecharDialogParada();
      invalidar();
    },
    onError: (e: Error) => setErroParada(e.message),
  });

  const removeParadaM = useMutation({
    mutationFn: (paradaId: number) => api.linhasTransporte.removeParada(linhaId, paradaId),
    onSuccess: () => {
      toast.success("Parada removida.");
      invalidar();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const reordenarM = useMutation({
    mutationFn: (ids: number[]) => api.linhasTransporte.reordenarParadas(linhaId, ids),
    onSuccess: () => invalidar(),
    // O 422 de "recarregue a página" é acionável — mostrar a mensagem do
    // servidor, e invalidar para a lista voltar a refletir o banco.
    onError: (e: Error) => {
      toast.error(e.message);
      invalidar();
    },
  });

  function abrirNovaParada() {
    setParadaEditando(null);
    setParadaDescricao("");
    setParadaObs("");
    setErroParada(null);
    setParadaDialogOpen(true);
  }

  function abrirEdicaoParada(p: LinhaParada) {
    setParadaEditando(p);
    setParadaDescricao(p.descricao);
    setParadaObs(p.observacoes ?? "");
    setErroParada(null);
    setParadaDialogOpen(true);
  }

  function fecharDialogParada() {
    setParadaDialogOpen(false);
    setParadaEditando(null);
  }

  function submeterParada(e: React.FormEvent) {
    e.preventDefault();
    setErroParada(null);
    const v = { descricao: paradaDescricao.trim(), observacoes: limpo(paradaObs) };
    if (paradaEditando) {
      updateParadaM.mutate({ id: paradaEditando.id, ...v });
    } else {
      addParadaM.mutate(v);
    }
  }

  async function pedirRemocaoParada(p: LinhaParada) {
    const ok = await confirm({
      title: `Remover a parada "${p.descricao}"?`,
      message: "A parada sai do itinerário da linha.",
      confirmLabel: "Remover",
      intent: "danger",
    });
    if (ok) removeParadaM.mutate(p.id);
  }

  function mover(idx: number, delta: -1 | 1) {
    const ids = paradas.map((p) => p.id);
    const alvo = idx + delta;
    if (alvo < 0 || alvo >= ids.length) return;
    [ids[idx], ids[alvo]] = [ids[alvo], ids[idx]];
    reordenarM.mutate(ids);
  }

  // --- Grade de horários ------------------------------------------------
  const [diaNovo, setDiaNovo] = useState("0");
  const [horaNova, setHoraNova] = useState("");

  const horarios = q.data?.horarios ?? [];

  const addHorarioM = useMutation({
    mutationFn: (v: { dia_semana: number; partida: string }) =>
      api.linhasTransporte.addHorario(linhaId, v),
    onSuccess: () => {
      toast.success("Horário adicionado.");
      setHoraNova("");
      invalidar();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const removeHorarioM = useMutation({
    mutationFn: (horarioId: number) => api.linhasTransporte.removeHorario(linhaId, horarioId),
    onSuccess: () => {
      toast.success("Horário removido.");
      invalidar();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function adicionarHorario() {
    if (!horaNova) return;
    addHorarioM.mutate({ dia_semana: Number(diaNovo), partida: `${horaNova}:00` });
  }

  const empresaSelecionadaNome = empresaSelecionadaQ.data
    ? empresaSelecionadaQ.data.nome_fantasia ?? empresaSelecionadaQ.data.razao_social
    : idEmpresaForm !== null
      ? `Empresa #${idEmpresaForm}`
      : null;
  const permSelecionadoNome = permSelecionadoQ.data
    ? permSelecionadoQ.data.nome
    : idPermissionarioForm !== null
      ? `Permissionário #${idPermissionarioForm}`
      : null;

  const linha = q.data;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Route}
        title={linha?.nome ?? "Linha"}
        description={linha ? `${linha.origem} → ${linha.destino}` : "Detalhe da linha."}
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Linhas", href: "/m/transporte/linhas" },
          { label: linha?.nome ?? "Linha" },
        ]}
      />

      {q.isLoading ? (
        <div className="py-8 text-center text-muted-foreground">Carregando...</div>
      ) : !linha ? (
        <div className="py-8 text-center text-muted-foreground">Linha não encontrada.</div>
      ) : (
        <>
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Dados</CardTitle>
              {canEdit && (
                <Button variant="secondary" size="sm" onClick={abrirEdicao}>
                  Editar
                </Button>
              )}
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <div>
                <div className="text-xs text-muted-foreground">Código</div>
                <div>{linha.codigo ?? "—"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Tipo</div>
                <div>{TIPO_LABEL[linha.tipo_servico] ?? linha.tipo_servico}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Operador</div>
                <div>{linha.operador_nome ?? "—"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Trajeto</div>
                <div>
                  {linha.origem} → {linha.destino}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Situação</div>
                <Badge intent={linha.situacao === "ativa" ? "success" : "neutral"}>
                  {linha.situacao === "ativa" ? "Ativa" : "Inativa"}
                </Badge>
              </div>
              {linha.observacoes && (
                <div className="col-span-2 sm:col-span-3">
                  <div className="text-xs text-muted-foreground">Observações</div>
                  <div>{linha.observacoes}</div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Itinerário</CardTitle>
              {canEdit && (
                <Button variant="secondary" size="sm" onClick={abrirNovaParada}>
                  <Plus className="mr-1 h-4 w-4" />
                  Adicionar parada
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {paradas.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nenhuma parada cadastrada nesta linha.
                </p>
              ) : (
                <ol className="space-y-2">
                  {paradas.map((p, idx) => (
                    <li
                      key={p.id}
                      className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface-1 px-3 py-2"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="font-medium">
                          {idx + 1}. {p.descricao}
                        </div>
                        {p.observacoes && (
                          <div className="text-xs text-muted-foreground">{p.observacoes}</div>
                        )}
                      </div>
                      {canEdit && (
                        <div className="flex shrink-0 items-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Mover "${p.descricao}" para cima`}
                            disabled={idx === 0 || reordenarM.isPending}
                            onClick={() => mover(idx, -1)}
                          >
                            <ArrowUp className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Mover "${p.descricao}" para baixo`}
                            disabled={idx === paradas.length - 1 || reordenarM.isPending}
                            onClick={() => mover(idx, 1)}
                          >
                            <ArrowDown className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => abrirEdicaoParada(p)}>
                            Editar
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => pedirRemocaoParada(p)}>
                            Remover
                          </Button>
                        </div>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Grade de horários</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-7">
                {DIAS.map((dia, diaIdx) => {
                  const doDia = horarios
                    .filter((h) => h.dia_semana === diaIdx)
                    .sort((a, b) => a.partida.localeCompare(b.partida));
                  return (
                    <div key={dia} className="rounded-md border border-border p-2">
                      <div className="mb-2 text-xs font-semibold text-muted-foreground">
                        {dia}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {doDia.length === 0 && (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                        {doDia.map((h) => (
                          <Badge key={h.id} intent="neutral" className="gap-1">
                            {h.partida.slice(0, 5)}
                            {canEdit && (
                              <button
                                type="button"
                                aria-label={`Remover horário ${h.partida.slice(0, 5)} de ${dia}`}
                                onClick={() => removeHorarioM.mutate(h.id)}
                                className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full hover:bg-muted"
                              >
                                <X className="h-3 w-3" />
                              </button>
                            )}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>

              {canEdit && (
                <div className="flex flex-wrap items-end gap-2">
                  <div>
                    <Label htmlFor="diaNovo">Dia</Label>
                    <Select
                      id="diaNovo"
                      value={diaNovo}
                      onChange={(e) => setDiaNovo(e.target.value)}
                      className="max-w-[160px]"
                    >
                      {DIAS.map((dia, idx) => (
                        <option key={dia} value={idx}>
                          {dia}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="horaNova">Horário</Label>
                    <Input
                      id="horaNova"
                      type="time"
                      value={horaNova}
                      onChange={(e) => setHoraNova(e.target.value)}
                      className="max-w-[140px]"
                    />
                  </div>
                  <Button
                    type="button"
                    onClick={adicionarHorario}
                    disabled={!horaNova || addHorarioM.isPending}
                  >
                    <Plus className="mr-1 h-4 w-4" />
                    Adicionar horário
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="Editar linha">
        {form && (
          <form className="space-y-3" onSubmit={submeterEdicao}>
            {err && (
              <div className="rounded-md border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
                {err}
              </div>
            )}
            <div>
              <Label htmlFor="nome">Nome</Label>
              <Input
                id="nome"
                required
                value={form.nome}
                onChange={(e) => set("nome", e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="codigo">Código</Label>
                <Input
                  id="codigo"
                  value={form.codigo}
                  onChange={(e) => set("codigo", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="tipo">Tipo de serviço</Label>
                <Select
                  id="tipo"
                  value={form.tipo_servico}
                  onChange={(e) => set("tipo_servico", e.target.value as TipoServico)}
                >
                  {TIPOS.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="origem">Origem</Label>
                <Input
                  id="origem"
                  required
                  value={form.origem}
                  onChange={(e) => set("origem", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="destino">Destino</Label>
                <Input
                  id="destino"
                  required
                  value={form.destino}
                  onChange={(e) => set("destino", e.target.value)}
                />
              </div>
            </div>
            <div>
              <Label htmlFor="situacao">Situação</Label>
              <Select
                id="situacao"
                value={form.situacao}
                onChange={(e) => set("situacao", e.target.value as LinhaSituacao)}
              >
                <option value="ativa">Ativa</option>
                <option value="inativa">Inativa</option>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="buscaEmpresa">Empresa operadora</Label>
                {form.id_empresa !== null ? (
                  <div className="flex h-11 items-center justify-between rounded-input border border-input bg-card px-3 text-sm">
                    <span className="truncate">{empresaSelecionadaNome}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => set("id_empresa", null)}
                    >
                      Limpar
                    </Button>
                  </div>
                ) : (
                  <>
                    <Input
                      id="buscaEmpresa"
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
                            onClick={() => set("id_empresa", emp.id)}
                          >
                            {emp.nome_fantasia ?? emp.razao_social}
                            <span className="ml-2 text-xs text-muted-foreground">
                              {emp.cnpj}
                            </span>
                          </button>
                        ))
                      )}
                    </div>
                  </>
                )}
              </div>
              <div>
                <Label htmlFor="buscaPerm">Permissionário operador</Label>
                {form.id_permissionario !== null ? (
                  <div className="flex h-11 items-center justify-between rounded-input border border-input bg-card px-3 text-sm">
                    <span className="truncate">{permSelecionadoNome}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => set("id_permissionario", null)}
                    >
                      Limpar
                    </Button>
                  </div>
                ) : (
                  <>
                    <Input
                      id="buscaPerm"
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
                            onClick={() => set("id_permissionario", p.id)}
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
            </div>
            <p className="text-xs text-muted-foreground">
              Informe ao menos um operador: empresa, permissionário, ou os dois.
            </p>
            <div>
              <Label htmlFor="obs">Observações</Label>
              <Input
                id="obs"
                value={form.observacoes}
                onChange={(e) => set("observacoes", e.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="secondary" onClick={() => setDialogOpen(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={salvarM.isPending}>
                {salvarM.isPending ? "Salvando..." : "Salvar"}
              </Button>
            </div>
          </form>
        )}
      </Dialog>

      <Dialog
        open={paradaDialogOpen}
        onClose={fecharDialogParada}
        title={paradaEditando ? "Editar parada" : "Nova parada"}
      >
        <form className="space-y-3" onSubmit={submeterParada}>
          {erroParada && (
            <div className="rounded-md border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
              {erroParada}
            </div>
          )}
          <div>
            <Label htmlFor="paradaDescricao">Descrição</Label>
            <Input
              id="paradaDescricao"
              required
              value={paradaDescricao}
              onChange={(e) => setParadaDescricao(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="paradaObs">Observações</Label>
            <Input
              id="paradaObs"
              value={paradaObs}
              onChange={(e) => setParadaObs(e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={fecharDialogParada}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={addParadaM.isPending || updateParadaM.isPending}
            >
              {addParadaM.isPending || updateParadaM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
