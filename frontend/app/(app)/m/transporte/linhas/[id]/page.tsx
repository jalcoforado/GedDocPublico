"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  Clock,
  MapPin,
  Pencil,
  Plus,
  Route,
  SearchX,
  Trash2,
  X,
} from "lucide-react";
import { use, useState } from "react";

import { modoDoVinculo, type ModoVinculo } from "@/components/transporte/campo-vinculo";
import { CamposLinha, comOperador, errosDaLinha, type CampoLinha } from "@/components/transporte/campos-linha";
import { useValidacao } from "@/components/transporte/formulario";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
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
  // O seletor de operador (busca no servidor, com debounce) mora em
  // `CamposLinha` → `ComboRegulado`.
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<LinhaForm | null>(null);
  const [modoOperador, setModoOperador] = useState<ModoVinculo>("empresa");
  const [err, setErr] = useState<string | null>(null);
  const val = useValidacao<CampoLinha>(form ? errosDaLinha(form, modoOperador) : {});

  const salvarM = useMutation({
    mutationFn: (f: LinhaForm) => api.linhasTransporte.update(linhaId, paraPayload(comOperador(f, modoOperador))),
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
    setModoOperador(
      modoDoVinculo(String(q.data.id_permissionario ?? ""), String(q.data.id_empresa ?? "")),
    );
    setErr(null);
    val.reiniciar();
    setDialogOpen(true);
  }

  function set<K extends keyof LinhaForm>(k: K, v: LinhaForm[K]) {
    setForm((f) => (f ? { ...f, [k]: v } : f));
  }

  function submeterEdicao() {
    if (!form) return;
    setErr(null);
    if (!val.conferir()) return;
    salvarM.mutate(form);
  }

  // --- Itinerário (paradas) -------------------------------------------
  const [paradaDialogOpen, setParadaDialogOpen] = useState(false);
  const [paradaEditando, setParadaEditando] = useState<LinhaParada | null>(null);
  const [paradaDescricao, setParadaDescricao] = useState("");
  const [paradaObs, setParadaObs] = useState("");
  const [erroParada, setErroParada] = useState<string | null>(null);
  const valParada = useValidacao<"descricao">({
    descricao: paradaDescricao.trim() === "" ? "Diga onde fica a parada." : undefined,
  });

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
    valParada.reiniciar();
    setParadaDialogOpen(true);
  }

  function abrirEdicaoParada(p: LinhaParada) {
    setParadaEditando(p);
    setParadaDescricao(p.descricao);
    setParadaObs(p.observacoes ?? "");
    setErroParada(null);
    valParada.reiniciar();
    setParadaDialogOpen(true);
  }

  function fecharDialogParada() {
    setParadaDialogOpen(false);
    setParadaEditando(null);
  }

  function submeterParada() {
    setErroParada(null);
    if (!valParada.conferir()) return;
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
  // O botão não fica mais desabilitado sem horário: clicar é o que diz o
  // que falta (padrão de formulário, regra 9).
  const valHorario = useValidacao<"hora">({
    hora: horaNova === "" ? "Escolha o horário de partida." : undefined,
  });

  const horarios = q.data?.horarios ?? [];

  const addHorarioM = useMutation({
    mutationFn: (v: { dia_semana: number; partida: string }) =>
      api.linhasTransporte.addHorario(linhaId, v),
    onSuccess: () => {
      toast.success("Horário adicionado.");
      setHoraNova("");
      valHorario.reiniciar();
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
    if (!valHorario.conferir()) return;
    addHorarioM.mutate({ dia_semana: Number(diaNovo), partida: `${horaNova}:00` });
  }

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
        <Carregando className="py-8 text-center text-muted-foreground" />
      ) : !linha ? (
        <EmptyState
          icon={SearchX}
          title="Linha não encontrada"
          description="Ela pode ter sido excluída. Volte para a lista de linhas."
        />
      ) : (
        <>
          <SectionCard
            title="Dados"
            icon={Route}
            actions={
              canEdit ? (
                <Button variant="secondary" size="sm" onClick={abrirEdicao}>
                  <Pencil className="mr-1 h-4 w-4" />
                  Editar linha
                </Button>
              ) : undefined
            }
          >
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs text-muted-foreground">Código</dt>
                <dd>{linha.codigo ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Tipo</dt>
                <dd>{TIPO_LABEL[linha.tipo_servico] ?? linha.tipo_servico}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Operador</dt>
                <dd>{linha.operador_nome ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Trajeto</dt>
                <dd>
                  {linha.origem} → {linha.destino}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Situação</dt>
                <dd>
                  <Badge intent={linha.situacao === "ativa" ? "success" : "neutral"}>
                    {linha.situacao === "ativa" ? "Ativa" : "Inativa"}
                  </Badge>
                </dd>
              </div>
              {linha.observacoes && (
                <div className="col-span-2 sm:col-span-3">
                  <dt className="text-xs text-muted-foreground">Observações</dt>
                  <dd>{linha.observacoes}</dd>
                </div>
              )}
            </dl>
          </SectionCard>

          <SectionCard
            title="Itinerário"
            icon={MapPin}
            description="As paradas na ordem em que a linha passa. Use as setas para reordenar."
            actions={
              canEdit ? (
                <Button variant="secondary" size="sm" onClick={abrirNovaParada}>
                  <Plus className="mr-1 h-4 w-4" />
                  Adicionar parada
                </Button>
              ) : undefined
            }
          >
            {paradas.length === 0 ? (
              <EmptyState
                icon={MapPin}
                title="Nenhuma parada"
                description="As paradas da linha aparecem aqui, na ordem do itinerário."
                className="p-6"
              />
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
                        <AcoesDaLinha
                          acoes={[
                            {
                              label: "Editar",
                              icon: Pencil,
                              onClick: () => abrirEdicaoParada(p),
                            },
                            {
                              label: "Remover",
                              icon: Trash2,
                              perigo: true,
                              onClick: () => pedirRemocaoParada(p),
                            },
                          ]}
                        />
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </SectionCard>

          <SectionCard
            title="Grade de horários"
            icon={Clock}
            description="Horários de partida por dia da semana."
          >
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
              <div
                ref={valHorario.ref}
                className="flex flex-wrap items-start gap-3 border-t border-border pt-4"
              >
                <FormField label="Dia" className="w-40">
                  <Select id="diaNovo" value={diaNovo} onChange={(e) => setDiaNovo(e.target.value)}>
                    {DIAS.map((dia, idx) => (
                      <option key={dia} value={idx}>
                        {dia}
                      </option>
                    ))}
                  </Select>
                </FormField>
                <FormField label="Partida" error={valHorario.erro("hora")} className="w-40">
                  <Input
                    id="horaNova"
                    type="time"
                    value={horaNova}
                    onChange={(e) => setHoraNova(e.target.value)}
                  />
                </FormField>
                <Button type="button" onClick={adicionarHorario} loading={addHorarioM.isPending} className="mt-6">
                  <Plus className="mr-1 h-4 w-4" />
                  Adicionar horário
                </Button>
              </div>
            )}
          </SectionCard>
        </>
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={linha ? `Editar linha — ${linha.nome}` : "Editar linha"}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={submeterEdicao} loading={salvarM.isPending}>
              Salvar alterações
            </Button>
          </>
        }
      >
        {form && (
          <div ref={val.ref} className="space-y-5">
            <CamposLinha
              form={form}
              set={set}
              tipos={TIPOS}
              modoOperador={modoOperador}
              onModoOperador={setModoOperador}
              ativo={dialogOpen}
              erro={val.erro}
              sair={val.sair}
            />
            {err && <Alert intent="danger">{err}</Alert>}
          </div>
        )}
      </Dialog>

      <Dialog
        open={paradaDialogOpen}
        onClose={fecharDialogParada}
        title={paradaEditando ? "Editar parada" : "Nova parada"}
        description={
          paradaEditando ? undefined : `Entra no fim do itinerário, como a parada ${paradas.length + 1}. Dá para reordenar depois.`
        }
        footer={
          <>
            <Button variant="ghost" onClick={fecharDialogParada}>
              Cancelar
            </Button>
            <Button onClick={submeterParada} loading={addParadaM.isPending || updateParadaM.isPending}>
              {paradaEditando ? "Salvar alterações" : "Adicionar parada"}
            </Button>
          </>
        }
      >
        <div ref={valParada.ref} className="space-y-4">
          <FormField
            label="Local da parada"
            required
            error={valParada.erro("descricao")}
            hint="Um ponto de referência que o passageiro reconhece."
          >
            <Input
              id="paradaDescricao"
              value={paradaDescricao}
              onChange={(e) => setParadaDescricao(e.target.value)}
              onBlur={valParada.sair("descricao")}
              placeholder="Ex.: Escola Municipal Rui Barbosa"
            />
          </FormField>
          <FormField label="Observações" opcional>
            <Input
              id="paradaObs"
              value={paradaObs}
              onChange={(e) => setParadaObs(e.target.value)}
              placeholder="Ex.: só em dias letivos"
            />
          </FormField>
          {erroParada && <Alert intent="danger">{erroParada}</Alert>}
        </div>
      </Dialog>
    </div>
  );
}
