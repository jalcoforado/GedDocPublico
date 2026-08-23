"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Inbox, Plus, Tags } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type OcorrenciaOrigem,
  type OcorrenciaSituacao,
  type OcorrenciaTransporte,
  type OcorrenciaTransporteCreate,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

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

// Ordem cronológica da apuração: registrada → em_apuracao → um dos três
// desfechos. Só "procedente" carrega gravidade (danger); os demais
// desfechos são encerramento neutro, não alerta.
const SITUACAO_INTENT: Record<OcorrenciaSituacao, "neutral" | "warning" | "danger"> = {
  registrada: "neutral",
  em_apuracao: "warning",
  procedente: "danger",
  improcedente: "neutral",
  arquivada: "neutral",
};

interface RegistroForm {
  id_tipo: number | null;
  origem: OcorrenciaOrigem;
  data_fato: string;
  descricao: string;
  referencia_alvo: string;
  observacoes: string;
  id_permissionario: number | null;
  id_empresa: number | null;
  id_veiculo: number | null;
}

const EMPTY: RegistroForm = {
  id_tipo: null,
  origem: "fiscalizacao",
  data_fato: "",
  descricao: "",
  referencia_alvo: "",
  observacoes: "",
  id_permissionario: null,
  id_empresa: null,
  id_veiculo: null,
};

