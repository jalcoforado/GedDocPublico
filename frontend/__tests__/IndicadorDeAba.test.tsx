/**
 * O sublinhado deslizante das abas: existe sob a aba ativa e acompanha a
 * troca. Ele chegou a não aparecer nunca na carga da página sem que nada
 * acusasse — por isso o teste olha o elemento, não só a ausência de erro.
 */
import { act, render } from "@testing-library/react";
import { useRef, useState } from "react";
import { describe, expect, it } from "vitest";

import { IndicadorDeAba } from "@/components/ui/indicador-aba";

function Abas({ inicial }: { inicial: number }) {
  const lista = useRef<HTMLUListElement>(null);
  const [ativa, setAtiva] = useState(inicial);
  return (
    <ul ref={lista} className="relative">
      {[0, 1, 2].map((i) => (
        <li key={i}>
          <a href="#x" aria-current={ativa === i ? "page" : undefined} onClick={() => setAtiva(i)}>
            aba {i}
          </a>
        </li>
      ))}
      <li className="contents">
        <IndicadorDeAba lista={lista} seletor='[aria-current="page"]' chave={ativa} />
      </li>
    </ul>
  );
}

describe("sublinhado da aba ativa", () => {
  it("aparece já na montagem e continua depois da troca", () => {
    const { container, getByText } = render(<Abas inicial={0} />);
    expect(container.querySelector("[data-indicador-aba]")).not.toBeNull();
    act(() => getByText("aba 2").click());
    expect(container.querySelector("[data-indicador-aba]")).not.toBeNull();
  });
});
