"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Car, FileText, Inbox, Pencil, Plus, SearchX, Settings2, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { numeroOuNulo, useErrosDoFormulario } from "@/components/frota/formulario";
import { COMBUSTIVEIS, SITUACOES_VEICULO } from "@/components/frota/rotulos";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada, type OpcaoEscolha } from "@/components/ui/escolha-segmentada";
import { FilterBar } from "@/components/ui/filter-bar";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type Veiculo,
  type VeiculoFormaPosse,
  type VeiculoSituacao,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

import { DocumentosDialog } from "./documentos-dialog";

const SITUACOES = SITUACOES_VEICULO;
// Quatro opções: à vista, com o que cada uma quer dizer (EscolhaSegmentada).
const FORMA_POSSE: OpcaoEscolha<VeiculoFormaPosse>[] = [
  { valor: "proprio", rotulo: "Próprio", descricao: "Patrimônio do município." },
  { valor: "locado", rotulo: "Locado", descricao: "Alugado de uma empresa, por contrato." },
  { valor: "cedido", rotulo: "Cedido", descricao: "Emprestado por outro órgão ou entidade." },
  { valor: "convenio", rotulo: "Convênio", descricao: "Recebido por convênio com outro ente público." },
];

// Mesma regra do backend (schemas/frota.py::PLACA_PATTERN), depois de tirar
// hífen e espaço: avisar aqui poupa a ida ao servidor só para ouvir "não".
const PLACA = /^[A-Z]{3}[0-9][0-9A-Z][0-9]{2}$/;

function anoInvalido(ano: number | null): boolean {
  return ano != null && (!Number.isInteger(ano) || ano < 1900 || ano > 2100);
}

function validar(form: VeiculoForm): Record<string, string | undefined> {
  const placa = form.placa.replace(/[-\s]/g, "").toUpperCase();
  return {
    placa: !placa
      ? "Informe a placa."
      : !PLACA.test(placa)
        ? "Use o formato ABC1234 ou ABC1D23 (Mercosul)."
        : undefined,
    ano_fab: anoInvalido(form.ano_fabricacao) ? "Informe um ano entre 1900 e 2100." : undefined,
    ano_mod: anoInvalido(form.ano_modelo) ? "Informe um ano entre 1900 e 2100." : undefined,
    km:
      !Number.isInteger(form.quilometragem_atual) || form.quilometragem_atual < 0
        ? "Informe a quilometragem em km inteiros, sem pontos."
        : undefined,
  };
}
const SITUACAO_POR_VALOR = Object.fromEntries(SITUACOES.map((s) => [s.value, s]));

interface VeiculoForm {
  placa: string;
  numero_tombo: string;
  renavam: string;
  chassi: string;
  marca: string;
  modelo: string;
  ano_fabricacao: number | null;
  ano_modelo: number | null;
  cor: string;
  tipo_veiculo: string;
  tipo_combustivel: string;
  situacao: VeiculoSituacao;
  id_unidade_responsavel: number | null;
  quilometragem_atual: number;
  data_aquisicao: string;
  forma_posse: VeiculoFormaPosse;
  observacoes: string;
}

