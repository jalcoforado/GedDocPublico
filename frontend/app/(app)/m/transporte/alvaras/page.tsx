"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, Plus, ScrollText } from "lucide-react";
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
  type Alvara,
  type AlvaraDocumento,
  type AlvaraDocumentoInput,
  type AlvaraInput,
  type AlvaraRenovarInput,
  type AlvaraResponsavel,
  type AlvaraResponsavelInput,
  type Empresa,
  type Permissionario,
  type TipoServico,
  type Usuario,
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
const TIPO_LABEL: Record<string, string> = Object.fromEntries(TIPOS.map((t) => [t.value, t.label]));

interface AlvaraForm {
  numero_alvara: string;
  data_inicio: string;
  data_validade: string;
  tipo_servico: TipoServico;
  observacoes: string;
  id_empresa: string;
  id_permissionario: string;
}

const EMPTY: AlvaraForm = {
  numero_alvara: "",
  data_inicio: "",
  data_validade: "",
  tipo_servico: "taxi",
  observacoes: "",
  id_empresa: "",
  id_permissionario: "",
};

interface RenovarForm {
  data_inicio: string;
  data_validade: string;
  observacoes: string;
}

const EMPTY_RENOV: RenovarForm = {
  data_inicio: "",
  data_validade: "",
  observacoes: "",
};

interface DocumentoForm {
  tipo_documento: string;
  arquivo: string;
  observacoes: string;
}