/** `""` vira `null` — o backend distingue "não informado" de string vazia. */
function limpo(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

function paraPayload(f: RegistroForm): OcorrenciaTransporteCreate {
  return {
    id_tipo: f.id_tipo as number,
    origem: f.origem,
    data_fato: f.data_fato,
    descricao: f.descricao.trim(),
    id_permissionario: f.id_permissionario,
    id_empresa: f.id_empresa,
    id_veiculo: f.id_veiculo,
    referencia_alvo: limpo(f.referencia_alvo),
    observacoes: limpo(f.observacoes),
  };
}

export default function OcorrenciasPage() {
  const { can } = useAuth();
  const canCreate = can("transporte_regulado", "inserir");
  const canDelete = can("transporte_regulado", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [busca, setBusca] = useState("");
  const [situacaoFiltro, setSituacaoFiltro] = useState("");
  const [origemFiltro, setOrigemFiltro] = useState("");
  const [tipoFiltro, setTipoFiltro] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<RegistroForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  // Busca NO SERVIDOR, com debounce. Filtrar no cliente sobre a página
  // truncada faz a tela afirmar que uma ocorrência não existe.
  const [buscaAplicada, setBuscaAplicada] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca.trim()), 300);
    return () => clearTimeout(t);
  }, [busca]);

  const q = useQuery({
    queryKey: ["tr-ocorrencias", buscaAplicada, situacaoFiltro, origemFiltro, tipoFiltro],
    queryFn: () =>
      api.ocorrenciasTransporte.list({
        q: buscaAplicada || undefined,
        situacao: situacaoFiltro || undefined,
        origem: origemFiltro || undefined,
        id_tipo: tipoFiltro ? Number(tipoFiltro) : undefined,
      }),
  });

  const tiposQ = useQuery({
    queryKey: ["tr-ocorrencias-tipos"],
    queryFn: () => api.ocorrenciasTransporte.tipos.list(),
  });
  const tipos = tiposQ.data ?? [];
  const tiposAtivos = tipos.filter((t) => t.ativo);

  // Seletores de alvo — busca NO SERVIDOR com debounce, mesmo padrão do
  // seletor de operador de linhas/page.tsx.
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

  const [buscaVeiculo, setBuscaVeiculo] = useState("");
  const [buscaVeiculoAplicada, setBuscaVeiculoAplicada] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBuscaVeiculoAplicada(buscaVeiculo.trim()), 300);
    return () => clearTimeout(t);
  }, [buscaVeiculo]);

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
  const veiculosQ = useQuery({
    queryKey: ["tr-veiculos-busca", buscaVeiculoAplicada],
    queryFn: () => api.veiculosRegulados.list({ q: buscaVeiculoAplicada || undefined }),
    enabled: dialogOpen,
  });

  const empresaSelecionadaQ = useQuery({
    queryKey: ["tr-empresa-selecionada", form.id_empresa],
    queryFn: () => api.empresas.get(form.id_empresa as number),
    enabled: form.id_empresa !== null,
  });
  const permSelecionadoQ = useQuery({
    queryKey: ["tr-perm-selecionado", form.id_permissionario],
    queryFn: () => api.permissionarios.get(form.id_permissionario as number),
    enabled: form.id_permissionario !== null,
  });
  const veiculoSelecionadoQ = useQuery({
    queryKey: ["tr-veiculo-selecionado", form.id_veiculo],
    queryFn: () => api.veiculosRegulados.get(form.id_veiculo as number),
    enabled: form.id_veiculo !== null,
  });

  function invalidar() {
    qc.invalidateQueries({ queryKey: ["tr-ocorrencias"] });
  }

  const registrarM = useMutation({
    mutationFn: () => api.ocorrenciasTransporte.registrar(paraPayload(form)),
    onSuccess: () => {
      toast.success("Ocorrência registrada.");
      setDialogOpen(false);
      invalidar();
    },
    onError: (e: Error) => setErr(e.message),
  });

  const excluirM = useMutation({
    mutationFn: (id: number) => api.ocorrenciasTransporte.remove(id),
    onSuccess: () => {
      toast.success("Ocorrência excluída.");
      invalidar();
    },
    // O 409 de "fora de `registrada`" é acionável — mostrar a mensagem do
    // servidor, não um genérico.
    onError: (e: Error) => toast.error(e.message),
  });

  function abrirNovo() {
    setForm(EMPTY);
    setErr(null);
    setBuscaEmpresa("");
    setBuscaEmpresaAplicada("");
    setBuscaPerm("");
    setBuscaPermAplicada("");
    setBuscaVeiculo("");
    setBuscaVeiculoAplicada("");
    setDialogOpen(true);
  }

  async function pedirExclusao(o: OcorrenciaTransporte) {
    const ok = await confirm({
      title: `Excluir ocorrência #${o.id}?`,
      message: "A ocorrência e sua trilha saem das listagens.",
      confirmLabel: "Excluir",
      intent: "danger",
    });
    if (ok) excluirM.mutate(o.id);
  }

  const itens = q.data?.items ?? [];

  function set<K extends keyof RegistroForm>(k: K, v: RegistroForm[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  function submeter(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (form.id_tipo === null) {
      setErr("Selecione o tipo da ocorrência.");
      return;
    }
    // Ao menos um alvo FORMAL: `exigir_alvo` no backend não aceita
    // `referencia_alvo` sozinha — ela é só complemento textual. Validar
    // igual ao servidor evita o round-trip que terminaria em 422.
    if (form.id_permissionario === null && form.id_empresa === null && form.id_veiculo === null) {
      setErr("Informe ao menos um alvo: permissionário, empresa ou veículo.");
      return;
    }
    registrarM.mutate();
  }

  const empresaSelecionadaNome = empresaSelecionadaQ.data
    ? empresaSelecionadaQ.data.nome_fantasia ?? empresaSelecionadaQ.data.razao_social
    : form.id_empresa !== null
      ? `Empresa #${form.id_empresa}`
      : null;
  const permSelecionadoNome = permSelecionadoQ.data
    ? permSelecionadoQ.data.nome
    : form.id_permissionario !== null
      ? `Permissionário #${form.id_permissionario}`
      : null;
  const veiculoSelecionadoNome = veiculoSelecionadoQ.data
    ? `${veiculoSelecionadoQ.data.placa} — ${veiculoSelecionadoQ.data.marca} ${veiculoSelecionadoQ.data.modelo}`
    : form.id_veiculo !== null
      ? `Veículo #${form.id_veiculo}`
      : null;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={AlertTriangle}
        title="Ocorrências"
        description="Apuração de fiscalizações e denúncias contra permissionários, empresas e veículos do transporte regulado."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Ocorrências" },
        ]}
        actions={
          <div className="flex gap-2">
            <Link href="/m/transporte/ocorrencias/tipos">
              <Button variant="secondary">
                <Tags className="mr-1 h-4 w-4" />
                Tipos de ocorrência
              </Button>
            </Link>
            {canCreate && (
              <Button onClick={abrirNovo}>
                <Plus className="mr-1 h-4 w-4" />
                Registrar ocorrência
              </Button>
            )}
          </div>
        }
      />

      <div className="flex flex-wrap gap-2">
        <Input
          placeholder="Buscar por descrição ou alvo..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="max-w-xs"
        />
        <Select
          value={situacaoFiltro}
          onChange={(e) => setSituacaoFiltro(e.target.value)}
          className="max-w-[180px]"
        >
          <option value="">Todas as situações</option>
          {(Object.keys(SITUACAO_LABEL) as OcorrenciaSituacao[]).map((s) => (
            <option key={s} value={s}>
              {SITUACAO_LABEL[s]}
            </option>
          ))}
        </Select>
        <Select
          value={origemFiltro}
          onChange={(e) => setOrigemFiltro(e.target.value)}
          className="max-w-[160px]"
        >
          <option value="">Todas as origens</option>
          {(Object.keys(ORIGEM_LABEL) as OcorrenciaOrigem[]).map((o) => (
            <option key={o} value={o}>
              {ORIGEM_LABEL[o]}
            </option>
          ))}
        </Select>
        <Select
          value={tipoFiltro}
          onChange={(e) => setTipoFiltro(e.target.value)}
          className="max-w-[200px]"
        >
          <option value="">Todos os tipos</option>
          {tipos.map((t) => (
            <option key={t.id} value={t.id}>
              {t.nome}
            </option>
          ))}
        </Select>
      </div>

      {q.isLoading ? (
        <div className="py-8 text-center text-muted-foreground">Carregando...</div>
      ) : itens.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={buscaAplicada ? "Nenhuma ocorrência encontrada" : "Nenhuma ocorrência registrada"}
          // Com busca ativa, NÃO oferecer "registrar": convidaria a duplicar
          // uma ocorrência que existe e a busca não achou.
          description={
            buscaAplicada
              ? "Nenhuma ocorrência corresponde à busca. Revise o termo."
              : "Registre fiscalizações e denúncias contra operadores do transporte regulado."
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Nº</TH>
              <TH>Tipo</TH>
              <TH>Alvo</TH>
              <TH>Origem</TH>
              <TH>Data do fato</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {itens.map((o) => (
              <TR key={o.id}>
                <TD className="font-medium">
                  <Link href={`/m/transporte/ocorrencias/${o.id}`} className="hover:underline">
                    #{o.id}
                  </Link>
                </TD>
                <TD className="text-sm">{o.tipo_nome ?? "—"}</TD>
                <TD className="text-sm text-muted-foreground">
                  {o.alvo_resumo ?? o.referencia_alvo ?? "—"}
                </TD>
                <TD className="text-sm">{ORIGEM_LABEL[o.origem]}</TD>
                <TD className="text-sm">{o.data_fato}</TD>
                <TD>
                  <Badge intent={SITUACAO_INTENT[o.situacao]}>
                    {SITUACAO_LABEL[o.situacao]}
                  </Badge>
                </TD>
                <TD className="space-x-2 text-right">
                  <Link href={`/m/transporte/ocorrencias/${o.id}`}>
                    <Button variant="ghost" size="sm">
                      Ver
                    </Button>
                  </Link>
                  {canDelete && o.situacao === "registrada" && (
                    <Button variant="ghost" size="sm" onClick={() => pedirExclusao(o)}>
                      Excluir
                    </Button>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="Registrar ocorrência">
        <form className="space-y-3" onSubmit={submeter}>
          {err && (
            <div className="rounded-md border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
              {err}
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="tipo">Tipo</Label>
              <Select
                id="tipo"
                required
                value={form.id_tipo ?? ""}
                onChange={(e) => set("id_tipo", e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Selecione...</option>
                {tiposAtivos.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.nome}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="origem">Origem</Label>
              <Select
                id="origem"
                value={form.origem}
                onChange={(e) => set("origem", e.target.value as OcorrenciaOrigem)}
              >
                {(Object.keys(ORIGEM_LABEL) as OcorrenciaOrigem[]).map((o) => (
                  <option key={o} value={o}>
                    {ORIGEM_LABEL[o]}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <div>
            <Label htmlFor="data_fato">Data do fato</Label>
            <Input
              id="data_fato"
              type="date"
              required
              value={form.data_fato}
              onChange={(e) => set("data_fato", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="descricao">Descrição</Label>
            <Textarea
              id="descricao"
              required
              rows={3}
              value={form.descricao}
              onChange={(e) => set("descricao", e.target.value)}
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label htmlFor="buscaEmpresa">Empresa alvo</Label>
              {form.id_empresa !== null ? (
                <div className="flex h-11 items-center justify-between rounded-input border border-input bg-card px-3 text-sm">
                  <span className="truncate">{empresaSelecionadaNome}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      set("id_empresa", null);
                      setBuscaEmpresa("");
                      setBuscaEmpresaAplicada("");
                    }}
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
                          <span className="ml-2 text-xs text-muted-foreground">{emp.cnpj}</span>
                        </button>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>
            <div>
              <Label htmlFor="buscaPerm">Permissionário alvo</Label>
              {form.id_permissionario !== null ? (
                <div className="flex h-11 items-center justify-between rounded-input border border-input bg-card px-3 text-sm">
                  <span className="truncate">{permSelecionadoNome}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      set("id_permissionario", null);
                      setBuscaPerm("");
                      setBuscaPermAplicada("");
                    }}
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
            <div>
              <Label htmlFor="buscaVeiculo">Veículo alvo</Label>
              {form.id_veiculo !== null ? (
                <div className="flex h-11 items-center justify-between rounded-input border border-input bg-card px-3 text-sm">
                  <span className="truncate">{veiculoSelecionadoNome}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      set("id_veiculo", null);
                      setBuscaVeiculo("");
                      setBuscaVeiculoAplicada("");
                    }}
                  >
                    Limpar
                  </Button>
                </div>
              ) : (
                <>
                  <Input
                    id="buscaVeiculo"
                    placeholder="Buscar por placa/marca/modelo..."
                    value={buscaVeiculo}
                    onChange={(e) => setBuscaVeiculo(e.target.value)}
                  />
                  <div className="mt-1 max-h-40 overflow-y-auto rounded-md border border-border">
                    {veiculosQ.isLoading ? (
                      <div className="p-2 text-xs text-muted-foreground">Carregando...</div>
                    ) : (veiculosQ.data?.items ?? []).length === 0 ? (
                      <div className="p-2 text-xs text-muted-foreground">
                        Nenhum veículo encontrado.
                      </div>
                    ) : (
                      (veiculosQ.data?.items ?? []).map((v) => (
                        <button
                          key={v.id}
                          type="button"
                          className="block w-full truncate px-3 py-2 text-left text-sm hover:bg-muted"
                          onClick={() => set("id_veiculo", v.id)}
                        >
                          {v.placa}
                          <span className="ml-2 text-xs text-muted-foreground">
                            {v.marca} {v.modelo}
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
          <div>
            <Label htmlFor="referencia">Referência do alvo (opcional)</Label>
            <Input
              id="referencia"
              placeholder="Ex.: placa do veículo"
              value={form.referencia_alvo}
              onChange={(e) => set("referencia_alvo", e.target.value)}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Complemento textual (ex.: placa); não substitui o vínculo formal.
            </p>
          </div>
          <p className="text-xs text-muted-foreground">
            Informe ao menos um alvo: permissionário, empresa ou veículo.
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
            <Button type="submit" disabled={registrarM.isPending}>
              {registrarM.isPending ? "Registrando..." : "Registrar"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
