"use client";

import { useQuery } from "@tanstack/react-query";
import { MapPinned } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Mapa, MAPA_TONS, type MapaMarcador, type MapaTom } from "@/components/Mapa";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { api, type Ponto } from "@/lib/api";
import { CENTRO_MUNICIPIO } from "@/lib/mapa";

// Teto de `page_size` do backend. Município com mais pontos do que isto vê o
// aviso de truncamento abaixo, em vez de um mapa silenciosamente incompleto.
const PAGINA = 100;

const TIPOS: Record<string, { label: string; tom: MapaTom }> = {
  taxi: { label: "Táxi", tom: "warning" },
  mototaxi: { label: "Mototáxi", tom: "brand" },
  motofrete: { label: "Motofrete", tom: "accent" },
  transporte_escolar: { label: "Transporte escolar", tom: "success" },
  transporte_distrital: { label: "Transporte distrital", tom: "info" },
  aplicativo: { label: "Aplicativo", tom: "danger" },
  outro: { label: "Outro", tom: "brand-dark" },
};

function tipo(p: Ponto) {
  return TIPOS[p.tipo_servico] ?? TIPOS.outro;
}

function endereco(p: Ponto): string {
  return [p.logradouro, p.numero, p.bairro].filter(Boolean).join(", ");
}

export default function MapaPontosPage() {
  const [selecionado, setSelecionado] = useState<number | null>(null);

  const pontosQ = useQuery({
    queryKey: ["tr-pontos-mapa"],
    queryFn: () => api.pontos.list({ situacao: "ativo", page_size: PAGINA }),
  });

  // Quem ocupa cada vaga do ponto selecionado — os permissionários do ponto.
  const vagasQ = useQuery({
    queryKey: ["tr-ponto-mapa-vagas", selecionado],
    queryFn: () => api.pontos.mapa(selecionado as number),
    enabled: selecionado !== null,
  });

  const todos = pontosQ.data?.items ?? [];
  const noMapa = useMemo(
    () => todos.filter((p) => p.latitude !== null && p.longitude !== null),
    [todos],
  );
  const semCoordenada = todos.length - noMapa.length;
  const truncado = (pontosQ.data?.total ?? 0) > todos.length;

  const marcadores = useMemo(
    () =>
      noMapa
        .filter((p) => selecionado === null || p.id === selecionado)
        .map(
          (p): MapaMarcador => ({
            posicao: [Number(p.latitude), Number(p.longitude)],
            tom: tipo(p).tom,
            titulo: p.nome,
            linhas: [
              tipo(p).label,
              ...(endereco(p) ? [endereco(p)] : []),
              `Vagas ocupadas: ${p.vagas_ocupadas} de ${p.vagas_total}`,
            ],
          }),
        ),
    [noMapa, selecionado],
  );

  return (
    <div className="space-y-4">
      <PageHeader
        icon={MapPinned}
        title="Mapa dos pontos"
        description="Pontos de táxi, mototáxi e demais serviços regulados no mapa do município, com a ocupação das vagas."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Mapa dos pontos" },
        ]}
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Mapa
          centro={CENTRO_MUNICIPIO}
          marcadores={marcadores}
          ariaLabel="Mapa com os pontos regulados do município"
        />

        <SectionCard
          icon={MapPinned}
          title="Pontos"
          description="Selecione um ponto para ver os permissionários das vagas."
        >
          {pontosQ.isLoading ? (
            <p className="text-sm text-foreground-muted">Carregando pontos…</p>
          ) : pontosQ.isError ? (
            <p className="text-sm text-danger-soft-foreground">
              Não foi possível carregar os pontos.
            </p>
          ) : noMapa.length === 0 ? (
            <p className="text-sm text-foreground-muted">
              Nenhum ponto ativo tem latitude e longitude. Informe as
              coordenadas em{" "}
              <Link href="/m/transporte/pontos" className="underline">
                Pontos e Vagas
              </Link>
              .
            </p>
          ) : (
            <ul className="space-y-1">
              {noMapa.map((p) => {
                const ativo = selecionado === p.id;
                return (
                  <li key={p.id}>
                    <button
                      type="button"
                      aria-pressed={ativo}
                      onClick={() => setSelecionado(ativo ? null : p.id)}
                      className={`flex w-full items-start gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors duration-fast hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${ativo ? "bg-muted" : ""}`}
                    >
                      <span
                        aria-hidden="true"
                        className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${MAPA_TONS[tipo(p).tom].chip}`}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-foreground">
                          {p.nome}
                        </span>
                        <span className="block text-xs text-foreground-muted">
                          {tipo(p).label} · {p.vagas_ocupadas}/{p.vagas_total} vagas
                        </span>
                      </span>
                    </button>
                    {ativo ? (
                      <div className="ml-7 mt-1 space-y-1 border-l border-border pl-3 text-xs">
                        {vagasQ.isLoading ? (
                          <p className="text-foreground-muted">Carregando vagas…</p>
                        ) : vagasQ.isError ? (
                          <p className="text-danger-soft-foreground">
                            Não foi possível carregar as vagas.
                          </p>
                        ) : (
                          (vagasQ.data?.vagas ?? []).map((v) => (
                            <p key={v.numero_vaga} className="text-foreground-muted">
                              <span className="font-medium text-foreground">
                                Vaga {v.numero_vaga}:
                              </span>{" "}
                              {v.ocupacao?.nome_permissionario ?? "livre"}
                            </p>
                          ))
                        )}
                        <Link
                          href={`/m/transporte/pontos/${p.id}`}
                          className="inline-block pt-1 underline"
                        >
                          Abrir o ponto
                        </Link>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
          {semCoordenada > 0 && noMapa.length > 0 ? (
            <p className="mt-3 text-xs text-foreground-muted">
              {semCoordenada} ponto(s) ativo(s) sem coordenadas não aparecem no mapa.
            </p>
          ) : null}
          {truncado ? (
            <p className="mt-3 text-xs text-warning-soft-foreground">
              Exibindo os primeiros {todos.length} de {pontosQ.data?.total} pontos.
            </p>
          ) : null}
        </SectionCard>
      </div>
    </div>
  );
}
