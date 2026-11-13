"use client";

import { Carregando } from "@/components/ui/carregando";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Eye,
  FileText,
  Inbox,
  Pencil,
  Plus,
  RefreshCw,
  ScrollText,
  SearchX,
  Trash2,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";

import {
  CampoVinculo,
  errosDoVinculo,
  idsDoVinculo,
  modoDoVinculo,
  type ModoVinculo,
} from "@/components/transporte/campo-vinculo";
import {
  AtalhosPrazo,
  dicaVigencia,
  erroValidade,
  GrupoCampos,
  hojeISO,
  useValidacao,
} from "@/components/transporte/formulario";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR, TRLink } from "@/components/ui/table";
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
const PAGE_SIZE = 50;
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
  // Truncava em 50 sem aviso (backend já pagina desde 2026-07-20; a UI nunca
  // ganhou controle). Reseta pra 1 a cada troca de filtro/busca.
  const [page, setPage] = useState(1);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Alvara | null>(null);
  const [form, setForm] = useState<AlvaraForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);
  const [modoVinculo, setModoVinculo] = useState<ModoVinculo>("permissionario");
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
    const t = setTimeout(() => {
      setBuscaAplicada(busca.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [busca]);

  const listaQ = useQuery({
    queryKey: ["tr-alvaras", empresaFiltro, permFiltro, buscaAplicada, page],
    queryFn: () =>
      api.alvaras.list({
        empresa_id: empresaFiltro ? Number(empresaFiltro) : undefined,
        permissionario_id: permFiltro ? Number(permFiltro) : undefined,
        // Busca NO SERVIDOR. Filtrar `items` aqui era o defeito: a lista chega
        // truncada em `page_size`, então número fora da primeira página
        // desaparecia e a tela afirmava que o alvará não existe.
        q: buscaAplicada || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  });
  const totalPages = Math.max(1, Math.ceil((listaQ.data?.total ?? 0) / PAGE_SIZE));

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

  // Regras do backend (`AlvaraCreate`), ditas no campo com o conserto. Antes
  // a primeira que falhasse ia para o topo e escondia as outras.
  const val = useValidacao<"id_permissionario" | "id_empresa" | "numero_alvara" | "data_validade">({
    ...errosDoVinculo(modoVinculo, form.id_permissionario, form.id_empresa),
    numero_alvara: form.numero_alvara.trim() === "" ? "Informe o número do alvará." : undefined,
    data_validade: erroValidade(form.data_inicio, form.data_validade),
  });
  const valRenov = useValidacao<"data_validade">({
    data_validade: erroValidade(renovarForm.data_inicio, renovarForm.data_validade),
  });
  const valDoc = useValidacao<"tipo_documento" | "arquivo">({
    tipo_documento: docForm.tipo_documento.trim() === "" ? "Informe o tipo do documento." : undefined,
    arquivo: docForm.arquivo.trim() === "" ? "Informe o nome do arquivo." : undefined,
  });
  const valResp = useValidacao<"id_usuario">({
    id_usuario: respForm.id_usuario === "" ? "Escolha o usuário na lista." : undefined,
  });

  function set<K extends keyof AlvaraForm>(key: K, value: AlvaraForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function openNew() {
    setEditing(null);
    // Início sugerido: hoje (a dica do campo diz isso).
    setForm({ ...EMPTY, data_inicio: hojeISO() });
    setModoVinculo("permissionario");
    setErr(null);
    val.reiniciar();
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
    setModoVinculo(
      modoDoVinculo(
        a.id_permissionario != null ? String(a.id_permissionario) : "",
        a.id_empresa != null ? String(a.id_empresa) : "",
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
    setErr(null);
  }

  function openRenovar(a: Alvara) {
    setSelectedAlvaraToRenew(a);
    // O novo alvará começa hoje; a validade a pessoa escolhe (há atalhos).
    setRenovarForm({ ...EMPTY_RENOV, data_inicio: hojeISO() });
    setRenovarErr(null);
    valRenov.reiniciar();
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
    valDoc.reiniciar();
  }

  function openEditDoc(doc: AlvaraDocumento) {
    setEditingDoc(doc);
    valDoc.reiniciar();
    setDocForm({
      tipo_documento: doc.tipo_documento,
      arquivo: doc.arquivo,
      observacoes: doc.observacoes ?? "",
    });
  }

  function salvarDoc() {
    setDocErr(null);
    if (!valDoc.conferir()) return;
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
    valResp.reiniciar();
  }

  function salvarResp() {
    setRespErr(null);
    if (!valResp.conferir()) return;
    const payload: AlvaraResponsavelInput = {
      id_usuario: Number(respForm.id_usuario),
      cargo_funcao: nullify(respForm.cargo_funcao),
    };
    addRespM.mutate(payload);
  }

  function salvarRenov() {
    setRenovarErr(null);
    if (!valRenov.conferir()) return;
    const payload: AlvaraRenovarInput = {
      data_inicio: nullify(renovarForm.data_inicio),
      data_validade: nullify(renovarForm.data_validade),
      observacoes: nullify(renovarForm.observacoes),
    };
    renovarM.mutate(payload);
  }

  function salvar() {
    setErr(null);
    if (!val.conferir()) return;
    const payload: AlvaraInput = {
      numero_alvara: form.numero_alvara.trim(),
      data_inicio: nullify(form.data_inicio),
      data_validade: nullify(form.data_validade),
      tipo_servico: form.tipo_servico,
      observacoes: nullify(form.observacoes),
      ...idsDoVinculo(modoVinculo, form.id_permissionario, form.id_empresa),
    };
    saveM.mutate(payload);
  }

  // Sem filtro no cliente: o que chega já veio filtrado pelo servidor.
  const filteredData = listaQ.data?.items ?? [];
  const buscando = buscaAplicada.length > 0;
  const filtrando = buscando || empresaFiltro !== "" || permFiltro !== "";

  function limparFiltros() {
    setEmpresaFiltro("");
    setPermFiltro("");
    setBusca("");
    setPage(1);
  }

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

      <FilterBar ariaLabel="Filtros dos alvarás">
        <FilterBar.Group label="Empresa" className="w-full sm:w-56">
          <Select
            id="f_emp"
            aria-label="Empresa"
            value={empresaFiltro}
            onChange={(e) => {
              setEmpresaFiltro(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Todas</option>
            {empresasQ.data?.items.map((e: Empresa) => (
              <option key={e.id} value={String(e.id)}>
                {e.razao_social}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        <FilterBar.Group label="Permissionário" className="w-full sm:w-56">
          <Select
            id="f_perm"
            aria-label="Permissionário"
            value={permFiltro}
            onChange={(e) => {
              setPermFiltro(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            {permsQ.data?.items.map((p: Permissionario) => (
              <option key={p.id} value={String(p.id)}>
                {p.nome}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        <FilterBar.Group label="Busca por número" className="min-w-[200px] flex-1">
          <Input
            id="f_q"
            aria-label="Busca por número"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="ALV-001, ALV-002..."
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

      {listaQ.isLoading ? (
        <Carregando className="text-center text-muted-foreground py-8" />
      ) : filteredData.length === 0 ? (
        // Dois estados distintos, mensagem distinta. "Cadastre o primeiro
        // alvará" numa busca sem resultado é informação errada — o tenant pode
        // ter centenas, e o botão convidaria a duplicar um que já existe.
        <EmptyState
          icon={filtrando ? SearchX : Inbox}
          title={filtrando ? "Nenhum alvará encontrado" : "Nenhum alvará"}
          description={
            buscando
              ? `Nada corresponde a "${buscaAplicada}". A busca cobre todos os alvarás do município, não só os desta página.`
              : filtrando
                ? "Nenhum alvará corresponde aos filtros aplicados."
                : "Cadastre o primeiro alvará do transporte regulado."
          }
          action={
            filtrando ? (
              <Button variant="secondary" onClick={limparFiltros}>
                Limpar filtros
              </Button>
            ) : canCreate ? (
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
              <TRLink key={a.id} href={`/m/transporte/alvaras/${a.id}`}>
                <TD className="whitespace-nowrap font-mono font-medium">
                  <Link
                    href={`/m/transporte/alvaras/${a.id}`}
                    className="text-primary hover:underline"
                  >
                    {a.numero_alvara}
                  </Link>
                </TD>
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
                  {/* A tela de detalhe (auditoria + veículos) existia desde a
                      P3 e NÃO tinha link nenhum: só se chegava digitando a
                      URL. Achado em 2026-08-05, ao consertar a guarda de
                      página órfã, que até então truncava a rota no primeiro
                      segmento dinâmico e por isso nunca a examinou.
                      Alvará vencido mostra "Renovar" à vista, que é o que se
                      faz com ele; os demais mostram "Editar". */}
                  <AcoesDaLinha
                    acoes={[
                      { label: "Detalhes", icon: Eye, href: `/m/transporte/alvaras/${a.id}` },
                      {
                        label: "Renovar",
                        icon: RefreshCw,
                        onClick: () => openRenovar(a),
                        oculta: !(canCreate && isExpired(a.data_validade)),
                      },
                      { label: "Editar", icon: Pencil, onClick: () => openEdit(a), oculta: !canEdit },
                      {
                        label: "Documentos",
                        icon: FileText,
                        onClick: () => openDocs(a),
                        oculta: !canCreate,
                      },
                      {
                        label: "Responsáveis",
                        icon: Users,
                        onClick: () => openResp(a),
                        oculta: !canCreate,
                      },
                      {
                        label: "Excluir",
                        icon: Trash2,
                        perigo: true,
                        oculta: !canDelete,
                        onClick: async () => {
                          const ok = await confirm({
                            title: "Excluir alvará",
                            message: `Excluir o alvará "${a.numero_alvara}"? Esta ação não pode ser desfeita.`,
                          });
                          if (ok) deleteM.mutate(a.id);
                        },
                      },
                    ]}
                  />
                </TD>
              </TRLink>
            ))}
          </TBody>
        </Table>
      )}

      {listaQ.data && listaQ.data.total > 0 && (
        <div className="flex flex-col items-start justify-between gap-2 text-sm text-muted-foreground sm:flex-row sm:items-center">
          <span className="tabular-nums">
            {listaQ.data.total} alvarás — página {page} de {totalPages}
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
        title={editing ? `Editar alvará — ${editing.numero_alvara}` : "Novo alvará"}
        description={editing ? undefined : "Em nome de quem, para qual serviço e por quanto tempo."}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={salvar} loading={saveM.isPending}>
              {editing ? "Salvar alterações" : "Emitir alvará"}
            </Button>
          </>
        }
      >
        <div ref={val.ref} className="space-y-5">
          <GrupoCampos titulo="Titular">
            <CampoVinculo
              nome="alvara-vinculo"
              titulo="O alvará está em nome de"
              modo={modoVinculo}
              onModo={setModoVinculo}
              descricoes={{
                permissionario: "Alvará de um permissionário que opera por conta própria.",
                empresa: "Alvará de uma empresa autorizada.",
                ambos: "Alvará da empresa, com o permissionário que opera por ela.",
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

          <GrupoCampos titulo="Alvará">
            <GradeCampos>
              <FormField
                label="Número do alvará"
                required
                error={val.erro("numero_alvara")}
                hint="Único no município."
              >
                <Input
                  id="numero"
                  value={form.numero_alvara}
                  onChange={(e) => set("numero_alvara", e.target.value)}
                  onBlur={val.sair("numero_alvara")}
                  className="font-mono"
                  placeholder="Ex.: ALV-0123/2026"
                />
              </FormField>
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
            </GradeCampos>
          </GrupoCampos>

          <GrupoCampos titulo="Vigência" descricao="Sem validade, o alvará aparece como indefinido nos indicadores.">
            <GradeCampos>
              <FormField label="Início" opcional hint={editing ? undefined : "Hoje, por padrão."}>
                <Input
                  id="data_inicio"
                  type="date"
                  value={form.data_inicio}
                  onChange={(e) => set("data_inicio", e.target.value)}
                />
              </FormField>
              <FormField
                label="Validade"
                opcional
                error={val.erro("data_validade")}
                acao={<AtalhosPrazo inicio={form.data_inicio} onEscolher={(d) => set("data_validade", d)} />}
                hint={dicaVigencia(form.data_inicio, form.data_validade, "Último dia em que o alvará vale.")}
              >
                <Input
                  id="data_validade"
                  type="date"
                  value={form.data_validade}
                  onChange={(e) => set("data_validade", e.target.value)}
                  onBlur={val.sair("data_validade")}
                />
              </FormField>
            </GradeCampos>
          </GrupoCampos>

          <div className="border-t border-border pt-5">
            <FormField label="Observações" opcional>
              <Textarea
                id="obs"
                value={form.observacoes}
                onChange={(e) => set("observacoes", e.target.value)}
                placeholder="Ex.: emitido após vistoria de 05/11/2026"
                rows={3}
              />
            </FormField>
          </div>

          {err && <Alert intent="danger">{err}</Alert>}
        </div>
      </Dialog>

      <Dialog
        open={renovarDialogOpen}
        onClose={closeRenovarDialog}
        title={selectedAlvaraToRenew ? `Renovar alvará — ${selectedAlvaraToRenew.numero_alvara}` : "Renovar alvará"}
        description="A renovação emite um alvará novo, ligado a este, para o mesmo titular."
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={closeRenovarDialog}>
              Cancelar
            </Button>
            <Button onClick={salvarRenov} loading={renovarM.isPending}>
              Renovar alvará
            </Button>
          </>
        }
      >
        <div ref={valRenov.ref} className="space-y-5">
          {selectedAlvaraToRenew && (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-border bg-surface-1 p-4 text-sm">
              <div>
                <dt className="text-xs text-foreground-muted">Alvará atual</dt>
                <dd className="font-mono font-medium text-foreground">{selectedAlvaraToRenew.numero_alvara}</dd>
              </div>
              <div>
                <dt className="text-xs text-foreground-muted">Tipo de serviço</dt>
                <dd className="text-foreground">
                  {TIPO_LABEL[selectedAlvaraToRenew.tipo_servico] ?? selectedAlvaraToRenew.tipo_servico}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="text-xs text-foreground-muted">Validade atual</dt>
                <dd className="flex items-center gap-2 text-foreground">
                  {formatarData(selectedAlvaraToRenew.data_validade)}
                  {isExpired(selectedAlvaraToRenew.data_validade) && <Badge intent="danger">Expirado</Badge>}
                </dd>
              </div>
            </dl>
          )}

          <GradeCampos>
            <FormField label="Início do novo alvará" opcional hint="Hoje, por padrão.">
              <Input
                id="renov_data_inicio"
                type="date"
                value={renovarForm.data_inicio}
                onChange={(e) => setRenov("data_inicio", e.target.value)}
              />
            </FormField>
            <FormField
              label="Nova validade"
              opcional
              error={valRenov.erro("data_validade")}
              acao={
                <AtalhosPrazo
                  inicio={renovarForm.data_inicio}
                  onEscolher={(d) => setRenov("data_validade", d)}
                />
              }
              hint={dicaVigencia(renovarForm.data_inicio, renovarForm.data_validade, "Último dia em que o novo alvará vale.")}
            >
              <Input
                id="renov_data_validade"
                type="date"
                value={renovarForm.data_validade}
                onChange={(e) => setRenov("data_validade", e.target.value)}
                onBlur={valRenov.sair("data_validade")}
              />
            </FormField>
          </GradeCampos>

          <FormField label="Observações" opcional>
            <Textarea
              id="renov_obs"
              value={renovarForm.observacoes}
              onChange={(e) => setRenov("observacoes", e.target.value)}
              placeholder="Ex.: renovação com vistoria em dia"
              rows={3}
            />
          </FormField>

          {renovarErr && <Alert intent="danger">{renovarErr}</Alert>}
        </div>
      </Dialog>

      <Dialog
        open={docsDialogOpen}
        onClose={closeDocs}
        title={selectedAlvaraForDocs ? `Documentos do alvará ${selectedAlvaraForDocs.numero_alvara}` : "Documentos do alvará"}
        size="lg"
      >
        <div className="space-y-5">
          <section
            aria-label={editingDoc ? "Editar documento" : "Adicionar documento"}
            className="space-y-4 rounded-lg border border-border bg-surface-1 p-4"
          >
            <h3 className="text-sm font-semibold text-foreground">
              {editingDoc ? `Editar documento — ${editingDoc.tipo_documento}` : "Adicionar documento"}
            </h3>
            <div ref={valDoc.ref} className="space-y-4">
              <GradeCampos>
                <FormField label="Tipo de documento" required error={valDoc.erro("tipo_documento")}>
                  <Input
                    id="doc_tipo"
                    value={docForm.tipo_documento}
                    onChange={(e) => setDoc("tipo_documento", e.target.value)}
                    onBlur={valDoc.sair("tipo_documento")}
                    placeholder="Ex.: Contrato social"
                  />
                </FormField>
                <FormField
                  label="Arquivo"
                  required
                  error={valDoc.erro("arquivo")}
                  hint="Nome do arquivo como está guardado."
                >
                  <Input
                    id="doc_arquivo"
                    value={docForm.arquivo}
                    onChange={(e) => setDoc("arquivo", e.target.value)}
                    onBlur={valDoc.sair("arquivo")}
                    placeholder="Ex.: contrato_2026.pdf"
                  />
                </FormField>
              </GradeCampos>
              <FormField label="Observações" opcional>
                <Textarea
                  id="doc_obs"
                  value={docForm.observacoes}
                  onChange={(e) => setDoc("observacoes", e.target.value)}
                  placeholder="Ex.: cópia autenticada"
                  rows={2}
                />
              </FormField>
              {docErr && <Alert intent="danger">{docErr}</Alert>}
              <div className="flex justify-end gap-2">
                {editingDoc && (
                  <Button variant="ghost" size="sm" onClick={resetDocForm}>
                    Cancelar edição
                  </Button>
                )}
                <Button size="sm" onClick={salvarDoc} loading={saveDocM.isPending}>
                  {editingDoc ? "Salvar documento" : "Adicionar documento"}
                </Button>
              </div>
            </div>
          </section>

          {docsQ.isLoading ? (
            <Carregando className="py-4 text-center text-muted-foreground" />
          ) : (docsQ.data?.items.length ?? 0) === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">Nenhum documento anexado ainda.</p>
          ) : (
            <div>
              <h3 className="mb-3 text-sm font-semibold text-foreground">Documentos anexados</h3>
              <div className="space-y-2">
                {docsQ.data?.items.map((doc) => (
                  <div key={doc.id} className="flex items-start justify-between gap-3 rounded-lg border border-border p-3">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium">{doc.tipo_documento}</div>
                      <div className="truncate text-xs text-muted-foreground">{doc.arquivo}</div>
                      {doc.observacoes && (
                        <div className="mt-1 text-xs italic text-muted-foreground">{doc.observacoes}</div>
                      )}
                    </div>
                    <div className="inline-flex flex-shrink-0 gap-1">
                      {canEdit && (
                        <Button variant="secondary" size="sm" onClick={() => openEditDoc(doc)}>
                          Editar
                        </Button>
                      )}
                      {canDelete && (
                        <Button
                          variant="danger-outline"
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
        title={selectedAlvaraForResp ? `Responsáveis pelo alvará ${selectedAlvaraForResp.numero_alvara}` : "Responsáveis do alvará"}
        description="Servidores que acompanham este alvará."
        size="lg"
      >
        <div className="space-y-5">
          <section
            aria-label="Adicionar responsável"
            className="space-y-4 rounded-lg border border-border bg-surface-1 p-4"
          >
            <h3 className="text-sm font-semibold text-foreground">Adicionar responsável</h3>
            <div ref={valResp.ref} className="space-y-4">
              <GradeCampos>
                <FormField label="Usuário" required error={valResp.erro("id_usuario")} hint="Busque pelo nome ou e-mail.">
                  <Combobox
                    id="resp_usuario"
                    options={(usuariosQ.data?.items ?? []).map((u: Usuario) => ({
                      value: u.id,
                      label: u.nome,
                      hint: u.email,
                    }))}
                    value={respForm.id_usuario ? Number(respForm.id_usuario) : null}
                    onChange={(id) => setRespForm((f) => ({ ...f, id_usuario: id == null ? "" : String(id) }))}
                    placeholder="Escolha o usuário…"
                    searchPlaceholder="Nome ou e-mail…"
                    emptyText="Nenhum usuário com esse nome ou e-mail."
                    loading={usuariosQ.isLoading}
                  />
                </FormField>
                <FormField label="Cargo ou função" opcional>
                  <Input
                    id="resp_cargo"
                    value={respForm.cargo_funcao}
                    onChange={(e) => setRespForm((f) => ({ ...f, cargo_funcao: e.target.value }))}
                    placeholder="Ex.: Fiscal de transporte"
                  />
                </FormField>
              </GradeCampos>
              {respErr && <Alert intent="danger">{respErr}</Alert>}
              <div className="flex justify-end">
                <Button size="sm" onClick={salvarResp} loading={addRespM.isPending}>
                  Adicionar responsável
                </Button>
              </div>
            </div>
          </section>

          {respQ.isLoading ? (
            <Carregando className="py-4 text-center text-muted-foreground" />
          ) : (respQ.data?.items.length ?? 0) === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">Nenhum responsável vinculado ainda.</p>
          ) : (
            <div>
              <h3 className="mb-3 text-sm font-semibold text-foreground">Responsáveis vinculados</h3>
              <div className="space-y-2">
                {respQ.data?.items.map((resp) => {
                  const usuario = usuariosQ.data?.items?.find((u: Usuario) => u.id === resp.id_usuario);
                  return (
                    <div key={resp.id} className="flex items-start justify-between gap-3 rounded-lg border border-border p-3">
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium">{usuario?.nome ?? `Usuário nº ${resp.id_usuario}`}</div>
                        {(resp.cargo_funcao || usuario?.email) && (
                          <div className="text-xs text-muted-foreground">
                            {[resp.cargo_funcao, usuario?.email].filter(Boolean).join(" · ")}
                          </div>
                        )}
                      </div>
                      {canDelete && (
                        <Button
                          variant="danger-outline"
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
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </Dialog>
    </div>
  );
}