const EMPTY_DOC: DocumentoForm = {
  tipo_documento: "",
  arquivo: "",
  observacoes: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

// Formata data ISO (YYYY-MM-DD) para exibição pt-BR sem passar por `new Date`:
// o parse de data-sem-hora é UTC, e em UTC-3 a tela mostraria o dia anterior.
function formatarData(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return y && m && d ? `${d}/${m}/${y}` : iso;
}

function isExpired(dataValidade: string | null | undefined): boolean {
  if (!dataValidade) return false;
  const today = new Date().toISOString().split("T")[0];
  return dataValidade <= today;
}

export default function AlvarasPage() {
  const { can } = useAuth();
  const canCreate = can("transporte_regulado", "inserir");
  const canEdit = can("transporte_regulado", "atualizar");
  const canDelete = can("transporte_regulado", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [empresaFiltro, setEmpresaFiltro] = useState("");
  const [permFiltro, setPermFiltro] = useState("");
  const [busca, setBusca] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Alvara | null>(null);
  const [form, setForm] = useState<AlvaraForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);
  const [renovarDialogOpen, setRenovarDialogOpen] = useState(false);
  const [renovarForm, setRenovarForm] = useState<RenovarForm>(EMPTY_RENOV);
  const [selectedAlvaraToRenew, setSelectedAlvaraToRenew] = useState<Alvara | null>(null);
  const [renovarErr, setRenovarErr] = useState<string | null>(null);

  const [docsDialogOpen, setDocsDialogOpen] = useState(false);
  const [selectedAlvaraForDocs, setSelectedAlvaraForDocs] = useState<Alvara | null>(null);
  const [docForm, setDocForm] = useState<DocumentoForm>(EMPTY_DOC);
  const [editingDoc, setEditingDoc] = useState<AlvaraDocumento | null>(null);
  const [docErr, setDocErr] = useState<string | null>(null);

  const [respDialogOpen, setRespDialogOpen] = useState(false);
  const [selectedAlvaraForResp, setSelectedAlvaraForResp] = useState<Alvara | null>(null);
  const [respForm, setRespForm] = useState({ id_usuario: "", cargo_funcao: "" });
  const [respErr, setRespErr] = useState<string | null>(null);

  // Debounce da busca. Antes `busca` já entrava na `queryKey` sem ir para a
  // API: cada tecla invalidava o cache e refazia a MESMA requisição. Agora o
  // termo vai para o servidor, então sem debounce seria uma consulta por tecla.
  const [buscaAplicada, setBuscaAplicada] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca.trim()), 300);
    return () => clearTimeout(t);
  }, [busca]);

  const listaQ = useQuery({
    queryKey: ["tr-alvaras", empresaFiltro, permFiltro, buscaAplicada],
    queryFn: () =>
      api.alvaras.list({
        empresa_id: empresaFiltro ? Number(empresaFiltro) : undefined,
        permissionario_id: permFiltro ? Number(permFiltro) : undefined,
        // Busca NO SERVIDOR. Filtrar `items` aqui era o defeito: a lista chega
        // truncada em `page_size`, então número fora da primeira página
        // desaparecia e a tela afirmava que o alvará não existe.
        q: buscaAplicada || undefined,
      }),
  });

  const empresasQ = useQuery({
    queryKey: ["tr-empresas-list"],
    queryFn: () => api.empresas.list(),
    enabled: dialogOpen,
  });

  const permsQ = useQuery({
    queryKey: ["tr-permissionarios-list"],
    queryFn: () => api.permissionarios.list(),
    enabled: dialogOpen,
  });

  const vencidosQ = useQuery({
    queryKey: ["tr-alvaras-vencidos"],
    queryFn: () => api.alvaras.listarVencidos(),
    enabled: renovarDialogOpen,
  });

  const docsQ = useQuery({
    queryKey: ["tr-alvara-documentos", selectedAlvaraForDocs?.id],
    queryFn: () =>
      selectedAlvaraForDocs
        ? api.alvaras.documentos.list(selectedAlvaraForDocs.id)
        : Promise.resolve({ items: [], total: 0, page: 1, page_size: 50 }),
    enabled: docsDialogOpen && selectedAlvaraForDocs !== null,
  });

  const respQ = useQuery({
    queryKey: ["tr-alvara-responsaveis", selectedAlvaraForResp?.id],
    queryFn: () =>
      selectedAlvaraForResp
        ? api.alvaras.responsaveis.list(selectedAlvaraForResp.id)
        : Promise.resolve({ items: [], total: 0, page: 1, page_size: 50 }),
    enabled: respDialogOpen && selectedAlvaraForResp !== null,
  });

  const usuariosQ = useQuery({
    queryKey: ["usuarios-list"],
    queryFn: () => api.usuarios.list(),
    enabled: respDialogOpen,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["tr-alvaras"] });
    qc.invalidateQueries({ queryKey: ["tr-alvaras-vencidos"] });
  };

  const saveM = useMutation({
    mutationFn: (data: AlvaraInput) =>
      editing ? api.alvaras.update(editing.id, data) : api.alvaras.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Alvará atualizado." : "Alvará cadastrado.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });

  const deleteM = useMutation({
    mutationFn: (id: number) => api.alvaras.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Alvará excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const renovarM = useMutation({
    mutationFn: (data: AlvaraRenovarInput) =>
      selectedAlvaraToRenew ? api.alvaras.renovar(selectedAlvaraToRenew.id, data) : Promise.reject(),
    onSuccess: () => {
      invalidate();
      toast.success("Alvará renovado.");
      closeRenovarDialog();
    },
    onError: (e: Error) => setRenovarErr(e.message),
  });

  const saveDocM = useMutation({
    mutationFn: (data: AlvaraDocumentoInput) =>
      selectedAlvaraForDocs
        ? editingDoc
          ? api.alvaras.documentos.update(selectedAlvaraForDocs.id, editingDoc.id, data)
          : api.alvaras.documentos.create(selectedAlvaraForDocs.id, data)
        : Promise.reject(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-alvara-documentos"] });
      toast.success(editingDoc ? "Documento atualizado." : "Documento adicionado.");
      resetDocForm();
    },
    onError: (e: Error) => setDocErr(e.message),
  });

  const deleteDocM = useMutation({
    mutationFn: (docId: number) =>
      selectedAlvaraForDocs ? api.alvaras.documentos.remove(selectedAlvaraForDocs.id, docId) : Promise.reject(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-alvara-documentos"] });
      toast.success("Documento removido.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const addRespM = useMutation({
    mutationFn: (data: AlvaraResponsavelInput) =>
      selectedAlvaraForResp ? api.alvaras.responsaveis.add(selectedAlvaraForResp.id, data) : Promise.reject(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-alvara-responsaveis"] });
      toast.success("Responsável adicionado.");
      resetRespForm();
    },
    onError: (e: Error) => setRespErr(e.message),
  });

  const deleteRespM = useMutation({
    mutationFn: (respId: number) =>
      selectedAlvaraForResp ? api.alvaras.responsaveis.remove(selectedAlvaraForResp.id, respId) : Promise.reject(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-alvara-responsaveis"] });
      toast.success("Responsável removido.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof AlvaraForm>(key: K, value: AlvaraForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setDialogOpen(true);
  }

  function openEdit(a: Alvara) {
    setEditing(a);
    setForm({
      numero_alvara: a.numero_alvara,
      data_inicio: a.data_inicio ?? "",
      data_validade: a.data_validade ?? "",
      tipo_servico: a.tipo_servico as TipoServico,
      observacoes: a.observacoes ?? "",
      id_empresa: a.id_empresa != null ? String(a.id_empresa) : "",
      id_permissionario: a.id_permissionario != null ? String(a.id_permissionario) : "",
    });
    setErr(null);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
  }

  function openRenovar(a: Alvara) {
    setSelectedAlvaraToRenew(a);
    setRenovarForm(EMPTY_RENOV);
    setRenovarErr(null);
    setRenovarDialogOpen(true);
  }

  function closeRenovarDialog() {
    setRenovarDialogOpen(false);
    setSelectedAlvaraToRenew(null);
    setRenovarForm(EMPTY_RENOV);
    setRenovarErr(null);
  }

  function setRenov<K extends keyof RenovarForm>(key: K, value: RenovarForm[K]) {
    setRenovarForm((f) => ({ ...f, [key]: value }));
  }

  function setDoc<K extends keyof DocumentoForm>(key: K, value: DocumentoForm[K]) {
    setDocForm((f) => ({ ...f, [key]: value }));
  }

  function openDocs(a: Alvara) {
    setSelectedAlvaraForDocs(a);
    resetDocForm();
    setDocsDialogOpen(true);
  }

  function closeDocs() {
    setDocsDialogOpen(false);
    setSelectedAlvaraForDocs(null);
    resetDocForm();
  }

  function resetDocForm() {
    setDocForm(EMPTY_DOC);
    setEditingDoc(null);
    setDocErr(null);
  }

  function openEditDoc(doc: AlvaraDocumento) {
    setEditingDoc(doc);
    setDocForm({
      tipo_documento: doc.tipo_documento,
      arquivo: doc.arquivo,
      observacoes: doc.observacoes ?? "",
    });
  }

  function salvarDoc() {
    setDocErr(null);
    if (docForm.tipo_documento.trim() === "") {
      setDocErr("Tipo de documento é obrigatório.");
      return;
    }
    if (docForm.arquivo.trim() === "") {
      setDocErr("Arquivo é obrigatório.");
      return;
    }
    const payload: AlvaraDocumentoInput = {
      tipo_documento: docForm.tipo_documento.trim(),
      arquivo: docForm.arquivo.trim(),
      observacoes: nullify(docForm.observacoes),
    };
    saveDocM.mutate(payload);
  }

  function openResp(a: Alvara) {
    setSelectedAlvaraForResp(a);
    resetRespForm();
    setRespDialogOpen(true);
  }

  function closeResp() {
    setRespDialogOpen(false);
    setSelectedAlvaraForResp(null);
    resetRespForm();
  }

  function resetRespForm() {
    setRespForm({ id_usuario: "", cargo_funcao: "" });
    setRespErr(null);
  }

  function salvarResp() {
    setRespErr(null);
    if (respForm.id_usuario === "") {
      setRespErr("Selecione um usuário.");
      return;
    }
    const payload: AlvaraResponsavelInput = {
      id_usuario: Number(respForm.id_usuario),
      cargo_funcao: nullify(respForm.cargo_funcao),
    };
    addRespM.mutate(payload);
  }

  function salvarRenov() {
    setRenovarErr(null);
    if (renovarForm.data_inicio && renovarForm.data_validade && renovarForm.data_inicio > renovarForm.data_validade) {
      setRenovarErr("Data de início não pode ser posterior à data de validade.");
      return;
    }
    const payload: AlvaraRenovarInput = {
      data_inicio: nullify(renovarForm.data_inicio),
      data_validade: nullify(renovarForm.data_validade),
      observacoes: nullify(renovarForm.observacoes),
    };
    renovarM.mutate(payload);
  }

  function salvar() {
    setErr(null);
    if (form.numero_alvara.trim() === "") {
      setErr("Número do alvará é obrigatório.");
      return;
    }
    if (form.tipo_servico.trim() === "") {
      setErr("Tipo de serviço é obrigatório.");
      return;
    }
    if (form.id_empresa === "" && form.id_permissionario === "") {
      setErr("Informe ao menos uma empresa ou permissionário.");
      return;
    }
    if (form.data_inicio && form.data_validade && form.data_inicio > form.data_validade) {
      setErr("Data de início não pode ser posterior à data de validade.");
      return;
    }
    const payload: AlvaraInput = {
      numero_alvara: form.numero_alvara.trim(),
      data_inicio: nullify(form.data_inicio),
      data_validade: nullify(form.data_validade),
      tipo_servico: form.tipo_servico,
      observacoes: nullify(form.observacoes),
      id_empresa: form.id_empresa === "" ? null : Number(form.id_empresa),
      id_permissionario: form.id_permissionario === "" ? null : Number(form.id_permissionario),
    };
    saveM.mutate(payload);
  }

  // Sem filtro no cliente: o que chega já veio filtrado pelo servidor.
  const filteredData = listaQ.data?.items ?? [];
  const buscando = buscaAplicada.length > 0;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={ScrollText}
        title="Alvarás"
        description="Autorizações e permissões de operação para permissionários e empresas."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Alvarás" },
        ]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Novo alvará
            </Button>
          ) : undefined
        }
      />

      <div className="flex flex-wrap gap-3">
        <div>
          <Label htmlFor="f_emp">Empresa</Label>
          <Select id="f_emp" value={empresaFiltro} onChange={(e) => setEmpresaFiltro(e.target.value)}>
            <option value="">Todas</option>
            {empresasQ.data?.items.map((e: Empresa) => (
              <option key={e.id} value={String(e.id)}>
                {e.razao_social}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="f_perm">Permissionário</Label>
          <Select id="f_perm" value={permFiltro} onChange={(e) => setPermFiltro(e.target.value)}>
            <option value="">Todos</option>
            {permsQ.data?.items.map((p: Permissionario) => (
              <option key={p.id} value={String(p.id)}>
                {p.nome}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex-1 min-w-[200px]">
          <Label htmlFor="f_q">Busca por número</Label>
          <Input
            id="f_q"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="ALV-001, ALV-002..."
          />
        </div>
      </div>

      {listaQ.isLoading ? (
        <div className="text-center text-muted-foreground py-8">Carregando...</div>
      ) : filteredData.length === 0 ? (
        // Dois estados distintos, mensagem distinta. "Cadastre o primeiro
        // alvará" numa busca sem resultado é informação errada — o tenant pode
        // ter centenas, e o botão convidaria a duplicar um que já existe.
        <EmptyState
          icon={Inbox}
          title={buscando ? "Nenhum alvará encontrado" : "Nenhum alvará"}
          description={
            buscando
              ? `Nada corresponde a "${buscaAplicada}". A busca cobre todos os alvarás do município, não só os desta página.`
              : "Cadastre o primeiro alvará do transporte regulado."
          }
          action={
            !buscando && canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Cadastrar alvará
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Número</TH>
              <TH>Tipo de serviço</TH>
              <TH>Vinculação</TH>
              <TH>Validade</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {filteredData.map((a) => (
              <TR key={a.id}>
                <TD className="font-mono font-medium">{a.numero_alvara}</TD>
                <TD>{TIPO_LABEL[a.tipo_servico] ?? a.tipo_servico}</TD>
                <TD className="text-sm text-muted-foreground">
                  {a.id_empresa && a.id_permissionario
                    ? "Empresa + Permissionário"
                    : a.id_empresa
                      ? "Empresa"
                      : "Permissionário"}
                </TD>
                <TD>
                  {a.data_validade ? (
                    <div className="flex items-center gap-2">
                      {isExpired(a.data_validade) && (
                        <Badge intent="danger">Expirado</Badge>
                      )}
                      <span className={isExpired(a.data_validade) ? "line-through text-muted-foreground" : ""}>
                        {formatarData(a.data_validade)}
                      </span>
                    </div>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TD>
                <TD className="text-right">
                  <div className="inline-flex flex-wrap justify-end gap-2">
                    {/* A tela de detalhe (auditoria + veículos) existia desde a
                        P3 e NÃO tinha link nenhum: só se chegava digitando a
                        URL. Achado em 2026-08-05, ao consertar a guarda de
                        página órfã, que até então truncava a rota no primeiro
                        segmento dinâmico e por isso nunca a examinou. */}
                    <Link href={`/m/transporte/alvaras/${a.id}`}>
                      <Button variant="secondary" size="sm">
                        Detalhes
                      </Button>
                    </Link>
                    {canCreate && (
                      <>
                        <Button variant="secondary" size="sm" onClick={() => openDocs(a)}>
                          Documentos
                        </Button>
                        <Button variant="secondary" size="sm" onClick={() => openResp(a)}>
                          Responsáveis
                        </Button>
                      </>
                    )}
                    {canEdit && (
                      <Button variant="secondary" size="sm" onClick={() => openEdit(a)}>
                        Editar
                      </Button>
                    )}
                    {canCreate && isExpired(a.data_validade) && (
                      <Button variant="secondary" size="sm" onClick={() => openRenovar(a)}>
                        Renovar
                      </Button>
                    )}
                    {canDelete && (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={async () => {
                          const ok = await confirm({
                            title: "Excluir alvará",
                            message: `Excluir o alvará "${a.numero_alvara}"? Esta ação não pode ser desfeita.`,
                          });
                          if (ok) deleteM.mutate(a.id);
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
        title={editing ? `Editar — ${editing.numero_alvara}` : "Novo alvará"}
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
          {err && (
            <div role="alert" className="rounded border border-danger/40 bg-danger-soft p-3 text-sm text-danger-soft-foreground">
              {err}
            </div>
          )}

          <div>
            <Label htmlFor="numero" required>
              Número do alvará
            </Label>
            <Input
              id="numero"
              value={form.numero_alvara}
              onChange={(e) => set("numero_alvara", e.target.value)}
              placeholder="ALV-001"
            />
          </div>

          <div>
            <Label htmlFor="tipo" required>
              Tipo de serviço
            </Label>
            <Select value={form.tipo_servico} onChange={(e) => set("tipo_servico", e.target.value as TipoServico)}>
              {TIPOS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="emp">Empresa</Label>
              <Select value={form.id_empresa} onChange={(e) => set("id_empresa", e.target.value)}>
                <option value="">Nenhuma</option>
                {empresasQ.data?.items.map((e: Empresa) => (
                  <option key={e.id} value={String(e.id)}>
                    {e.razao_social}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="perm">Permissionário</Label>
              <Select value={form.id_permissionario} onChange={(e) => set("id_permissionario", e.target.value)}>
                <option value="">Nenhum</option>
                {permsQ.data?.items.map((p: Permissionario) => (
                  <option key={p.id} value={String(p.id)}>
                    {p.nome}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="data_inicio">Data de início</Label>
              <Input
                id="data_inicio"
                type="date"
                value={form.data_inicio}
                onChange={(e) => set("data_inicio", e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="data_validade">Data de validade</Label>
              <Input
                id="data_validade"
                type="date"
                value={form.data_validade}
                onChange={(e) => set("data_validade", e.target.value)}
              />
            </div>
          </div>

          <div>
            <Label htmlFor="obs">Observações</Label>
            <Textarea
              id="obs"
              value={form.observacoes}
              onChange={(e) => set("observacoes", e.target.value)}
              placeholder="Notas adicionais sobre o alvará"
              rows={3}
            />
          </div>
        </div>
      </Dialog>

      <Dialog
        open={renovarDialogOpen}
        onClose={closeRenovarDialog}
        title={selectedAlvaraToRenew ? `Renovar — ${selectedAlvaraToRenew.numero_alvara}` : "Renovar alvará"}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={closeRenovarDialog}>
              Cancelar
            </Button>
            <Button onClick={salvarRenov} disabled={renovarM.isPending}>
              {renovarM.isPending ? "Renovando..." : "Renovar"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {renovarErr && (
            <div role="alert" className="rounded border border-danger/40 bg-danger-soft p-3 text-sm text-danger-soft-foreground">
              {renovarErr}
            </div>
          )}

          {selectedAlvaraToRenew && (
            <div className="rounded border border-warning/40 bg-warning-soft p-4">
              <div className="text-sm font-medium text-warning-soft-foreground mb-2">Alvará Original</div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Número:</span> {selectedAlvaraToRenew.numero_alvara}
                </div>
                <div>
                  <span className="text-muted-foreground">Tipo:</span> {TIPO_LABEL[selectedAlvaraToRenew.tipo_servico]}
                </div>
                <div>
                  <span className="text-muted-foreground">Válido até:</span>{" "}
                  <span className="line-through text-danger font-semibold">
                    {formatarData(selectedAlvaraToRenew.data_validade)}
                  </span>
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="renov_data_inicio">Data de início</Label>
              <Input
                id="renov_data_inicio"
                type="date"
                value={renovarForm.data_inicio}
                onChange={(e) => setRenov("data_inicio", e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="renov_data_validade">Data de validade</Label>
              <Input
                id="renov_data_validade"
                type="date"
                value={renovarForm.data_validade}
                onChange={(e) => setRenov("data_validade", e.target.value)}
              />
            </div>
          </div>

          <div>
            <Label htmlFor="renov_obs">Observações</Label>
            <Textarea
              id="renov_obs"
              value={renovarForm.observacoes}
              onChange={(e) => setRenov("observacoes", e.target.value)}
              placeholder="Notas sobre a renovação"
              rows={3}
            />
          </div>
        </div>
      </Dialog>

      <Dialog
        open={docsDialogOpen}
        onClose={closeDocs}
        title={selectedAlvaraForDocs ? `Documentos — ${selectedAlvaraForDocs.numero_alvara}` : "Documentos do alvará"}
        size="lg"
      >
        <div className="space-y-4">
          {docErr && (
            <div role="alert" className="rounded border border-danger/40 bg-danger-soft p-3 text-sm text-danger-soft-foreground">
              {docErr}
            </div>
          )}

          <div className="border-t pt-4">
            <h3 className="font-semibold mb-3">{editingDoc ? "Editar documento" : "Adicionar documento"}</h3>
            <div className="space-y-3">
              <div>
                <Label htmlFor="doc_tipo" required>
                  Tipo de documento
                </Label>
                <Input
                  id="doc_tipo"
                  value={docForm.tipo_documento}
                  onChange={(e) => setDoc("tipo_documento", e.target.value)}
                  placeholder="ex: Contrato, Procuração, Comprovante"
                />
              </div>

              <div>
                <Label htmlFor="doc_arquivo" required>
                  Arquivo (filename/path)
                </Label>
                <Input
                  id="doc_arquivo"
                  value={docForm.arquivo}
                  onChange={(e) => setDoc("arquivo", e.target.value)}
                  placeholder="ex: contrato_2026.pdf"
                />
              </div>

              <div>
                <Label htmlFor="doc_obs">Observações</Label>
                <Textarea
                  id="doc_obs"
                  value={docForm.observacoes}
                  onChange={(e) => setDoc("observacoes", e.target.value)}
                  placeholder="Notas sobre o documento"
                  rows={2}
                />
              </div>

              <div className="flex justify-end gap-2">
                {editingDoc && (
                  <Button variant="secondary" size="sm" onClick={resetDocForm}>
                    Cancelar edição
                  </Button>
                )}
                <Button size="sm" onClick={salvarDoc} disabled={saveDocM.isPending}>
                  {saveDocM.isPending ? "Salvando..." : editingDoc ? "Atualizar" : "Adicionar"}
                </Button>
              </div>
            </div>
          </div>

          {docsQ.isLoading ? (
            <div className="text-center text-muted-foreground py-4">Carregando documentos...</div>
          ) : (docsQ.data?.items.length ?? 0) === 0 ? (
            <div className="text-center text-muted-foreground py-4">Nenhum documento anexado.</div>
          ) : (
            <div className="border-t pt-4">
              <h3 className="font-semibold mb-3">Documentos anexados</h3>
              <div className="space-y-2">
                {docsQ.data?.items.map((doc) => (
                  <div key={doc.id} className="rounded border p-3 flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <div className="font-medium text-sm">{doc.tipo_documento}</div>
                      <div className="text-xs text-muted-foreground">{doc.arquivo}</div>
                      {doc.observacoes && (
                        <div className="text-xs text-muted-foreground mt-1 italic">{doc.observacoes}</div>
                      )}
                    </div>
                    <div className="inline-flex gap-1 flex-shrink-0">
                      {canEdit && (
                        <Button variant="secondary" size="sm" onClick={() => openEditDoc(doc)}>
                          Editar
                        </Button>
                      )}
                      {canDelete && (
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={async () => {
                            const ok = await confirm({
                              title: "Remover documento",
                              message: `Remover o documento "${doc.tipo_documento}"? Esta ação não pode ser desfeita.`,
                            });
                            if (ok) deleteDocM.mutate(doc.id);
                          }}
                          disabled={deleteDocM.isPending}
                        >
                          {deleteDocM.isPending ? "Removendo..." : "Remover"}
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </Dialog>

      <Dialog
        open={respDialogOpen}
        onClose={closeResp}
        title={selectedAlvaraForResp ? `Responsáveis — ${selectedAlvaraForResp.numero_alvara}` : "Responsáveis do alvará"}
        size="lg"
      >
        <div className="space-y-4">
          {respErr && (
            <div role="alert" className="rounded border border-danger/40 bg-danger-soft p-3 text-sm text-danger-soft-foreground">
              {respErr}
            </div>
          )}

          <div className="border-t pt-4">
            <h3 className="font-semibold mb-3">Adicionar responsável</h3>
            <div className="space-y-3">
              <div>
                <Label htmlFor="resp_usuario" required>
                  Usuário
                </Label>
                <Select
                  id="resp_usuario"
                  value={respForm.id_usuario}
                  onChange={(e) => setRespForm((f) => ({ ...f, id_usuario: e.target.value }))}
                >
                  <option value="">Selecione um usuário</option>
                  {usuariosQ.data?.items?.map((u: Usuario) => (
                    <option key={u.id} value={String(u.id)}>
                      {u.nome} ({u.email})
                    </option>
                  ))}
                </Select>
              </div>

              <div>
                <Label htmlFor="resp_cargo">Cargo/Função</Label>
                <Input
                  id="resp_cargo"
                  value={respForm.cargo_funcao}
                  onChange={(e) => setRespForm((f) => ({ ...f, cargo_funcao: e.target.value }))}
                  placeholder="ex: Gerente, Operador"
                />
              </div>

              <div className="flex justify-end gap-2">
                <Button size="sm" onClick={salvarResp} disabled={addRespM.isPending}>
                  {addRespM.isPending ? "Adicionando..." : "Adicionar"}
                </Button>
              </div>
            </div>
          </div>

          {respQ.isLoading ? (
            <div className="text-center text-muted-foreground py-4">Carregando responsáveis...</div>
          ) : (respQ.data?.items.length ?? 0) === 0 ? (
            <div className="text-center text-muted-foreground py-4">Nenhum responsável vinculado.</div>
          ) : (
            <div className="border-t pt-4">
              <h3 className="font-semibold mb-3">Responsáveis vinculados</h3>
              <div className="space-y-2">
                {respQ.data?.items.map((resp) => (
                  <div key={resp.id} className="rounded border p-3 flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <div className="font-medium text-sm">ID Usuário: {resp.id_usuario}</div>
                      {resp.cargo_funcao && (
                        <div className="text-xs text-muted-foreground">{resp.cargo_funcao}</div>
                      )}
                    </div>
                    {canDelete && (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={async () => {
                          const ok = await confirm({
                            title: "Remover responsável",
                            message: `Remover este responsável? Esta ação não pode ser desfeita.`,
                          });
                          if (ok) deleteRespM.mutate(resp.id);
                        }}
                        disabled={deleteRespM.isPending}
                      >
                        {deleteRespM.isPending ? "Removendo..." : "Remover"}
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </Dialog>
    </div>
  );
}
