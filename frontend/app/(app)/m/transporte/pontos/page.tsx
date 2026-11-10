"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, MapPin, ParkingSquare, Pencil, Plus, SearchX, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { GrupoCampos, useValidacao } from "@/components/transporte/formulario";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FilterBar } from "@/components/ui/filter-bar";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type Ponto,
  type PontoCreate,
  type PontoSituacao,
  type TipoServico,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

// O ponto é objeto de táxi e mototáxi, mas a lista não impede os demais: a
// coluna no banco não tem CHECK e o Literal do schema aceita o vocabulário
// inteiro. Motofrete com ponto é plausível.
const TIPOS: { value: TipoServico; label: string }[] = [
  { value: "taxi", label: "Táxi" },
  { value: "mototaxi", label: "Mototáxi" },
  { value: "motofrete", label: "Motofrete" },
  { value: "transporte_escolar", label: "Transporte escolar" },
  { value: "transporte_distrital", label: "Transporte distrital" },
  { value: "aplicativo", label: "Aplicativo" },
  { value: "outro", label: "Outro" },
];
const TIPO_LABEL: Record<string, string> = Object.fromEntries(
  TIPOS.map((t) => [t.value, t.label]),
);

interface PontoForm {
  nome: string;
  codigo: string;
  tipo_servico: TipoServico;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cep: string;
  latitude: string;
  longitude: string;
  vagas_total: string;
  situacao: PontoSituacao;
  observacoes: string;
}

const EMPTY: PontoForm = {
  nome: "",
  codigo: "",
  tipo_servico: "taxi",
  logradouro: "",
  numero: "",
  complemento: "",
  bairro: "",
  cep: "",
  latitude: "",
  longitude: "",
  vagas_total: "1",
  situacao: "ativo",
  observacoes: "",
};

