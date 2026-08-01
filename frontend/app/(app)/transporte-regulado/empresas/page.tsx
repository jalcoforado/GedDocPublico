"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Inbox, Plus } from "lucide-react";
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
  type Empresa,
  type EmpresaSituacao,
  type TipoServico,
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
const SITUACOES: { value: EmpresaSituacao; label: string }[] = [
  { value: "pendente", label: "Pendente" },
  { value: "ativa", label: "Ativa" },
  { value: "suspensa", label: "Suspensa" },
  { value: "cassada", label: "Cassada" },
  { value: "inativa", label: "Inativa" },
];
const TIPO_LABEL: Record<string, string> = Object.fromEntries(TIPOS.map((t) => [t.value, t.label]));
const SIT_LABEL: Record<string, string> = Object.fromEntries(SITUACOES.map((s) => [s.value, s.label]));
const SIT_INTENT: Record<string, "success" | "warning" | "info" | "danger" | "neutral"> = {
  ativa: "success",
  pendente: "warning",
  suspensa: "info",
  cassada: "danger",
  inativa: "neutral",
};

interface EmpresaForm {
  razao_social: string;
  nome_fantasia: string;
  cnpj: string;
  inscricao_municipal: string;
  inscricao_estadual: string;
  telefone: string;
  email: string;
  cep: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  municipio: string;
  uf: string;
  tipo_servico: TipoServico;
  numero_autorizacao: string;
  data_inicio_autorizacao: string;
  data_validade_autorizacao: string;
  id_representante_permissionario: string;
  situacao: EmpresaSituacao;
  observacoes: string;
}

