"use client";

import { Combobox } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { type ModoUnidadeRelatorio } from "@/lib/api";
import { ROTULO_MODO_UNIDADE, type FiltroDaUrl } from "@/lib/relatorios";

import { useOpcoesDoRecorte } from "./opcoesDoRecorte";

/**
 * Os campos do recorte comum dos relatórios — período, tipo, assunto,
 * serviço, unidade e o sentido da unidade —, na mesma ordem e com os mesmos
 * rótulos em TODO lugar que filtra relatório: a barra das listas
 * (`FiltrosDoRelatorio`) e o montador (SI-35). Dois formulários parecidos
 * divergiriam no rótulo, na ordem ou nas opções; aqui há um.
 *
 * Só desenha e avisa a mudança; quem usa decide quando aplicar.
 */
export function CamposDoRecorte({
  valor,
  onChange,
  prefixo = "rel",
  periodo,
  periodoInvertido = false,
}: {
  valor: FiltroDaUrl;
  onChange: (v: FiltroDaUrl) => void;
  /** Prefixo dos `id` dos campos, para duas instâncias não colidirem. */
  prefixo?: string;
  /** Substitui os campos De/Até — o montador tem período relativo. */
  periodo?: React.ReactNode;
  periodoInvertido?: boolean;
}) {
  const op = useOpcoesDoRecorte(valor.id_tipo_processo);
  const num = (v: number | string | null) => (typeof v === "number" ? v : undefined);

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
      {periodo ?? (
        <>
          <div>
            <Label htmlFor={`${prefixo}-desde`}>De</Label>
            <Input
              id={`${prefixo}-desde`}
              type="date"
              value={valor.desde ?? ""}
              onChange={(e) => onChange({ ...valor, desde: e.target.value || undefined })}
            />
          </div>
          <div>
            <Label htmlFor={`${prefixo}-ate`}>Até</Label>
            <Input
              id={`${prefixo}-ate`}
              type="date"
              value={valor.ate ?? ""}
              onChange={(e) => onChange({ ...valor, ate: e.target.value || undefined })}
              aria-invalid={periodoInvertido || undefined}
              aria-describedby={periodoInvertido ? `${prefixo}-periodo-erro` : undefined}
            />
          </div>
        </>
      )}
      <div>
        <Label htmlFor={`${prefixo}-tipo`}>Tipo de processo</Label>
        <Combobox
          id={`${prefixo}-tipo`}
          options={op.tipos}
          value={valor.id_tipo_processo ?? null}
          onChange={(v) => {
            const id_tipo_processo = num(v);
            // Assunto de outro tipo não combina com o tipo novo.
            onChange({
              ...valor,
              id_tipo_processo,
              id_assunto: op.assuntoCombina(valor.id_assunto, id_tipo_processo) ? valor.id_assunto : undefined,
            });
          }}
          placeholder="Todos"
          loading={op.carregando.tipos}
        />
      </div>
      <div>
        <Label htmlFor={`${prefixo}-assunto`}>Assunto</Label>
        <Combobox
          id={`${prefixo}-assunto`}
          options={op.assuntos}
          value={valor.id_assunto ?? null}
          onChange={(v) => onChange({ ...valor, id_assunto: num(v) })}
          placeholder="Todos"
          loading={op.carregando.assuntos}
        />
      </div>
      <div className="md:col-span-2">
        <Label htmlFor={`${prefixo}-servico`}>Serviço</Label>
        <Combobox
          id={`${prefixo}-servico`}
          options={op.servicos}
          value={valor.id_servico ?? null}
          onChange={(v) => onChange({ ...valor, id_servico: num(v) })}
          placeholder="Todos"
          searchPlaceholder="Nome do serviço…"
          loading={op.carregando.servicos}
        />
      </div>
      <div className="md:col-span-2">
        <Label htmlFor={`${prefixo}-unidade`}>Unidade</Label>
        <Combobox
          id={`${prefixo}-unidade`}
          options={op.unidades}
          value={valor.id_unidade ?? null}
          onChange={(v) => onChange({ ...valor, id_unidade: num(v) })}
          placeholder="Todas as unidades"
          searchPlaceholder="Nome ou sigla da unidade…"
          loading={op.carregando.unidades}
        />
      </div>
      {valor.id_unidade ? (
        <div className="md:col-span-2">
          <Label htmlFor={`${prefixo}-modo`}>Contar processos da unidade que é</Label>
          <Select
            id={`${prefixo}-modo`}
            value={valor.modo_unidade ?? "envolvida"}
            onChange={(e) => onChange({ ...valor, modo_unidade: e.target.value as ModoUnidadeRelatorio })}
          >
            {(Object.keys(ROTULO_MODO_UNIDADE) as ModoUnidadeRelatorio[]).map((m) => (
              <option key={m} value={m}>
                {ROTULO_MODO_UNIDADE[m]}
              </option>
            ))}
          </Select>
        </div>
      ) : null}
    </div>
  );
}
