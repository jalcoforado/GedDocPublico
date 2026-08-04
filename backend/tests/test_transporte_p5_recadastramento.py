"""Transporte P5.1 — ciclo de recadastramento, convocação e escalonamento.

Spec: `docs/superpowers/specs/2026-08-04-transporte-p5-1-recadastramento-ciclo-design.md`.

O teste mais importante deste arquivo é
`test_gera_convoca_permissionario_e_empresa`. `Permissionario.situacao` usa
masculino (`ativo`) e `Empresa.situacao` usa feminino (`ativa`); filtrar
`"ativo"` nos dois convoca ZERO empresas **sem erro nenhum**. Um teste que
olhasse só o total passaria com o filtro errado, porque o número seria menor e
ninguém repararia. Por isso ele afirma sobre cada um dos dois vínculos
separadamente.

Toda negativa tem controle positivo na mesma sessão: "levantou exceção" não
distingue a regra funcionando de um serviço quebrado.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fastapi import HTTPException

from app.models import RecadastramentoCiclo, RecadastramentoConvocacao
from app.schemas.transporte_regulado import (
    EmpresaCreate,
    PermissionarioCreate,
    RecadastramentoAjustePrazo,
    RecadastramentoCicloCreate,
    RecadastramentoCicloUpdate,
)
from httpx import ASGITransport, AsyncClient

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import Usuario
from app.services import transporte_regulado as tr
from app.services.modulos import contratar
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

HOJE = date.today()
INICIO = HOJE
FIM = HOJE + timedelta(days=30)


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str = "p51") -> str:
    return f"{p}-{uuid.uuid4().hex[:8]}"


def _cpf(final: str = "0") -> str:
    """CPF com o último dígito controlado — é ele que escolhe a faixa."""
    return uuid.uuid4().int.__str__()[:10] + final


def _cnpj(final: str = "0") -> str:
    return uuid.uuid4().int.__str__()[:13] + final


async def _provisionar(engine):
    slug = _slug()
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref P5.1",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    return tenant


async def _permissionario(engine, tenant_id: int, *, nome="Perm", situacao="ativo",
                          final="0"):
    async with _sm(engine)() as db:
        p = await tr.criar_permissionario(
            db,
            tenant_id=tenant_id,
            payload=PermissionarioCreate(
                nome=nome, cpf=_cpf(final), tipo_servico="taxi", situacao=situacao
            ),
        )
    return p


async def _empresa(engine, tenant_id: int, *, razao="Empresa", situacao="ativa",
                   final="0"):
    async with _sm(engine)() as db:
        e = await tr.criar_empresa(
            db,
            tenant_id=tenant_id,
            payload=EmpresaCreate(
                razao_social=razao,
                cnpj=_cnpj(final),
                tipo_servico="taxi",
                situacao=situacao,
            ),
        )
    return e


async def _ciclo(engine, tenant_id: int, *, nome=None, inicio=INICIO, fim=FIM,
                 criterio="final_documento"):
    async with _sm(engine)() as db:
        return await tr.criar_ciclo(
            db,
            tenant_id=tenant_id,
            payload=RecadastramentoCicloCreate(
                nome=nome or f"Recad {uuid.uuid4().hex[:6]}",
                data_inicio=inicio,
                data_fim=fim,
                criterio_escalonamento=criterio,
            ),
        )


async def _convocacoes(engine, tenant_id: int, ciclo_id: int):
    async with _sm(engine)() as db:
        return (
            (
                await db.execute(
                    select(RecadastramentoConvocacao).where(
                        RecadastramentoConvocacao.tenant_id == tenant_id,
                        RecadastramentoConvocacao.id_ciclo == ciclo_id,
                        RecadastramentoConvocacao.excluido.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )


# ======================= Escalonamento (função pura) =======================


def _ciclo_solto(criterio="final_documento", inicio=date(2026, 1, 1),
                 fim=date(2026, 1, 31)) -> RecadastramentoCiclo:
    """Instância NÃO persistida. O escalonamento é pura aritmética de datas;
    exercitá-lo com banco só esconderia isso."""
    return RecadastramentoCiclo(
        data_inicio=inicio, data_fim=fim, criterio_escalonamento=criterio
    )


def test_escalonamento_distribui_os_dez_finais_na_janela():
    """Dez finais, dez prazos distintos e crescentes, todos dentro da janela."""
    c = _ciclo_solto()
    prazos = [tr.prazo_do_regulado(f"1234567890{d}", c) for d in range(10)]

    assert len(set(prazos)) == 10, "finais diferentes têm de dar prazos diferentes"
    assert prazos == sorted(prazos)
    assert all(c.data_inicio <= p <= c.data_fim for p in prazos)
    # A última faixa fecha exatamente no fim da janela — não um dia depois.
    assert prazos[-1] == c.data_fim


def test_escalonamento_final_0_e_final_9_caem_em_prazos_diferentes():
    """O caso que a spec pede nomeadamente: os extremos não colidem."""
    c = _ciclo_solto()
    assert tr.prazo_do_regulado("00000000000", c) != tr.prazo_do_regulado(
        "00000000009", c
    )


def test_sem_escalonamento_da_data_fim_a_todos():
    c = _ciclo_solto(criterio="sem_escalonamento")
    assert tr.prazo_do_regulado("00000000000", c) == c.data_fim
    assert tr.prazo_do_regulado("00000000009", c) == c.data_fim
    # Controle: com o critério de escalonamento, esses dois divergem.
    assert tr.prazo_do_regulado("00000000000", _ciclo_solto()) != c.data_fim


def test_documento_sujo_cai_na_faixa_final_em_vez_de_quebrar():
    """Base vinda do legado tem cadastro sujo. Falhar a geração inteira por um
    registro seria pior do que jogá-lo na última faixa."""
    c = _ciclo_solto()
    assert tr.prazo_do_regulado("123.456.789-X", c) == c.data_fim
    assert tr.prazo_do_regulado("", c) == c.data_fim
    assert tr.prazo_do_regulado(None, c) == c.data_fim
    # Controle: documento limpo terminando em 0 NÃO cai no fim.
    assert tr.prazo_do_regulado("12345678900", c) != c.data_fim


def test_janela_de_um_dia_nao_estoura():
    """`data_inicio == data_fim` é janela válida; todos caem no mesmo dia."""
    c = _ciclo_solto(inicio=date(2026, 5, 1), fim=date(2026, 5, 1))
    assert {tr.prazo_do_regulado(f"1{d}", c) for d in range(10)} == {date(2026, 5, 1)}


# ============================ Geração ======================================


@pytest.mark.asyncio
async def test_gera_convoca_permissionario_e_empresa(admin_engine):
    """**O teste do masculino/feminino.**

    Um permissionário `ativo` e uma empresa `ativa`. A geração tem de alcançar
    OS DOIS. Afirmar sobre cada vínculo separadamente, e não sobre o total, é o
    que faz este teste ficar vermelho quando o filtro da empresa vira `"ativo"`.
    """
    t = await _provisionar(admin_engine)
    p = await _permissionario(admin_engine, t.id, nome="Fulano")
    e = await _empresa(admin_engine, t.id, razao="Transportes Beltrano")
    ciclo = await _ciclo(admin_engine, t.id)

    async with _sm(admin_engine)() as db:
        resultado = await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id)

    assert resultado == {"criadas": 2, "ja_existentes": 0}

    convs = await _convocacoes(admin_engine, t.id, ciclo.id)
    assert [c.id_permissionario for c in convs].count(p.id) == 1, (
        "permissionário ativo não foi convocado"
    )
    assert [c.id_empresa for c in convs].count(e.id) == 1, (
        "empresa ATIVA não foi convocada — filtro provavelmente usa o masculino"
    )
    # Exatamente um vínculo por linha, como o CHECK exige.
    assert all(bool(c.id_permissionario) != bool(c.id_empresa) for c in convs)
    # Prazo original nasce igual ao prazo, e nenhuma linha nasce ajustada.
    assert all(c.prazo == c.prazo_original for c in convs)
    assert all(c.ajustado_em is None for c in convs)


@pytest.mark.asyncio
async def test_geracao_e_idempotente(admin_engine):
    """Segundo disparo devolve `criadas=0` e o total no banco não muda."""
    t = await _provisionar(admin_engine)
    await _permissionario(admin_engine, t.id)
    await _empresa(admin_engine, t.id)
    ciclo = await _ciclo(admin_engine, t.id)

    async with _sm(admin_engine)() as db:
        primeiro = await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id)
    async with _sm(admin_engine)() as db:
        segundo = await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id)

    assert primeiro == {"criadas": 2, "ja_existentes": 0}
    assert segundo == {"criadas": 0, "ja_existentes": 2}
    assert len(await _convocacoes(admin_engine, t.id, ciclo.id)) == 2


@pytest.mark.asyncio
async def test_segundo_disparo_alcanca_regulado_novo(admin_engine):
    """Idempotência não pode virar "não faz nada": quem entrou depois é
    convocado, e quem já tinha prazo não é remarcado."""
    t = await _provisionar(admin_engine)
    p1 = await _permissionario(admin_engine, t.id, nome="Antigo", final="3")
    ciclo = await _ciclo(admin_engine, t.id)

    async with _sm(admin_engine)() as db:
        await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id)
    prazo_antes = [
        c.prazo
        for c in await _convocacoes(admin_engine, t.id, ciclo.id)
        if c.id_permissionario == p1.id
    ][0]

    p2 = await _permissionario(admin_engine, t.id, nome="Novo", final="7")
    async with _sm(admin_engine)() as db:
        segundo = await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id)

    assert segundo == {"criadas": 1, "ja_existentes": 1}
    convs = {c.id_permissionario: c for c in await _convocacoes(
        admin_engine, t.id, ciclo.id
    )}
    assert p2.id in convs
    assert convs[p1.id].prazo == prazo_antes, "regulado já convocado foi remarcado"


@pytest.mark.asyncio
async def test_nao_convoca_regulado_fora_de_atividade(admin_engine):
    """Um de cada situação inativa no mesmo tenant, mais um ativo de controle.

    Sem o controle, um serviço que não convocasse NINGUÉM passaria.
    """
    t = await _provisionar(admin_engine)
    ativo = await _permissionario(admin_engine, t.id, nome="Ativo")
    inativos = [
        await _permissionario(admin_engine, t.id, nome=s, situacao=s)
        for s in ("pendente", "suspenso", "cassado", "inativo")
    ]
    empresa_inativa = await _empresa(
        admin_engine, t.id, razao="Suspensa", situacao="suspensa"
    )
    ciclo = await _ciclo(admin_engine, t.id)

    async with _sm(admin_engine)() as db:
        resultado = await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id)

    assert resultado["criadas"] == 1
    convs = await _convocacoes(admin_engine, t.id, ciclo.id)
    assert [c.id_permissionario for c in convs] == [ativo.id]
    convocados = {c.id_permissionario for c in convs} | {c.id_empresa for c in convs}
    assert all(p.id not in convocados for p in inativos)
    assert empresa_inativa.id not in convocados


@pytest.mark.asyncio
async def test_nao_convoca_regulado_excluido(admin_engine):
    t = await _provisionar(admin_engine)
    ativo = await _permissionario(admin_engine, t.id, nome="Fica")
    removido = await _permissionario(admin_engine, t.id, nome="Sai")
    async with _sm(admin_engine)() as db:
        await tr.excluir_permissionario(
            db, tenant_id=t.id, permissionario_id=removido.id
        )
    ciclo = await _ciclo(admin_engine, t.id)

    async with _sm(admin_engine)() as db:
        await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id)

    convs = await _convocacoes(admin_engine, t.id, ciclo.id)
    assert [c.id_permissionario for c in convs] == [ativo.id]


@pytest.mark.asyncio
async def test_geracao_recusa_ciclo_encerrado_e_aceita_rascunho(admin_engine):
    """Negativa com controle: `rascunho` gera (é o ensaio antes de abrir)."""
    t = await _provisionar(admin_engine)
    await _permissionario(admin_engine, t.id)
    rascunho = await _ciclo(admin_engine, t.id)
    encerrado = await _ciclo(admin_engine, t.id)
    async with _sm(admin_engine)() as db:
        await tr.atualizar_ciclo(
            db,
            tenant_id=t.id,
            ciclo_id=encerrado.id,
            payload=RecadastramentoCicloUpdate(situacao="encerrado"),
        )

    async with _sm(admin_engine)() as db:
        assert (
            await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=rascunho.id)
        )["criadas"] == 1

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=encerrado.id)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_geracao_zero_zero_em_tenant_sem_regulado_ativo(admin_engine):
    """`0/0` diz ao operador que não há regulado ativo — diferente de
    "funcionou"."""
    t = await _provisionar(admin_engine)
    await _permissionario(admin_engine, t.id, situacao="pendente")
    ciclo = await _ciclo(admin_engine, t.id)

    async with _sm(admin_engine)() as db:
        assert await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id) == {
            "criadas": 0,
            "ja_existentes": 0,
        }


@pytest.mark.asyncio
async def test_geracao_aplica_o_criterio_do_ciclo(admin_engine):
    """Dois permissionários com finais distantes: escalonado, prazos diferem;
    `sem_escalonamento`, os dois caem em `data_fim`."""
    t = await _provisionar(admin_engine)
    await _permissionario(admin_engine, t.id, nome="Final0", final="0")
    await _permissionario(admin_engine, t.id, nome="Final9", final="9")
    escalonado = await _ciclo(admin_engine, t.id)
    plano = await _ciclo(admin_engine, t.id, criterio="sem_escalonamento")

    async with _sm(admin_engine)() as db:
        await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=escalonado.id)
    async with _sm(admin_engine)() as db:
        await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=plano.id)

    prazos_esc = {c.prazo for c in await _convocacoes(admin_engine, t.id, escalonado.id)}
    prazos_plano = {c.prazo for c in await _convocacoes(admin_engine, t.id, plano.id)}
    assert len(prazos_esc) == 2
    assert prazos_plano == {FIM}


# ======================== Vínculo exclusivo ================================


def test_validador_de_vinculo_exige_exatamente_um():
    """Nenhum e ambos são 400; um só passa (controle positivo)."""
    for par in ((None, None), (1, 2)):
        with pytest.raises(HTTPException) as exc:
            tr._validar_vinculo_exclusivo(*par)
        assert exc.value.status_code == 400
    tr._validar_vinculo_exclusivo(1, None)
    tr._validar_vinculo_exclusivo(None, 2)


@pytest.mark.asyncio
async def test_banco_recusa_convocacao_sem_vinculo_unico(admin_engine):
    """A barreira que importa é o CHECK, não a validação do serviço: ela só
    alcança quem passa pelo serviço. Este teste insere por baixo dele."""
    t = await _provisionar(admin_engine)
    p = await _permissionario(admin_engine, t.id)
    ciclo = await _ciclo(admin_engine, t.id)
    e = await _empresa(admin_engine, t.id)

    async def _inserir(id_perm, id_emp):
        async with _sm(admin_engine)() as db:
            await db.execute(
                text(
                    "INSERT INTO transporte_regulado.recadastramento_convocacao "
                    "(tenant_id, id_ciclo, id_permissionario, id_empresa, prazo, "
                    " prazo_original, situacao, criado_em, excluido) VALUES "
                    "(:t, :c, :p, :e, :d, :d, 'convocado', NOW(), false)"
                ),
                {"t": t.id, "c": ciclo.id, "p": id_perm, "e": id_emp, "d": FIM},
            )
            await db.commit()

    for par in ((None, None), (p.id, e.id)):
        with pytest.raises(IntegrityError):
            await _inserir(*par)
    # Controle: com exatamente um vínculo, o mesmo INSERT passa.
    await _inserir(p.id, None)


@pytest.mark.asyncio
async def test_banco_recusa_convocacao_duplicada_no_ciclo(admin_engine):
    """A idempotência mora no índice único parcial. Um `if not exists` em
    Python não segura duas execuções concorrentes — as duas passariam pela
    checagem antes de qualquer INSERT."""
    t = await _provisionar(admin_engine)
    p = await _permissionario(admin_engine, t.id)
    ciclo = await _ciclo(admin_engine, t.id)

    async def _inserir():
        async with _sm(admin_engine)() as db:
            db.add(
                RecadastramentoConvocacao(
                    tenant_id=t.id,
                    id_ciclo=ciclo.id,
                    id_permissionario=p.id,
                    prazo=FIM,
                    prazo_original=FIM,
                    situacao="convocado",
                    criado_em=date.today(),
                )
            )
            await db.commit()

    await _inserir()
    with pytest.raises(IntegrityError):
        await _inserir()


# ============================ Ajuste de prazo ==============================


async def _uma_convocacao(engine, tenant_id: int):
    await _permissionario(engine, tenant_id)
    ciclo = await _ciclo(engine, tenant_id)
    async with _sm(engine)() as db:
        await tr.gerar_convocacoes(db, tenant_id=tenant_id, ciclo_id=ciclo.id)
    conv = (await _convocacoes(engine, tenant_id, ciclo.id))[0]
    return ciclo, conv


@pytest.mark.asyncio
async def test_ajuste_grava_autor_data_e_preserva_prazo_original(admin_engine):
    t = await _provisionar(admin_engine)
    ciclo, conv = await _uma_convocacao(admin_engine, t.id)
    original = conv.prazo_original
    novo = ciclo.data_fim

    async with _sm(admin_engine)() as db:
        ajustada = await tr.ajustar_prazo(
            db,
            tenant_id=t.id,
            convocacao_id=conv.id,
            payload=RecadastramentoAjustePrazo(
                prazo=novo, justificativa="Titular internado, comprovante anexo"
            ),
            usuario_id=1,
        )

    assert ajustada.prazo == novo
    assert ajustada.prazo_original == original, "prazo_original foi sobrescrito"
    assert ajustada.ajuste_justificativa.startswith("Titular internado")
    assert ajustada.ajustado_por == 1
    assert ajustada.ajustado_em is not None


@pytest.mark.asyncio
async def test_ajuste_sem_justificativa_e_recusado(admin_engine):
    """O schema barra na borda; o serviço barra quem não passa por ela. As duas
    portas são testadas, e o controle positivo prova que a boa passa."""
    t = await _provisionar(admin_engine)
    ciclo, conv = await _uma_convocacao(admin_engine, t.id)

    with pytest.raises(ValueError):
        RecadastramentoAjustePrazo(prazo=ciclo.data_fim, justificativa="     ")

    class _SemJustificativa:
        prazo = ciclo.data_fim
        justificativa = "   "

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.ajustar_prazo(
                db,
                tenant_id=t.id,
                convocacao_id=conv.id,
                payload=_SemJustificativa(),
            )
    assert exc.value.status_code == 400

    async with _sm(admin_engine)() as db:
        ok = await tr.ajustar_prazo(
            db,
            tenant_id=t.id,
            convocacao_id=conv.id,
            payload=RecadastramentoAjustePrazo(
                prazo=ciclo.data_fim, justificativa="Motivo registrado"
            ),
        )
    assert ok.prazo == ciclo.data_fim


@pytest.mark.asyncio
async def test_ajuste_fora_da_janela_e_400_dentro_dela_passa(admin_engine):
    t = await _provisionar(admin_engine)
    ciclo, conv = await _uma_convocacao(admin_engine, t.id)

    for fora in (ciclo.data_inicio - timedelta(days=1),
                 ciclo.data_fim + timedelta(days=1)):
        with pytest.raises(HTTPException) as exc:
            async with _sm(admin_engine)() as db:
                await tr.ajustar_prazo(
                    db,
                    tenant_id=t.id,
                    convocacao_id=conv.id,
                    payload=RecadastramentoAjustePrazo(
                        prazo=fora, justificativa="Tentativa fora da janela"
                    ),
                )
        assert exc.value.status_code == 400

    async with _sm(admin_engine)() as db:
        ok = await tr.ajustar_prazo(
            db,
            tenant_id=t.id,
            convocacao_id=conv.id,
            payload=RecadastramentoAjustePrazo(
                prazo=ciclo.data_inicio, justificativa="Antecipado a pedido"
            ),
        )
    assert ok.prazo == ciclo.data_inicio


@pytest.mark.asyncio
async def test_ajuste_para_data_passada_e_permitido(admin_engine):
    """Regularizar alguém retroativamente é caso real de balcão. A janela é o
    limite, não o calendário."""
    t = await _provisionar(admin_engine)
    ontem = HOJE - timedelta(days=10)
    await _permissionario(admin_engine, t.id)
    ciclo = await _ciclo(admin_engine, t.id, inicio=ontem, fim=FIM)
    async with _sm(admin_engine)() as db:
        await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id)
    conv = (await _convocacoes(admin_engine, t.id, ciclo.id))[0]

    async with _sm(admin_engine)() as db:
        ajustada = await tr.ajustar_prazo(
            db,
            tenant_id=t.id,
            convocacao_id=conv.id,
            payload=RecadastramentoAjustePrazo(
                prazo=ontem, justificativa="Compareceu antes da abertura"
            ),
        )
    assert ajustada.prazo == ontem


@pytest.mark.asyncio
async def test_ajuste_em_ciclo_encerrado_e_409(admin_engine):
    t = await _provisionar(admin_engine)
    ciclo, conv = await _uma_convocacao(admin_engine, t.id)

    # Controle: antes de encerrar, o mesmo ajuste passa.
    async with _sm(admin_engine)() as db:
        await tr.ajustar_prazo(
            db,
            tenant_id=t.id,
            convocacao_id=conv.id,
            payload=RecadastramentoAjustePrazo(
                prazo=ciclo.data_fim, justificativa="Ajuste antes do encerramento"
            ),
        )
    async with _sm(admin_engine)() as db:
        await tr.atualizar_ciclo(
            db,
            tenant_id=t.id,
            ciclo_id=ciclo.id,
            payload=RecadastramentoCicloUpdate(situacao="encerrado"),
        )

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.ajustar_prazo(
                db,
                tenant_id=t.id,
                convocacao_id=conv.id,
                payload=RecadastramentoAjustePrazo(
                    prazo=ciclo.data_inicio, justificativa="Tarde demais"
                ),
            )
    assert exc.value.status_code == 409


# ============================ Ciclo: CRUD ==================================


@pytest.mark.asyncio
async def test_ciclo_nasce_em_rascunho(admin_engine):
    t = await _provisionar(admin_engine)
    ciclo = await _ciclo(admin_engine, t.id)
    assert ciclo.situacao == "rascunho"


@pytest.mark.asyncio
async def test_nome_de_ciclo_e_unico_por_tenant(admin_engine):
    """Negativa com controle: o MESMO nome passa em outro tenant."""
    t1 = await _provisionar(admin_engine)
    t2 = await _provisionar(admin_engine)
    nome = f"Recadastramento {uuid.uuid4().hex[:6]}"
    await _ciclo(admin_engine, t1.id, nome=nome)

    with pytest.raises(HTTPException) as exc:
        await _ciclo(admin_engine, t1.id, nome=nome)
    assert exc.value.status_code == 409

    outro = await _ciclo(admin_engine, t2.id, nome=nome)
    assert outro.id


@pytest.mark.asyncio
async def test_atualizar_ciclo_confronta_a_janela_gravada(admin_engine):
    """Mandar SÓ `data_fim`, anterior ao `data_inicio` já persistido, passa
    pelo validador do schema — ele enxerga apenas o que foi enviado."""
    t = await _provisionar(admin_engine)
    ciclo = await _ciclo(admin_engine, t.id, inicio=HOJE + timedelta(days=10), fim=FIM)

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.atualizar_ciclo(
                db,
                tenant_id=t.id,
                ciclo_id=ciclo.id,
                payload=RecadastramentoCicloUpdate(data_fim=HOJE),
            )
    assert exc.value.status_code == 400

    # Controle: `data_fim` posterior ao início gravado é aceito.
    async with _sm(admin_engine)() as db:
        ok = await tr.atualizar_ciclo(
            db,
            tenant_id=t.id,
            ciclo_id=ciclo.id,
            payload=RecadastramentoCicloUpdate(data_fim=FIM + timedelta(days=5)),
        )
    assert ok.data_fim == FIM + timedelta(days=5)


@pytest.mark.asyncio
async def test_editar_janela_nao_remarca_quem_ja_foi_convocado(admin_engine):
    """Decisão da §8 da spec: remarcar em massa prazo já comunicado é decisão
    de produto, e mudar em silêncio seria pior."""
    t = await _provisionar(admin_engine)
    ciclo, conv = await _uma_convocacao(admin_engine, t.id)
    antes = conv.prazo

    async with _sm(admin_engine)() as db:
        await tr.atualizar_ciclo(
            db,
            tenant_id=t.id,
            ciclo_id=ciclo.id,
            payload=RecadastramentoCicloUpdate(data_fim=FIM + timedelta(days=60)),
        )

    depois = (await _convocacoes(admin_engine, t.id, ciclo.id))[0].prazo
    assert depois == antes


@pytest.mark.asyncio
async def test_ciclo_excluido_some_da_lista_e_do_obter(admin_engine):
    t = await _provisionar(admin_engine)
    fica = await _ciclo(admin_engine, t.id)
    sai = await _ciclo(admin_engine, t.id)
    async with _sm(admin_engine)() as db:
        await tr.excluir_ciclo(db, tenant_id=t.id, ciclo_id=sai.id)

    async with _sm(admin_engine)() as db:
        itens, total = await tr.listar_ciclos(db, tenant_id=t.id)
    assert total == 1
    assert [c.id for c in itens] == [fica.id]

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.obter_ciclo(db, tenant_id=t.id, ciclo_id=sai.id)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_listar_ciclos_busca_por_nome_no_servidor(admin_engine):
    """Com ruído: sem ele, um serviço que ignorasse `q` passaria."""
    t = await _provisionar(admin_engine)
    alvo = await _ciclo(admin_engine, t.id, nome="Recadastramento Taxi 2026")
    await _ciclo(admin_engine, t.id, nome="Campanha Escolar 2027")

    async with _sm(admin_engine)() as db:
        itens, total = await tr.listar_ciclos(db, tenant_id=t.id, q="taxi")

    assert total == 1, "`total` tem de acompanhar o filtro, senão a paginação mente"
    assert [c.id for c in itens] == [alvo.id]


@pytest.mark.asyncio
async def test_listar_ciclos_pagina_com_total_do_conjunto_inteiro(admin_engine):
    t = await _provisionar(admin_engine)
    for i in range(3):
        await _ciclo(admin_engine, t.id, nome=f"Ciclo {i} {uuid.uuid4().hex[:4]}")

    async with _sm(admin_engine)() as db:
        itens, total = await tr.listar_ciclos(db, tenant_id=t.id, limit=2)
    assert total == 3
    assert len(itens) == 2


# ======================== Convocações: listagem ============================


@pytest.mark.asyncio
async def test_listar_convocacoes_resolve_nome_dos_dois_tipos(admin_engine):
    t = await _provisionar(admin_engine)
    await _permissionario(admin_engine, t.id, nome="Joana Condutora")
    await _empresa(admin_engine, t.id, razao="Viacao Central")
    ciclo = await _ciclo(admin_engine, t.id)
    async with _sm(admin_engine)() as db:
        await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id)

    async with _sm(admin_engine)() as db:
        itens, total = await tr.listar_convocacoes(
            db, tenant_id=t.id, ciclo_id=ciclo.id
        )

    assert total == 2
    por_tipo = {i["tipo_regulado"]: i for i in itens}
    assert por_tipo["permissionario"]["nome_regulado"] == "Joana Condutora"
    assert por_tipo["empresa"]["nome_regulado"] == "Viacao Central"


@pytest.mark.asyncio
async def test_listar_convocacoes_busca_no_servidor_com_ruido(admin_engine):
    """A busca casa nome de permissionário OU razão social, e `total` segue o
    filtro. O ruído é o que impede o teste de passar por acidente."""
    t = await _provisionar(admin_engine)
    await _permissionario(admin_engine, t.id, nome="Joana Condutora")
    await _permissionario(admin_engine, t.id, nome="Carlos Motorista")
    await _empresa(admin_engine, t.id, razao="Joana Transportes")
    await _empresa(admin_engine, t.id, razao="Viacao Central")
    ciclo = await _ciclo(admin_engine, t.id)
    async with _sm(admin_engine)() as db:
        await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id)

    async with _sm(admin_engine)() as db:
        itens, total = await tr.listar_convocacoes(
            db, tenant_id=t.id, ciclo_id=ciclo.id, q="joana"
        )
    assert total == 2
    assert {i["nome_regulado"] for i in itens} == {
        "Joana Condutora",
        "Joana Transportes",
    }

    # Controle: sem `q`, os quatro aparecem.
    async with _sm(admin_engine)() as db:
        _, total_sem_filtro = await tr.listar_convocacoes(
            db, tenant_id=t.id, ciclo_id=ciclo.id
        )
    assert total_sem_filtro == 4


@pytest.mark.asyncio
async def test_listar_convocacoes_filtra_por_tipo(admin_engine):
    t = await _provisionar(admin_engine)
    await _permissionario(admin_engine, t.id, nome="So Permissionario")
    await _empresa(admin_engine, t.id, razao="So Empresa")
    ciclo = await _ciclo(admin_engine, t.id)
    async with _sm(admin_engine)() as db:
        await tr.gerar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id)

    async with _sm(admin_engine)() as db:
        itens, total = await tr.listar_convocacoes(
            db, tenant_id=t.id, ciclo_id=ciclo.id, tipo="empresa"
        )
    assert total == 1
    assert itens[0]["nome_regulado"] == "So Empresa"

    async with _sm(admin_engine)() as db:
        _, total_perm = await tr.listar_convocacoes(
            db, tenant_id=t.id, ciclo_id=ciclo.id, tipo="permissionario"
        )
    assert total_perm == 1


@pytest.mark.asyncio
async def test_listagem_marca_convocacao_ajustada(admin_engine):
    t = await _provisionar(admin_engine)
    ciclo, conv = await _uma_convocacao(admin_engine, t.id)

    async with _sm(admin_engine)() as db:
        itens, _ = await tr.listar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id)
    assert itens[0]["ajustado"] is False

    async with _sm(admin_engine)() as db:
        await tr.ajustar_prazo(
            db,
            tenant_id=t.id,
            convocacao_id=conv.id,
            payload=RecadastramentoAjustePrazo(
                prazo=ciclo.data_fim, justificativa="Reagendado no balcao"
            ),
        )

    async with _sm(admin_engine)() as db:
        itens, _ = await tr.listar_convocacoes(db, tenant_id=t.id, ciclo_id=ciclo.id)
    assert itens[0]["ajustado"] is True
    assert itens[0]["prazo_original"] != itens[0]["prazo"] or ciclo.data_fim == (
        itens[0]["prazo_original"]
    )


# ============================ Isolamento ===================================


@pytest.mark.asyncio
async def test_ciclo_de_outro_tenant_e_404_nao_403(admin_engine):
    """404 e não 403: responder 403 confirmaria que o id existe."""
    t1 = await _provisionar(admin_engine)
    t2 = await _provisionar(admin_engine)
    ciclo = await _ciclo(admin_engine, t1.id)

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.obter_ciclo(db, tenant_id=t2.id, ciclo_id=ciclo.id)
    assert exc.value.status_code == 404

    # Controle: o dono enxerga.
    async with _sm(admin_engine)() as db:
        assert (await tr.obter_ciclo(db, tenant_id=t1.id, ciclo_id=ciclo.id)).id == (
            ciclo.id
        )


@pytest.mark.asyncio
async def test_geracao_nao_alcanca_regulado_de_outro_tenant(admin_engine):
    t1 = await _provisionar(admin_engine)
    t2 = await _provisionar(admin_engine)
    meu = await _permissionario(admin_engine, t1.id, nome="Meu")
    alheio = await _permissionario(admin_engine, t2.id, nome="Alheio")
    ciclo = await _ciclo(admin_engine, t1.id)

    async with _sm(admin_engine)() as db:
        await tr.gerar_convocacoes(db, tenant_id=t1.id, ciclo_id=ciclo.id)

    ids = {c.id_permissionario for c in await _convocacoes(admin_engine, t1.id, ciclo.id)}
    assert ids == {meu.id}
    assert alheio.id not in ids


@pytest.mark.asyncio
async def test_ajuste_cross_tenant_e_404(admin_engine):
    t1 = await _provisionar(admin_engine)
    t2 = await _provisionar(admin_engine)
    ciclo, conv = await _uma_convocacao(admin_engine, t1.id)

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.ajustar_prazo(
                db,
                tenant_id=t2.id,
                convocacao_id=conv.id,
                payload=RecadastramentoAjustePrazo(
                    prazo=ciclo.data_fim, justificativa="Tentativa de outro tenant"
                ),
            )
    assert exc.value.status_code == 404


# ================================ HTTP =====================================
#
# Testes de service provam a CONSULTA; estes provam a FIAÇÃO. Um `q` declarado
# no router e esquecido na chamada ao service passa em toda a bateria de
# service e devolve, por HTTP, a lista inteira sem filtrar.
#
# E todos usam usuário COMUM, não super-usuário. `require_permission` faz
# bypass de SU antes do `getattr(item, action)`; foi assim que dez rotas deste
# mesmo arquivo ficaram devolvendo 500 para operador não-SU sem que a suíte
# inteira reparasse.

APP = get_settings().app_name


async def _cria_usuario_comum_transporte(engine, tenant_id: int) -> int:
    """Usuário não-SU (nível != 0) cujo grupo recebe a transação
    `transporte_regulado`. Cópia deliberada de
    `test_transporte_p4_relatorio.py::_cria_usuario_comum_transporte` — os dois
    arquivos são independentes, e compartilhar o helper acoplaria a limpeza de
    um à do outro."""
    async with _sm(engine)() as session:
        async with session.begin():
            sistema_id = (
                await session.execute(
                    text(
                        "SELECT id FROM utils.sistema WHERE app = :app "
                        "AND excluido = false LIMIT 1"
                    ),
                    {"app": APP},
                )
            ).scalar_one()
            nivel_id = (
                await session.execute(
                    text(
                        "SELECT id FROM utils.nivel WHERE valor <> 0 "
                        "AND excluido = false LIMIT 1"
                    )
                )
            ).scalar_one_or_none()
            if nivel_id is None:
                nivel_id = (
                    await session.execute(
                        text(
                            "INSERT INTO utils.nivel (nivel, valor, excluido) "
                            "VALUES ('Operacional', 1, false) RETURNING id"
                        )
                    )
                ).scalar_one()
            transacao_id = (
                await session.execute(
                    text(
                        "SELECT id FROM utils.transacao WHERE codigo = "
                        "'transporte_regulado' AND excluido = false LIMIT 1"
                    )
                )
            ).scalar_one()
            uid = (
                await session.execute(
                    text(
                        "INSERT INTO utils.usuario (tenant_id, nome, email, senha, "
                        "cpf, ativo, excluido, app, nivel_acesso_sigilo) VALUES "
                        "(:t, 'Comum Recad', :email, '', :cpf, true, false, :app, "
                        "'interno') RETURNING id"
                    ),
                    {
                        "t": tenant_id,
                        "email": f"comum-recad-{uuid.uuid4().hex[:8]}@t.local",
                        "cpf": uuid.uuid4().hex[:11],
                        "app": APP,
                    },
                )
            ).scalar_one()
            gid = (
                await session.execute(
                    text(
                        "INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, "
                        "grupo, excluido) VALUES (:t, :n, :s, 'Grupo Recad', false) "
                        "RETURNING id"
                    ),
                    {"t": tenant_id, "n": nivel_id, "s": sistema_id},
                )
            ).scalar_one()
            await session.execute(
                text(
                    "INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, "
                    "id_grupo, ativo, excluido, app) "
                    "VALUES (:t, :u, :g, true, false, :app)"
                ),
                {"t": tenant_id, "u": uid, "g": gid, "app": APP},
            )
            await session.execute(
                text(
                    "INSERT INTO utils.grupo_transacao (tenant_id, id_grupo, "
                    "id_transacao, inserir, atualizar, excluir, excluido) "
                    "VALUES (:t, :g, :tr, true, true, true, false)"
                ),
                {"t": tenant_id, "g": gid, "tr": transacao_id},
            )
        return uid


def _as_user(engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    async def _get_user():
        async with _sm(engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == usuario_id))
            ).scalar_one()

    def _setup():
        app.dependency_overrides[get_current_user] = _get_user
        arreio_tenant_http(tenant_id, tenant_slug)

    return _setup


async def _cleanup_tenant_http(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM transporte_regulado.recadastramento_convocacao "
            "WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.recadastramento_ciclo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.empresa WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.permissionario WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


async def _encerrar_arreio(engine, tenant_id: int) -> None:
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    await _cleanup_tenant_http(engine, tenant_id)


@pytest.mark.asyncio
async def test_http_usuario_comum_percorre_o_rito_inteiro(admin_engine):
    """Criar ciclo, gerar, listar e ajustar — tudo como operador NÃO-SU.

    Se algum gate usasse um `action` inválido (o defeito histórico deste
    arquivo foi `"visualizar"`), a resposta seria 500 e não 403: o
    `AttributeError` sobe sem handler. Um SU passaria por tudo sem tocar na
    linha quebrada.
    """
    tenant = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()
        await _permissionario(admin_engine, tenant.id, nome="Joana Condutora")
        await _empresa(admin_engine, tenant.id, razao="Viacao Central")
        uid = await _cria_usuario_comum_transporte(admin_engine, tenant.id)
        _as_user(admin_engine, uid, tenant.id, tenant.slug)()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            base = "/api/v2/transporte-regulado/recadastramento"
            r = await client.post(
                f"{base}/ciclos",
                json={
                    "nome": "Recadastramento HTTP",
                    "data_inicio": INICIO.isoformat(),
                    "data_fim": FIM.isoformat(),
                    "criterio_escalonamento": "final_documento",
                },
            )
            assert r.status_code == 201, r.text
            ciclo_id = r.json()["id"]
            assert r.json()["situacao"] == "rascunho"

            r = await client.post(f"{base}/ciclos/{ciclo_id}/gerar-convocacoes")
            assert r.status_code == 200, r.text
            assert r.json() == {"criadas": 2, "ja_existentes": 0}

            r = await client.get(f"{base}/ciclos/{ciclo_id}/convocacoes")
            assert r.status_code == 200, r.text
            corpo = r.json()
            # Contrato paginado de verdade: `.items`, não lista nua. Declarar
            # `X[]` onde o backend devolve `Paginated[X]` deixa o tsc verde e
            # estoura no navegador com "…map is not a function".
            assert corpo["total"] == 2
            assert {i["nome_regulado"] for i in corpo["items"]} == {
                "Joana Condutora",
                "Viacao Central",
            }

            conv_id = corpo["items"][0]["id"]
            r = await client.put(
                f"{base}/convocacoes/{conv_id}/prazo",
                json={"prazo": FIM.isoformat(), "justificativa": "Remarcado no balcao"},
            )
            assert r.status_code == 200, r.text
            # O autor vem do TOKEN, nunca do payload.
            assert r.json()["ajustado_por"] == uid
            assert r.json()["ajustado"] is True
            # E a resposta do ajuste tem a MESMA forma da listagem: nome
            # resolvido, nao string vazia. Devolver "" num campo tipado como
            # `str` obrigaria a tela a recarregar a lista so para exibir o nome.
            assert r.json()["nome_regulado"] == corpo["items"][0]["nome_regulado"]
            assert r.json()["nome_regulado"] != ""
    finally:
        await _encerrar_arreio(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_busca_de_convocacao_atravessa_a_paginacao(admin_engine):
    """`q` sai do HTTP e chega ao SQL — acha fora da página corrente.

    `page_size=1` força o cenário: sem busca no servidor, o convocado procurado
    não estaria na resposta, e a tela diria que ele não existe.
    """
    tenant = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()
        for nome in ("Aaa Primeiro", "Bbb Segundo", "Zzz Procurado"):
            await _permissionario(admin_engine, tenant.id, nome=nome)
        ciclo = await _ciclo(admin_engine, tenant.id)
        async with _sm(admin_engine)() as db:
            await tr.gerar_convocacoes(db, tenant_id=tenant.id, ciclo_id=ciclo.id)
        uid = await _cria_usuario_comum_transporte(admin_engine, tenant.id)
        _as_user(admin_engine, uid, tenant.id, tenant.slug)()

        rota = (
            "/api/v2/transporte-regulado/recadastramento/ciclos/"
            f"{ciclo.id}/convocacoes"
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(rota, params={"page_size": 1, "q": "procurado"})
            assert r.status_code == 200, r.text
            corpo = r.json()
            assert corpo["total"] == 1
            assert corpo["items"][0]["nome_regulado"] == "Zzz Procurado"

            # Controle: sem `q`, `page_size=1` devolve outra pessoa e total 3.
            r = await client.get(rota, params={"page_size": 1})
            assert r.json()["total"] == 3
    finally:
        await _encerrar_arreio(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_sem_o_modulo_contratado_e_403(admin_engine):
    """O gate de contratação nega antes de qualquer coisa — e nega para o
    usuário comum COM a transação concedida, que é o caso que importa."""
    tenant = await _provisionar(admin_engine)
    try:
        # `provisionar_tenant` já contrata os módulos iniciais; descontratar é
        # o que monta o cenário. Confiar num tenant "recém-criado e portanto
        # sem módulos" faria o teste passar pelo motivo errado — foi o que
        # aconteceu na primeira escrita dele.
        async with _sm(admin_engine)() as s:
            await s.execute(
                text(
                    "DELETE FROM aprimora_py.tenant_modulo tm USING aprimora_py.modulo m "
                    "WHERE tm.id_modulo = m.id AND tm.tenant_id = :t AND m.slug = 'transporte'"
                ),
                {"t": tenant.id},
            )
            await s.commit()
        uid = await _cria_usuario_comum_transporte(admin_engine, tenant.id)
        _as_user(admin_engine, uid, tenant.id, tenant.slug)()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/api/v2/transporte-regulado/recadastramento/ciclos"
            )
        assert r.status_code == 403, r.text

        # Controle: contratado, o MESMO usuário passa. Sem isto, um 403 por
        # qualquer outro motivo (usuário sem grupo, rota inexistente) passaria.
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/api/v2/transporte-regulado/recadastramento/ciclos"
            )
        assert r.status_code == 200, r.text
    finally:
        await _encerrar_arreio(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_ajuste_sem_justificativa_e_422_na_borda(admin_engine):
    """O schema barra na borda (422), e o controle prova que o bom passa."""
    tenant = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()
        await _permissionario(admin_engine, tenant.id)
        ciclo = await _ciclo(admin_engine, tenant.id)
        async with _sm(admin_engine)() as db:
            await tr.gerar_convocacoes(db, tenant_id=tenant.id, ciclo_id=ciclo.id)
        conv = (await _convocacoes(admin_engine, tenant.id, ciclo.id))[0]
        uid = await _cria_usuario_comum_transporte(admin_engine, tenant.id)
        _as_user(admin_engine, uid, tenant.id, tenant.slug)()

        rota = (
            "/api/v2/transporte-regulado/recadastramento/convocacoes/"
            f"{conv.id}/prazo"
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.put(rota, json={"prazo": FIM.isoformat()})
            assert r.status_code == 422, r.text
            r = await client.put(
                rota,
                json={"prazo": FIM.isoformat(), "justificativa": "Motivo do balcao"},
            )
            assert r.status_code == 200, r.text
    finally:
        await _encerrar_arreio(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_null_explicito_nao_derruba_a_atualizacao(admin_engine):
    """`{"nome": null}` num PUT e um `setattr` fiel ao payload gravariam NULL
    numa coluna NOT NULL — IntegrityError, ou seja, 500 num erro de ENTRADA.

    Todo campo do `Update` e opcional (para permitir PATCH parcial), entao nada
    no schema impede o cliente de mandar isso. O controle positivo prova que a
    atualizacao normal continua passando, e que `observacoes: null` — onde o
    nulo e apagar de proposito — de fato apaga.
    """
    tenant = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()
        async with _sm(admin_engine)() as db:
            ciclo = await tr.criar_ciclo(
                db,
                tenant_id=tenant.id,
                payload=RecadastramentoCicloCreate(
                    nome="Ciclo com observacoes",
                    data_inicio=INICIO,
                    data_fim=FIM,
                    observacoes="texto a apagar",
                ),
            )
        uid = await _cria_usuario_comum_transporte(admin_engine, tenant.id)
        _as_user(admin_engine, uid, tenant.id, tenant.slug)()

        rota = (
            f"/api/v2/transporte-regulado/recadastramento/ciclos/{ciclo.id}"
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.put(
                rota, json={"nome": None, "data_inicio": None, "situacao": None}
            )
            assert r.status_code == 200, r.text
            assert r.json()["nome"] == "Ciclo com observacoes"
            assert r.json()["data_inicio"] == INICIO.isoformat()
            assert r.json()["situacao"] == "rascunho"

            # Controle 1: atualizacao normal continua funcionando.
            r = await client.put(rota, json={"nome": "Nome novo"})
            assert r.status_code == 200, r.text
            assert r.json()["nome"] == "Nome novo"

            # Controle 2: em `observacoes`, o nulo APAGA — nao e descartado.
            r = await client.put(rota, json={"observacoes": None})
            assert r.status_code == 200, r.text
            assert r.json()["observacoes"] is None
    finally:
        await _encerrar_arreio(admin_engine, tenant.id)
