"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Car, Inbox, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

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
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<VeiculoRegulado | null>(null);
  const [form, setForm] = useState<VeiculoForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const listaQ = useQuery({
    queryKey: ["tr-veiculos", situacaoFiltro, tipoFiltro, busca],
    queryFn: () =>
      api.veiculosRegulados.list({
        situacao: situacaoFiltro || undefined,
        tipo_servico: tipoFiltro || undefined,
        q: busca.trim() || undefined,
      }),
  });

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

  function set<K extends keyof VeiculoForm>(key: K, value: VeiculoForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }
  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
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
    setErr(null);
    setDialogOpen(true);
  }
  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }
  function salvar() {
    setErr(null);
    if (form.placa.trim() === "") {
      setErr("Placa é obrigatória.");
      return;
    }
    if (form.marca.trim() === "" || form.modelo.trim() === "") {
      setErr("Marca e modelo são obrigatórios.");
      return;
    }
    if (form.id_permissionario === "" && form.id_empresa === "") {
      setErr("Informe ao menos um vínculo: permissionário ou empresa.");
      return;
    }
    const payload = {
      id_permissionario: form.id_permissionario === "" ? null : Number(form.id_permissionario),
      id_empresa: form.id_empresa === "" ? null : Number(form.id_empresa),
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
        <div role="alert" className="rounded-md bg-warning-soft px-3 py-2 text-sm text-warning-soft-foreground">
          Cadastre ao menos um permissionário ou empresa antes de registrar veículos — todo veículo
          regulado precisa de um vínculo.
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <div>
          <Label htmlFor="f_sit">Situação</Label>
          <Select id="f_sit" value={situacaoFiltro} onChange={(e) => setSituacaoFiltro(e.target.value)}>
            <option value="">Todas</option>
            {SITUACOES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="f_tipo">Tipo de serviço</Label>
          <Select id="f_tipo" value={tipoFiltro} onChange={(e) => setTipoFiltro(e.target.value)}>
            <option value="">Todos</option>
            {TIPOS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex-1 min-w-[200px]">
          <Label htmlFor="f_q">Busca</Label>
          <Input
            id="f_q"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Placa, marca, modelo, RENAVAM ou chassi"
          />
        </div>
      </div>

      {!listaQ.isLoading && (listaQ.data?.items.length ?? 0) === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhum veículo regulado"
          description="Cadastre o primeiro veículo vinculado a um permissionário ou empresa."
          action={
            canCreate && !semVinculos ? (
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
            {listaQ.isLoading && (
              <TR>
                <TD colSpan={7} className="text-center text-muted-foreground">
                  Carregando...
                </TD>
              </TR>
            )}
            {listaQ.data?.items.map((v) => (
              <TR key={v.id}>
                <TD className="font-mono">
                  <Link href={`/m/transporte/veiculos/${v.id}`} className="text-blue-600 hover:underline">
                    {v.placa}
                  </Link>
                </TD>
                <TD>
                  <div className="font-medium">{v.marca}</div>
                  <div className="text-xs text-muted-foreground">{v.modelo}</div>
                </TD>
                <TD className="text-sm text-muted-foreground">
                  {permLabel(v.id_permissionario) && <div>👤 {permLabel(v.id_permissionario)}</div>}
                  {empLabel(v.id_empresa) && <div>🏢 {empLabel(v.id_empresa)}</div>}
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
                  <div className="inline-flex flex-wrap justify-end gap-2">
                    <Link href={`/m/transporte/veiculos/${v.id}`}>
                      <Button variant="secondary" size="sm">
                        Detalhes
                      </Button>
                    </Link>
                    {canEdit && (
                      <Button variant="secondary" size="sm" onClick={() => openEdit(v)}>
                        Editar
                      </Button>
                    )}
                    {canEdit && v.situacao !== "ativo" && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => actionM.mutate({ id: v.id, acao: "reativar" })}
                      >
                        Reativar
                      </Button>
                    )}
                    {canEdit && v.situacao !== "suspenso" && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => actionM.mutate({ id: v.id, acao: "suspender" })}
                      >
                        Suspender
                      </Button>
                    )}
                    {canEdit && v.situacao !== "inativo" && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => actionM.mutate({ id: v.id, acao: "inativar" })}
                      >
                        Inativar
                      </Button>
                    )}
                    {canDelete && (
                      <Button
                        variant="danger"
                        size="sm"
                        disabled={deleteM.isPending}
                        onClick={async () => {
                          const ok = await confirm({
                            title: "Excluir veículo",
                            message: `Excluir o veículo de placa "${v.placa}"? Esta ação não pode ser desfeita.`,
                            confirmLabel: "Excluir",
                            intent: "danger",
                          });
                          if (ok) deleteM.mutate(v.id);
                        }}
                      >
                        Excluir
                      </Button>
                    )}
                  </div>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? `Editar — ${editing.placa}` : "Novo veículo regulado"}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={salvar} disabled={saveM.isPending}>
              {saveM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </>
        }
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="perm">Permissionário (vínculo)</Label>
            <Select
              id="perm"
              value={form.id_permissionario}
              onChange={(e) => set("id_permissionario", e.target.value)}
            >
              <option value="">— Nenhum —</option>
              {permsQ.data?.items.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.nome} ({p.cpf})
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="emp">Empresa (vínculo)</Label>
            <Select id="emp" value={form.id_empresa} onChange={(e) => set("id_empresa", e.target.value)}>
              <option value="">— Nenhuma —</option>
              {empresasQ.data?.items.map((e) => (
                <option key={e.id} value={String(e.id)}>
                  {e.razao_social}
                </option>
              ))}
            </Select>
          </div>
          <div className="sm:col-span-2 text-xs text-muted-foreground -mt-2">
            Informe ao menos um vínculo (permissionário ou empresa).
          </div>
          <div>
            <Label htmlFor="placa" required>
              Placa
            </Label>
            <Input id="placa" value={form.placa} onChange={(e) => set("placa", e.target.value)} placeholder="ABC1D23" />
          </div>
          <div>
            <Label htmlFor="renavam">RENAVAM</Label>
            <Input id="renavam" value={form.renavam} onChange={(e) => set("renavam", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="chassi">Chassi</Label>
            <Input id="chassi" value={form.chassi} onChange={(e) => set("chassi", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="marca" required>
              Marca
            </Label>
            <Input id="marca" value={form.marca} onChange={(e) => set("marca", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="modelo" required>
              Modelo
            </Label>
            <Input id="modelo" value={form.modelo} onChange={(e) => set("modelo", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="anofab">Ano de fabricação</Label>
            <Input id="anofab" type="number" value={form.ano_fabricacao} onChange={(e) => set("ano_fabricacao", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="anomod">Ano do modelo</Label>
            <Input id="anomod" type="number" value={form.ano_modelo} onChange={(e) => set("ano_modelo", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="cor">Cor</Label>
            <Input id="cor" value={form.cor} onChange={(e) => set("cor", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="cat">Categoria</Label>
            <Select id="cat" value={form.categoria} onChange={(e) => set("categoria", e.target.value)}>
              <option value="">—</option>
              {CATEGORIAS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="tipo" required>
              Tipo de serviço
            </Label>
            <Select id="tipo" value={form.tipo_servico} onChange={(e) => set("tipo_servico", e.target.value as TipoServico)}>
              {TIPOS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="comb">Combustível</Label>
            <Select id="comb" value={form.tipo_combustivel} onChange={(e) => set("tipo_combustivel", e.target.value)}>
              <option value="">—</option>
              {COMBUSTIVEIS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="cap">Capacidade (passageiros)</Label>
            <Input id="cap" type="number" min={1} value={form.capacidade_passageiros} onChange={(e) => set("capacidade_passageiros", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="sit">Situação</Label>
            <Select id="sit" value={form.situacao} onChange={(e) => set("situacao", e.target.value as VeiculoReguladoSituacao)}>
              {SITUACOES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex items-end gap-2">
            <input
              id="adaptado"
              type="checkbox"
              className="h-4 w-4"
              checked={form.adaptado}
              onChange={(e) => set("adaptado", e.target.checked)}
            />
            <Label htmlFor="adaptado">Adaptado (acessibilidade)</Label>
          </div>
          <div>
            <Label htmlFor="numaut">Número da autorização</Label>
            <Input id="numaut" value={form.numero_autorizacao} onChange={(e) => set("numero_autorizacao", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="ini">Início da autorização</Label>
            <Input id="ini" type="date" value={form.data_inicio_autorizacao} onChange={(e) => set("data_inicio_autorizacao", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="val">Validade da autorização</Label>
            <Input id="val" type="date" value={form.data_validade_autorizacao} onChange={(e) => set("data_validade_autorizacao", e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="obs">Observações</Label>
            <Textarea id="obs" rows={2} value={form.observacoes} onChange={(e) => set("observacoes", e.target.value)} />
          </div>
          {err && (
            <div role="alert" className="sm:col-span-2 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
              {err}
            </div>
          )}
        </div>
      </Dialog>
    </div>
  );
}
