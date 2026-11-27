import type { AnexoNoProcesso } from "@/lib/api";

/**
 * SI-72 — a lista principal mostra a versão vigente de cada documento. A
 * substituída continua no processo (mesmo número, mesmas folhas: folha não se
 * renumera) e aparece recolhida sob a vigente. Se a sucessora não está na
 * lista (foi desentranhada), a substituída volta para a lista principal, para
 * não sumir da tela.
 */
export function separarVersoes(anexos: AnexoNoProcesso[]) {
  const porId = new Map(anexos.map((a) => [a.id, a]));
  const principais = anexos.filter(
    (a) => a.id_anexo_substituto == null || !porId.has(a.id_anexo_substituto),
  );
  function anterioresDe(a: AnexoNoProcesso): AnexoNoProcesso[] {
    const out: AnexoNoProcesso[] = [];
    const vistos = new Set<number>([a.id]);
    let cur = a.id_anexo_anterior ?? null;
    while (cur != null && !vistos.has(cur)) {
      const anterior = porId.get(cur);
      if (!anterior) break;
      out.push(anterior);
      vistos.add(cur);
      cur = anterior.id_anexo_anterior ?? null;
    }
    return out;
  }
  return { principais, anterioresDe, porId };
}
