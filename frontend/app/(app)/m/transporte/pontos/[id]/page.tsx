"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapPin, UserPlus } from "lucide-react";
import { use, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type PontoVaga } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface PageParams {
  params: Promise<{ id: string }>;
}

const MOTIVOS = [
  { value: "transferencia", label: "Transferência" },
  { value: "desistencia", label: "Desistência" },
  { value: "cassacao", label: "Cassação" },
  { value: "obito", label: "Óbito" },
  { value: "outro", label: "Outro" },
];
const MOTIVO_LABEL: Record<string, string> = Object.fromEntries(
  MOTIVOS.map((m) => [m.value, m.label]),
);

function formataData(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString("pt-BR");
}

export default function PontoDetalhePage({ params }: PageParams) {
  const { id } = use(params);
  const pontoId = Number(id);

  const { can } = useAuth();
  const canGerir = can("transporte_regulado", "atualizar");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [vagaAlvo, setVagaAlvo] = useState<number | null>(null);
  const [buscaPerm, setBuscaPerm] = useState("");
  const [permEscolhido, setPermEscolhido] = useState<number | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const mapaQ = useQuery({
    queryKey: ["tr-ponto-mapa", pontoId],
    queryFn: () => api.pontos.mapa(pontoId),
  });

  const historicoQ = useQuery({
    queryKey: ["tr-ponto-ocupacoes", pontoId],
    queryFn: () => api.pontos.ocupacoes(pontoId),
  });

  // Busca no servidor, e só quando o diálogo está aberto: a lista de
  // permissionários é grande e não faz sentido carregá-la para ver o mapa.
  const permsQ = useQuery({
    queryKey: ["tr-perms-para-vaga", buscaPerm],
    queryFn: () =>
      api.permissionarios.list({
        q: buscaPerm || undefined,
        situacao: "ativo",
      }),
    enabled: vagaAlvo !== null,
  });

  function invalidar() {
    qc.invalidateQueries({ queryKey: ["tr-ponto-mapa", pontoId] });
    qc.invalidateQueries({ queryKey: ["tr-ponto-ocupacoes", pontoId] });
  }

  const ocuparM = useMutation({
    mutationFn: () =>
      api.pontos.ocupar(pontoId, {
        numero_vaga: vagaAlvo as number,
        id_permissionario: permEscolhido as number,
      }),
    onSuccess: () => {
      toast.success(`Vaga ${vagaAlvo} ocupada.`);
      setVagaAlvo(null);
      setPermEscolhido(null);
      setBuscaPerm("");
      invalidar();
    },
    // A mensagem do servidor nomeia o ponto onde o permissionário já está —
    // trocá-la por um genérico tiraria justamente a parte acionável.
    onError: (e: Error) => setErro(e.message),
  });

  const liberarM = useMutation({
    mutationFn: (v: { ocupacaoId: number; motivo: string }) =>
      api.pontos.liberar(pontoId, v.ocupacaoId, {
        motivo_liberacao: v.motivo,
      }),
    onSuccess: () => {
      toast.success("Vaga liberada. A ocupação fica no histórico.");
      invalidar();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function pedirLiberacao(vaga: PontoVaga) {
    const oc = vaga.ocupacao;
    if (!oc) return;
    const ok = await confirm({
      title: `Liberar a vaga ${vaga.numero_vaga}?`,
      message: `${oc.nome_permissionario ?? "O ocupante"} deixa a vaga. A ocupação é encerrada, não apagada — continua no histórico.`,
      confirmLabel: "Liberar",
    });
    if (ok) liberarM.mutate({ ocupacaoId: oc.id, motivo: "transferencia" });
  }

  const mapa = mapaQ.data;
  const historico = historicoQ.data?.items ?? [];
  const perms = permsQ.data?.items ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        icon={MapPin}
        title={mapa?.nome ?? "Ponto"}
        description={
          mapa
            ? `${mapa.vagas_ocupadas} de ${mapa.vagas_total} vaga(s) ocupada(s).`
            : "Mapa de vagas do ponto."
        }
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Pontos", href: "/m/transporte/pontos" },
          { label: mapa?.nome ?? "Ponto" },
        ]}
      />

      {mapa && mapa.situacao === "inativo" && (
        <div className="rounded-md border border-warning/40 bg-warning/10 p-3 text-sm">
          Ponto <strong>inativo</strong>: não recebe novas ocupações. Quem já está
          na vaga permanece até ser liberado.
        </div>
      )}

      {mapaQ.isLoading ? (
        <div className="py-8 text-center text-muted-foreground">Carregando...</div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {/* O mapa desenha SEMPRE as vagas_total vagas, livres inclusive. */}
          {(mapa?.vagas ?? []).map((v) => (
            <div
              key={v.numero_vaga}
              className={`rounded-lg border p-3 ${
                v.ocupacao ? "border-border bg-surface-1" : "border-dashed border-border"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  Vaga {v.numero_vaga}
                </span>
                <Badge intent={v.ocupacao ? "success" : "neutral"}>
                  {v.ocupacao ? "Ocupada" : "Livre"}
                </Badge>
              </div>
              {v.ocupacao ? (
                <>
                  <div className="mt-2 truncate font-medium" title={v.ocupacao.nome_permissionario ?? ""}>
                    {v.ocupacao.nome_permissionario}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    desde {formataData(v.ocupacao.desde)}
                  </div>
                  {canGerir && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="mt-2 w-full"
                      onClick={() => pedirLiberacao(v)}
                      disabled={liberarM.isPending}
                    >
                      Liberar
                    </Button>
                  )}
                </>
              ) : (
                <>
                  <div className="mt-2 text-sm text-muted-foreground">Sem ocupante</div>
                  {canGerir && mapa?.situacao === "ativo" && (
                    <Button
                      variant="secondary"
                      size="sm"
                      className="mt-2 w-full"
                      onClick={() => {
                        setVagaAlvo(v.numero_vaga);
                        setErro(null);
                      }}
                    >
                      <UserPlus className="mr-1 h-4 w-4" />
                      Ocupar
                    </Button>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}

      <div>
        <h2 className="mb-2 mt-6 font-semibold">Histórico de ocupação</h2>
        {historico.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma ocupação registrada neste ponto.
          </p>
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Vaga</TH>
                <TH>Permissionário</TH>
                <TH>Desde</TH>
                <TH>Até</TH>
                <TH>Motivo</TH>
              </TR>
            </THead>
            <TBody>
              {historico.map((o) => (
                <TR key={o.id}>
                  <TD>{o.numero_vaga}</TD>
                  <TD className="font-medium">{o.nome_permissionario}</TD>
                  <TD className="text-sm">{formataData(o.desde)}</TD>
                  <TD className="text-sm">
                    {o.ate ? formataData(o.ate) : <Badge intent="success">vigente</Badge>}
                  </TD>
                  <TD className="text-sm text-muted-foreground">
                    {o.motivo_liberacao ? MOTIVO_LABEL[o.motivo_liberacao] ?? o.motivo_liberacao : "—"}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </div>

      <Dialog
        open={vagaAlvo !== null}
        onClose={() => setVagaAlvo(null)}
        title={`Ocupar a vaga ${vagaAlvo ?? ""}`}
      >
        <div className="space-y-3">
          {erro && (
            <div className="rounded-md border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
              {erro}
            </div>
          )}
          <div>
            <Label htmlFor="buscaPerm">Permissionário</Label>
            <Input
              id="buscaPerm"
              placeholder="Buscar por nome..."
              value={buscaPerm}
              onChange={(e) => setBuscaPerm(e.target.value)}
            />
          </div>
          <Select
            value={permEscolhido ?? ""}
            onChange={(e) =>
              setPermEscolhido(e.target.value ? Number(e.target.value) : null)
            }
          >
            <option value="">Selecione...</option>
            {perms.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nome} — {p.cpf}
              </option>
            ))}
          </Select>
          <p className="text-xs text-muted-foreground">
            Um permissionário ocupa no máximo uma vaga. Se já estiver lotado em
            outro ponto, o sistema informa onde.
          </p>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setVagaAlvo(null)}>
              Cancelar
            </Button>
            <Button
              onClick={() => {
                setErro(null);
                ocuparM.mutate();
              }}
              disabled={permEscolhido === null || ocuparM.isPending}
            >
              {ocuparM.isPending ? "Ocupando..." : "Ocupar"}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
