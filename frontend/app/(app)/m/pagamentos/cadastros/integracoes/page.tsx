"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, KeyRound, Plus, ShieldOff } from "lucide-react";
import { useState } from "react";

import { fmtDataHora } from "@/components/pagamentos/format";
import { useValidacaoCampos } from "@/components/pagamentos/useValidacaoCampos";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type SistemaIntegrado, type SistemaIntegradoInput } from "@/lib/api";

const FORM_INICIAL: SistemaIntegradoInput = {
  nome: "",
  escopo_leitura: false,
  escopo_escrita: false,
};

export default function IntegracoesPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [criarOpen, setCriarOpen] = useState(false);
  const [form, setForm] = useState<SistemaIntegradoInput>(FORM_INICIAL);
  const [chaveCriada, setChaveCriada] = useState<string | null>(null);
  const vCriar = useValidacaoCampos(
    { nome: !form.nome.trim() && "Dê um nome para reconhecer a chave na lista." },
    { nome: "integracao-nome" },
  );

  const sistemasQ = useQuery({
    queryKey: ["pag-sistemas-integrados"],
    queryFn: () => api.pagamentos.sistemasIntegrados.listar(),
  });

  const sistemas = sistemasQ.data ?? [];

  const criar = useMutation({
    mutationFn: () => api.pagamentos.sistemasIntegrados.criar(form),
    onSuccess: (criado) => {
      qc.invalidateQueries({ queryKey: ["pag-sistemas-integrados"] });
      setCriarOpen(false);
      setForm(FORM_INICIAL);
      // A chave completa só existe nesta resposta — depois disto o backend
      // não a devolve mais. O modal de sucesso é a única chance de copiá-la.
      setChaveCriada(criado.chave);
    },
    onError: (e: unknown) => {
      toast.error(e instanceof Error ? e.message : "Falha ao criar a chave.");
    },
  });

  const revogar = useMutation({
    mutationFn: (id: number) => api.pagamentos.sistemasIntegrados.revogar(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-sistemas-integrados"] });
      toast.success("Chave revogada.");
    },
    onError: (e: unknown) => {
      toast.error(e instanceof Error ? e.message : "Falha ao revogar a chave.");
    },
  });

  function abrirCriar() {
    setForm(FORM_INICIAL);
    vCriar.reiniciar();
    setCriarOpen(true);
  }

  async function pedirRevogacao(sistema: SistemaIntegrado) {
    const ok = await confirm({
      title: "Revogar chave",
      message: (
        <>
          Revogar <strong>{sistema.nome}</strong> invalida a chave imediatamente.
          Chamadas do sistema integrado passam a receber 401. Esta ação não tem
          desfazer — para voltar a integrar é preciso criar uma chave nova.
        </>
      ),
      confirmLabel: "Revogar",
      intent: "danger",
    });
    if (!ok) return;
    revogar.mutate(sistema.id);
  }

  async function copiarChave() {
    if (!chaveCriada) return;
    try {
      await navigator.clipboard.writeText(chaveCriada);
      toast.success("Chave copiada.");
    } catch {
      toast.error("Não foi possível copiar. Selecione e copie manualmente.");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={KeyRound}
        breadcrumbs={[
          { label: "Pagamentos", href: "/m/pagamentos" },
          { label: "Cadastros e controle", href: "/m/pagamentos/cadastros" },
          { label: "Sistemas integrados" },
        ]}
        title="Sistemas integrados"
        description="Chaves de API para sistemas externos lerem ou gravarem dados de pagamentos (cabeçalho X-Api-Key)."
        actions={
          <Button onClick={abrirCriar}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Nova chave
          </Button>
        }
      />

      <SectionCard title="Chaves cadastradas">
        {sistemasQ.isLoading ? (
          <Carregando className="text-sm text-foreground-muted" />
        ) : sistemas.length === 0 ? (
          <EmptyState
            icon={KeyRound}
            title="Nenhum sistema integrado cadastrado"
            description="Crie uma chave para permitir que um sistema externo leia ou grave dados de pagamentos via API."
            action={
              <Button onClick={abrirCriar}>
                <Plus className="h-4 w-4" aria-hidden="true" />
                Nova chave
              </Button>
            }
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Nome</TH>
                <TH>Prefixo</TH>
                <TH>Escopos</TH>
                <TH>Estado</TH>
                <TH>Criado em</TH>
                <TH className="text-right">Ações</TH>
              </TR>
            </THead>
            <TBody>
              {sistemas.map((s) => (
                <TR key={s.id}>
                  <TD className="font-medium">{s.nome}</TD>
                  <TD>
                    <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{s.prefixo}</code>
                  </TD>
                  <TD>
                    <div className="flex flex-wrap gap-1">
                      {s.escopo_leitura && <Badge intent="info">Leitura</Badge>}
                      {s.escopo_escrita && <Badge intent="brand">Escrita</Badge>}
                      {!s.escopo_leitura && !s.escopo_escrita && (
                        <span className="text-xs text-foreground-muted">—</span>
                      )}
                    </div>
                  </TD>
                  <TD>
                    {s.ativo ? (
                      <Badge intent="success">Ativa</Badge>
                    ) : (
                      <Badge intent="neutral">Revogada</Badge>
                    )}
                  </TD>
                  <TD>{fmtDataHora(s.criado_em)}</TD>
                  <TD className="text-right">
                    <AcoesDaLinha
                      acoes={[
                        {
                          label: "Revogar",
                          icon: ShieldOff,
                          perigo: true,
                          onClick: () => pedirRevogacao(s),
                          disabled: revogar.isPending,
                          oculta: !s.ativo,
                        },
                      ]}
                    />
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </SectionCard>

      <Dialog
        open={criarOpen}
        onClose={() => setCriarOpen(false)}
        title="Nova chave de integração"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCriarOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => {
                if (vCriar.conferir()) criar.mutate();
              }}
              loading={criar.isPending}
            >
              Criar chave
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <FormField
            label="Nome do sistema"
            required
            error={vCriar.erro("nome")}
            hint="Para reconhecer a chave na lista. Ex.: o nome do ERP que vai usá-la."
          >
            <Input
              id="integracao-nome"
              value={form.nome}
              onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))}
              onBlur={vCriar.tocar("nome")}
              placeholder="Ex.: ERP Financeiro"
              autoFocus
            />
          </FormField>
          <fieldset className="space-y-2">
            <legend className="mb-1 text-sm font-medium text-foreground">O que a chave pode fazer</legend>
            <div className="flex items-center gap-2">
              <Checkbox
                id="integracao-leitura"
                checked={!!form.escopo_leitura}
                onChange={(e) =>
                  setForm((f) => ({ ...f, escopo_leitura: e.target.checked }))
                }
              />
              <Label htmlFor="integracao-leitura" className="mb-0 cursor-pointer font-normal">
                Leitura
              </Label>
            </div>
            <p className="pl-7 text-xs text-foreground-muted">
              Consultar solicitações, ordens de pagamento e baixas.
            </p>
            <div className="flex items-center gap-2">
              <Checkbox
                id="integracao-escrita"
                checked={!!form.escopo_escrita}
                onChange={(e) =>
                  setForm((f) => ({ ...f, escopo_escrita: e.target.checked }))
                }
              />
              <Label htmlFor="integracao-escrita" className="mb-0 cursor-pointer font-normal">
                Escrita
              </Label>
            </div>
            <p className="pl-7 text-xs text-foreground-muted">
              Criar solicitações e registrar liquidação pela API.
            </p>
          </fieldset>
        </div>
      </Dialog>

      <Dialog
        open={!!chaveCriada}
        onClose={() => setChaveCriada(null)}
        title="Chave criada"
        size="sm"
        footer={<Button onClick={() => setChaveCriada(null)}>Entendi, copiei a chave</Button>}
      >
        <div className="space-y-3 text-sm">
          <p className="font-semibold text-danger">
            Copie agora — esta chave não será mostrada de novo.
          </p>
          <div className="flex items-center gap-2">
            <code className="break-all rounded bg-muted px-2 py-1.5 font-mono text-xs">
              {chaveCriada}
            </code>
            <Button variant="secondary" size="sm" onClick={copiarChave} type="button">
              <Copy className="mr-2 h-4 w-4" aria-hidden="true" />
              Copiar
            </Button>
          </div>
          <p className="text-foreground-muted">
            Guarde-a em local seguro (cofre de segredos do sistema integrado). O
            prefixo continua visível na lista para identificar a chave depois, mas
            o segredo não é recuperável — só é possível revogar e criar uma nova.
          </p>
        </div>
      </Dialog>
    </div>
  );
}
