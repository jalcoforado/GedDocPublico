"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlarmClock,
  Building2,
  CalendarClock,
  ClipboardCheck,
  IdCard,
  Inbox,
  Play,
  RefreshCw,
  SearchX,
} from "lucide-react";
import Link from "next/link";
import { use, useEffect, useState } from "react";

import { fmtData } from "@/components/pagamentos/format";
import { useValidacao } from "@/components/transporte/formulario";
import { SITUACAO_CONVOCACAO } from "@/components/transporte/rotulos";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, type RecadastramentoConvocacao } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface PageParams {
  params: Promise<{ id: string }>;
}

const SITUACAO_LABEL: Record<string, string> = {
  rascunho: "Rascunho",
  aberto: "Aberto",
  encerrado: "Encerrado",
};
const SITUACAO_INTENT: Record<string, "neutral" | "success" | "info"> = {
  rascunho: "neutral",
  aberto: "success",
  encerrado: "info",
};

/** Selo de atraso na listagem: prazo vencido E situação ainda aberta — a mesma
 *  regra de `esta_em_atraso` no servidor.
 *
 *  Isto é APENAS o selo. A contagem de dias e o relatório de faltosos vêm do
 *  servidor, que é a autoridade sobre "hoje" — o relógio do posto de
 *  atendimento não decide quem está em falta. */
const SITUACOES_ABERTAS = ["convocado", "em_analise"];

function emAtraso(c: RecadastramentoConvocacao): boolean {
  if (!SITUACOES_ABERTAS.includes(c.situacao)) return false;
  return c.prazo < new Date().toISOString().slice(0, 10);
}

