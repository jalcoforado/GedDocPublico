"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Eye, Inbox, Plus, SearchX, Tags, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { fmtData } from "@/components/pagamentos/format";
import { CamposAlvo } from "@/components/transporte/campos-alvo";
import { GrupoCampos, hojeISO, useValidacao } from "@/components/transporte/formulario";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
    // O fato costuma ser de hoje (a dica do campo diz isso).
    setForm({ ...EMPTY, data_fato: hojeISO() });
    setErr(null);
    val.reiniciar();
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

  const tipoEscolhido = tiposAtivos.find((t) => t.id === form.id_tipo);
  // Ao menos um alvo FORMAL: `exigir_alvo` no backend não aceita
  // `referencia_alvo` sozinha — ela é só complemento textual. Validar igual
  // ao servidor evita o round-trip que terminaria em 422.
  const val = useValidacao<"alvo" | "id_tipo" | "data_fato" | "descricao">({
    alvo:
      form.id_permissionario === null && form.id_empresa === null && form.id_veiculo === null
        ? "Escolha ao menos um alvo: permissionário, empresa ou veículo."
        : undefined,
    id_tipo: form.id_tipo === null ? "Escolha o tipo da ocorrência." : undefined,
    data_fato:
      form.data_fato === ""
        ? "Informe a data do fato."
        : form.data_fato > hojeISO()
          ? "A data do fato não pode ser futura."
          : undefined,
    descricao: form.descricao.trim() === "" ? "Descreva o que aconteceu." : undefined,
  });

  function submeter() {
    setErr(null);
    if (!val.conferir()) return;
    registrarM.mutate();
  }

  const filtrando =
    buscaAplicada !== "" || situacaoFiltro !== "" || origemFiltro !== "" || tipoFiltro !== "";

  function limparFiltros() {
    setBusca("");
    setSituacaoFiltro("");
    setOrigemFiltro("");
    setTipoFiltro("");
  }

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
          <>
            <Button asChild variant="secondary">
              <Link href="/m/transporte/ocorrencias/tipos">
                <Tags className="mr-1 h-4 w-4" />
                Tipos de ocorrência
              </Link>
            </Button>
            {canCreate && (
              <Button onClick={abrirNovo}>
                <Plus className="mr-1 h-4 w-4" />
                Registrar ocorrência
              </Button>
            )}
          </>
        }
      />

      <FilterBar ariaLabel="Filtros das ocorrências">
        <FilterBar.Group label="Busca" className="w-full sm:w-72">
          <Input
            aria-label="Buscar por descrição ou alvo"
            placeholder="Buscar por descrição ou alvo..."
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
        </FilterBar.Group>
        <FilterBar.Group label="Situação" className="w-full sm:w-48">
          <Select
            aria-label="Situação"
            value={situacaoFiltro}
            onChange={(e) => setSituacaoFiltro(e.target.value)}
          >
            <option value="">Todas as situações</option>
            {(Object.keys(SITUACAO_LABEL) as OcorrenciaSituacao[]).map((s) => (
              <option key={s} value={s}>
                {SITUACAO_LABEL[s]}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        <FilterBar.Group label="Origem" className="w-full sm:w-44">
          <Select
            aria-label="Origem"
            value={origemFiltro}
            onChange={(e) => setOrigemFiltro(e.target.value)}
          >
            <option value="">Todas as origens</option>
            {(Object.keys(ORIGEM_LABEL) as OcorrenciaOrigem[]).map((o) => (
              <option key={o} value={o}>
                {ORIGEM_LABEL[o]}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        <FilterBar.Group label="Tipo" className="w-full sm:w-52">
          <Select
            aria-label="Tipo de ocorrência"
            value={tipoFiltro}
            onChange={(e) => setTipoFiltro(e.target.value)}
          >
            <option value="">Todos os tipos</option>
            {tipos.map((t) => (
              <option key={t.id} value={t.id}>
                {t.nome}
              </option>
            ))}
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
          title={filtrando ? "Nenhuma ocorrência encontrada" : "Nenhuma ocorrência registrada"}
          // Com busca ativa, NÃO oferecer "registrar": convidaria a duplicar
          // uma ocorrência que existe e a busca não achou.
          description={
            filtrando
              ? "Nenhuma ocorrência corresponde à busca ou aos filtros. Revise o termo."
              : "Registre fiscalizações e denúncias contra operadores do transporte regulado."
          }
          action={
            filtrando ? (
              <Button variant="secondary" onClick={limparFiltros}>
                Limpar filtros
              </Button>
            ) : canCreate ? (
              <Button onClick={abrirNovo}>
                <Plus className="mr-1 h-4 w-4" />
                Registrar ocorrência
              </Button>
            ) : undefined
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
                  <Link
                    href={`/m/transporte/ocorrencias/${o.id}`}
                    className="text-primary hover:underline"
                  >
                    #{o.id}
                  </Link>
                </TD>
                <TD className="text-sm">{o.tipo_nome ?? "—"}</TD>
                <TD className="text-sm text-muted-foreground">
                  {o.alvo_resumo ?? o.referencia_alvo ?? "—"}
                </TD>
                <TD className="text-sm">{ORIGEM_LABEL[o.origem]}</TD>
                <TD className="text-sm tabular-nums">{fmtData(o.data_fato)}</TD>
                <TD>
                  <Badge intent={SITUACAO_INTENT[o.situacao]}>
                    {SITUACAO_LABEL[o.situacao]}
                  </Badge>
                </TD>
                <TD className="text-right">
                  <AcoesDaLinha
                    acoes={[
                      { label: "Ver", icon: Eye, href: `/m/transporte/ocorrencias/${o.id}` },
                      {
                        label: "Excluir",
                        icon: Trash2,
                        perigo: true,
                        onClick: () => pedirExclusao(o),
                        // Só a recém-registrada sai: depois disso há apuração.
                        oculta: !(canDelete && o.situacao === "registrada"),
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
        title="Registrar ocorrência"
        description="Contra quem, o que aconteceu e quando. A apuração começa depois, na tela da ocorrência."
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={submeter} loading={registrarM.isPending}>
              Registrar ocorrência
            </Button>
          </>
        }
      >
        <div ref={val.ref} className="space-y-5">
          <GrupoCampos titulo="Contra quem">
            <CamposAlvo
              ativo={dialogOpen}
              idPermissionario={form.id_permissionario}
              idEmpresa={form.id_empresa}
              idVeiculo={form.id_veiculo}
              onPermissionario={(id) => set("id_permissionario", id)}
              onEmpresa={(id) => set("id_empresa", id)}
              onVeiculo={(id) => set("id_veiculo", id)}
              erro={val.erro("alvo")}
            />
            <FormField
              label="Referência complementar"
              opcional
              hint="Texto livre que ajuda a achar o alvo; não substitui a escolha acima."
            >
              <Input
                id="referencia"
                placeholder="Ex.: placa ABC1D23, se o veículo não tem cadastro"
                value={form.referencia_alvo}
                onChange={(e) => set("referencia_alvo", e.target.value)}
              />
            </FormField>
          </GrupoCampos>

          <GrupoCampos titulo="O que aconteceu">
            <GradeCampos>
              <FormField
                label="Tipo"
                required
                error={val.erro("id_tipo")}
                hint={tipoEscolhido?.descricao ?? undefined}
              >
                <Select
                  id="tipo"
                  value={form.id_tipo ?? ""}
                  onChange={(e) => set("id_tipo", e.target.value ? Number(e.target.value) : null)}
                  onBlur={val.sair("id_tipo")}
                >
                  <option value="">Selecione…</option>
                  {tiposAtivos.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.nome}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField
                label="Data do fato"
                required
                error={val.erro("data_fato")}
                hint="Hoje, por padrão. Não pode ser data futura."
              >
                <Input
                  id="data_fato"
                  type="date"
                  max={hojeISO()}
                  value={form.data_fato}
                  onChange={(e) => set("data_fato", e.target.value)}
                  onBlur={val.sair("data_fato")}
                />
              </FormField>
            </GradeCampos>
            <EscolhaSegmentada<OcorrenciaOrigem>
              nome="origem"
              titulo="Origem"
              moldura={false}
              valor={form.origem}
              onChange={(o) => set("origem", o)}
              opcoes={[
                { valor: "fiscalizacao", rotulo: ORIGEM_LABEL.fiscalizacao, descricao: "Constatada por agente durante a fiscalização." },
                { valor: "denuncia", rotulo: ORIGEM_LABEL.denuncia, descricao: "Relatada por cidadão ou outro órgão." },
                { valor: "outro", rotulo: ORIGEM_LABEL.outro, descricao: "Outra origem — conte na descrição como chegou." },
              ]}
            />
            <FormField
              label="Descrição"
              required
              error={val.erro("descricao")}
              hint="O que aconteceu, onde e como foi constatado."
            >
              <Textarea
                id="descricao"
                rows={4}
                value={form.descricao}
                onChange={(e) => set("descricao", e.target.value)}
                onBlur={val.sair("descricao")}
                placeholder="Ex.: veículo operando com alvará vencido na Av. Central, às 14h."
              />
            </FormField>
          </GrupoCampos>

          <div className="border-t border-border pt-5">
            <FormField label="Observações" opcional>
              <Input
                id="obs"
                value={form.observacoes}
                onChange={(e) => set("observacoes", e.target.value)}
                placeholder="Ex.: auto de infração nº 1234"
              />
            </FormField>
          </div>

          {err && <Alert intent="danger">{err}</Alert>}
        </div>
      </Dialog>
    </div>
  );
}
