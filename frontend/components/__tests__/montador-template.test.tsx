import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { MontadorTemplate } from "@/components/protocolo/MontadorTemplate";
import { blocosParaHtml, type Bloco } from "@/lib/template-blocos";

const CAMPOS = [
  { chave: "processo.numero", descricao: "Número do processo" },
  { chave: "requerente.nome", descricao: "Nome do requerente/manifestante" },
];

let ultimo: Bloco[] = [];

function Montador({ inicial = [] as Bloco[] }) {
  const [blocos, setBlocos] = React.useState<Bloco[]>(inicial);
  ultimo = blocos;
  return <MontadorTemplate blocos={blocos} onChange={setBlocos} campos={CAMPOS} />;
}

/** DataTransfer de mentira: o jsdom não tem um. */
function dt(dados: Record<string, string>) {
  return {
    types: Object.keys(dados),
    getData: (t: string) => dados[t] ?? "",
    setData: () => {},
    dropEffect: "none",
    effectAllowed: "all",
  };
}

const folha = () => screen.getByRole("list", { name: "Blocos do modelo" });
const tipos = () => ultimo.map((b) => b.tipo);

describe("MontadorTemplate", () => {
  it("folha vazia convida a arrastar e oferece o esqueleto de um ofício", async () => {
    const u = userEvent.setup();
    render(<Montador />);
    expect(within(folha()).getByText("Arraste um bloco para cá")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Começar com o esqueleto de um ofício" }));
    expect(tipos()).toEqual(["titulo", "texto", "data_local", "assinatura"]);
  });

  it("clicar num bloco da paleta põe no fim e anuncia", async () => {
    const u = userEvent.setup();
    render(<Montador />);
    await u.click(screen.getByRole("button", { name: "Adicionar bloco Título" }));
    await u.click(screen.getByRole("button", { name: "Adicionar bloco Assinatura" }));
    expect(tipos()).toEqual(["titulo", "assinatura"]);
    expect(screen.getByText("Assinatura adicionado na posição 2 de 2.")).toBeInTheDocument();
    expect(within(folha()).getAllByRole("listitem")).toHaveLength(2);
  });

  it("arrastar da paleta e soltar na folha insere o bloco", () => {
    render(<Montador />);
    const transfer = dt({ "application/x-aprimora-bloco-novo": "data_local" });
    fireEvent.dragOver(folha(), { dataTransfer: transfer, clientY: 10 });
    expect(within(folha()).getByText("Solte para começar o modelo")).toBeInTheDocument();
    fireEvent.drop(folha(), { dataTransfer: transfer, clientY: 10 });
    expect(tipos()).toEqual(["data_local"]);
  });

  it("arrasto que não é de bloco (arquivo, texto) é ignorado", () => {
    render(<Montador />);
    fireEvent.drop(folha(), { dataTransfer: dt({ Files: "" }) });
    expect(tipos()).toEqual([]);
  });

  it("arrastar um bloco da folha para o fim muda a ordem", () => {
    const inicial: Bloco[] = [
      { id: "t", tipo: "titulo", texto: "A", alinhamento: "center" },
      { id: "s", tipo: "separador" },
      { id: "d", tipo: "data_local", local: "" },
    ];
    render(<Montador inicial={inicial} />);
    // jsdom não mede: o ponto de soltar cai depois do último bloco.
    fireEvent.drop(folha(), { dataTransfer: dt({ "application/x-aprimora-bloco-mover": "t" }), clientY: 999 });
    expect(tipos()).toEqual(["separador", "data_local", "titulo"]);
  });

  it("Subir/Descer/Duplicar/Remover pelo teclado, com o primeiro e o último travados", async () => {
    const u = userEvent.setup();
    render(
      <Montador
        inicial={[
          { id: "t", tipo: "titulo", texto: "A", alinhamento: "center" },
          { id: "s", tipo: "separador" },
        ]}
      />,
    );
    expect(screen.getByRole("button", { name: "Subir Título" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Descer Separador" })).toBeDisabled();
    await u.click(screen.getByRole("button", { name: "Descer Título" }));
    expect(tipos()).toEqual(["separador", "titulo"]);
    expect(screen.getByText("Título movido para a posição 2 de 2.")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Duplicar Separador" }));
    expect(tipos()).toEqual(["separador", "separador", "titulo"]);
    await u.click(screen.getAllByRole("button", { name: "Remover Separador" })[0]);
    expect(tipos()).toEqual(["separador", "titulo"]);
  });

  it("editar os campos do bloco muda o HTML do modelo", async () => {
    const u = userEvent.setup();
    render(<Montador />);
    await u.click(screen.getByRole("button", { name: "Adicionar bloco Campo automático" }));
    await u.type(screen.getByLabelText(/^Rótulo/), "Requerente");
    await u.selectOptions(screen.getByLabelText("Dado do processo"), "requerente.nome");
    expect(blocosParaHtml(ultimo)).toBe(
      '<div class="bloco bloco-campo"><p><strong>Requerente:</strong> {{requerente.nome}}</p></div>',
    );
  });

  it("título: alinhamento à esquerda", async () => {
    const u = userEvent.setup();
    render(<Montador inicial={[{ id: "t", tipo: "titulo", texto: "Ofício", alinhamento: "center" }]} />);
    await u.click(screen.getByRole("button", { name: "À esquerda" }));
    expect(screen.getByRole("button", { name: "À esquerda" })).toHaveAttribute("aria-pressed", "true");
    expect(blocosParaHtml(ultimo)).toContain("<h2>Ofício</h2>");
  });
});
