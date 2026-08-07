"""Guardas transversais do rito de pagamento: segregação e concorrência.

Vivem fora de `pagamentos_debitos.py` porque valem para toda transição e porque
são a parte do fluxo que dá para exercitar sem banco.

**Segregação de funções não é permissão.** Permissão responde "este perfil pode
fazer isto?"; segregação responde "esta PESSOA já fez algo que a impede de fazer
isto neste débito?". Por isso a checagem mora no serviço, não no `Depends`, e
por isso o bypass de super-usuário do `auth/perms.py` não a alcança — decisão
deliberada, registrada na spec §6.2.
"""
from __future__ import annotations

from fastapi import HTTPException, status

from ..models import Debito


class SegregacaoError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ConflitoDeEdicaoError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


# Para cada ato, os papéis já exercidos que o impedem. Ordem = ordem do rito.
_IMPEDIMENTOS: dict[str, tuple[tuple[str, str], ...]] = {
    "GERIR":     (("id_usuario_solicitante", "solicitou"),),
    "VALIDAR":   (("id_usuario_solicitante", "solicitou"),
                  ("id_gestor_decisor", "decidiu como gestor da pasta")),
    "AUTORIZAR": (("id_usuario_solicitante", "solicitou"),
                  ("id_gestor_decisor", "decidiu como gestor da pasta"),
                  ("id_validador", "validou a conformidade")),
    "PAGAR":     (("id_usuario_solicitante", "solicitou"),
                  ("id_gestor_decisor", "decidiu como gestor da pasta"),
                  ("id_validador", "validou a conformidade")),
}

_NOME_DO_ATO = {
    "GERIR": "decidir como gestor", "VALIDAR": "validar",
    "AUTORIZAR": "autorizar", "PAGAR": "executar o pagamento",
}


def assert_segregacao(debito: Debito, *, usuario_id: int, ato: str) -> None:
    """Levanta 403 se o usuário já exerceu, neste débito, um papel incompatível."""
    for campo, feito in _IMPEDIMENTOS[ato]:
        if getattr(debito, campo, None) == usuario_id:
            raise SegregacaoError(
                f"Segregação de funções: você {feito} esta solicitação e por isso "
                f"não pode {_NOME_DO_ATO[ato]}. Outro servidor precisa fazê-lo.")


def assert_lock_version(debito: Debito, *, esperado: int) -> None:
    """Levanta 409 quando o débito mudou desde que o usuário carregou a tela."""
    atual = debito.lock_version or 0
    if atual != esperado:
        raise ConflitoDeEdicaoError(
            "Esta solicitação foi atualizada por outro usuário depois que você "
            "abriu a tela. Recarregue para ver o estado atual antes de decidir.")
