"""Contratos G1 — regras do service: ciclo do contrato, aditivos, apostilas e
isolamento entre tenants.

Spec: docs/superpowers/specs/2026-10-08-contratos-g1-modulo-e-contrato-design.md
(§2.1 a §2.3 e §5.1).

Estes testes chamam o service direto. Eles NÃO provam a fiação HTTP nem o gate
de permissão — isso é `test_contratos_http.py`.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.schemas.contratos import (
    AditivoCreate,
    AditivoUpdate,
    ApostilaCreate,
    ContratoUpdate,
)
from app.services import contratos as svc
from app.services.contratos import ContratoError
from tests.contratos_util import (
    aditivo_vigente,
    contrato_vigente,
    criar_fornecedor_e_unidade,
    numero,
    payload_contrato,
    provisionar,
    sm,
)

HOJE = date(2026, 6, 1)


async def _ambiente(engine):
    tenant = await provisionar(engine)
    # O service só usa `usuario` para o sigilo do processo vinculado; nenhum
    # contrato daqui vincula processo, então um portador de id basta.
    usuario = SimpleNamespace(id=None, nivel_acesso_sigilo="interno")
    return tenant, usuario


async def _valores_gravados(engine, contrato_id: int):
    async with sm(engine)() as s:
        return (await s.execute(text(
            "SELECT valor_total, vigencia_inicio, vigencia_fim, situacao, exercicio "
            "FROM pagamentos.contrato WHERE id = :i"), {"i": contrato_id})).one()


# ---------- ciclo do contrato --------------------------------------------------

async def test_contrato_nasce_rascunho_e_assinatura_o_torna_vigente(admin_engine):
    tenant, usuario = await _ambiente(admin_engine)
    f, u = await criar_fornecedor_e_unidade(admin_engine, tenant.id)
    async with sm(admin_engine)() as s:
        c = await svc.criar(
            s, tenant_id=tenant.id, usuario=usuario, payload=payload_contrato(f, u))
        assert c.situacao == "RASCUNHO"
        assert c.exercicio == 2026
        c = await svc.assinar(s, tenant_id=tenant.id, contrato_id=c.id)
        assert c.situacao == "VIGENTE"


async def test_assinar_exige_os_dados_que_o_tribunal_cobra(admin_engine):
    tenant, usuario = await _ambiente(admin_engine)
    f, u = await criar_fornecedor_e_unidade(admin_engine, tenant.id)
    async with sm(admin_engine)() as s:
        c = await svc.criar(s, tenant_id=tenant.id, usuario=usuario, payload=payload_contrato(
            f, u, data_celebracao=None, tipo_objeto=None, natureza_duracao=None))
        with pytest.raises(ContratoError) as exc:
            await svc.assinar(s, tenant_id=tenant.id, contrato_id=c.id)
    assert exc.value.status_code == 422
    for campo in ("data de celebração", "tipo de objeto", "natureza da duração"):
        assert campo in exc.value.detail


async def test_assinar_recusa_numero_maior_que_o_campo_do_sim(admin_engine):
    tenant, usuario = await _ambiente(admin_engine)
    f, u = await criar_fornecedor_e_unidade(admin_engine, tenant.id)
    async with sm(admin_engine)() as s:
        c = await svc.criar(s, tenant_id=tenant.id, usuario=usuario, payload=payload_contrato(
            f, u, numero="CONTRATO-2026-0000001"))
        with pytest.raises(ContratoError) as exc:
            await svc.assinar(s, tenant_id=tenant.id, contrato_id=c.id)
    assert exc.value.status_code == 422
    assert "15" in exc.value.detail


@pytest.mark.parametrize("acao", ["assinar", "encerrar", "rescindir"])
async def test_transicao_ilegal_e_409(admin_engine, acao):
    """Assinar o que já é vigente; encerrar e rescindir o que ainda é rascunho."""
    tenant, usuario = await _ambiente(admin_engine)
    f, u = await criar_fornecedor_e_unidade(admin_engine, tenant.id)
    async with sm(admin_engine)() as s:
        c = await svc.criar(
            s, tenant_id=tenant.id, usuario=usuario, payload=payload_contrato(f, u))
        if acao == "assinar":
            await svc.assinar(s, tenant_id=tenant.id, contrato_id=c.id)
        with pytest.raises(ContratoError) as exc:
            if acao == "assinar":
                await svc.assinar(s, tenant_id=tenant.id, contrato_id=c.id)
            elif acao == "encerrar":
                await svc.encerrar(
                    s, tenant_id=tenant.id, contrato_id=c.id, data_encerramento=HOJE)
            else:
                await svc.rescindir(
                    s, tenant_id=tenant.id, contrato_id=c.id, data_encerramento=HOJE,
                    motivo="Inexecução total do objeto")
    assert exc.value.status_code == 409


async def test_encerrado_e_rescindido_sao_terminais(admin_engine):
    tenant, usuario = await _ambiente(admin_engine)
    c = await contrato_vigente(admin_engine, tenant.id, usuario)
    async with sm(admin_engine)() as s:
        c2 = await svc.rescindir(
            s, tenant_id=tenant.id, contrato_id=c.id, data_encerramento=HOJE,
            motivo="Inexecução total do objeto")
        assert c2.situacao == "RESCINDIDO"
        assert c2.motivo_rescisao == "Inexecução total do objeto"
        with pytest.raises(ContratoError) as exc:
            await svc.encerrar(s, tenant_id=tenant.id, contrato_id=c.id, data_encerramento=HOJE)
    assert exc.value.status_code == 409


async def test_so_rascunho_se_exclui(admin_engine):
    tenant, usuario = await _ambiente(admin_engine)
    f, u = await criar_fornecedor_e_unidade(admin_engine, tenant.id)
    async with sm(admin_engine)() as s:
        rascunho = await svc.criar(
            s, tenant_id=tenant.id, usuario=usuario, payload=payload_contrato(f, u))
        await svc.excluir(s, tenant_id=tenant.id, contrato_id=rascunho.id)
        with pytest.raises(ContratoError) as sumiu:
            await svc.obter(s, tenant_id=tenant.id, contrato_id=rascunho.id)
    assert sumiu.value.status_code == 404

    vigente = await contrato_vigente(admin_engine, tenant.id, usuario)
    async with sm(admin_engine)() as s:
        with pytest.raises(ContratoError) as exc:
            await svc.excluir(s, tenant_id=tenant.id, contrato_id=vigente.id)
    assert exc.value.status_code == 409


async def test_contrato_vigente_trava_os_campos_do_ato(admin_engine):
    tenant, usuario = await _ambiente(admin_engine)
    c = await contrato_vigente(admin_engine, tenant.id, usuario)
    async with sm(admin_engine)() as s:
        for campo, valor in (
            ("valor_total", Decimal("1.00")),
            ("vigencia_fim", date(2030, 1, 1)),
            ("objeto", "Outro objeto"),
            ("numero", numero()),
            ("reforma", True),
        ):
            with pytest.raises(ContratoError) as exc:
                await svc.atualizar(
                    s, tenant_id=tenant.id, contrato_id=c.id, usuario=usuario,
                    payload=ContratoUpdate(**{campo: valor}))
            assert exc.value.status_code == 409, campo
            assert campo in exc.value.detail

        # Os dados SOBRE o contrato continuam editáveis.
        ok = await svc.atualizar(
            s, tenant_id=tenant.id, contrato_id=c.id, usuario=usuario,
            payload=ContratoUpdate(pncp_id="0428019700017610000692026", tipo_objeto="N"))
        assert ok.pncp_id == "0428019700017610000692026"
        assert ok.tipo_objeto == "N"


async def test_reenviar_o_mesmo_valor_travado_nao_e_erro(admin_engine):
    """A tela reenvia o formulário inteiro. Campo travado com o MESMO valor não
    é tentativa de alteração — recusar faria todo PUT de contrato vigente falhar."""
    tenant, usuario = await _ambiente(admin_engine)
    c = await contrato_vigente(admin_engine, tenant.id, usuario)
    async with sm(admin_engine)() as s:
        ok = await svc.atualizar(
            s, tenant_id=tenant.id, contrato_id=c.id, usuario=usuario,
            payload=ContratoUpdate(
                valor_total=Decimal("100000.00"), vigencia_fim=date(2026, 12, 31),
                tipo_objeto="G"))
    assert ok.tipo_objeto == "G"


async def test_numero_e_unico_por_exercicio_nao_por_tenant(admin_engine):
    """O SIM exige unicidade POR exercício: o mesmo número em anos diferentes
    é o caso normal de município que reinicia a numeração."""
    tenant, usuario = await _ambiente(admin_engine)
    f, u = await criar_fornecedor_e_unidade(admin_engine, tenant.id)
    n = numero()
    async with sm(admin_engine)() as s:
        await svc.criar(s, tenant_id=tenant.id, usuario=usuario, payload=payload_contrato(
            f, u, numero=n))
        outro_ano = await svc.criar(
            s, tenant_id=tenant.id, usuario=usuario, payload=payload_contrato(
                f, u, numero=n, data_celebracao=date(2027, 1, 4),
                vigencia_inicio=date(2027, 1, 4), vigencia_fim=date(2027, 12, 31)))
        assert outro_ano.exercicio == 2027
        with pytest.raises(ContratoError) as exc:
            await svc.criar(s, tenant_id=tenant.id, usuario=usuario, payload=payload_contrato(
                f, u, numero=n))
    assert exc.value.status_code == 409


# ---------- aditivos -----------------------------------------------------------

async def test_aditivo_nao_altera_as_colunas_do_contrato(admin_engine):
    """O coração da G1: valor e vigência originais ficam CONGELADOS. O aditivo
    muda o que `calcular` devolve, não o que está gravado."""
    tenant, usuario = await _ambiente(admin_engine)
    c = await contrato_vigente(admin_engine, tenant.id, usuario)
    antes = await _valores_gravados(admin_engine, c.id)

    await aditivo_vigente(
        admin_engine, tenant.id, c.id, None, tipo="PA", valor="20000",
        nova_vigencia_fim=date(2027, 6, 30))

    assert await _valores_gravados(admin_engine, c.id) == antes
    async with sm(admin_engine)() as s:
        d = await svc.detalhar(
            s, tenant_id=tenant.id, contrato_id=c.id, usuario=usuario, hoje=HOJE)
    assert d["calculo"].valor_atualizado == Decimal("120000.00")
    assert d["calculo"].vigencia_fim_atual == date(2027, 6, 30)
    assert d["valor_total"] == Decimal("100000.00")
    assert d["vigencia_fim"] == date(2026, 12, 31)


async def test_aditivo_so_em_contrato_vigente(admin_engine):
    tenant, usuario = await _ambiente(admin_engine)
    f, u = await criar_fornecedor_e_unidade(admin_engine, tenant.id)
    async with sm(admin_engine)() as s:
        rascunho = await svc.criar(
            s, tenant_id=tenant.id, usuario=usuario, payload=payload_contrato(f, u))
        with pytest.raises(ContratoError) as exc:
            await svc.criar_aditivo(
                s, tenant_id=tenant.id, contrato_id=rascunho.id, usuario_id=None,
                payload=AditivoCreate(
                    numero=numero(), tipo="AA", data_assinatura=HOJE, valor=Decimal("1")))
    assert exc.value.status_code == 409


async def test_nova_vigencia_tem_de_ser_posterior_a_atual(admin_engine):
    tenant, usuario = await _ambiente(admin_engine)
    c = await contrato_vigente(admin_engine, tenant.id, usuario)
    with pytest.raises(ContratoError) as exc:
        await aditivo_vigente(
            admin_engine, tenant.id, c.id, None, tipo="AP",
            nova_vigencia_fim=date(2026, 12, 31))
    assert exc.value.status_code == 422

    await aditivo_vigente(
        admin_engine, tenant.id, c.id, None, tipo="AP", nova_vigencia_fim=date(2027, 12, 31))
    # A referência passa a ser a vigência ATUAL, não a original.
    with pytest.raises(ContratoError) as exc2:
        await aditivo_vigente(
            admin_engine, tenant.id, c.id, None, tipo="AP",
            nova_vigencia_fim=date(2027, 6, 30))
    assert exc2.value.status_code == 422


async def test_acima_do_limite_exige_justificativa_e_nao_bloqueia(admin_engine):
    tenant, usuario = await _ambiente(admin_engine)
    c = await contrato_vigente(admin_engine, tenant.id, usuario)

    with pytest.raises(ContratoError) as exc:
        await aditivo_vigente(admin_engine, tenant.id, c.id, None, tipo="AA", valor="30000")
    assert exc.value.status_code == 422
    assert "art. 125" in exc.value.detail

    # A recusa não pode ter deixado o aditivo valendo pela metade.
    async with sm(admin_engine)() as s:
        d = await svc.detalhar(
            s, tenant_id=tenant.id, contrato_id=c.id, usuario=usuario, hoje=HOJE)
    assert d["calculo"].valor_atualizado == Decimal("100000.00")
    assert [a.situacao for a in d["aditivos"]] == ["RASCUNHO"]

    a = await aditivo_vigente(
        admin_engine, tenant.id, c.id, None, tipo="AA", valor="30000",
        justificativa="Fato superveniente documentado no processo 123/2026.")
    assert a.situacao == "VIGENTE"
    async with sm(admin_engine)() as s:
        d = await svc.detalhar(
            s, tenant_id=tenant.id, contrato_id=c.id, usuario=usuario, hoje=HOJE)
    assert d["calculo"].acima_do_limite is True
    assert d["calculo"].valor_atualizado == Decimal("130000.00")


async def test_reducao_nao_pode_zerar_o_contrato(admin_engine):
    tenant, usuario = await _ambiente(admin_engine)
    c = await contrato_vigente(admin_engine, tenant.id, usuario)
    with pytest.raises(ContratoError) as exc:
        await aditivo_vigente(
            admin_engine, tenant.id, c.id, None, tipo="AR", valor="100000",
            justificativa="Supressão integral.")
    assert exc.value.status_code == 422


async def test_aditivo_e_contrato_dividem_a_numeracao_do_exercicio(admin_engine):
    """No SIM os dois vão no mesmo campo. O banco tem um índice por tabela; a
    regra cruzada só existe no service — este teste é o que a segura."""
    tenant, usuario = await _ambiente(admin_engine)
    c = await contrato_vigente(admin_engine, tenant.id, usuario)
    async with sm(admin_engine)() as s:
        with pytest.raises(ContratoError) as exc:
            await svc.criar_aditivo(
                s, tenant_id=tenant.id, contrato_id=c.id, usuario_id=None,
                payload=AditivoCreate(
                    numero=c.numero, tipo="AA", data_assinatura=date(2026, 6, 1),
                    valor=Decimal("1")))
        assert exc.value.status_code == 409

        # Em OUTRO exercício o mesmo número é livre.
        livre = await svc.criar_aditivo(
            s, tenant_id=tenant.id, contrato_id=c.id, usuario_id=None,
            payload=AditivoCreate(
                numero=c.numero, tipo="AA", data_assinatura=date(2027, 2, 1),
                valor=Decimal("1")))
    assert livre.exercicio == 2027


async def test_sequencial_e_ciclo_do_aditivo(admin_engine):
    tenant, usuario = await _ambiente(admin_engine)
    c = await contrato_vigente(admin_engine, tenant.id, usuario)
    primeiro = await aditivo_vigente(admin_engine, tenant.id, c.id, None, tipo="AA", valor="1000")
    segundo = await aditivo_vigente(admin_engine, tenant.id, c.id, None, tipo="AA", valor="2000")
    assert (primeiro.sequencial, segundo.sequencial) == (1, 2)

    async with sm(admin_engine)() as s:
        # Assinado não se edita nem se exclui: anula.
        with pytest.raises(ContratoError) as edita:
            await svc.atualizar_aditivo(
                s, tenant_id=tenant.id, contrato_id=c.id, aditivo_id=primeiro.id,
                payload=AditivoUpdate(valor=Decimal("5")))
        assert edita.value.status_code == 409
        with pytest.raises(ContratoError) as exclui:
            await svc.excluir_aditivo(
                s, tenant_id=tenant.id, contrato_id=c.id, aditivo_id=primeiro.id)
        assert exclui.value.status_code == 409

        anulado = await svc.anular_aditivo(
            s, tenant_id=tenant.id, contrato_id=c.id, aditivo_id=primeiro.id,
            motivo="Assinado com valor errado.")
        assert anulado.situacao == "ANULADO"
        d = await svc.detalhar(
            s, tenant_id=tenant.id, contrato_id=c.id, usuario=usuario, hoje=HOJE)
    assert d["calculo"].valor_atualizado == Decimal("102000.00")


# ---------- apostilas ----------------------------------------------------------

async def test_apostila_de_reajuste_muda_a_base_e_as_outras_nao_levam_valor(admin_engine):
    tenant, usuario = await _ambiente(admin_engine)
    c = await contrato_vigente(admin_engine, tenant.id, usuario)
    async with sm(admin_engine)() as s:
        await svc.criar_apostila(
            s, tenant_id=tenant.id, contrato_id=c.id, usuario_id=None, hoje=HOJE,
            payload=ApostilaCreate(
                tipo="REAJUSTE", data=HOJE, valor_delta=Decimal("5000"),
                indice="IPCA 12 meses 5,00%", descricao="Reajuste anual"))
        d = await svc.detalhar(
            s, tenant_id=tenant.id, contrato_id=c.id, usuario=usuario, hoje=HOJE)
        assert d["calculo"].valor_inicial_atualizado == Decimal("105000.00")

        with pytest.raises(ContratoError) as sem_valor:
            await svc.criar_apostila(
                s, tenant_id=tenant.id, contrato_id=c.id, usuario_id=None, hoje=HOJE,
                payload=ApostilaCreate(tipo="REAJUSTE", data=HOJE, descricao="Sem valor"))
        assert sem_valor.value.status_code == 422

        with pytest.raises(ContratoError) as com_valor:
            await svc.criar_apostila(
                s, tenant_id=tenant.id, contrato_id=c.id, usuario_id=None, hoje=HOJE,
                payload=ApostilaCreate(
                    tipo="RAZAO_SOCIAL", data=HOJE, valor_delta=Decimal("1"),
                    descricao="Nova razão social"))
        assert com_valor.value.status_code == 422


# ---------- isolamento ---------------------------------------------------------

async def test_contrato_de_outro_tenant_e_404_em_toda_operacao(admin_engine):
    tenant_a, usuario = await _ambiente(admin_engine)
    tenant_b, _ = await _ambiente(admin_engine)
    c = await contrato_vigente(admin_engine, tenant_a.id, usuario)
    a = await aditivo_vigente(admin_engine, tenant_a.id, c.id, None, tipo="AA", valor="1000")

    async with sm(admin_engine)() as s:
        chamadas = (
            svc.obter(s, tenant_id=tenant_b.id, contrato_id=c.id),
            svc.detalhar(s, tenant_id=tenant_b.id, contrato_id=c.id, usuario=usuario),
            svc.atualizar(
                s, tenant_id=tenant_b.id, contrato_id=c.id, usuario=usuario,
                payload=ContratoUpdate(tipo_objeto="N")),
            svc.encerrar(s, tenant_id=tenant_b.id, contrato_id=c.id, data_encerramento=HOJE),
            svc.criar_aditivo(
                s, tenant_id=tenant_b.id, contrato_id=c.id, usuario_id=None,
                payload=AditivoCreate(
                    numero=numero(), tipo="AA", data_assinatura=HOJE, valor=Decimal("1"))),
            svc.anular_aditivo(
                s, tenant_id=tenant_b.id, contrato_id=c.id, aditivo_id=a.id,
                motivo="Tentativa cross-tenant"),
            svc.criar_apostila(
                s, tenant_id=tenant_b.id, contrato_id=c.id, usuario_id=None,
                payload=ApostilaCreate(tipo="OUTRO", data=HOJE, descricao="Cross-tenant")),
        )
        for chamada in chamadas:
            with pytest.raises(ContratoError) as exc:
                await chamada
            assert exc.value.status_code == 404

    # E o contrato do tenant A continua intacto.
    async with sm(admin_engine)() as s:
        d = await svc.detalhar(
            s, tenant_id=tenant_a.id, contrato_id=c.id, usuario=usuario, hoje=HOJE)
    assert d["situacao"] == "VIGENTE"
    assert [x.situacao for x in d["aditivos"]] == ["VIGENTE"]


async def test_fornecedor_e_unidade_de_outro_tenant_sao_recusados(admin_engine):
    """A FK do Postgres não filtra tenant: sem a validação same-tenant, um
    contrato do tenant B apontaria para o fornecedor do tenant A."""
    tenant_a, usuario = await _ambiente(admin_engine)
    tenant_b, _ = await _ambiente(admin_engine)
    f_a, u_a = await criar_fornecedor_e_unidade(admin_engine, tenant_a.id)
    f_b, u_b = await criar_fornecedor_e_unidade(admin_engine, tenant_b.id)

    async with sm(admin_engine)() as s:
        for f, u in ((f_a, u_b), (f_b, u_a)):
            with pytest.raises(ContratoError) as exc:
                await svc.criar(
                    s, tenant_id=tenant_b.id, usuario=usuario, payload=payload_contrato(f, u))
            assert exc.value.status_code == 422


async def test_listagem_e_painel_so_enxergam_o_proprio_tenant(admin_engine):
    tenant_a, usuario = await _ambiente(admin_engine)
    tenant_b, _ = await _ambiente(admin_engine)
    c = await contrato_vigente(admin_engine, tenant_a.id, usuario)

    async with sm(admin_engine)() as s:
        itens_a, total_a = await svc.listar(
            s, tenant_id=tenant_a.id, page=1, page_size=20, hoje=HOJE)
        itens_b, total_b = await svc.listar(
            s, tenant_id=tenant_b.id, page=1, page_size=20, hoje=HOJE)
        painel_b = await svc.painel(s, tenant_id=tenant_b.id, hoje=HOJE)
    assert total_a == 1 and [i["id"] for i in itens_a] == [c.id]
    assert total_b == 0 and itens_b == []
    assert painel_b["vigentes"] == 0


async def test_filtro_vence_ate_usa_a_vigencia_atual_e_nao_a_original(admin_engine):
    """A listagem filtra em SQL e o detalhe calcula em Python. Este teste é o
    que impede as duas contas de divergirem: um contrato prorrogado por aditivo
    NÃO pode aparecer em "vence até" a data original."""
    tenant, usuario = await _ambiente(admin_engine)
    prorrogado = await contrato_vigente(admin_engine, tenant.id, usuario)
    no_prazo = await contrato_vigente(admin_engine, tenant.id, usuario)
    await aditivo_vigente(
        admin_engine, tenant.id, prorrogado.id, None, tipo="AP",
        nova_vigencia_fim=date(2027, 12, 31))

    async with sm(admin_engine)() as s:
        itens, total = await svc.listar(
            s, tenant_id=tenant.id, page=1, page_size=20, vence_ate=date(2026, 12, 31),
            hoje=HOJE)
        painel = await svc.painel(s, tenant_id=tenant.id, hoje=date(2026, 12, 1))
    assert total == 1
    assert [i["id"] for i in itens] == [no_prazo.id]
    assert itens[0]["vigencia_fim_atual"] == date(2026, 12, 31)
    # Em 01/12/2026 só o não prorrogado vence em 30 dias.
    assert painel["vigentes"] == 2
    assert painel["vencendo_30"] == 1
