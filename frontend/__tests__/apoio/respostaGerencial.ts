import type { GerencialResposta } from "@/lib/api";

/**
 * Uma resposta de `GET /relatorios/gerencial.json` para os testes do Panorama
 * do protocolo (Painel de controle) e de quem mais o renderiza. Os números
 * são distintos de propósito, para o teste saber qual cartão mostrou qual.
 */
export function respostaGerencial(): GerencialResposta {
  return {
    descricao_filtros: ["Período: 01/10/2026 a 31/10/2026 — cada seção diz por qual data conta"],
    entrada: {
      abertos: 142,
      por_canal: [
        { canal: "balcao", rotulo: "Balcão", count: 100 },
        { canal: null, rotulo: "Não informado", count: 42 },
      ],
    },
    andamento: { em_andamento: 88, em_transito: 9, parados: 12, dias_parado: 15 },
    saida: { arquivados: 41, dias_medio_ate_arquivar: 18.25 },
    prazos: {
      concluidos_no_prazo: 32, concluidos_atrasados: 9, concluidos_sem_prazo: 0,
      dentro_do_prazo: 51, vencendo: 8, atrasados: 6, em_aberto_sem_prazo: 23,
    },
    tendencia: {
      granularidade: "semana", desde: "2026-10-01", ate: "2026-10-31",
      pontos: [
        { inicio: "2026-09-28", abertos: 30, arquivados: 10 },
        { inicio: "2026-10-05", abertos: 40, arquivados: 12 },
      ],
    },
    gargalos: {
      unidades: [
        { id_unidade: 3, unidade: "Secretaria de Obras", chegadas: 20, com_prazo: 10, atrasos: 7, dias_medio: 4.5 },
        { id_unidade: 4, unidade: "Protocolo Geral", chegadas: 50, com_prazo: 30, atrasos: 0, dias_medio: 1.5 },
      ],
      cortado: false,
    },
    assinaturas: { total: 30, pendentes: 16, concluidas: 12, canceladas: 2, minutos_medio_conclusao: 2880 },
    documentacao: {
      pendentes: 5, parciais: 3, completos: 12, sem_documentos_exigidos: 122,
      complementacao_pedida: 7, aguardando_cidadao: 4, complementacao_respondida: 2, dias_medio_resposta: 3.5,
    },
  };
}
