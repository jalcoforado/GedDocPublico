"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, IdCard, Inbox, Play, RefreshCw } from "lucide-react";
import Link from "next/link";
import { use, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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

  function abrirAjuste(c: RecadastramentoConvocacao) {
    setAlvo(c);
    setPrazo(c.prazo);
    setJustificativa("");
    setAjusteErr(null);
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
    if (!prazo) {
      setAjusteErr("Informe o novo prazo.");
      return;
    }
    // A justificativa é obrigatória também no formulário, e não só no backend:
    // descobrir a regra por mensagem de erro depois de digitar tudo é pior.
    if (justificativa.trim().length < 5) {
      setAjusteErr("Justifique o ajuste (mínimo de 5 caracteres).");
      return;
    }
    ajusteM.mutate();
  }

  const ciclo = cicloQ.data;
  const convocacoes = convocacoesQ.data?.items ?? [];
  const total = convocacoesQ.data?.total ?? 0;
  const buscando = buscaAplicada.length > 0 || tipoFiltro !== "";
  const encerrado = ciclo?.situacao === "encerrado";

  if (cicloQ.isLoading) {
    return <div className="text-center text-muted-foreground py-8">Carregando...</div>;
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
        description={`Janela de ${ciclo.data_inicio} a ${ciclo.data_fim}. ${
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
          canCreate && !encerrado ? (
            <Button onClick={() => gerarM.mutate()} disabled={gerarM.isPending}>
              <Play className="mr-1 h-4 w-4" />
              {gerarM.isPending ? "Gerando..." : "Gerar convocações"}
            </Button>
          ) : undefined
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

      <div className="flex flex-wrap gap-3">
        <div>
          <Label htmlFor="f_tipo">Tipo de regulado</Label>
          <Select
            id="f_tipo"
            value={tipoFiltro}
            onChange={(e) => setTipoFiltro(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="permissionario">Permissionários</option>
            <option value="empresa">Empresas</option>
          </Select>
        </div>
        <div className="flex-1 min-w-[200px]">
          <Label htmlFor="f_q">Busca por nome</Label>
          <Input
            id="f_q"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Nome do permissionário ou razão social..."
          />
        </div>
      </div>

      {convocacoesQ.isLoading ? (
        <div className="text-center text-muted-foreground py-8">Carregando...</div>
      ) : convocacoes.length === 0 ? (
        // "A busca não achou" NÃO oferece gerar: o ciclo pode ter centenas de
        // convocados e o botão sugeriria que a lista está vazia.
        <EmptyState
          icon={Inbox}
          title={buscando ? "Nenhum convocado encontrado" : "Nenhuma convocação"}
          description={
            buscando
              ? "Nada corresponde ao filtro atual. A busca cobre todos os convocados do ciclo, não só os desta página."
              : "Gere as convocações para chamar os permissionários e empresas ativos."
          }
          action={
            !buscando && canCreate && !encerrado ? (
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
                    <span>{c.prazo}</span>
                    {c.ajustado && (
                      // O prazo original fica visível: sem ele o ajuste não é
                      // auditável na tela, só no banco.
                      <Badge intent="warning" title={c.ajuste_justificativa ?? undefined}>
                        ajustado (era {c.prazo_original})
                      </Badge>
                    )}
                  </div>
                </TD>
                <TD className="text-sm text-muted-foreground">{c.situacao}</TD>
                <TD className="text-right">
                  <div className="inline-flex flex-wrap justify-end gap-2">
                    {/* Sem este link a tela de atendimento existiria e ninguem
                        chegaria nela — foi o defeito que a costura de
                        2026-08-01 achou em Alvaras e Relatorios. */}
                    <Button variant="secondary" size="sm" asChild>
                      <Link
                        href={`/m/transporte/recadastramento/${cicloId}/convocacao/${c.id}`}
                      >
                        Atender
                      </Link>
                    </Button>
                    {canEdit && !encerrado && (
                      <Button variant="secondary" size="sm" onClick={() => abrirAjuste(c)}>
                        Ajustar prazo
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
        open={ajusteAberto}
        onClose={fecharAjuste}
        title={`Ajustar prazo — ${alvo?.nome_regulado ?? ""}`}
        footer={
          <>
            <Button variant="secondary" onClick={fecharAjuste}>
              Cancelar
            </Button>
            <Button onClick={submeterAjuste} disabled={ajusteM.isPending}>
              {ajusteM.isPending ? "Salvando..." : "Salvar ajuste"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          {ajusteErr && <div className="text-sm text-danger">{ajusteErr}</div>}
          <p className="text-sm text-muted-foreground">
            O prazo tem de ficar dentro da janela do ciclo ({ciclo.data_inicio} a{" "}
            {ciclo.data_fim}). Data no passado é permitida — regularizar alguém
            retroativamente é caso de balcão.
          </p>
          <div>
            <Label htmlFor="a_prazo">Novo prazo</Label>
            <Input
              id="a_prazo"
              type="date"
              min={ciclo.data_inicio}
              max={ciclo.data_fim}
              value={prazo}
              onChange={(e) => setPrazo(e.target.value)}
            />
            {alvo && (
              <p className="mt-1 text-xs text-muted-foreground">
                Prazo calculado pela regra: {alvo.prazo_original}
              </p>
            )}
          </div>
          <div>
            <Label htmlFor="a_just">Justificativa</Label>
            <Textarea
              id="a_just"
              rows={3}
              value={justificativa}
              onChange={(e) => setJustificativa(e.target.value)}
              placeholder="Por que este regulado recebe prazo diferente?"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Obrigatória: sem ela o ajuste vira favor invisível. Fica registrada com
              autor e data.
            </p>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
