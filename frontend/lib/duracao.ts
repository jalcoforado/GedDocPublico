/**
 * Formatação de duração em português, para os números de permanência (F1).
 *
 * Duas unidades, no máximo
 * -----------------------
 * "3 d 4 h" e não "3 d 4 h 27 min 13 s". O terceiro termo não muda nenhuma
 * decisão — quem olha a permanência quer saber se o processo está parado há
 * horas ou há semanas — e cada termo extra custa largura numa célula de tabela
 * que já disputa espaço.
 *
 * Por que arredondar para baixo
 * -----------------------------
 * `Math.floor` em todos os níveis. "2 h" para 2 h 59 min é impreciso, mas
 * arredondar para cima produziria "3 h" num processo que ainda não completou
 * três horas — e o número que aparece na tela é o que alguém vai citar numa
 * cobrança. Errar para menos é o lado seguro.
 *
 * Não usa `Intl.RelativeTimeFormat`: ele formata UMA unidade relativa ("há 3
 * horas"), e aqui a duração é absoluta e composta.
 */

const MINUTO = 60;
const HORA = 60 * MINUTO;
const DIA = 24 * HORA;

/**
 * Segundos → texto curto. Entrada negativa vira "—": o backend já faz clamp em
 * zero, então negativo aqui só chega se alguém passar um valor calculado no
 * front, e nesse caso mentir com "0 min" seria pior que admitir que não sei.
 */
export function formatarDuracao(segundos: number): string {
  if (!Number.isFinite(segundos) || segundos < 0) return "—";
  if (segundos < MINUTO) return "menos de 1 min";

  if (segundos < HORA) {
    return `${Math.floor(segundos / MINUTO)} min`;
  }

  if (segundos < DIA) {
    const horas = Math.floor(segundos / HORA);
    const minutos = Math.floor((segundos % HORA) / MINUTO);
    return minutos > 0 ? `${horas} h ${minutos} min` : `${horas} h`;
  }

  const dias = Math.floor(segundos / DIA);
  const horas = Math.floor((segundos % DIA) / HORA);
  return horas > 0 ? `${dias} d ${horas} h` : `${dias} d`;
}

/**
 * Tempo decorrido desde uma data ISO até agora, já formatado.
 *
 * É o item (c) da fatia: a data sozinha ("12/03/2026") obriga quem lê a fazer
 * a conta de cabeça para saber se é recente. O clamp em zero repete o do
 * backend porque o relógio do navegador é do usuário e pode estar adiantado.
 */
export function decorridoDesde(iso: string, agora: Date = new Date()): string {
  const inicio = new Date(iso).getTime();
  if (Number.isNaN(inicio)) return "—";
  return formatarDuracao(Math.max(0, (agora.getTime() - inicio) / 1000));
}