/** `""` vira `null` — o backend distingue "não informado" de string vazia. */
function limpo(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

/** Aceita vírgula decimal, que é como o brasileiro digita e cola coordenada. */
function coordenada(v: string): string | null {
  const t = v.trim().replace(",", ".");
  return t === "" ? null : t;
}

function paraPayload(f: PontoForm): PontoCreate {
  return {
    nome: f.nome.trim(),
    codigo: limpo(f.codigo),
    tipo_servico: f.tipo_servico,
    logradouro: limpo(f.logradouro),
    numero: limpo(f.numero),
    complemento: limpo(f.complemento),
    bairro: limpo(f.bairro),
    cep: limpo(f.cep),
    latitude: coordenada(f.latitude),
    longitude: coordenada(f.longitude),
    vagas_total: Number(f.vagas_total) || 1,
    situacao: f.situacao,
    observacoes: limpo(f.observacoes),
  };
}

function paraForm(p: Ponto): PontoForm {
  return {
    nome: p.nome,
    codigo: p.codigo ?? "",
    tipo_servico: p.tipo_servico,
    logradouro: p.logradouro ?? "",
    numero: p.numero ?? "",
    complemento: p.complemento ?? "",
    bairro: p.bairro ?? "",
    cep: p.cep ?? "",
    latitude: p.latitude ?? "",
    longitude: p.longitude ?? "",
    vagas_total: String(p.vagas_total),
    situacao: p.situacao,
    observacoes: p.observacoes ?? "",
  };
}

export default function PontosPage() {
  const { can } = useAuth();
  const canCreate = can("transporte_regulado", "inserir");
  const canEdit = can("transporte_regulado", "atualizar");
  const canDelete = can("transporte_regulado", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [busca, setBusca] = useState("");
  const [tipoFiltro, setTipoFiltro] = useState("");
  const [situacaoFiltro, setSituacaoFiltro] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Ponto | null>(null);
  const [form, setForm] = useState<PontoForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  // Busca NO SERVIDOR, com debounce. Filtrar no cliente sobre a página
  // truncada faz a tela afirmar que um ponto não existe.
  const [buscaAplicada, setBuscaAplicada] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca.trim()), 300);
    return () => clearTimeout(t);
  }, [busca]);

  const q = useQuery({
    queryKey: ["tr-pontos", buscaAplicada, tipoFiltro, situacaoFiltro],
    queryFn: () =>
      api.pontos.list({
        q: buscaAplicada || undefined,
        tipo_servico: tipoFiltro || undefined,
        situacao: situacaoFiltro || undefined,
      }),
  });

  function invalidar() {
    qc.invalidateQueries({ queryKey: ["tr-pontos"] });
  }

  const salvarM = useMutation({
    mutationFn: () =>
      editing
        ? api.pontos.update(editing.id, paraPayload(form))
        : api.pontos.create(paraPayload(form)),
    onSuccess: () => {
      toast.success(editing ? "Ponto atualizado." : "Ponto criado.");
      setDialogOpen(false);
      invalidar();
    },
    onError: (e: Error) => setErr(e.message),
  });

  const excluirM = useMutation({
    mutationFn: (id: number) => api.pontos.remove(id),
    onSuccess: () => {
      toast.success("Ponto excluído.");
      invalidar();
    },
    // O 409 de "tem vaga ocupada" traz instrução acionável; mostrar a
    // mensagem do servidor é melhor do que traduzir para um genérico.
    onError: (e: Error) => toast.error(e.message),
  });

  // Antes só o `required` nativo do formulário conferia; agora o erro vem
  // no campo, depois de sair dele ou de tentar salvar.
  const val = useValidacao<"nome" | "vagas_total">({
    nome: form.nome.trim() === "" ? "Informe o nome do ponto." : undefined,
    vagas_total:
      !/^\d+$/.test(form.vagas_total.trim()) || Number(form.vagas_total) < 1
        ? "Informe quantas vagas o ponto tem (1 ou mais)."
        : undefined,
  });

  function submeter() {
    setErr(null);
    if (!val.conferir()) return;
    salvarM.mutate();
  }

  function abrirNovo() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    val.reiniciar();
    setDialogOpen(true);
  }

  function abrirEdicao(p: Ponto) {
    setEditing(p);
    setForm(paraForm(p));
    setErr(null);
    val.reiniciar();
    setDialogOpen(true);
  }

  async function pedirExclusao(p: Ponto) {
    const ok = await confirm({
      title: `Excluir "${p.nome}"?`,
      message:
        "O ponto sai das listagens. O histórico de ocupação é preservado.",
      confirmLabel: "Excluir",
      intent: "danger",
    });
    if (ok) excluirM.mutate(p.id);
  }

  const itens = q.data?.items ?? [];
  const filtrando = buscaAplicada !== "" || tipoFiltro !== "" || situacaoFiltro !== "";

  function limparFiltros() {
    setBusca("");
    setTipoFiltro("");
    setSituacaoFiltro("");
  }

  function set<K extends keyof PontoForm>(k: K, v: PontoForm[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={MapPin}
        title="Pontos e Vagas"
        description="Pontos de estacionamento regulados, com as vagas numeradas e quem ocupa cada uma."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Pontos" },
        ]}
        actions={
          canCreate ? (
            <Button onClick={abrirNovo}>
              <Plus className="mr-1 h-4 w-4" />
              Novo ponto
            </Button>
          ) : undefined
        }
      />

      <FilterBar ariaLabel="Filtros dos pontos">
        <FilterBar.Group label="Busca" className="w-full sm:w-72">
          <Input
            aria-label="Buscar por nome"
            placeholder="Buscar por nome..."
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
        </FilterBar.Group>
        <FilterBar.Group label="Tipo de serviço" className="w-full sm:w-56">
          <Select
            aria-label="Tipo de serviço"
            value={tipoFiltro}
            onChange={(e) => setTipoFiltro(e.target.value)}
          >
            <option value="">Todos os tipos</option>
            {TIPOS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        <FilterBar.Group label="Situação" className="w-full sm:w-40">
          <Select
            aria-label="Situação"
            value={situacaoFiltro}
            onChange={(e) => setSituacaoFiltro(e.target.value)}
          >
            <option value="">Todas</option>
            <option value="ativo">Ativos</option>
            <option value="inativo">Inativos</option>
          </Select>
        </FilterBar.Group>
        {filtrando && (
          <FilterBar.Actions>
            <Button variant="ghost" onClick={limparFiltros}>
              Limpar
            </Button>
          </FilterBar.Actions>
        )}
      </FilterBar>

      {q.isLoading ? (
        <Carregando className="py-8 text-center text-muted-foreground" />
      ) : itens.length === 0 ? (
        <EmptyState
          icon={filtrando ? SearchX : Inbox}
          title={filtrando ? "Nenhum ponto encontrado" : "Nenhum ponto cadastrado"}
          // Com busca ativa, NÃO oferecer "cadastrar": convidaria a duplicar
          // um ponto que existe e a busca não achou.
          description={
            filtrando
              ? "Nenhum ponto corresponde à busca ou aos filtros. Revise o termo."
              : "Cadastre os pontos de táxi e mototáxi do município."
          }
          action={
            filtrando ? (
              <Button variant="secondary" onClick={limparFiltros}>
                Limpar filtros
              </Button>
            ) : canCreate ? (
              <Button onClick={abrirNovo}>
                <Plus className="mr-1 h-4 w-4" />
                Cadastrar ponto
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Ponto</TH>
              <TH>Tipo</TH>
              <TH>Endereço</TH>
              <TH>Ocupação</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {itens.map((p) => (
              <TR key={p.id}>
                <TD className="font-medium">
                  <Link
                    href={`/m/transporte/pontos/${p.id}`}
                    className="text-primary hover:underline"
                  >
                    {p.nome}
                  </Link>
                  {p.codigo && (
                    <span className="ml-2 text-xs text-muted-foreground">
                      {p.codigo}
                    </span>
                  )}
                </TD>
                <TD className="text-sm">
                  {TIPO_LABEL[p.tipo_servico] ?? p.tipo_servico}
                </TD>
                <TD className="text-sm text-muted-foreground">
                  {[p.logradouro, p.numero, p.bairro].filter(Boolean).join(", ") || "—"}
                </TD>
                <TD>
                  <Badge intent={p.vagas_ocupadas >= p.vagas_total ? "warning" : "neutral"}>
                    {p.vagas_ocupadas}/{p.vagas_total}
                  </Badge>
                </TD>
                <TD>
                  <Badge intent={p.situacao === "ativo" ? "success" : "neutral"}>
                    {p.situacao === "ativo" ? "Ativo" : "Inativo"}
                  </Badge>
                </TD>
                <TD className="text-right">
                  <AcoesDaLinha
                    acoes={[
                      { label: "Vagas", icon: ParkingSquare, href: `/m/transporte/pontos/${p.id}` },
                      {
                        label: "Editar",
                        icon: Pencil,
                        onClick: () => abrirEdicao(p),
                        oculta: !canEdit,
                      },
                      {
                        label: "Excluir",
                        icon: Trash2,
                        perigo: true,
                        onClick: () => pedirExclusao(p),
                        oculta: !canDelete,
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
        onClose={() => setDialogOpen(false)}
        title={editing ? `Editar ponto — ${editing.nome}` : "Novo ponto"}
        description={editing ? undefined : "O ponto, quantas vagas tem e onde fica. As vagas se ocupam depois, na tela do ponto."}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={submeter} loading={salvarM.isPending}>
              {editing ? "Salvar alterações" : "Criar ponto"}
            </Button>
          </>
        }
      >
        <div ref={val.ref} className="space-y-5">
          <GrupoCampos titulo="Ponto">
            <FormField label="Nome" required error={val.erro("nome")}>
              <Input
                id="nome"
                value={form.nome}
                onChange={(e) => set("nome", e.target.value)}
                onBlur={val.sair("nome")}
                placeholder="Ex.: Ponto da Rodoviária"
              />
            </FormField>
            <GradeCampos>
              <FormField label="Código" opcional>
                <Input
                  id="codigo"
                  value={form.codigo}
                  onChange={(e) => set("codigo", e.target.value)}
                  placeholder="Ex.: PT-12"
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
            <GradeCampos>
              <FormField
                label="Total de vagas"
                required
                error={val.erro("vagas_total")}
                hint={editing ? "Não dá para reduzir abaixo da maior vaga ocupada." : "As vagas são numeradas de 1 até este total."}
              >
                <CampoComUnidade
                  id="vagas"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  sufixo="vagas"
                  value={form.vagas_total}
                  onChange={(e) => set("vagas_total", e.target.value)}
                  onBlur={val.sair("vagas_total")}
                />
              </FormField>
              <div aria-hidden="true" className="hidden sm:block" />
            </GradeCampos>
            <EscolhaSegmentada<PontoSituacao>
              nome="ponto-situacao"
              titulo="Situação"
              moldura={false}
              valor={form.situacao}
              onChange={(s) => set("situacao", s)}
              opcoes={[
                { valor: "ativo", rotulo: "Ativo", descricao: "O ponto recebe ocupações nas vagas livres." },
                { valor: "inativo", rotulo: "Inativo", descricao: "Não recebe novas ocupações; quem já está fica." },
              ]}
            />
          </GrupoCampos>

          <GrupoCampos titulo="Localização" descricao="Opcional. Com latitude e longitude, o ponto aparece no mapa.">
            <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_8rem]">
              <FormField label="Logradouro">
                <Input
                  id="logradouro"
                  value={form.logradouro}
                  onChange={(e) => set("logradouro", e.target.value)}
                  placeholder="Ex.: Av. Dom José"
                />
              </FormField>
              <FormField label="Número">
                <Input id="numero" value={form.numero} onChange={(e) => set("numero", e.target.value)} placeholder="Ex.: s/n" />
              </FormField>
            </div>
            <GradeCampos>
              <FormField label="Bairro">
                <Input id="bairro" value={form.bairro} onChange={(e) => set("bairro", e.target.value)} />
              </FormField>
              <FormField label="CEP">
                <Input
                  id="cep"
                  inputMode="numeric"
                  value={form.cep}
                  onChange={(e) => set("cep", e.target.value)}
                  placeholder="Ex.: 62010-000"
                />
              </FormField>
            </GradeCampos>
            <GradeCampos>
              <FormField label="Latitude" hint="Aceita vírgula ou ponto.">
                <Input
                  id="latitude"
                  inputMode="decimal"
                  placeholder="Ex.: -3,9694"
                  value={form.latitude}
                  onChange={(e) => set("latitude", e.target.value)}
                />
              </FormField>
              <FormField label="Longitude" hint="Copie do mapa junto com a latitude.">
                <Input
                  id="longitude"
                  inputMode="decimal"
                  placeholder="Ex.: -38,5280"
                  value={form.longitude}
                  onChange={(e) => set("longitude", e.target.value)}
                />
              </FormField>
            </GradeCampos>
          </GrupoCampos>

          <div className="border-t border-border pt-5">
            <FormField label="Observações" opcional>
              <Input
                id="obs"
                value={form.observacoes}
                onChange={(e) => set("observacoes", e.target.value)}
                placeholder="Ex.: funciona das 6h às 22h"
              />
            </FormField>
          </div>

          {err && <Alert intent="danger">{err}</Alert>}
        </div>
      </Dialog>
    </div>
  );
}
