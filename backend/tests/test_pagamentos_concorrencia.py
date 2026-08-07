"""Concorrência otimista nas decisões (spec §6.3, cenário 21 do pedido)."""
import pytest

from app.models import Debito
from app.services.pagamentos_guardas import ConflitoDeEdicaoError, assert_lock_version


def test_versao_igual_passa():
    assert_lock_version(Debito(lock_version=7), esperado=7)


def test_versao_diferente_e_conflito_409():
    with pytest.raises(ConflitoDeEdicaoError) as e:
        assert_lock_version(Debito(lock_version=8), esperado=7)
    assert e.value.status_code == 409


def test_mensagem_orienta_a_recarregar():
    """'Conflito' sozinho não diz o que fazer (spec §12)."""
    with pytest.raises(ConflitoDeEdicaoError) as e:
        assert_lock_version(Debito(lock_version=8), esperado=7)
    assert "recarregue" in str(e.value.detail).lower()