const EMPTY: VeiculoForm = {
  placa: "",
  numero_tombo: "",
  renavam: "",
  chassi: "",
  marca: "",
  modelo: "",
  ano_fabricacao: null,
  ano_modelo: null,
  cor: "",
  tipo_veiculo: "",
  tipo_combustivel: "",
  situacao: "disponivel",
  id_unidade_responsavel: null,
  quilometragem_atual: 0,
  data_aquisicao: "",
  forma_posse: "proprio",
  observacoes: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

export default function VeiculosPage() {
  const { can } = useAuth();
  const canCreate = can("frota", "inserir");
  const canEdit = can("frota", "atualizar");
  const canDelete = can("frota", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [busca, setBusca] = useState("");
  const [situacaoFiltro, setSituacaoFiltro] = useState<string>("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Veiculo | null>(null);
  const [form, setForm] = useState<VeiculoForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);
  const [docsVeiculo, setDocsVeiculo] = useState<Veiculo | null>(null);
  const campos = useErrosDoFormulario(validar(form));

  const veiculosQ = useQuery({ queryKey: ["frota-veiculos"], queryFn: () => api.frota.listAll() });
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });
  const unidades = unidadesQ.data?.items ?? [];
  const unidadeNome = (id: number | null) =>
    unidades.find((u) => u.id === id)?.unidade_trabalho ?? "—";

  const veiculos = veiculosQ.data ?? [];
  const filtrados = useMemo(() => {
    const q = busca.trim().toLowerCase();
    return veiculos.filter((v) => {
      if (situacaoFiltro && v.situacao !== situacaoFiltro) return false;
      if (!q) return true;
      return [v.placa, v.numero_tombo, v.marca, v.modelo, v.renavam, v.chassi]
        .some((campo) => campo?.toLowerCase().includes(q));
    });
  }, [veiculos, busca, situacaoFiltro]);
  const temFiltroAtivo = busca.trim() !== "" || situacaoFiltro !== "";
  function limparFiltros() {
    setBusca("");
    setSituacaoFiltro("");
  }

  const invalidate = () => qc.invalidateQueries({ queryKey: ["frota-veiculos"] });

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing ? api.frota.update(editing.id, data) : api.frota.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Veículo atualizado." : "Veículo cadastrado.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.frota.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Veículo excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof VeiculoForm>(key: K, value: VeiculoForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    campos.limpar();
    setDialogOpen(true);
  }

  function openEdit(v: Veiculo) {
    setEditing(v);
    setForm({
      placa: v.placa,
      numero_tombo: v.numero_tombo ?? "",
      renavam: v.renavam ?? "",
      chassi: v.chassi ?? "",
      marca: v.marca ?? "",
      modelo: v.modelo ?? "",
      ano_fabricacao: v.ano_fabricacao,
      ano_modelo: v.ano_modelo,
      cor: v.cor ?? "",
      tipo_veiculo: v.tipo_veiculo ?? "",
      tipo_combustivel: v.tipo_combustivel ?? "",
      situacao: v.situacao,
      id_unidade_responsavel: v.id_unidade_responsavel,
      quilometragem_atual: v.quilometragem_atual,
      data_aquisicao: v.data_aquisicao ?? "",
      forma_posse: v.forma_posse,
      observacoes: v.observacoes ?? "",
    });
    setErr(null);
    campos.limpar();
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }

  function salvar() {
    setErr(null);
    if (!campos.podeEnviar()) return;
    const payload = {
      placa: form.placa.trim(),
      numero_tombo: nullify(form.numero_tombo),
      renavam: nullify(form.renavam),
      chassi: nullify(form.chassi),
      marca: nullify(form.marca),
      modelo: nullify(form.modelo),
      ano_fabricacao: form.ano_fabricacao ?? null,
      ano_modelo: form.ano_modelo ?? null,
      cor: nullify(form.cor),
      tipo_veiculo: nullify(form.tipo_veiculo),
      tipo_combustivel: nullify(form.tipo_combustivel),
      situacao: form.situacao,
      id_unidade_responsavel: form.id_unidade_responsavel ?? null,
      quilometragem_atual: form.quilometragem_atual ?? 0,
      data_aquisicao: nullify(form.data_aquisicao),
      forma_posse: form.forma_posse,
      observacoes: nullify(form.observacoes),
    };
    saveM.mutate(payload);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Car}
        title="Veículos"
        description="Cadastro da frota própria do município."
        breadcrumbs={[{ label: "Frota Pública", href: "/m/frota" }, { label: "Veículos" }]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Novo veículo
            </Button>
          ) : undefined
        }
      />

      {(veiculosQ.isLoading || veiculos.length > 0) && (
        <FilterBar>
          <FilterBar.Group label="Situação">
            <Select
              aria-label="Situação"
              value={situacaoFiltro}
              onChange={(e) => setSituacaoFiltro(e.target.value)}
            >
              <option value="">Todas</option>
              {SITUACOES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </Select>
          </FilterBar.Group>
          <FilterBar.Group label="Busca" className="min-w-[200px] flex-1">
            <Input
              aria-label="Busca"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Placa, tombo, marca, modelo, RENAVAM ou chassi"
            />
          </FilterBar.Group>
          {temFiltroAtivo && (
            <FilterBar.Actions>
              <Button variant="ghost" onClick={limparFiltros}>
                Limpar
              </Button>
            </FilterBar.Actions>
          )}
        </FilterBar>
      )}

      {!veiculosQ.isLoading && veiculos.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhum veículo cadastrado"
          description="Cadastre o primeiro veículo da frota."
          action={
            canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Novo veículo
              </Button>
            ) : undefined
          }
        />
      ) : !veiculosQ.isLoading && filtrados.length === 0 && temFiltroAtivo ? (
        <EmptyState
          icon={SearchX}
          title="Nenhum veículo encontrado"
          description="Nenhum veículo corresponde à busca ou ao filtro aplicado."
          action={
            <Button variant="secondary" onClick={limparFiltros}>
              Limpar filtros
            </Button>
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Placa</TH>
              <TH>Tombo</TH>
              <TH>Marca / Modelo</TH>
              <TH>Situação</TH>
              <TH>Unidade</TH>
              <TH className="text-right">Km</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {veiculosQ.isLoading && (
              <TR>
                <TD colSpan={7} className="text-center text-muted-foreground">
                  Carregando veículos...
                </TD>
              </TR>
            )}
            {filtrados.map((v) => (
              <TR key={v.id}>
                <TD className="font-mono">{v.placa}</TD>
                <TD className="tabular-nums text-muted-foreground">{v.numero_tombo ?? "—"}</TD>
                <TD>{[v.marca, v.modelo].filter(Boolean).join(" ") || "—"}</TD>
                <TD>
                  <Badge intent={SITUACAO_POR_VALOR[v.situacao]?.intent ?? "neutral"}>
                    {SITUACAO_POR_VALOR[v.situacao]?.label ?? v.situacao}
                  </Badge>
                </TD>
                <TD className="text-muted-foreground">{unidadeNome(v.id_unidade_responsavel)}</TD>
                <TD className="text-right tabular-nums">
                  {v.quilometragem_atual.toLocaleString("pt-BR")}
                </TD>
                <TD className="text-right">
                  <AcoesDaLinha
                    acoes={[
                      { label: "Documentos", icon: FileText, onClick: () => setDocsVeiculo(v) },
                      {
                        label: "Editar",
                        icon: Pencil,
                        oculta: !canEdit,
                        onClick: () => openEdit(v),
                      },
                      {
                        label: "Excluir",
                        icon: Trash2,
                        perigo: true,
                        oculta: !canDelete,
                        disabled: deleteM.isPending,
                        onClick: async () => {
                          const ok = await confirm({
                            title: "Excluir veículo",
                            message: `Excluir o veículo de placa "${v.placa}"? Esta ação não pode ser desfeita.`,
                            confirmLabel: "Excluir",
                            intent: "danger",
                          });
                          if (ok) deleteM.mutate(v.id);
                        },
                      },
                    ]}
                  />
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? "Editar veículo" : "Novo veículo"}
        description={editing ? `Placa ${editing.placa}` : "Só a placa é obrigatória; o resto pode ser completado depois."}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button type="submit" form="form-veiculo" loading={saveM.isPending}>
              {editing ? "Salvar alterações" : "Cadastrar veículo"}
            </Button>
          </>
        }
      >
        <form
          id="form-veiculo"
          noValidate
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            salvar();
          }}
        >
          <SectionCard icon={FileText} title="Identificação" description="Como o veículo é reconhecido nos documentos.">
            <div className="space-y-4">
              <GradeCampos>
                <FormField
                  label="Placa"
                  required
                  hint="Antiga (ABC1234) ou Mercosul (ABC1D23)."
                  error={campos.erro("placa")}
                >
                  <Input
                    id="placa"
                    value={form.placa}
                    onChange={(e) => set("placa", e.target.value.toUpperCase())}
                    onBlur={campos.tocar("placa")}
                    className="font-mono uppercase"
                    placeholder="Ex.: ABC1D23"
                    maxLength={8}
                    autoComplete="off"
                  />
                </FormField>
                <FormField
                  label="Número de tombo"
                  hint="Liga o veículo ao bem no Patrimônio."
                >
                  <Input
                    id="numero_tombo"
                    value={form.numero_tombo}
                    onChange={(e) => set("numero_tombo", e.target.value)}
                    maxLength={30}
                    placeholder="Ex.: 004512"
                  />
                </FormField>
              </GradeCampos>
              <GradeCampos>
                <FormField label="RENAVAM">
                  <Input
                    id="renavam"
                    value={form.renavam}
                    onChange={(e) => set("renavam", e.target.value)}
                    inputMode="numeric"
                    className="font-mono"
                    placeholder="Ex.: 01234567890"
                    maxLength={20}
                  />
                </FormField>
                <FormField label="Chassi">
                  <Input
                    id="chassi"
                    value={form.chassi}
                    onChange={(e) => set("chassi", e.target.value.toUpperCase())}
                    className="font-mono uppercase"
                    placeholder="Ex.: 9BD000000A0000000"
                    maxLength={30}
                  />
                </FormField>
              </GradeCampos>
            </div>
          </SectionCard>

          <SectionCard icon={Car} title="Modelo" description="O que é o veículo — aparece nas listas junto da placa.">
            <div className="space-y-4">
              <GradeCampos>
                <FormField label="Marca">
                  <Input
                    id="marca"
                    value={form.marca}
                    onChange={(e) => set("marca", e.target.value)}
                    placeholder="Ex.: Fiat"
                    maxLength={60}
                  />
                </FormField>
                <FormField label="Modelo">
                  <Input
                    id="modelo"
                    value={form.modelo}
                    onChange={(e) => set("modelo", e.target.value)}
                    placeholder="Ex.: Strada Freedom"
                    maxLength={80}
                  />
                </FormField>
              </GradeCampos>
              <GradeCampos>
                <FormField label="Ano de fabricação" error={campos.erro("ano_fab")}>
                  <Input
                    id="ano_fab"
                    type="number"
                    inputMode="numeric"
                    min={1900}
                    max={2100}
                    value={form.ano_fabricacao ?? ""}
                    onChange={(e) => set("ano_fabricacao", numeroOuNulo(e.target.value))}
                    onBlur={campos.tocar("ano_fab")}
                    placeholder="Ex.: 2022"
                  />
                </FormField>
                <FormField label="Ano do modelo" error={campos.erro("ano_mod")}>
                  <Input
                    id="ano_mod"
                    type="number"
                    inputMode="numeric"
                    min={1900}
                    max={2100}
                    value={form.ano_modelo ?? ""}
                    onChange={(e) => set("ano_modelo", numeroOuNulo(e.target.value))}
                    onBlur={campos.tocar("ano_mod")}
                    placeholder="Ex.: 2023"
                  />
                </FormField>
              </GradeCampos>
              <GradeCampos colunas={3}>
                <FormField label="Tipo de veículo">
                  <Input
                    id="tipo_veiculo"
                    value={form.tipo_veiculo}
                    onChange={(e) => set("tipo_veiculo", e.target.value)}
                    placeholder="Ex.: caminhonete"
                    maxLength={40}
                  />
                </FormField>
                <FormField label="Combustível">
                  <Select
                    id="combustivel"
                    value={form.tipo_combustivel}
                    onChange={(e) => set("tipo_combustivel", e.target.value)}
                  >
                    <option value="">Não informado</option>
                    {COMBUSTIVEIS.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </Select>
                </FormField>
                <FormField label="Cor">
                  <Input
                    id="cor"
                    value={form.cor}
                    onChange={(e) => set("cor", e.target.value)}
                    placeholder="Ex.: branca"
                    maxLength={30}
                  />
                </FormField>
              </GradeCampos>
            </div>
          </SectionCard>

          <SectionCard
            icon={Settings2}
            title="Situação e posse"
            description="De quem é, quem responde por ele e como está agora."
          >
            <div className="space-y-4">
              <EscolhaSegmentada
                nome="forma_posse"
                titulo="Forma de posse"
                moldura={false}
                valor={form.forma_posse}
                opcoes={FORMA_POSSE}
                onChange={(p) => set("forma_posse", p)}
              />
              <GradeCampos>
                <FormField label="Unidade responsável" hint="Quem responde pelo veículo.">
                  <Select
                    id="unidade"
                    value={form.id_unidade_responsavel ?? ""}
                    onChange={(e) =>
                      set("id_unidade_responsavel", e.target.value ? Number(e.target.value) : null)
                    }
                  >
                    <option value="">Nenhuma</option>
                    {unidades.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.unidade_trabalho}
                      </option>
                    ))}
                  </Select>
                </FormField>
                <FormField
                  label="Situação"
                  hint="Muda sozinha na saída e no retorno de viagens e nas manutenções."
                >
                  <Select
                    id="situacao"
                    value={form.situacao}
                    onChange={(e) => set("situacao", e.target.value as VeiculoSituacao)}
                  >
                    {SITUACOES.map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </Select>
                </FormField>
              </GradeCampos>
              <GradeCampos>
                <FormField
                  label="Quilometragem atual"
                  hint="O que marca o painel hoje. Depois, as viagens atualizam."
                  error={campos.erro("km")}
                >
                  <CampoComUnidade
                    id="km"
                    type="number"
                    inputMode="numeric"
                    min={0}
                    sufixo="km"
                    value={form.quilometragem_atual}
                    onChange={(e) => set("quilometragem_atual", e.target.value ? Number(e.target.value) : 0)}
                    onBlur={campos.tocar("km")}
                  />
                </FormField>
                <FormField label="Data de aquisição">
                  <Input
                    id="data_aquisicao"
                    type="date"
                    value={form.data_aquisicao}
                    onChange={(e) => set("data_aquisicao", e.target.value)}
                  />
                </FormField>
              </GradeCampos>
              <FormField label="Observações">
                <Textarea
                  id="obs"
                  rows={3}
                  value={form.observacoes}
                  onChange={(e) => set("observacoes", e.target.value)}
                  placeholder="Ex.: adesivado com o brasão; tem engate"
                />
              </FormField>
            </div>
          </SectionCard>
          {err && (
            <Alert intent="danger" title="Não foi possível salvar">
              {err}
            </Alert>
          )}
        </form>
      </Dialog>

      <DocumentosDialog
        veiculo={docsVeiculo}
        open={docsVeiculo != null}
        onClose={() => setDocsVeiculo(null)}
      />
    </div>
  );
}
