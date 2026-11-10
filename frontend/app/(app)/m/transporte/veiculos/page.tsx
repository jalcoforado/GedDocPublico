"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  Building2,
  Car,
  Eye,
  Inbox,
  PauseCircle,
  Pencil,
  Plus,
  RotateCcw,
  SearchX,
  Trash2,
  User,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import {
  CampoVinculo,
  errosDoVinculo,
  idsDoVinculo,
  modoDoVinculo,
  type ModoVinculo,
} from "@/components/transporte/campo-vinculo";
import {
  dicaVigencia,
  erroValidade,
  GrupoCampos,
  useValidacao,
} from "@/components/transporte/formulario";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { SkeletonRow } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type TipoCombustivel,
  type TipoServico,
  type VeiculoCategoria,
  type VeiculoRegulado,
  type VeiculoReguladoSituacao,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TIPOS: { value: TipoServico; label: string }[] = [
  { value: "taxi", label: "Táxi" },
  { value: "mototaxi", label: "Mototáxi" },
  { value: "transporte_escolar", label: "Transporte escolar" },
  { value: "motofrete", label: "Motofrete" },
  { value: "transporte_distrital", label: "Transporte distrital" },
  { value: "aplicativo", label: "Aplicativo" },
  { value: "outro", label: "Outro" },
];
const SITUACOES: { value: VeiculoReguladoSituacao; label: string }[] = [
  { value: "pendente", label: "Pendente" },
  { value: "ativo", label: "Ativo" },
  { value: "suspenso", label: "Suspenso" },
  { value: "cassado", label: "Cassado" },
  { value: "inativo", label: "Inativo" },
];
const CATEGORIAS: { value: VeiculoCategoria; label: string }[] = [
  { value: "automovel", label: "Automóvel" },
  { value: "motocicleta", label: "Motocicleta" },
  { value: "van", label: "Van" },
  { value: "micro_onibus", label: "Micro-ônibus" },
  { value: "onibus", label: "Ônibus" },
  { value: "utilitario", label: "Utilitário" },
  { value: "outro", label: "Outro" },
];
const COMBUSTIVEIS: { value: TipoCombustivel; label: string }[] = [
  { value: "gasolina", label: "Gasolina" },
  { value: "etanol", label: "Etanol" },
  { value: "diesel", label: "Diesel" },
  { value: "flex", label: "Flex" },
  { value: "gnv", label: "GNV" },
  { value: "eletrico", label: "Elétrico" },
  { value: "hibrido", label: "Híbrido" },
  { value: "outro", label: "Outro" },
];
const PAGE_SIZE = 50;
const TIPO_LABEL: Record<string, string> = Object.fromEntries(TIPOS.map((t) => [t.value, t.label]));
const SIT_LABEL: Record<string, string> = Object.fromEntries(SITUACOES.map((s) => [s.value, s.label]));
const SIT_INTENT: Record<string, "success" | "warning" | "info" | "danger" | "neutral"> = {
  ativo: "success",
  pendente: "warning",
  suspenso: "info",
  cassado: "danger",
  inativo: "neutral",
};

interface VeiculoForm {
  id_permissionario: string;
  id_empresa: string;
  placa: string;
  renavam: string;
  chassi: string;
  marca: string;
  modelo: string;
  ano_fabricacao: string;
  ano_modelo: string;
  cor: string;
  categoria: string;
  tipo_servico: TipoServico;
  capacidade_passageiros: string;
  tipo_combustivel: string;
  adaptado: boolean;
  numero_autorizacao: string;
  data_inicio_autorizacao: string;
  data_validade_autorizacao: string;
  situacao: VeiculoReguladoSituacao;
  observacoes: string;
}

const EMPTY: VeiculoForm = {
  id_permissionario: "",
  id_empresa: "",
  placa: "",
  renavam: "",
  chassi: "",
  marca: "",
  modelo: "",
  ano_fabricacao: "",
  ano_modelo: "",
  cor: "",
  categoria: "",
  tipo_servico: "taxi",
  capacidade_passageiros: "",
  tipo_combustivel: "",
  adaptado: false,
  numero_autorizacao: "",
  data_inicio_autorizacao: "",
  data_validade_autorizacao: "",
  situacao: "pendente",
  observacoes: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}
function numOrNull(v: string): number | null {
  const t = v.trim();
  return t === "" ? null : Number(t);
}

