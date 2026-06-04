import { render, screen } from "@testing-library/react";
import { Users } from "lucide-react";
import { describe, expect, it } from "vitest";

import { SectionCard } from "@/components/ui/section-card";

describe("SectionCard", () => {
  it("renderiza apenas título + children quando nada mais é passado", () => {
    render(
      <SectionCard title="Geral">
        <div data-testid="body">conteúdo</div>
      </SectionCard>,
    );
    expect(
      screen.getByRole("heading", { level: 2, name: "Geral" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("body")).toBeInTheDocument();
  });

  it("renderiza description quando informada", () => {
    render(
      <SectionCard title="Geral" description="Um subtítulo curto">
        <div>conteúdo</div>
      </SectionCard>,
    );
    expect(screen.getByText("Um subtítulo curto")).toBeInTheDocument();
  });

  it("não renderiza description quando ausente", () => {
    render(
      <SectionCard title="Geral">
        <div>conteúdo</div>
      </SectionCard>,
    );
    expect(screen.queryByText(/subtítulo/i)).not.toBeInTheDocument();
  });

  it("renderiza ícone (aria-hidden) quando passado", () => {
    const { container } = render(
      <SectionCard title="Geral" icon={Users}>
        <div>conteúdo</div>
      </SectionCard>,
    );
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("exibe 'passo N' quando step é informado", () => {
    render(
      <SectionCard title="Geral" step={3}>
        <div>conteúdo</div>
      </SectionCard>,
    );
    expect(screen.getByText(/passo 3/i)).toBeInTheDocument();
  });

  it("não exibe 'passo' quando step é omitido", () => {
    render(
      <SectionCard title="Geral">
        <div>conteúdo</div>
      </SectionCard>,
    );
    expect(screen.queryByText(/^passo/i)).not.toBeInTheDocument();
  });

  it("aceita className extra no wrapper", () => {
    const { container } = render(
      <SectionCard title="Geral" className="ring-2 ring-amber-500">
        <div>conteúdo</div>
      </SectionCard>,
    );
    expect(container.querySelector("section")?.className).toContain(
      "ring-amber-500",
    );
  });
});
