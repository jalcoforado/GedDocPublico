"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Car, FileText, Inbox, Plus, Settings2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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

const SITUACOES: { value: VeiculoSituacao; label: string }[] = [
  { value: "disponivel", label: "Disponível" },
  { value: "em_uso", label: "Em uso" },
  { value: "manutencao", label: "Manutenção" },
  { value: "inativo", label: "Inativo" },
  { value: "baixado", label: "Baixado" },
];
const FORMA_POSSE: { value: VeiculoFormaPosse; label: string }[] = [
  { value: "proprio", label: "Próprio" },
  { value: "locado", label: "Locado" },
  { value: "cedido", label: "Cedido" },
  { value: "convenio", label: "Convênio" },
];
const COMBUSTIVEIS = ["gasolina", "etanol", "flex", "diesel", "gnv", "eletrico", "hibrido"];

const SITUACAO_LABEL: Record<string, string> = Object.fromEntries(
  SITUACOES.map((s) => [s.value, s.label]),
);

interface VeiculoForm {
  placa: string;
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

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Veiculo | null>(null);
  const [form, setForm] = useState<VeiculoForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);
  const [docsVeiculo, setDocsVeiculo] = useState<Veiculo | null>(null);

  const veiculosQ = useQuery({ queryKey: ["frota-veiculos"], queryFn: () => api.frota.listAll() });
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });
  const unidades = unidadesQ.data?.items ?? [];
  const unidadeNome = (id: number | null) =>
    unidades.find((u) => u.id === id)?.unidade_trabalho ?? "—";

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
    setDialogOpen(true);
  }

  function openEdit(v: Veiculo) {
    setEditing(v);
    setForm({
      placa: v.placa,
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
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }

  function salvar() {
    setErr(null);
    const payload = {
      placa: form.placa.trim(),
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
        breadcrumbs={[{ label: "Frota Pública", href: "/frotas" }, { label: "Veículos" }]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Novo veículo
            </Button>
          ) : undefined
        }
      />

      {!veiculosQ.isLoading && (veiculosQ.data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhum veículo cadastrado"
          description="Cadastre o primeiro veículo da frota."
          action={
            canCreate ? (
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
              <TH>Situação</TH>
              <TH>Unidade</TH>
              <TH className="text-right">Km</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {veiculosQ.isLoading && (
              <TR>
                <TD colSpan={6} className="text-center text-muted-foreground">
                  Carregando veículos...
                </TD>
              </TR>
            )}
            {veiculosQ.data?.map((v) => (
              <TR key={v.id}>
                <TD className="font-mono">{v.placa}</TD>
                <TD>{[v.marca, v.modelo].filter(Boolean).join(" ") || "—"}</TD>
                <TD>
                  <Badge intent={v.situacao === "disponivel" ? "success" : "neutral"}>
                    {SITUACAO_LABEL[v.situacao] ?? v.situacao}
                  </Badge>
                </TD>
                <TD className="text-muted-foreground">{unidadeNome(v.id_unidade_responsavel)}</TD>
                <TD className="text-right tabular-nums">
                  {v.quilometragem_atual.toLocaleString("pt-BR")}
                </TD>
                <TD className="text-right">
                  <div className="inline-flex gap-2">
                    <Button variant="secondary" size="sm" onClick={() => setDocsVeiculo(v)}>
                      <FileText className="mr-1 h-4 w-4" />
                      Documentos
                    </Button>
                    {canEdit && (
                      <Button variant="secondary" size="sm" onClick={() => openEdit(v)}>
                        Editar
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
        title={editing ? `Editar — ${editing.placa}` : "Novo veículo"}
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
        <div className="space-y-4">
          <SectionCard
            icon={FileText}
            title="Identificação"
            description="Dados do veículo e documentação."
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="placa" required>
                  Placa
                </Label>
                <Input
                  id="placa"
                  value={form.placa}
                  onChange={(e) => set("placa", e.target.value)}
                  className="font-mono uppercase"
                  placeholder="ABC1D23"
                />
              </div>
              <div>
                <Label htmlFor="renavam">RENAVAM</Label>
                <Input id="renavam" value={form.renavam} onChange={(e) => set("renavam", e.target.value)} />
              </div>
              <div>
                <Label htmlFor="marca">Marca</Label>
                <Input id="marca" value={form.marca} onChange={(e) => set("marca", e.target.value)} />
              </div>
              <div>
                <Label htmlFor="modelo">Modelo</Label>
                <Input id="modelo" value={form.modelo} onChange={(e) => set("modelo", e.target.value)} />
              </div>
              <div>
                <Label htmlFor="ano_fab">Ano fabricação</Label>
                <Input
                  id="ano_fab"
                  type="number"
                  value={form.ano_fabricacao ?? ""}
                  onChange={(e) => set("ano_fabricacao", e.target.value ? Number(e.target.value) : null)}
                />
              </div>
              <div>
                <Label htmlFor="ano_mod">Ano modelo</Label>
                <Input
                  id="ano_mod"
                  type="number"
                  value={form.ano_modelo ?? ""}
                  onChange={(e) => set("ano_modelo", e.target.value ? Number(e.target.value) : null)}
                />
              </div>
              <div>
                <Label htmlFor="cor">Cor</Label>
                <Input id="cor" value={form.cor} onChange={(e) => set("cor", e.target.value)} />
              </div>
              <div>
                <Label htmlFor="chassi">Chassi</Label>
                <Input id="chassi" value={form.chassi} onChange={(e) => set("chassi", e.target.value)} />
              </div>
              <div>
                <Label htmlFor="tipo_veiculo">Tipo de veículo</Label>
                <Input
                  id="tipo_veiculo"
                  value={form.tipo_veiculo}
                  onChange={(e) => set("tipo_veiculo", e.target.value)}
                  placeholder="ex.: automóvel, caminhonete, ônibus"
                />
              </div>
              <div>
                <Label htmlFor="combustivel">Combustível</Label>
                <Select
                  id="combustivel"
                  value={form.tipo_combustivel}
                  onChange={(e) => set("tipo_combustivel", e.target.value)}
                >
                  <option value="">—</option>
                  {COMBUSTIVEIS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            icon={Settings2}
            title="Situação e posse"
            description="Estado operacional, forma de posse, unidade responsável e quilometragem."
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="situacao">Situação</Label>
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
              </div>
              <div>
                <Label htmlFor="forma_posse">Forma de posse</Label>
                <Select
                  id="forma_posse"
                  value={form.forma_posse}
                  onChange={(e) => set("forma_posse", e.target.value as VeiculoFormaPosse)}
                >
                  {FORMA_POSSE.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="unidade">Unidade responsável</Label>
                <Select
                  id="unidade"
                  value={form.id_unidade_responsavel ?? ""}
                  onChange={(e) =>
                    set("id_unidade_responsavel", e.target.value ? Number(e.target.value) : null)
                  }
                >
                  <option value="">—</option>
                  {unidades.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.unidade_trabalho}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="km">Quilometragem atual</Label>
                <Input
                  id="km"
                  type="number"
                  min={0}
                  value={form.quilometragem_atual}
                  onChange={(e) => set("quilometragem_atual", e.target.value ? Number(e.target.value) : 0)}
                />
              </div>
              <div>
                <Label htmlFor="data_aquisicao">Data de aquisição</Label>
                <Input
                  id="data_aquisicao"
                  type="date"
                  value={form.data_aquisicao}
                  onChange={(e) => set("data_aquisicao", e.target.value)}
                />
              </div>
              <div className="sm:col-span-2">
                <Label htmlFor="obs">Observações</Label>
                <Textarea
                  id="obs"
                  rows={3}
                  value={form.observacoes}
                  onChange={(e) => set("observacoes", e.target.value)}
                />
              </div>
            </div>
          </SectionCard>

          {err && (
            <div role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
              {err}
            </div>
          )}
        </div>
      </Dialog>

      <DocumentosDialog
        veiculo={docsVeiculo}
        open={docsVeiculo != null}
        onClose={() => setDocsVeiculo(null)}
      />
    </div>
  );
}
