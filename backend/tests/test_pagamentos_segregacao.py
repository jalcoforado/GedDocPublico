"""Segregação de funções (spec §6.2).

A regra: a mesma pessoa não exerce dois atos decisórios sobre o mesmo débito.
Antes da F1 existia só solicitante ≠ validador.

O teste que mais importa é o do super-usuário. Segregação de funções NÃO é
permissão — é controle interno —, então o bypass de SU do `auth/perms.py` não
se aplica aqui. É exceção deliberada ao padrão do projeto, registrada na spec
§6.2 e na premissa nº 6.
"""
import pytest

from app.models import Debito
from app.services.pagamentos_guardas import SegregacaoError, assert_segregacao


def _debito(**kw) -> Debito:
    base = dict(id_usuario_solicitante=10, id_gestor_decisor=None, id_validador=None)
    base.update(kw)
    return Debito(**base)


def test_solicitante_nao_gere():
    with pytest.raises(SegregacaoError) as e:
        assert_segregacao(_debito(), usuario_id=10, ato="GERIR")
    assert e.value.status_code == 403


def test_solicitante_nao_valida():
    with pytest.raises(SegregacaoError):
        assert_segregacao(_debito(), usuario_id=10, ato="VALIDAR")


def test_gestor_nao_valida():
    with pytest.raises(SegregacaoError):
        assert_segregacao(_debito(id_gestor_decisor=20), usuario_id=20, ato="VALIDAR")


def test_gestor_nao_autoriza():
    with pytest.raises(SegregacaoError):
        assert_segregacao(_debito(id_gestor_decisor=20), usuario_id=20, ato="AUTORIZAR")


def test_validador_nao_autoriza():
    with pytest.raises(SegregacaoError):
        assert_segregacao(_debito(id_validador=30), usuario_id=30, ato="AUTORIZAR")


def test_terceiro_pode():
    assert_segregacao(_debito(id_gestor_decisor=20, id_validador=30),
                      usuario_id=40, ato="AUTORIZAR")


def test_pagar_e_impedido_para_todos_os_anteriores():
    d = _debito(id_gestor_decisor=20, id_validador=30)
    for uid in (10, 20, 30):
        with pytest.raises(SegregacaoError):
            assert_segregacao(d, usuario_id=uid, ato="PAGAR")
    assert_segregacao(d, usuario_id=99, ato="PAGAR")


def test_mensagem_diz_qual_ato_a_pessoa_ja_exerceu():
    """Erro de segregação sem dizer o motivo vira chamado de suporte."""
    with pytest.raises(SegregacaoError) as e:
        assert_segregacao(_debito(id_gestor_decisor=20), usuario_id=20, ato="VALIDAR")
    assert "gestor" in str(e.value.detail).lower()
