"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { GerencialResposta } from "@/lib/api";
import { fmtData } from "@/lib/relatorios";

/**
 * Abertos × arquivados por semana (ou mês) — a tendência do estoque (SI-34).
 * Barras de abertos acima das de arquivados, semana após semana, é estoque
 * crescendo: o sinal que um número solto do período não mostra.
 *
 * Cores dos tokens (marca e informação), legíveis no modo escuro e
 * distinguíveis por quem não enxerga vermelho/verde. Os mesmos números vão
 * numa tabela só para leitor de tela: gráfico não é acessível sozinho.
 */
export function GraficoEntradaSaida({ tendencia }: { tendencia: GerencialResposta["tendencia"] }) {
  const porMes = tendencia.granularidade === "mes";
  const rotulo = (inicio: string) =>
    porMes ? fmtData(inicio).slice(3) : `sem. ${fmtData(inicio).slice(0, 5)}`;
  const dados = tendencia.pontos.map((p) => ({ ...p, rotulo: rotulo(p.inicio) }));

  return (
    <div>
      <div className="h-64" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={dados} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis dataKey="rotulo" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="abertos" name="Abertos" fill="hsl(var(--brand))" radius={[3, 3, 0, 0]} />
            <Bar dataKey="arquivados" name="Arquivados" fill="hsl(var(--info))" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only">
        <caption>
          Processos abertos e arquivados por {porMes ? "mês" : "semana"}, de {fmtData(tendencia.desde)} a{" "}
          {fmtData(tendencia.ate)}
        </caption>
        <thead>
          <tr>
            <th scope="col">{porMes ? "Mês" : "Semana iniciada em"}</th>
            <th scope="col">Abertos</th>
            <th scope="col">Arquivados</th>
          </tr>
        </thead>
        <tbody>
          {tendencia.pontos.map((p) => (
            <tr key={p.inicio}>
              <th scope="row">{fmtData(p.inicio)}</th>
              <td>{p.abertos}</td>
              <td>{p.arquivados}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
