import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GoogleConnectDialog } from "@/components/GoogleConnectDialog";

describe("GoogleConnectDialog", () => {
  it("renders connect button", () => {
    render(
      <GoogleConnectDialog
        open={true}
        onClose={vi.fn()}
        minutaId={123}
        processoId={456}
      />
    );
    expect(screen.getByText("Conectar Conta Google")).toBeInTheDocument();
  });

  it("renders cancel button", () => {
    render(
      <GoogleConnectDialog
        open={true}
        onClose={vi.fn()}
        minutaId={123}
        processoId={456}
      />
    );
    expect(screen.getByText("Cancelar")).toBeInTheDocument();
  });

  it("calls onClose when cancel clicked", () => {
    const onClose = vi.fn();
    render(
      <GoogleConnectDialog
        open={true}
        onClose={onClose}
        minutaId={123}
        processoId={456}
      />
    );
    fireEvent.click(screen.getByText("Cancelar"));
    expect(onClose).toHaveBeenCalled();
  });

  it("doesn't render when open=false", () => {
    const { container } = render(
      <GoogleConnectDialog
        open={false}
        onClose={vi.fn()}
        minutaId={123}
        processoId={456}
      />
    );
    expect(container.firstChild).toBeNull();
  });
});
