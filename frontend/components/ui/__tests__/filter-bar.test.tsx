import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FilterBar } from "@/components/ui/filter-bar";

describe("FilterBar", () => {
  it("renderiza wrapper com role=region e aria-label padrão", () => {
    render(
      <FilterBar>
        <div>x</div>
      </FilterBar>,
    );
    const region = screen.getByRole("region", { name: /filtros/i });
    expect(region).toBeInTheDocument();
  });

  it("aceita aria-label customizado", () => {
    render(
      <FilterBar ariaLabel="Filtros do dashboard">
        <div>x</div>
      </FilterBar>,
    );
    expect(
      screen.getByRole("region", { name: /filtros do dashboard/i }),
    ).toBeInTheDocument();
  });

  it("FilterBar.Group renderiza label quando informado", () => {
    render(
      <FilterBar>
        <FilterBar.Group label="Unidade">
          <input data-testid="picker" />
        </FilterBar.Group>
      </FilterBar>,
    );
    expect(screen.getByText("Unidade")).toBeInTheDocument();
    expect(screen.getByTestId("picker")).toBeInTheDocument();
  });

  it("FilterBar.Group renderiza só children quando label é omitido", () => {
    render(
      <FilterBar>
        <FilterBar.Group>
          <input data-testid="picker" />
        </FilterBar.Group>
      </FilterBar>,
    );
    expect(screen.getByTestId("picker")).toBeInTheDocument();
    expect(screen.queryByText(/^Unidade$/)).not.toBeInTheDocument();
  });

  it("FilterBar.Actions tem classe ml-auto (alinhamento à direita)", () => {
    const { container } = render(
      <FilterBar>
        <FilterBar.Group label="X">
          <input />
        </FilterBar.Group>
        <FilterBar.Actions>
          <button>Exportar</button>
        </FilterBar.Actions>
      </FilterBar>,
    );
    const actions = container.querySelector(".ml-auto");
    expect(actions).toBeInTheDocument();
    expect(actions?.textContent).toContain("Exportar");
  });

  it("aceita className extra no wrapper", () => {
    const { container } = render(
      <FilterBar className="ring-2 ring-amber-500">
        <FilterBar.Group label="X"><input /></FilterBar.Group>
      </FilterBar>,
    );
    expect(container.firstChild).toHaveClass("ring-amber-500");
  });
});