const EMPTY: EmpresaForm = {
  razao_social: "",
  nome_fantasia: "",
  cnpj: "",
  inscricao_municipal: "",
  inscricao_estadual: "",
  telefone: "",
  email: "",
  cep: "",
  logradouro: "",
  numero: "",
  complemento: "",
  bairro: "",
  municipio: "",
  uf: "",
  tipo_servico: "taxi",
  numero_autorizacao: "",
  data_inicio_autorizacao: "",
  data_validade_autorizacao: "",
  id_representante_permissionario: "",
  situacao: "pendente",
  observacoes: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

export default function EmpresasPage() {
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
  const [editing, setEditing] = useState<Empresa | null>(null);
  const [form, setForm] = useState<EmpresaForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const listaQ = useQuery({
    queryKey: ["tr-empresas", situacaoFiltro, tipoFiltro, busca],
    queryFn: () =>
      api.empresas.list({
        situacao: situacaoFiltro || undefined,
        tipo_servico: tipoFiltro || undefined,
        q: busca.trim() || undefined,
      }),
  });

  // Permissionários para o select de representante (opcional).
  const permsQ = useQuery({
    queryKey: ["tr-permissionarios-rep"],
    queryFn: () => api.permissionarios.list(),
    enabled: dialogOpen,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["tr-empresas"] });

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing ? api.empresas.update(editing.id, data) : api.empresas.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Empresa atualizada." : "Empresa cadastrada.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const actionM = useMutation({
    mutationFn: ({ id, acao }: { id: number; acao: "inativar" | "reativar" | "suspender" }) =>
      acao === "inativar"
        ? api.empresas.inativar(id)
        : acao === "reativar"
          ? api.empresas.reativar(id)
          : api.empresas.suspender(id),
    onSuccess: () => {
      invalidate();
      toast.success("Situação atualizada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.empresas.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Empresa excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof EmpresaForm>(key: K, value: EmpresaForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }
  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setDialogOpen(true);
  }
  function openEdit(e: Empresa) {
    setEditing(e);
    setForm({
      razao_social: e.razao_social,
      nome_fantasia: e.nome_fantasia ?? "",
      cnpj: e.cnpj,
      inscricao_municipal: e.inscricao_municipal ?? "",
      inscricao_estadual: e.inscricao_estadual ?? "",
      telefone: e.telefone ?? "",
      email: e.email ?? "",
      cep: e.cep ?? "",
      logradouro: e.logradouro ?? "",
      numero: e.numero ?? "",
      complemento: e.complemento ?? "",
      bairro: e.bairro ?? "",
      municipio: e.municipio ?? "",
      uf: e.uf ?? "",
      tipo_servico: e.tipo_servico,
      numero_autorizacao: e.numero_autorizacao ?? "",
      data_inicio_autorizacao: e.data_inicio_autorizacao ?? "",
      data_validade_autorizacao: e.data_validade_autorizacao ?? "",
      id_representante_permissionario:
        e.id_representante_permissionario != null
          ? String(e.id_representante_permissionario)
          : "",
      situacao: e.situacao,
      observacoes: e.observacoes ?? "",
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
    if (form.razao_social.trim() === "") {
      setErr("Razão social é obrigatória.");
      return;
    }
    if (form.cnpj.trim() === "") {
      setErr("CNPJ é obrigatório.");
      return;
    }
    const payload = {
      razao_social: form.razao_social.trim(),
      nome_fantasia: nullify(form.nome_fantasia),
      cnpj: form.cnpj.trim(),
      inscricao_municipal: nullify(form.inscricao_municipal),
      inscricao_estadual: nullify(form.inscricao_estadual),
      telefone: nullify(form.telefone),
      email: nullify(form.email),
      cep: nullify(form.cep),
      logradouro: nullify(form.logradouro),
      numero: nullify(form.numero),
      complemento: nullify(form.complemento),
      bairro: nullify(form.bairro),
      municipio: nullify(form.municipio),
      uf: nullify(form.uf),
      tipo_servico: form.tipo_servico,
      numero_autorizacao: nullify(form.numero_autorizacao),
      data_inicio_autorizacao: nullify(form.data_inicio_autorizacao),
      data_validade_autorizacao: nullify(form.data_validade_autorizacao),
      id_representante_permissionario:
        form.id_representante_permissionario === ""
          ? null
          : Number(form.id_representante_permissionario),
      situacao: form.situacao,
      observacoes: nullify(form.observacoes),
    };
    saveM.mutate(payload);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Building2}
        title="Empresas"
        description="Cadastro de empresas e operadoras do transporte regulado."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/transporte-regulado" },
          { label: "Empresas" },
        ]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Nova empresa
            </Button>
          ) : undefined
        }
      />

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
            placeholder="Razão social, nome fantasia ou CNPJ"
          />
        </div>
      </div>

      {!listaQ.isLoading && (listaQ.data?.items.length ?? 0) === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhuma empresa"
          description="Cadastre a primeira empresa do transporte regulado."
          action={
            canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Cadastrar empresa
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Razão social</TH>
              <TH>CNPJ</TH>
              <TH>Tipo de serviço</TH>
              <TH>Autorização</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {listaQ.isLoading && (
              <TR>
                <TD colSpan={6} className="text-center text-muted-foreground">
                  Carregando...
                </TD>
              </TR>
            )}
            {listaQ.data?.items.map((e) => (
              <TR key={e.id}>
                <TD>
                  <div className="font-medium">{e.razao_social}</div>
                  {e.nome_fantasia && (
                    <div className="text-xs text-muted-foreground">{e.nome_fantasia}</div>
                  )}
                </TD>
                <TD className="font-mono">{e.cnpj}</TD>
                <TD>{TIPO_LABEL[e.tipo_servico] ?? e.tipo_servico}</TD>
                <TD className="text-muted-foreground">{e.numero_autorizacao ?? "—"}</TD>
                <TD>
                  <Badge intent={SIT_INTENT[e.situacao] ?? "neutral"}>
                    {SIT_LABEL[e.situacao] ?? e.situacao}
                  </Badge>
                </TD>
                <TD className="text-right">
                  <div className="inline-flex flex-wrap justify-end gap-2">
                    {canEdit && (
                      <Button variant="secondary" size="sm" onClick={() => openEdit(e)}>
                        Editar
                      </Button>
                    )}
                    {canEdit && e.situacao !== "ativa" && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => actionM.mutate({ id: e.id, acao: "reativar" })}
                      >
                        Reativar
                      </Button>
                    )}
                    {canEdit && e.situacao !== "suspensa" && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => actionM.mutate({ id: e.id, acao: "suspender" })}
                      >
                        Suspender
                      </Button>
                    )}
                    {canEdit && e.situacao !== "inativa" && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => actionM.mutate({ id: e.id, acao: "inativar" })}
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
                            title: "Excluir empresa",
                            message: `Excluir a empresa "${e.razao_social}"? Esta ação não pode ser desfeita.`,
                            confirmLabel: "Excluir",
                            intent: "danger",
                          });
                          if (ok) deleteM.mutate(e.id);
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
        title={editing ? `Editar — ${editing.razao_social}` : "Nova empresa"}
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
          <div className="sm:col-span-2">
            <Label htmlFor="razao" required>
              Razão social
            </Label>
            <Input id="razao" value={form.razao_social} onChange={(e) => set("razao_social", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="fantasia">Nome fantasia</Label>
            <Input id="fantasia" value={form.nome_fantasia} onChange={(e) => set("nome_fantasia", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="cnpj" required>
              CNPJ
            </Label>
            <Input id="cnpj" value={form.cnpj} onChange={(e) => set("cnpj", e.target.value)} placeholder="00.000.000/0000-00" />
          </div>
          <div>
            <Label htmlFor="im">Inscrição municipal</Label>
            <Input id="im" value={form.inscricao_municipal} onChange={(e) => set("inscricao_municipal", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="ie">Inscrição estadual</Label>
            <Input id="ie" value={form.inscricao_estadual} onChange={(e) => set("inscricao_estadual", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="tel">Telefone</Label>
            <Input id="tel" value={form.telefone} onChange={(e) => set("telefone", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="email">E-mail</Label>
            <Input id="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
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
            <Label htmlFor="sit">Situação</Label>
            <Select id="sit" value={form.situacao} onChange={(e) => set("situacao", e.target.value as EmpresaSituacao)}>
              {SITUACOES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="cep">CEP</Label>
            <Input id="cep" value={form.cep} onChange={(e) => set("cep", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="logr">Logradouro</Label>
            <Input id="logr" value={form.logradouro} onChange={(e) => set("logradouro", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="num">Número</Label>
            <Input id="num" value={form.numero} onChange={(e) => set("numero", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="compl">Complemento</Label>
            <Input id="compl" value={form.complemento} onChange={(e) => set("complemento", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="bairro">Bairro</Label>
            <Input id="bairro" value={form.bairro} onChange={(e) => set("bairro", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="mun">Município</Label>
            <Input id="mun" value={form.municipio} onChange={(e) => set("municipio", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="uf">UF</Label>
            <Input id="uf" value={form.uf} maxLength={2} onChange={(e) => set("uf", e.target.value)} />
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
            <Label htmlFor="rep">Representante (permissionário)</Label>
            <Select
              id="rep"
              value={form.id_representante_permissionario}
              onChange={(e) => set("id_representante_permissionario", e.target.value)}
            >
              <option value="">— Nenhum —</option>
              {permsQ.data?.items.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.nome} ({p.cpf})
                </option>
              ))}
            </Select>
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