export default function CicloRecadastramentoPage({ params }: PageParams) {
  const { id } = use(params);
  const cicloId = Number(id);

  const { can } = useAuth();
  const canCreate = can("transporte_regulado", "inserir");
  const canEdit = can("transporte_regulado", "atualizar");
  const qc = useQueryClient();
  const toast = useToast();

  const [tipoFiltro, setTipoFiltro] = useState("");
  const [busca, setBusca] = useState("");
  const [ajusteAberto, setAjusteAberto] = useState(false);
  const [alvo, setAlvo] = useState<RecadastramentoConvocacao | null>(null);
  const [prazo, setPrazo] = useState("");
  const [justificativa, setJustificativa] = useState("");
  const [ajusteErr, setAjusteErr] = useState<string | null>(null);

  const [buscaAplicada, setBuscaAplicada] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca.trim()), 300);
    return () => clearTimeout(t);
  }, [busca]);

  const cicloQ = useQuery({
    queryKey: ["tr-recad-ciclo", cicloId],
    queryFn: () => api.recadastramento.ciclos.get(cicloId),
    enabled: Number.isFinite(cicloId),
  });

  const convocacoesQ = useQuery({
    queryKey: ["tr-recad-convocacoes", cicloId, tipoFiltro, buscaAplicada],
    queryFn: () =>
      api.recadastramento.convocacoes.list(cicloId, {
        tipo: tipoFiltro || undefined,
        // Busca no SERVIDOR — o convocado procurado pode estar fora da página
        // corrente, e filtrar aqui faria a tela dizer que ele não existe.
        q: buscaAplicada || undefined,
      }),
    enabled: Number.isFinite(cicloId),
  });

  const gerarM = useMutation({
    mutationFn: () => api.recadastramento.ciclos.gerarConvocacoes(cicloId),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["tr-recad-convocacoes", cicloId] });
      // Os dois números vão na mensagem: `0/0` diz que não há regulado ativo,
      // que é informação diferente de "funcionou".
      toast.success(
        `${r.criadas} convocação(ões) criada(s); ${r.ja_existentes} já existia(m).`,
      );
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const ajusteM = useMutation({
    mutationFn: () =>
      alvo
        ? api.recadastramento.convocacoes.ajustarPrazo(alvo.id, {
            prazo,
            justificativa: justificativa.trim(),
          })
        : Promise.reject(new Error("Nenhuma convocação selecionada")),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tr-recad-convocacoes", cicloId] });
      toast.success("Prazo ajustado.");
      fecharAjuste();
    },
    onError: (e: Error) => setAjusteErr(e.message),
  });

  // A justificativa é obrigatória também no formulário, e não só no backend:
  // descobrir a regra por mensagem de erro depois de digitar tudo é pior.
  const janela = cicloQ.data;
  const valAjuste = useValidacao<"prazo" | "justificativa">({
    prazo: !prazo
      ? "Informe o novo prazo."
      : janela && (prazo < janela.data_inicio || prazo > janela.data_fim)
        ? `Escolha uma data dentro da janela do ciclo (${fmtData(janela.data_inicio)} a ${fmtData(janela.data_fim)}).`
        : undefined,
    justificativa:
      justificativa.trim().length < 5
        ? `Justifique o ajuste: mínimo de 5 caracteres${justificativa.trim() ? ` (faltam ${5 - justificativa.trim().length})` : ""}.`
        : undefined,
  });

  function abrirAjuste(c: RecadastramentoConvocacao) {
    setAlvo(c);
    setPrazo(c.prazo);
    setJustificativa("");
    setAjusteErr(null);
    valAjuste.reiniciar();
    setAjusteAberto(true);
  }

  function fecharAjuste() {
    setAjusteAberto(false);
    setAlvo(null);
    setPrazo("");
    setJustificativa("");
    setAjusteErr(null);
  }

  function submeterAjuste() {
    setAjusteErr(null);
    if (!valAjuste.conferir()) return;
    ajusteM.mutate();
  }

  const ciclo = cicloQ.data;
  const convocacoes = convocacoesQ.data?.items ?? [];
  const total = convocacoesQ.data?.total ?? 0;
  const buscando = buscaAplicada.length > 0 || tipoFiltro !== "";
  const encerrado = ciclo?.situacao === "encerrado";

  function limparFiltros() {
    setTipoFiltro("");
    setBusca("");
  }

  if (cicloQ.isLoading) {
    return <Carregando className="text-center text-muted-foreground py-8" />;
  }
  if (cicloQ.isError || !ciclo) {
    return (
      <EmptyState
        icon={Inbox}
        title="Ciclo não encontrado"
        description="O ciclo pode ter sido excluído ou pertence a outro município."
      />
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={RefreshCw}
        title={ciclo.nome}
        description={`Janela de ${fmtData(ciclo.data_inicio)} a ${fmtData(ciclo.data_fim)}. ${
          ciclo.criterio_escalonamento === "final_documento"
            ? "Prazos escalonados pelo final do CPF/CNPJ."
            : "Todos os convocados no fim da janela."
        }`}
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Recadastramento", href: "/m/transporte/recadastramento" },
          { label: ciclo.nome },
        ]}
        actions={
          <>
            {/* Sem este link a tela de faltosos existiria e ninguem chegaria
                nela. `__tests__/rotas-modulo.test.ts` reprova pagina orfa —
                e so passou a reprovar DE VERDADE na P5.3, ver o docstring de
                lá. */}
            <Button variant="secondary" asChild>
              <Link href={`/m/transporte/recadastramento/${cicloId}/faltosos`}>
                <AlarmClock className="mr-1 h-4 w-4" />
                Faltosos
              </Link>
            </Button>
            {canCreate && !encerrado && (
              <Button onClick={() => gerarM.mutate()} disabled={gerarM.isPending}>
                <Play className="mr-1 h-4 w-4" />
                {gerarM.isPending ? "Gerando..." : "Gerar convocações"}
              </Button>
            )}
          </>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <Badge intent={SITUACAO_INTENT[ciclo.situacao] ?? "neutral"}>
          {SITUACAO_LABEL[ciclo.situacao] ?? ciclo.situacao}
        </Badge>
        <span className="text-sm text-muted-foreground">
          {total} convocado(s){buscando ? " no filtro atual" : ""}
        </span>
        {encerrado && (
          <span className="text-sm text-muted-foreground">
            Ciclo encerrado: não gera novas convocações nem aceita ajuste de prazo.
          </span>
        )}
      </div>

      <FilterBar ariaLabel="Filtros dos convocados">
        <FilterBar.Group label="Tipo de regulado" className="w-full sm:w-48">
          <Select
            id="f_tipo"
            aria-label="Tipo de regulado"
            value={tipoFiltro}
            onChange={(e) => setTipoFiltro(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="permissionario">Permissionários</option>
            <option value="empresa">Empresas</option>
          </Select>
        </FilterBar.Group>
        <FilterBar.Group label="Busca por nome" className="min-w-[200px] flex-1">
          <Input
            id="f_q"
            aria-label="Busca por nome"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Nome do permissionário ou razão social..."
          />
        </FilterBar.Group>
        {buscando && (
          <FilterBar.Actions>
            <Button variant="ghost" onClick={limparFiltros}>
              Limpar
            </Button>
          </FilterBar.Actions>
        )}
      </FilterBar>

      {convocacoesQ.isLoading ? (
        <Carregando className="text-center text-muted-foreground py-8" />
      ) : convocacoes.length === 0 ? (
        // "A busca não achou" NÃO oferece gerar: o ciclo pode ter centenas de
        // convocados e o botão sugeriria que a lista está vazia.
        <EmptyState
          icon={buscando ? SearchX : Inbox}
          title={buscando ? "Nenhum convocado encontrado" : "Nenhuma convocação"}
          description={
            buscando
              ? "Nada corresponde ao filtro atual. A busca cobre todos os convocados do ciclo, não só os desta página."
              : "Gere as convocações para chamar os permissionários e empresas ativos."
          }
          action={
            buscando ? (
              <Button variant="secondary" onClick={limparFiltros}>
                Limpar filtros
              </Button>
            ) : canCreate && !encerrado ? (
              <Button onClick={() => gerarM.mutate()} disabled={gerarM.isPending}>
                <Play className="mr-1 h-4 w-4" />
                Gerar convocações
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Regulado</TH>
              <TH>Tipo</TH>
              <TH>Prazo</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {convocacoes.map((c) => (
              <TR key={c.id}>
                <TD className="font-medium">{c.nome_regulado}</TD>
                <TD className="text-sm text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    {c.tipo_regulado === "empresa" ? (
                      <Building2 className="h-3.5 w-3.5" aria-hidden="true" />
                    ) : (
                      <IdCard className="h-3.5 w-3.5" aria-hidden="true" />
                    )}
                    {c.tipo_regulado === "empresa" ? "Empresa" : "Permissionário"}
                  </span>
                </TD>
                <TD>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="tabular-nums">{fmtData(c.prazo)}</span>
                    {c.ajustado && (
                      // O prazo original fica visível: sem ele o ajuste não é
                      // auditável na tela, só no banco.
                      <Badge intent="warning" title={c.ajuste_justificativa ?? undefined}>
                        Ajustado (era {fmtData(c.prazo_original)})
                      </Badge>
                    )}
                    {emAtraso(c) && <Badge intent="danger">Em atraso</Badge>}
                  </div>
                </TD>
                <TD>
                  <Badge intent={SITUACAO_CONVOCACAO[c.situacao]?.intent ?? "neutral"}>
                    {SITUACAO_CONVOCACAO[c.situacao]?.label ?? c.situacao}
                  </Badge>
                </TD>
                <TD className="text-right">
                  {/* Sem o "Atender" a tela de atendimento existiria e ninguem
                      chegaria nela — foi o defeito que a costura de
                      2026-08-01 achou em Alvaras e Relatorios. */}
                  <AcoesDaLinha
                    acoes={[
                      {
                        label: "Atender",
                        icon: ClipboardCheck,
                        href: `/m/transporte/recadastramento/${cicloId}/convocacao/${c.id}`,
                      },
                      {
                        label: "Ajustar prazo",
                        icon: CalendarClock,
                        onClick: () => abrirAjuste(c),
                        oculta: !(canEdit && !encerrado),
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
        open={ajusteAberto}
        onClose={fecharAjuste}
        title={`Ajustar prazo — ${alvo?.nome_regulado ?? ""}`}
        description="Data no passado é permitida — regularizar alguém retroativamente é caso de balcão."
        footer={
          <>
            <Button variant="ghost" onClick={fecharAjuste}>
              Cancelar
            </Button>
            <Button onClick={submeterAjuste} loading={ajusteM.isPending}>
              Ajustar prazo
            </Button>
          </>
        }
      >
        <div ref={valAjuste.ref} className="space-y-4">
          <FormField
            label="Novo prazo"
            required
            error={valAjuste.erro("prazo")}
            hint={
              alvo
                ? `Pela regra do ciclo seria ${fmtData(alvo.prazo_original)}. A janela vai de ${fmtData(ciclo.data_inicio)} a ${fmtData(ciclo.data_fim)}.`
                : undefined
            }
          >
            <Input
              id="a_prazo"
              type="date"
              min={ciclo.data_inicio}
              max={ciclo.data_fim}
              value={prazo}
              onChange={(e) => setPrazo(e.target.value)}
              onBlur={valAjuste.sair("prazo")}
              className="max-w-xs"
            />
          </FormField>
          <FormField
            label="Justificativa"
            required
            error={valAjuste.erro("justificativa")}
            hint="Fica registrada com autor e data: sem ela o ajuste vira favor invisível."
          >
            <Textarea
              id="a_just"
              rows={3}
              value={justificativa}
              onChange={(e) => setJustificativa(e.target.value)}
              onBlur={valAjuste.sair("justificativa")}
              placeholder="Ex.: permissionário internado no período; laudo anexado ao processo."
            />
          </FormField>
          {ajusteErr && <Alert intent="danger">{ajusteErr}</Alert>}
        </div>
      </Dialog>
    </div>
  );
}