export default function VeiculosReguladosPage() {
  const { can } = useAuth();
  const canCreate = can("transporte_regulado", "inserir");
  const canEdit = can("transporte_regulado", "atualizar");
  const canDelete = can("transporte_regulado", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [situacaoFiltro, setSituacaoFiltro] = useState("");
  const [tipoFiltro, setTipoFiltro] = useState("");
  const [busca, setBusca] = useState("");
  // Truncava em 50 sem aviso (backend já pagina desde 2026-07-20; a UI nunca
  // ganhou controle). Reseta pra 1 a cada troca de filtro/busca.
  const [page, setPage] = useState(1);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<VeiculoRegulado | null>(null);
  const [form, setForm] = useState<VeiculoForm>(EMPTY);
  const [modoVinculo, setModoVinculo] = useState<ModoVinculo>("permissionario");
  const [err, setErr] = useState<string | null>(null);

  const listaQ = useQuery({
    queryKey: ["tr-veiculos", situacaoFiltro, tipoFiltro, busca, page],
    queryFn: () =>
      api.veiculosRegulados.list({
        situacao: situacaoFiltro || undefined,
        tipo_servico: tipoFiltro || undefined,
        q: busca.trim() || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  });
  const totalPages = Math.max(1, Math.ceil((listaQ.data?.total ?? 0) / PAGE_SIZE));
  const filtrando = situacaoFiltro !== "" || tipoFiltro !== "" || busca.trim() !== "";

  function limparFiltros() {
    setSituacaoFiltro("");
    setTipoFiltro("");
    setBusca("");
    setPage(1);
  }

  // Vínculos para os selects (permissionário / empresa).
  const permsQ = useQuery({
    queryKey: ["tr-perms-vinc"],
    queryFn: () => api.permissionarios.list(),
  });
  const empresasQ = useQuery({
    queryKey: ["tr-empresas-vinc"],
    queryFn: () => api.empresas.list(),
  });
  const semVinculos =
    (permsQ.data?.items.length ?? 0) === 0 && (empresasQ.data?.items.length ?? 0) === 0 &&
    !permsQ.isLoading && !empresasQ.isLoading;

  const permLabel = (id: number | null) =>
    id == null ? null : permsQ.data?.items.find((p) => p.id === id)?.nome ?? `#${id}`;
  const empLabel = (id: number | null) =>
    id == null ? null : empresasQ.data?.items.find((e) => e.id === id)?.razao_social ?? `#${id}`;

  const invalidate = () => qc.invalidateQueries({ queryKey: ["tr-veiculos"] });

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing ? api.veiculosRegulados.update(editing.id, data) : api.veiculosRegulados.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Veículo atualizado." : "Veículo cadastrado.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const actionM = useMutation({
    mutationFn: ({ id, acao }: { id: number; acao: "inativar" | "reativar" | "suspender" }) =>
      acao === "inativar"
        ? api.veiculosRegulados.inativar(id)
        : acao === "reativar"
          ? api.veiculosRegulados.reativar(id)
          : api.veiculosRegulados.suspender(id),
    onSuccess: () => {
      invalidate();
      toast.success("Situação atualizada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.veiculosRegulados.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Veículo excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Regras do backend (`VeiculoReguladoCreate`) ditas no campo, com o conserto.
  const placaNorm = form.placa.replace(/[\s-]/g, "");
  const renavamDigitos = form.renavam.replace(/\D/g, "");
  const errosVinculo = errosDoVinculo(modoVinculo, form.id_permissionario, form.id_empresa);
  const val = useValidacao<
    "id_permissionario" | "id_empresa" | "placa" | "renavam" | "marca" | "modelo" | "ano_modelo" | "data_validade_autorizacao"
  >({
    ...errosVinculo,
    placa:
      placaNorm === ""
        ? "Informe a placa."
        : !/^[A-Za-z0-9]{7}$/.test(placaNorm)
          ? "A placa tem 7 caracteres: ABC1D23 (Mercosul) ou ABC-1234."
          : undefined,
    renavam:
      renavamDigitos !== "" && (renavamDigitos.length < 9 || renavamDigitos.length > 11)
        ? "O RENAVAM tem de 9 a 11 dígitos: confira no documento do veículo."
        : undefined,
    marca: form.marca.trim() === "" ? "Informe a marca." : undefined,
    modelo: form.modelo.trim() === "" ? "Informe o modelo." : undefined,
    ano_modelo:
      form.ano_fabricacao && form.ano_modelo && Number(form.ano_modelo) < Number(form.ano_fabricacao)
        ? "O ano do modelo não pode ser antes do ano de fabricação."
        : undefined,
    data_validade_autorizacao: erroValidade(form.data_inicio_autorizacao, form.data_validade_autorizacao),
  });

  function set<K extends keyof VeiculoForm>(key: K, value: VeiculoForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }
  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setModoVinculo("permissionario");
    setErr(null);
    val.reiniciar();
    setDialogOpen(true);
  }
  function openEdit(v: VeiculoRegulado) {
    setEditing(v);
    setForm({
      id_permissionario: v.id_permissionario != null ? String(v.id_permissionario) : "",
      id_empresa: v.id_empresa != null ? String(v.id_empresa) : "",
      placa: v.placa,
      renavam: v.renavam ?? "",
      chassi: v.chassi ?? "",
      marca: v.marca,
      modelo: v.modelo,
      ano_fabricacao: v.ano_fabricacao != null ? String(v.ano_fabricacao) : "",
      ano_modelo: v.ano_modelo != null ? String(v.ano_modelo) : "",
      cor: v.cor ?? "",
      categoria: v.categoria ?? "",
      tipo_servico: v.tipo_servico,
      capacidade_passageiros: v.capacidade_passageiros != null ? String(v.capacidade_passageiros) : "",
      tipo_combustivel: v.tipo_combustivel ?? "",
      adaptado: v.adaptado,
      numero_autorizacao: v.numero_autorizacao ?? "",
      data_inicio_autorizacao: v.data_inicio_autorizacao ?? "",
      data_validade_autorizacao: v.data_validade_autorizacao ?? "",
      situacao: v.situacao,
      observacoes: v.observacoes ?? "",
    });
    setModoVinculo(
      modoDoVinculo(
        v.id_permissionario != null ? String(v.id_permissionario) : "",
        v.id_empresa != null ? String(v.id_empresa) : "",
      ),
    );
    setErr(null);
    val.reiniciar();
    setDialogOpen(true);
  }
  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }
  function salvar() {
    setErr(null);
    if (!val.conferir()) return;
    const payload = {
      ...idsDoVinculo(modoVinculo, form.id_permissionario, form.id_empresa),
      placa: form.placa.trim(),
      renavam: nullify(form.renavam),
      chassi: nullify(form.chassi),
      marca: form.marca.trim(),
      modelo: form.modelo.trim(),
      ano_fabricacao: numOrNull(form.ano_fabricacao),
      ano_modelo: numOrNull(form.ano_modelo),
      cor: nullify(form.cor),
      categoria: form.categoria === "" ? null : form.categoria,
      tipo_servico: form.tipo_servico,
      capacidade_passageiros: numOrNull(form.capacidade_passageiros),
      tipo_combustivel: form.tipo_combustivel === "" ? null : form.tipo_combustivel,
      adaptado: form.adaptado,
      numero_autorizacao: nullify(form.numero_autorizacao),
      data_inicio_autorizacao: nullify(form.data_inicio_autorizacao),
      data_validade_autorizacao: nullify(form.data_validade_autorizacao),
      situacao: form.situacao,
      observacoes: nullify(form.observacoes),
    };
    saveM.mutate(payload);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Car}
        title="Veículos regulados"
        description="Veículos vinculados a permissionários ou empresas autorizadas (não confundir com a frota interna do município)."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Veículos regulados" },
        ]}
        actions={
          canCreate ? (
            <Button onClick={openNew} disabled={semVinculos}>
              <Plus className="mr-1 h-4 w-4" />
              Novo veículo
            </Button>
          ) : undefined
        }
      />

      {semVinculos && (
        <Alert intent="warning">
          Cadastre ao menos um permissionário ou empresa antes de registrar veículos — todo veículo
          regulado precisa de um vínculo.
        </Alert>
      )}

      <FilterBar ariaLabel="Filtros dos veículos">
        <FilterBar.Group label="Situação" className="w-full sm:w-48">
          <Select
            id="f_sit"
            aria-label="Situação"
            value={situacaoFiltro}
            onChange={(e) => {
              setSituacaoFiltro(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Todas</option>
            {SITUACOES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        <FilterBar.Group label="Tipo de serviço" className="w-full sm:w-56">
          <Select
            id="f_tipo"
            aria-label="Tipo de serviço"
            value={tipoFiltro}
            onChange={(e) => {
              setTipoFiltro(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            {TIPOS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        <FilterBar.Group label="Busca" className="min-w-[200px] flex-1">
          <Input
            id="f_q"
            aria-label="Busca"
            value={busca}
            onChange={(e) => {
              setBusca(e.target.value);
              setPage(1);
            }}
            placeholder="Placa, marca, modelo, RENAVAM ou chassi"
          />
        </FilterBar.Group>
        {filtrando && (
          <FilterBar.Actions>
            <Button variant="ghost" onClick={limparFiltros}>
              Limpar
            </Button>
          </FilterBar.Actions>
        )}
      </FilterBar>

      {!listaQ.isLoading && (listaQ.data?.items.length ?? 0) === 0 ? (
        <EmptyState
          icon={filtrando ? SearchX : Inbox}
          title={filtrando ? "Nenhum veículo encontrado" : "Nenhum veículo regulado"}
          description={
            filtrando
              ? "Nenhum veículo corresponde à busca ou aos filtros aplicados."
              : "Cadastre o primeiro veículo vinculado a um permissionário ou empresa."
          }
          action={
            filtrando ? (
              <Button variant="secondary" onClick={limparFiltros}>
                Limpar filtros
              </Button>
            ) : canCreate && !semVinculos ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Cadastrar veículo
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Placa</TH>
              <TH>Marca / Modelo</TH>
              <TH>Vínculo</TH>
              <TH>Tipo de serviço</TH>
              <TH>Autorização</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {listaQ.isLoading &&
              Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} cols={7} />)}
            {listaQ.data?.items.map((v) => (
              <TR key={v.id}>
                <TD className="whitespace-nowrap font-mono font-medium">
                  <Link
                    href={`/m/transporte/veiculos/${v.id}`}
                    className="text-primary hover:underline"
                  >
                    {v.placa}
                  </Link>
                </TD>
                <TD>
                  <div className="font-medium">{v.marca}</div>
                  <div className="text-xs text-muted-foreground">{v.modelo}</div>
                </TD>
                {/* Era 👤/🏢 em emoji, que em parte das fontes do sistema
                    virava um "▌" antes do nome. Ícone da própria UI no lugar. */}
                <TD className="text-sm text-muted-foreground">
                  {permLabel(v.id_permissionario) && (
                    <div className="flex items-center gap-1.5">
                      <User className="h-3.5 w-3.5 shrink-0" aria-label="Permissionário" />
                      {permLabel(v.id_permissionario)}
                    </div>
                  )}
                  {empLabel(v.id_empresa) && (
                    <div className="flex items-center gap-1.5">
                      <Building2 className="h-3.5 w-3.5 shrink-0" aria-label="Empresa" />
                      {empLabel(v.id_empresa)}
                    </div>
                  )}
                  {v.id_permissionario == null && v.id_empresa == null && "—"}
                </TD>
                <TD>{TIPO_LABEL[v.tipo_servico] ?? v.tipo_servico}</TD>
                <TD className="text-muted-foreground">{v.numero_autorizacao ?? "—"}</TD>
                <TD>
                  <Badge intent={SIT_INTENT[v.situacao] ?? "neutral"}>
                    {SIT_LABEL[v.situacao] ?? v.situacao}
                  </Badge>
                </TD>
                <TD className="text-right">
                  {/* Mesma ordem dos permissionários: o que muda com a
                      situação vem à vista; Inativar e Excluir ficam no ⋯. */}
                  <AcoesDaLinha
                    acoes={[
                      { label: "Detalhes", icon: Eye, href: `/m/transporte/veiculos/${v.id}` },
                      { label: "Editar", icon: Pencil, onClick: () => openEdit(v), oculta: !canEdit },
                      {
                        label: "Reativar",
                        icon: RotateCcw,
                        onClick: () => actionM.mutate({ id: v.id, acao: "reativar" }),
                        oculta: !canEdit || v.situacao === "ativo",
                      },
                      {
                        label: "Suspender",
                        icon: PauseCircle,
                        onClick: () => actionM.mutate({ id: v.id, acao: "suspender" }),
                        oculta: !canEdit || v.situacao === "suspenso",
                      },
                      {
                        label: "Inativar",
                        icon: Ban,
                        perigo: true,
                        onClick: () => actionM.mutate({ id: v.id, acao: "inativar" }),
                        oculta: !canEdit || v.situacao === "inativo",
                      },
                      {
                        label: "Excluir",
                        icon: Trash2,
                        perigo: true,
                        disabled: deleteM.isPending,
                        oculta: !canDelete,
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

      {listaQ.data && listaQ.data.total > 0 && (
        <div className="flex flex-col items-start justify-between gap-2 text-sm text-muted-foreground sm:flex-row sm:items-center">
          <span className="tabular-nums">
            {listaQ.data.total} veículos — página {page} de {totalPages}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              Anterior
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              Próxima
            </Button>
          </div>
        </div>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? `Editar veículo — ${editing.placa}` : "Novo veículo regulado"}
        description={
          editing ? undefined : "De quem é, qual veículo e com que autorização roda. Placa, marca e modelo são obrigatórios."
        }
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={salvar} loading={saveM.isPending}>
              {editing ? "Salvar alterações" : "Cadastrar veículo"}
            </Button>
          </>
        }
      >
        <div ref={val.ref} className="space-y-5">
          <GrupoCampos titulo="Vínculo">
            <CampoVinculo
              nome="veiculo-vinculo"
              titulo="O veículo está em nome de"
              modo={modoVinculo}
              onModo={setModoVinculo}
              descricoes={{
                permissionario: "Veículo de um permissionário que opera por conta própria.",
                empresa: "Veículo da frota de uma empresa autorizada.",
                ambos: "Veículo de uma empresa, conduzido por um permissionário.",
              }}
              idPermissionario={form.id_permissionario}
              idEmpresa={form.id_empresa}
              onPermissionario={(id) => set("id_permissionario", id)}
              onEmpresa={(id) => set("id_empresa", id)}
              permissionarios={permsQ.data?.items ?? []}
              empresas={empresasQ.data?.items ?? []}
              carregando={permsQ.isLoading || empresasQ.isLoading}
              erroPermissionario={val.erro("id_permissionario")}
              erroEmpresa={val.erro("id_empresa")}
            />
          </GrupoCampos>

          <GrupoCampos titulo="Identificação" descricao="Como está no documento do veículo (CRLV).">
            <GradeCampos>
              <FormField label="Placa" required error={val.erro("placa")} hint="Mercosul (ABC1D23) ou antiga (ABC-1234).">
                <Input
                  id="placa"
                  value={form.placa}
                  onChange={(e) => set("placa", e.target.value.toUpperCase())}
                  onBlur={val.sair("placa")}
                  maxLength={8}
                  autoComplete="off"
                  className="font-mono uppercase tracking-wide"
                  placeholder="Ex.: ABC1D23"
                />
              </FormField>
              <FormField label="RENAVAM" opcional error={val.erro("renavam")} hint="De 9 a 11 dígitos.">
                <Input
                  id="renavam"
                  inputMode="numeric"
                  maxLength={11}
                  className="font-mono tabular-nums"
                  value={form.renavam}
                  onChange={(e) => set("renavam", e.target.value.replace(/\D/g, ""))}
                  onBlur={val.sair("renavam")}
                  placeholder="Ex.: 01234567890"
                />
              </FormField>
            </GradeCampos>
            <FormField label="Chassi" opcional hint="Até 17 caracteres, sem espaços.">
              <Input
                id="chassi"
                maxLength={17}
                className="font-mono uppercase tracking-wide"
                value={form.chassi}
                onChange={(e) => set("chassi", e.target.value.toUpperCase().replace(/\s/g, ""))}
                placeholder="Ex.: 9BWZZZ377VT004251"
              />
            </FormField>
            <GradeCampos>
              <FormField label="Marca" required error={val.erro("marca")}>
                <Input
                  id="marca"
                  value={form.marca}
                  onChange={(e) => set("marca", e.target.value)}
                  onBlur={val.sair("marca")}
                  placeholder="Ex.: Chevrolet"
                />
              </FormField>
              <FormField label="Modelo" required error={val.erro("modelo")}>
                <Input
                  id="modelo"
                  value={form.modelo}
                  onChange={(e) => set("modelo", e.target.value)}
                  onBlur={val.sair("modelo")}
                  placeholder="Ex.: Spin LTZ 1.8"
                />
              </FormField>
            </GradeCampos>
            <GradeCampos>
              <FormField label="Ano de fabricação" opcional>
                <Input
                  id="anofab"
                  type="number"
                  inputMode="numeric"
                  value={form.ano_fabricacao}
                  onChange={(e) => set("ano_fabricacao", e.target.value)}
                  placeholder="Ex.: 2022"
                />
              </FormField>
              <FormField label="Ano do modelo" opcional error={val.erro("ano_modelo")}>
                <Input
                  id="anomod"
                  type="number"
                  inputMode="numeric"
                  value={form.ano_modelo}
                  onChange={(e) => set("ano_modelo", e.target.value)}
                  onBlur={val.sair("ano_modelo")}
                  placeholder="Ex.: 2023"
                />
              </FormField>
            </GradeCampos>
            <GradeCampos>
              <FormField label="Categoria" opcional>
                <Select id="cat" value={form.categoria} onChange={(e) => set("categoria", e.target.value)}>
                  <option value="">Selecione…</option>
                  {CATEGORIAS.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField label="Cor" opcional>
                <Input id="cor" value={form.cor} onChange={(e) => set("cor", e.target.value)} placeholder="Ex.: Prata" />
              </FormField>
            </GradeCampos>
          </GrupoCampos>

          <GrupoCampos titulo="Uso">
            <GradeCampos>
              <FormField label="Tipo de serviço" required>
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
              </FormField>
              <FormField label="Combustível" opcional>
                <Select id="comb" value={form.tipo_combustivel} onChange={(e) => set("tipo_combustivel", e.target.value)}>
                  <option value="">Selecione…</option>
                  {COMBUSTIVEIS.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </Select>
              </FormField>
            </GradeCampos>
            <GradeCampos>
              <FormField label="Capacidade de passageiros" opcional hint="Lugares para passageiros, como no CRLV.">
                <Input
                  id="cap"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  value={form.capacidade_passageiros}
                  onChange={(e) => set("capacidade_passageiros", e.target.value)}
                  placeholder="Ex.: 4"
                />
              </FormField>
              <div className="flex items-center gap-2 sm:pt-7">
                <Checkbox
                  id="adaptado"
                  checked={form.adaptado}
                  onChange={(e) => set("adaptado", e.target.checked)}
                />
                <label htmlFor="adaptado" className="cursor-pointer text-sm text-foreground">
                  Adaptado para acessibilidade
                </label>
              </div>
            </GradeCampos>
          </GrupoCampos>

          <GrupoCampos titulo="Autorização" descricao="A autorização municipal para o veículo rodar no serviço.">
            <FormField label="Número da autorização" opcional>
              <Input
                id="numaut"
                value={form.numero_autorizacao}
                onChange={(e) => set("numero_autorizacao", e.target.value)}
                placeholder="Ex.: AUT-0456/2026"
              />
            </FormField>
            <GradeCampos>
              <FormField label="Início da autorização" opcional>
                <Input
                  id="ini"
                  type="date"
                  value={form.data_inicio_autorizacao}
                  onChange={(e) => set("data_inicio_autorizacao", e.target.value)}
                />
              </FormField>
              <FormField
                label="Validade da autorização"
                opcional
                error={val.erro("data_validade_autorizacao")}
                hint={dicaVigencia(
                  form.data_inicio_autorizacao,
                  form.data_validade_autorizacao,
                  "Último dia em que a autorização vale.",
                )}
              >
                <Input
                  id="val"
                  type="date"
                  value={form.data_validade_autorizacao}
                  onChange={(e) => set("data_validade_autorizacao", e.target.value)}
                  onBlur={val.sair("data_validade_autorizacao")}
                />
              </FormField>
            </GradeCampos>
            <FormField
              label="Situação"
              hint={
                editing
                  ? "Suspender e reativar também ficam nas ações da linha."
                  : "Cadastro novo entra como Pendente, salvo se mudar aqui."
              }
            >
              <Select
                id="sit"
                value={form.situacao}
                onChange={(e) => set("situacao", e.target.value as VeiculoReguladoSituacao)}
              >
                {SITUACOES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </Select>
            </FormField>
          </GrupoCampos>

          <div className="border-t border-border pt-5">
            <FormField label="Observações" opcional>
              <Textarea
                id="obs"
                rows={2}
                value={form.observacoes}
                onChange={(e) => set("observacoes", e.target.value)}
                placeholder="Ex.: veículo reserva, troca de placa em andamento"
              />
            </FormField>
          </div>

          {err && <Alert intent="danger">{err}</Alert>}
        </div>
      </Dialog>
    </div>
  );
}
