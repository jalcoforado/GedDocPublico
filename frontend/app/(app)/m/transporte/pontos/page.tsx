"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, MapPin, Plus } from "lucide-react";
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
  vagas_total: "1",
  situacao: "ativo",
  observacoes: "",
};

/** `""` vira `null` — o backend distingue "não informado" de string vazia. */
function limpo(v: string): string | null {
  const t = v.trim();
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

  function abrirNovo() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setDialogOpen(true);
  }

  function abrirEdicao(p: Ponto) {
    setEditing(p);
    setForm(paraForm(p));
    setErr(null);
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

      <div className="flex flex-wrap gap-2">
        <Input
          placeholder="Buscar por nome..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="max-w-xs"
        />
        <Select
          value={tipoFiltro}
          onChange={(e) => setTipoFiltro(e.target.value)}
          className="max-w-[200px]"
        >
          <option value="">Todos os tipos</option>
          {TIPOS.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </Select>
        <Select
          value={situacaoFiltro}
          onChange={(e) => setSituacaoFiltro(e.target.value)}
          className="max-w-[160px]"
        >
          <option value="">Todas</option>
          <option value="ativo">Ativos</option>
          <option value="inativo">Inativos</option>
        </Select>
      </div>

      {q.isLoading ? (
        <div className="py-8 text-center text-muted-foreground">Carregando...</div>
      ) : itens.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={buscaAplicada ? "Nenhum ponto encontrado" : "Nenhum ponto cadastrado"}
          // Com busca ativa, NÃO oferecer "cadastrar": convidaria a duplicar
          // um ponto que existe e a busca não achou.
          description={
            buscaAplicada
              ? "Nenhum ponto corresponde à busca. Revise o termo."
              : "Cadastre os pontos de táxi e mototáxi do município."
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
                    className="hover:underline"
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
                <TD className="space-x-2 text-right">
                  <Link href={`/m/transporte/pontos/${p.id}`}>
                    <Button variant="secondary" size="sm">
                      Vagas
                    </Button>
                  </Link>
                  {canEdit && (
                    <Button variant="ghost" size="sm" onClick={() => abrirEdicao(p)}>
                      Editar
                    </Button>
                  )}
                  {canDelete && (
                    <Button variant="ghost" size="sm" onClick={() => pedirExclusao(p)}>
                      Excluir
                    </Button>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editing ? "Editar ponto" : "Novo ponto"}
      >
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            setErr(null);
            salvarM.mutate();
          }}
        >
          {err && (
            <div className="rounded-md border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
              {err}
            </div>
          )}
          <div>
            <Label htmlFor="nome">Nome</Label>
            <Input
              id="nome"
              required
              value={form.nome}
              onChange={(e) => set("nome", e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="codigo">Código</Label>
              <Input
                id="codigo"
                value={form.codigo}
                onChange={(e) => set("codigo", e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="tipo">Tipo de serviço</Label>
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
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <Label htmlFor="logradouro">Logradouro</Label>
              <Input
                id="logradouro"
                value={form.logradouro}
                onChange={(e) => set("logradouro", e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="numero">Número</Label>
              <Input
                id="numero"
                value={form.numero}
                onChange={(e) => set("numero", e.target.value)}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="bairro">Bairro</Label>
              <Input
                id="bairro"
                value={form.bairro}
                onChange={(e) => set("bairro", e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="cep">CEP</Label>
              <Input
                id="cep"
                value={form.cep}
                onChange={(e) => set("cep", e.target.value)}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="vagas">Total de vagas</Label>
              <Input
                id="vagas"
                type="number"
                min={1}
                required
                value={form.vagas_total}
                onChange={(e) => set("vagas_total", e.target.value)}
              />
              {editing && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Não é possível reduzir abaixo da maior vaga ocupada.
                </p>
              )}
            </div>
            <div>
              <Label htmlFor="situacao">Situação</Label>
              <Select
                id="situacao"
                value={form.situacao}
                onChange={(e) => set("situacao", e.target.value as PontoSituacao)}
              >
                <option value="ativo">Ativo</option>
                <option value="inativo">Inativo</option>
              </Select>
              {form.situacao === "inativo" && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Ponto inativo não recebe novas ocupações; quem já está fica.
                </p>
              )}
            </div>
          </div>
          <div>
            <Label htmlFor="obs">Observações</Label>
            <Input
              id="obs"
              value={form.observacoes}
              onChange={(e) => set("observacoes", e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setDialogOpen(false)}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={salvarM.isPending}>
              {salvarM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
