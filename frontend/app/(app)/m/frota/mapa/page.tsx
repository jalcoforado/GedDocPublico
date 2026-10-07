"use client";

import { useQuery } from "@tanstack/react-query";
import { MapPinned } from "lucide-react";
import { useMemo, useState } from "react";

import {
  Mapa,
  MAPA_TONS,
  MAPA_TONS_EM_ORDEM,
  type LatLng,
  type MapaMarcador,
  type MapaTom,
  type MapaTrajeto,
} from "@/components/Mapa";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { api, type Veiculo, type VeiculoPosicao } from "@/lib/api";
import { CENTRO_MUNICIPIO } from "@/lib/mapa";

const JANELA_HORAS = 24;


interface TrajetoVeiculo {
  veiculo: Veiculo;
  tom: MapaTom;
  posicoes: VeiculoPosicao[];
}

/** `data_hora` chega em UTC sem fuso (ver `lib/api.ts`). */
function fmtDataHora(iso: string): string {
  return new Date(`${iso}Z`).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function rotulo(v: Veiculo): string {
  return [v.placa, v.modelo].filter(Boolean).join(" — ");
}

export default function MapaFrotaPage() {
  const [selecionado, setSelecionado] = useState<number | null>(null);

  const trajetosQ = useQuery({
    queryKey: ["frota-mapa-trajetos", JANELA_HORAS],
    queryFn: async (): Promise<TrajetoVeiculo[]> => {
      const veiculos = await api.frota.listAll();
      const fim = new Date();
      const inicio = new Date(fim.getTime() - JANELA_HORAS * 3600 * 1000);
      const periodo = { inicio: inicio.toISOString(), fim: fim.toISOString() };
      return Promise.all(
        veiculos.map(async (veiculo, i) => ({
          veiculo,
          tom: MAPA_TONS_EM_ORDEM[i % MAPA_TONS_EM_ORDEM.length],
          posicoes: await api.telemetriaVeiculo.listPosicoes(veiculo.id, periodo),
        })),
      );
    },
    refetchInterval: 60_000,
  });

  const comPosicao = useMemo(
    () => (trajetosQ.data ?? []).filter((t) => t.posicoes.length > 0),
    [trajetosQ.data],
  );
  const semPosicao = (trajetosQ.data ?? []).length - comPosicao.length;

  const { trajetos, marcadores } = useMemo(() => {
    const trajetos: MapaTrajeto[] = [];
    const marcadores: MapaMarcador[] = [];
    for (const t of comPosicao) {
      if (selecionado !== null && t.veiculo.id !== selecionado) continue;
      const pontos = t.posicoes.map(
        (p): LatLng => [Number(p.latitude), Number(p.longitude)],
      );
      const ultima = t.posicoes[t.posicoes.length - 1];
      trajetos.push({ tom: t.tom, pontos });
      marcadores.push({
        posicao: pontos[pontos.length - 1],
        tom: t.tom,
        titulo: rotulo(t.veiculo),
        linhas: [
          `Última posição: ${fmtDataHora(ultima.data_hora)}`,
          ...(ultima.velocidade !== null
            ? [`Velocidade: ${Number(ultima.velocidade).toFixed(0)} km/h`]
            : []),
        ],
      });
    }
    return { trajetos, marcadores };
  }, [comPosicao, selecionado]);

  return (
    <div className="space-y-4">
      <PageHeader
        icon={MapPinned}
        title="Mapa da frota"
        description={`Última posição e trajeto de cada veículo nas últimas ${JANELA_HORAS} horas.`}
        breadcrumbs={[{ label: "Frota Pública", href: "/m/frota" }, { label: "Mapa da frota" }]}
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Mapa
          centro={CENTRO_MUNICIPIO}
          trajetos={trajetos}
          marcadores={marcadores}
          ariaLabel="Mapa com a posição dos veículos da frota"
        />

        <SectionCard
          icon={MapPinned}
          title="Veículos"
          description="Selecione um veículo para ver só o trajeto dele."
        >
          {trajetosQ.isLoading ? (
            <p className="text-sm text-foreground-muted">Carregando posições…</p>
          ) : trajetosQ.isError ? (
            <p className="text-sm text-danger-soft-foreground">
              Não foi possível carregar as posições dos veículos.
            </p>
          ) : comPosicao.length === 0 ? (
            <p className="text-sm text-foreground-muted">
              Nenhum veículo enviou posição nas últimas {JANELA_HORAS} horas.
            </p>
          ) : (
            <ul className="space-y-1">
              {comPosicao.map((t) => {
                const ativo = selecionado === t.veiculo.id;
                const ultima = t.posicoes[t.posicoes.length - 1];
                return (
                  <li key={t.veiculo.id}>
                    <button
                      type="button"
                      aria-pressed={ativo}
                      onClick={() => setSelecionado(ativo ? null : t.veiculo.id)}
                      className={`flex w-full items-start gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors duration-fast hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${ativo ? "bg-muted" : ""}`}
                    >
                      <span
                        aria-hidden="true"
                        className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${MAPA_TONS[t.tom].chip}`}
                      />
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-foreground">
                          {rotulo(t.veiculo)}
                        </span>
                        <span className="block text-xs text-foreground-muted">
                          {fmtDataHora(ultima.data_hora)}
                          {ultima.ignicao_ligada === null
                            ? ""
                            : ultima.ignicao_ligada
                              ? " · ligado"
                              : " · desligado"}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {semPosicao > 0 && comPosicao.length > 0 ? (
            <p className="mt-3 text-xs text-foreground-muted">
              {semPosicao} veículo(s) sem posição no período.
            </p>
          ) : null}
        </SectionCard>
      </div>
    </div>
  );
}
