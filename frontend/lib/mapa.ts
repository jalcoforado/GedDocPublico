import type { LatLng } from "@/components/Mapa";

/**
 * Sede de Itaitinga — CE. É só o enquadramento inicial dos mapas, usado
 * enquanto não há nada para desenhar; havendo dados, o mapa enquadra os dados.
 *
 * Constante, e não dado do tenant, porque `aprimora_py.tenant` ainda não guarda
 * coordenada do município. Um segundo município com mapa pede essa coluna.
 */
export const CENTRO_MUNICIPIO: LatLng = [-3.9694, -38.528];
