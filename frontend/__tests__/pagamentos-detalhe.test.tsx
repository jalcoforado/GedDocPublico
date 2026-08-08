/**
 * O detalhe responde, sem o usuário abrir outra tela: em que etapa está, quem é
 * o responsável e qual é a próxima ação (spec §10.5 do pedido).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EtapasFluxo } from "@/components/pagamentos/EtapasFluxo";
import { ProximaAcao } from "@/components/pagamentos/ProximaAcao";
import { SituacoesDebito } from "@/components/pagamentos/SituacoesDebito";

describe("EtapasFluxo", () => {
  it("marca a etapa atual e as concluídas", () => {
    render(<EtapasFluxo tramitacao="AGUARDANDO_AUTORIDADE" />);
    const atual = screen.getByTestId("etapa-AUTORIDADE");
    expect(atual).toHaveAttribute("data-estado", "atual");
    expect(screen.getByTestId("etapa-GESTOR")).toHaveAttribute(
      "data-estado",
      "concluida"
    );
    expect(screen.getByTestId("etapa-TESOURARIA")).toHaveAttribute(
      "data-estado",
      "futura"
    );
  });

  it("distingue etapa com ajuste pendente", () => {
    render(<EtapasFluxo tramitacao="AJUSTE_VALIDACAO" />);
    expect(screen.getByTestId("etapa-UNIDADE")).toHaveAttribute(
      "data-estado",
      "ajuste"
    );
  });

  it("distingue etapa encerrada por decisão", () => {
    render(<EtapasFluxo tramitacao="REJEITADA_GESTOR" />);
    expect(screen.getByTestId("etapa-GESTOR")).toHaveAttribute(
      "data-estado",
      "encerrada"
    );
  });

  it("cada etapa tem texto, não só cor", () => {
    render(<EtapasFluxo tramitacao="AGUARDANDO_GESTOR" />);
    for (const nome of [
      "Unidade setorial",
      "Gestor da pasta",
      "Validação financeira",
      "Autoridade competente",
      "Tesouraria",
    ]) {
      expect(screen.getByText(nome)).toBeInTheDocument();
    }
  });
});

describe("SituacoesDebito", () => {
  it("mostra as três dimensões em português", () => {
    render(
      <SituacoesDebito
        tramitacao="AUTORIZADA"
        fila="BLOQUEADA"
        pagamento="NAO_INICIADA"
      />
    );
    expect(screen.getByText("Autorizada para pagamento")).toBeInTheDocument();
    expect(screen.getByText("Bloqueada")).toBeInTheDocument();
    expect(screen.getByText("Não iniciado")).toBeInTheDocument();
  });
});

describe("ProximaAcao", () => {
  it("diz ao gestor, em uma frase, o que se espera dele", () => {
    render(
      <ProximaAcao
        tramitacao="AGUARDANDO_GESTOR"
        perfis={["pagamento_gerir"]}
      />
    );
    expect(screen.getByText(/aguarda sua análise/i)).toBeInTheDocument();
  });

  it("para quem não é o responsável, explica de quem se espera", () => {
    render(
      <ProximaAcao
        tramitacao="AGUARDANDO_GESTOR"
        perfis={["pagamento_solicitar"]}
      />
    );
    expect(screen.getByText(/gestor da pasta/i)).toBeInTheDocument();
  });

  it("não oferece rejeição na etapa de validação", () => {
    render(
      <ProximaAcao
        tramitacao="AGUARDANDO_VALIDACAO"
        perfis={["pagamento_validar"]}
      />
    );
    expect(
      screen.getByRole("button", { name: /validar conformidade/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /solicitar ajustes/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /rejeitar/i })
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: /não validar/i })
    ).toBeNull();
  });

  it("oferece as três decisões ao gestor", () => {
    render(
      <ProximaAcao
        tramitacao="AGUARDANDO_GESTOR"
        perfis={["pagamento_gerir"]}
      />
    );
    for (const nome of [
      /autorizar solicitação/i,
      /solicitar ajustes/i,
      /rejeitar solicitação/i,
    ]) {
      expect(screen.getByRole("button", { name: nome })).toBeInTheDocument();
    }
  });
});
