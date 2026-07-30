"""Toda transação que os routers exigem existe e está ligada ao sistema do app."""
import re
from pathlib import Path

import pytest
from sqlalchemy import text

from app.config import get_settings

ROUTERS = Path(__file__).resolve().parents[1] / "app" / "routers"


def codigos_exigidos_pelos_routers() -> set[str]:
    """Extrai os códigos usados em require_permission/require_any_permission.

    `require_permission("codigo", "action")` tem a ação como segundo argumento
    — só o primeiro literal é código. `require_any_permission(*codigos)` só tem
    códigos. As tuplas de constante no topo dos módulos de pagamentos são
    passadas por *splat e por isso não aparecem na chamada.
    """
    codigos: set[str] = set()
    um_so = re.compile(r'require_permission\(\s*"([a-zA-Z_]+)"')
    varios = re.compile(r'require_any_permission\(\s*((?:"[a-zA-Z_]+"\s*,?\s*)+)')
    constante = re.compile(
        r'^(?:_LEITURA|PERMS_LEITURA|PERM_VALIDAR|PERM_ENCAMINHAR)\s*=\s*\(([^)]*)\)',
        re.MULTILINE,
    )
    for arquivo in ROUTERS.glob("*.py"):
        texto = arquivo.read_text(encoding="utf-8")
        codigos.update(um_so.findall(texto))
        for bloco in varios.findall(texto):
            codigos.update(re.findall(r'"([a-zA-Z_]+)"', bloco))
        for bloco in constante.findall(texto):
            codigos.update(re.findall(r'"([a-zA-Z_]+)"', bloco))
    return codigos


@pytest.mark.asyncio
async def test_toda_transacao_exigida_existe(admin_session):
    exigidos = codigos_exigidos_pelos_routers()
    assert exigidos, "a extração não achou nenhum código — o regex quebrou"
    assert not exigidos & {"inserir", "atualizar", "excluir", "visualizar"}, (
        "o regex voltou a capturar a `action` de require_permission(codigo, action) "
        "como se fosse código — regressão na extração"
    )

    existentes = set((await admin_session.execute(text(
        "SELECT codigo FROM utils.transacao WHERE excluido = false"
    ))).scalars().all())

    faltando = sorted(exigidos - existentes)
    assert not faltando, (
        f"Códigos exigidos por require_permission sem linha em utils.transacao: {faltando}. "
        "Usuário não-SU leva 403 nesses endpoints por ausência de cadastro, não de permissão."
    )


@pytest.mark.asyncio
async def test_toda_transacao_exigida_esta_no_sistema(admin_session):
    """Sem o vínculo, o ramo SU de load_permissions devolve lista vazia."""
    exigidos = codigos_exigidos_pelos_routers()
    app = get_settings().app_name
    ligados = set((await admin_session.execute(text("""
        SELECT t.codigo
          FROM utils.transacao t
          JOIN utils.sistema_transacao st ON st.id_transacao = t.id AND st.excluido = false
          JOIN utils.sistema s ON s.id = st.id_sistema AND s.app = :app
         WHERE t.excluido = false
    """), {"app": app})).scalars().all())

    faltando = sorted(exigidos - ligados)
    assert not faltando, (
        f"Transações sem vínculo em sistema_transacao: {faltando}. "
        "Rode `python -m app.cli.seed_bootstrap`."
    )
