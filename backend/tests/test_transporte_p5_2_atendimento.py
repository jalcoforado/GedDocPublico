"""Transporte P5.2 — atendimento: checklist, amarra da vistoria e fechamento.

Spec: `docs/superpowers/specs/2026-08-04-transporte-p5-2-recadastramento-atendimento-design.md`.

Dois testes carregam esta fatia:

`test_indeferir_sem_completude_e_permitido` — a **assimetria central**. Deferir
exige checklist completo; indeferir não. Uma bateria que só exercitasse o
caminho feliz nunca a veria, e o defeito (exigir completude para indeferir)
deixaria o sistema só sabendo dizer sim.

`test_vistoria_condicional_nao_satisfaz` — `condicional` é o valor que parece
aprovado e não é. Nada além de um teste impede alguém de escrever
`resultado != "reprovado"`.

Toda negativa tem controle positivo na mesma sessão.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import RecadastramentoDecisao, RecadastramentoMarca, Usuario
from app.schemas.transporte_regulado import (
    EmpresaCreate,
    PermissionarioCreate,
    RecadastramentoCicloCreate,
    RecadastramentoCicloUpdate,
    RecadastramentoDecisaoInput,
    RecadastramentoItemCreate,
    RecadastramentoItemUpdate,
    RecadastramentoMarcarInput,
    VeiculoReguladoCreate,
    VeiculoVistoriaCreate,
)
from app.services import transporte_regulado as tr
from app.services.modulos import contratar
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name
HOJE = date.today()
FIM = HOJE + timedelta(days=30)


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _digitos(n: int) -> str:
    return uuid.uuid4().int.__str__()[:n]


async def _provisionar(engine):
    slug = f"p52-{uuid.uuid4().hex[:8]}"
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref P5.2",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    return tenant


async def _um_usuario(engine, tenant_id: int) -> int:
    """Id de um usuário REAL do tenant.

    Cravar `usuario_id=1` passa no banco de dev e estoura
    `ForeignKeyViolationError` no CI, que roda em banco limpo. Foi o único
    vermelho da P5.1.
    """
    async with _sm(engine)() as s:
        return (
            await s.execute(
                text(
                    "SELECT id FROM utils.usuario WHERE tenant_id = :t "
                    "AND excluido = false ORDER BY id LIMIT 1"
                ),
                {"t": tenant_id},
            )
        ).scalar_one()


async def _permissionario(engine, tenant_id: int, *, nome="Perm"):
    async with _sm(engine)() as db:
        return await tr.criar_permissionario(
            db,
            tenant_id=tenant_id,
            payload=PermissionarioCreate(
                nome=nome, cpf=_digitos(11), tipo_servico="taxi", situacao="ativo"
            ),
        )


async def _empresa(engine, tenant_id: int, *, razao="Empresa"):
    async with _sm(engine)() as db:
        return await tr.criar_empresa(
            db,
            tenant_id=tenant_id,
            payload=EmpresaCreate(
                razao_social=razao,
                cnpj=_digitos(14),
                tipo_servico="taxi",
                situacao="ativa",
            ),
        )


async def _veiculo(engine, tenant_id: int, *, perm_id=None, empresa_id=None,
                   situacao="ativo"):
    async with _sm(engine)() as db:
        return await tr.criar_veiculo(
            db,
            tenant_id=tenant_id,
            payload=VeiculoReguladoCreate(
                placa=uuid.uuid4().hex[:7].upper(),
                marca="Marca",
                modelo="Modelo",
                tipo_servico="taxi",
                id_permissionario=perm_id,
                id_empresa=empresa_id,
                situacao=situacao,
            ),
        )


async def _vistoria(engine, tenant_id: int, veiculo_id: int, auditor_id: int, *,
                    resultado="aprovado", validade=None):
    async with _sm(engine)() as db:
        return await tr.criar_vistoria(
            db,
            tenant_id=tenant_id,
            veiculo_id=veiculo_id,
            auditor_id=auditor_id,
            payload=VeiculoVistoriaCreate(
                resultado=resultado,
                parecer="Parecer de vistoria para teste",
                data_vistoria=datetime.utcnow(),
                data_validade=validade,
            ),
        )


async def _item(engine, tenant_id: int, *, descricao=None, aplica_a="ambos",
                obrigatorio=True, ativo=True, ordem=0):
    async with _sm(engine)() as db:
        return await tr.criar_item_recadastramento(
            db,
            tenant_id=tenant_id,
            payload=RecadastramentoItemCreate(
                descricao=descricao or f"Documento {uuid.uuid4().hex[:6]}",
                aplica_a=aplica_a,
                obrigatorio=obrigatorio,
                ativo=ativo,
                ordem=ordem,
            ),
        )


async def _convocacao(engine, tenant_id: int, regulado, *, ciclo=None):
    """Ciclo + geração, devolvendo a convocação daquele regulado."""
    if ciclo is None:
        async with _sm(engine)() as db:
            ciclo = await tr.criar_ciclo(
                db,
                tenant_id=tenant_id,
                payload=RecadastramentoCicloCreate(
                    nome=f"Ciclo {uuid.uuid4().hex[:6]}",
                    data_inicio=HOJE,
                    data_fim=FIM,
                ),
            )
    async with _sm(engine)() as db:
        await tr.gerar_convocacoes(db, tenant_id=tenant_id, ciclo_id=ciclo.id)
    async with _sm(engine)() as db:
        itens, _ = await tr.listar_convocacoes(
            db, tenant_id=tenant_id, ciclo_id=ciclo.id
        )
    alvo = [i for i in itens if i["nome_regulado"] == getattr(
        regulado, "nome", None) or i["nome_regulado"] == getattr(
        regulado, "razao_social", None)]
    assert alvo, "o regulado não foi convocado — cenário montado errado"
    async with _sm(engine)() as db:
        conv = await tr.obter_convocacao(
            db, tenant_id=tenant_id, convocacao_id=alvo[0]["id"]
        )
    return ciclo, conv


async def _marcar(engine, tenant_id, conv_id, item_id, marcado=True, uid=None,
                  obs=None):
    async with _sm(engine)() as db:
        return await tr.marcar_item_recadastramento(
            db,
            tenant_id=tenant_id,
            convocacao_id=conv_id,
            item_id=item_id,
            payload=RecadastramentoMarcarInput(marcado=marcado, observacao=obs),
            usuario_id=uid,
        )


# ============================ Catálogo (D6, D7) ============================


@pytest.mark.asyncio
async def test_item_de_empresa_nao_aparece_para_permissionario(admin_engine):
    """D7, e o teste precisa dos DOIS tipos no mesmo tenant.

    Com só um permissionário, um filtro invertido (`aplica_a == "empresa"`)
    devolveria lista vazia e o teste que só contasse itens passaria achando que
    o cenário é que estava vazio.
    """
    t = await _provisionar(admin_engine)
    so_perm = await _item(admin_engine, t.id, descricao="CNH", aplica_a="permissionario")
    so_emp = await _item(admin_engine, t.id, descricao="Contrato social", aplica_a="empresa")
    ambos = await _item(admin_engine, t.id, descricao="Comprovante", aplica_a="ambos")

    async with _sm(admin_engine)() as db:
        do_perm = {
            i.id for i in await tr.itens_aplicaveis(
                db, tenant_id=t.id, tipo_regulado="permissionario"
            )
        }
        da_emp = {
            i.id for i in await tr.itens_aplicaveis(
                db, tenant_id=t.id, tipo_regulado="empresa"
            )
        }

    assert do_perm == {so_perm.id, ambos.id}, "ficha do permissionário errada"
    assert da_emp == {so_emp.id, ambos.id}, "ficha da empresa errada"


@pytest.mark.asyncio
async def test_item_inativo_ou_excluido_sai_das_exigencias(admin_engine):
    t = await _provisionar(admin_engine)
    vivo = await _item(admin_engine, t.id, descricao="Vivo")
    inativo = await _item(admin_engine, t.id, descricao="Inativo", ativo=False)
    removido = await _item(admin_engine, t.id, descricao="Removido")
    async with _sm(admin_engine)() as db:
        await tr.excluir_item_recadastramento(
            db, tenant_id=t.id, item_id=removido.id
        )

    async with _sm(admin_engine)() as db:
        ids = {
            i.id for i in await tr.itens_aplicaveis(
                db, tenant_id=t.id, tipo_regulado="permissionario"
            )
        }
    assert ids == {vivo.id}
    assert inativo.id not in ids and removido.id not in ids


@pytest.mark.asyncio
async def test_descricao_de_item_e_unica_por_tenant(admin_engine):
    """Negativa com controle: a MESMA descrição passa em outro tenant."""
    t1 = await _provisionar(admin_engine)
    t2 = await _provisionar(admin_engine)
    await _item(admin_engine, t1.id, descricao="CNH válida")

    with pytest.raises(HTTPException) as exc:
        await _item(admin_engine, t1.id, descricao="CNH válida")
    assert exc.value.status_code == 409

    outro = await _item(admin_engine, t2.id, descricao="CNH válida")
    assert outro.id


@pytest.mark.asyncio
async def test_null_explicito_no_update_do_item_nao_derruba(admin_engine):
    """Todo campo do `Update` é opcional, então `{"descricao": null}` chega.
    Em coluna NOT NULL isso seria IntegrityError — 500 num erro de ENTRADA."""
    t = await _provisionar(admin_engine)
    item = await _item(admin_engine, t.id, descricao="Original", ordem=3)

    async with _sm(admin_engine)() as db:
        mantido = await tr.atualizar_item_recadastramento(
            db,
            tenant_id=t.id,
            item_id=item.id,
            payload=RecadastramentoItemUpdate(
                descricao=None, aplica_a=None, ordem=None
            ),
        )
    assert mantido.descricao == "Original"
    assert mantido.ordem == 3

    # Controle: atualização de verdade continua funcionando.
    async with _sm(admin_engine)() as db:
        mudado = await tr.atualizar_item_recadastramento(
            db,
            tenant_id=t.id,
            item_id=item.id,
            payload=RecadastramentoItemUpdate(descricao="Novo nome"),
        )
    assert mudado.descricao == "Novo nome"


# ========================= Marcação (append-only) ==========================


@pytest.mark.asyncio
async def test_marcar_e_append_only_e_vale_a_mais_recente(admin_engine):
    """Marcar, desmarcar, marcar: TRÊS linhas, e o estado é a última.

    Se a marcação sobrescrevesse a linha, o rastro de quem voltou atrás
    sumiria — que é justamente o que se audita num balcão.
    """
    t = await _provisionar(admin_engine)
    item = await _item(admin_engine, t.id)
    p = await _permissionario(admin_engine, t.id, nome="Fulano")
    _, conv = await _convocacao(admin_engine, t.id, p)

    await _marcar(admin_engine, t.id, conv.id, item.id, True, obs="primeira")
    await _marcar(admin_engine, t.id, conv.id, item.id, False, obs="voltei atras")
    await _marcar(admin_engine, t.id, conv.id, item.id, True, obs="confirmado")

    async with _sm(admin_engine)() as db:
        linhas = (
            await db.execute(
                select(RecadastramentoMarca).where(
                    RecadastramentoMarca.id_convocacao == conv.id,
                    RecadastramentoMarca.id_item == item.id,
                )
            )
        ).scalars().all()
    assert len(linhas) == 3, "a marcação sobrescreveu em vez de acrescentar"

    async with _sm(admin_engine)() as db:
        estado = await tr.estado_do_checklist(
            db, tenant_id=t.id, convocacao_id=conv.id
        )
    assert estado[0]["marcado"] is True
    assert estado[0]["observacao"] == "confirmado"


@pytest.mark.asyncio
async def test_item_nunca_tocado_e_none_e_nao_false(admin_engine):
    """`None` (ninguém olhou) é diferente de `False` (olhou e não está em
    ordem). Colapsar os dois perderia informação real do balcão."""
    t = await _provisionar(admin_engine)
    intocado = await _item(admin_engine, t.id, descricao="Intocado", ordem=1)
    negado = await _item(admin_engine, t.id, descricao="Negado", ordem=2)
    p = await _permissionario(admin_engine, t.id, nome="Fulano")
    _, conv = await _convocacao(admin_engine, t.id, p)
    await _marcar(admin_engine, t.id, conv.id, negado.id, False)

    async with _sm(admin_engine)() as db:
        por_item = {
            i["id_item"]: i
            for i in await tr.estado_do_checklist(
                db, tenant_id=t.id, convocacao_id=conv.id
            )
        }
    assert por_item[intocado.id]["marcado"] is None
    assert por_item[negado.id]["marcado"] is False


@pytest.mark.asyncio
async def test_primeira_marcacao_leva_para_em_analise(admin_engine):
    t = await _provisionar(admin_engine)
    item = await _item(admin_engine, t.id)
    p = await _permissionario(admin_engine, t.id, nome="Fulano")
    _, conv = await _convocacao(admin_engine, t.id, p)
    assert conv.situacao == "convocado"

    await _marcar(admin_engine, t.id, conv.id, item.id, True)

    async with _sm(admin_engine)() as db:
        atual = await tr.obter_convocacao(
            db, tenant_id=t.id, convocacao_id=conv.id
        )
    assert atual.situacao == "em_analise"


@pytest.mark.asyncio
async def test_marcar_item_que_nao_se_aplica_e_400(admin_engine):
    """Sem isto a API aceitaria marcar 'contrato social' na ficha de uma
    pessoa física, e o item nem apareceria na tela depois."""
    t = await _provisionar(admin_engine)
    so_empresa = await _item(admin_engine, t.id, descricao="Contrato", aplica_a="empresa")
    para_todos = await _item(admin_engine, t.id, descricao="Comprovante", aplica_a="ambos")
    p = await _permissionario(admin_engine, t.id, nome="Fulano")
    _, conv = await _convocacao(admin_engine, t.id, p)

    with pytest.raises(HTTPException) as exc:
        await _marcar(admin_engine, t.id, conv.id, so_empresa.id, True)
    assert exc.value.status_code == 400

    # Controle: o item que se aplica passa.
    assert await _marcar(admin_engine, t.id, conv.id, para_todos.id, True)


# ====================== Amarra da vistoria (D8, A1, A2) ====================


@pytest.mark.asyncio
async def test_veiculo_sem_vistoria_aprovada_fica_pendente(admin_engine):
    t = await _provisionar(admin_engine)
    uid = await _um_usuario(admin_engine, t.id)
    p = await _permissionario(admin_engine, t.id, nome="Fulano")
    sem = await _veiculo(admin_engine, t.id, perm_id=p.id)
    _, conv = await _convocacao(admin_engine, t.id, p)

    async with _sm(admin_engine)() as db:
        v = await tr.situacao_vistorias(db, tenant_id=t.id, conv=conv)
    assert v["satisfeita"] is False
    assert [x["id_veiculo"] for x in v["pendentes"]] == [sem.id]

    # Controle: com vistoria aprovada, satisfaz.
    await _vistoria(admin_engine, t.id, sem.id, uid, validade=FIM)
    async with _sm(admin_engine)() as db:
        v = await tr.situacao_vistorias(db, tenant_id=t.id, conv=conv)
    assert v["satisfeita"] is True
    assert v["pendentes"] == []


@pytest.mark.asyncio
async def test_vistoria_condicional_nao_satisfaz(admin_engine):
    """`condicional` é o valor que PARECE aprovado. Nada além deste teste
    impede alguém de escrever `resultado != "reprovado"`."""
    t = await _provisionar(admin_engine)
    uid = await _um_usuario(admin_engine, t.id)
    p = await _permissionario(admin_engine, t.id, nome="Fulano")
    veic = await _veiculo(admin_engine, t.id, perm_id=p.id)
    _, conv = await _convocacao(admin_engine, t.id, p)
    await _vistoria(
        admin_engine, t.id, veic.id, uid, resultado="condicional", validade=FIM
    )

    async with _sm(admin_engine)() as db:
        v = await tr.situacao_vistorias(db, tenant_id=t.id, conv=conv)
    assert v["satisfeita"] is False

    # Controle: aprovada no mesmo veículo satisfaz.
    await _vistoria(admin_engine, t.id, veic.id, uid, validade=FIM)
    async with _sm(admin_engine)() as db:
        v = await tr.situacao_vistorias(db, tenant_id=t.id, conv=conv)
    assert v["satisfeita"] is True


@pytest.mark.asyncio
async def test_vistoria_vencida_nao_satisfaz_e_sem_validade_satisfaz(admin_engine):
    """A2, nos dois sentidos, com dois veículos para não confundir os casos."""
    t = await _provisionar(admin_engine)
    uid = await _um_usuario(admin_engine, t.id)
    p = await _permissionario(admin_engine, t.id, nome="Fulano")
    vencido = await _veiculo(admin_engine, t.id, perm_id=p.id)
    _, conv = await _convocacao(admin_engine, t.id, p)
    await _vistoria(
        admin_engine, t.id, vencido.id, uid, validade=HOJE - timedelta(days=1)
    )

    async with _sm(admin_engine)() as db:
        v = await tr.situacao_vistorias(db, tenant_id=t.id, conv=conv)
    assert v["satisfeita"] is False, "vistoria vencida foi aceita"

    # A2: validade nula conta como válida (cadastro herdado costuma não ter).
    await _vistoria(admin_engine, t.id, vencido.id, uid, validade=None)
    async with _sm(admin_engine)() as db:
        v = await tr.situacao_vistorias(db, tenant_id=t.id, conv=conv)
    assert v["satisfeita"] is True


@pytest.mark.asyncio
async def test_regulado_sem_veiculo_satisfaz_por_vacuidade_mas_e_distinguivel(
    admin_engine,
):
    """Assunção A1. O teste afirma sobre os DOIS campos: só o booleano não
    distinguiria 'nenhum veículo cadastrado' de 'todos em dia', e é essa
    distinção que a tela precisa mostrar."""
    t = await _provisionar(admin_engine)
    uid = await _um_usuario(admin_engine, t.id)
    sem_veiculo = await _permissionario(admin_engine, t.id, nome="Sem veiculo")
    com_veiculo = await _permissionario(admin_engine, t.id, nome="Com veiculo")
    veic = await _veiculo(admin_engine, t.id, perm_id=com_veiculo.id)
    await _vistoria(admin_engine, t.id, veic.id, uid, validade=FIM)
    ciclo, conv_sem = await _convocacao(admin_engine, t.id, sem_veiculo)
    _, conv_com = await _convocacao(admin_engine, t.id, com_veiculo, ciclo=ciclo)

    async with _sm(admin_engine)() as db:
        v_sem = await tr.situacao_vistorias(db, tenant_id=t.id, conv=conv_sem)
        v_com = await tr.situacao_vistorias(db, tenant_id=t.id, conv=conv_com)

    assert v_sem["satisfeita"] is True
    assert v_sem["total_veiculos_ativos"] == 0
    # As duas satisfazem e NÃO significam a mesma coisa.
    assert v_com["satisfeita"] is True
    assert v_com["total_veiculos_ativos"] == 1


@pytest.mark.asyncio
async def test_veiculo_nao_ativo_fica_fora_da_conta(admin_engine):
    t = await _provisionar(admin_engine)
    p = await _permissionario(admin_engine, t.id, nome="Fulano")
    await _veiculo(admin_engine, t.id, perm_id=p.id, situacao="suspenso")
    await _veiculo(admin_engine, t.id, perm_id=p.id, situacao="inativo")
    _, conv = await _convocacao(admin_engine, t.id, p)

    async with _sm(admin_engine)() as db:
        v = await tr.situacao_vistorias(db, tenant_id=t.id, conv=conv)
    assert v["total_veiculos_ativos"] == 0
    assert v["satisfeita"] is True

    # Controle: um ativo sem vistoria entra na conta e trava.
    await _veiculo(admin_engine, t.id, perm_id=p.id, situacao="ativo")
    async with _sm(admin_engine)() as db:
        v = await tr.situacao_vistorias(db, tenant_id=t.id, conv=conv)
    assert v["total_veiculos_ativos"] == 1
    assert v["satisfeita"] is False


@pytest.mark.asyncio
async def test_vistoria_da_empresa_usa_o_vinculo_de_empresa(admin_engine):
    """O ramo `id_empresa` do filtro de veículos. Sem este teste, um serviço
    que só olhasse `id_permissionario` daria 'satisfeita' para toda empresa,
    por vacuidade — verde silencioso."""
    t = await _provisionar(admin_engine)
    e = await _empresa(admin_engine, t.id, razao="Viacao Central")
    veic = await _veiculo(admin_engine, t.id, empresa_id=e.id)
    _, conv = await _convocacao(admin_engine, t.id, e)

    async with _sm(admin_engine)() as db:
        v = await tr.situacao_vistorias(db, tenant_id=t.id, conv=conv)
    assert v["total_veiculos_ativos"] == 1, "o veículo da empresa não foi visto"
    assert v["satisfeita"] is False
    assert v["pendentes"][0]["id_veiculo"] == veic.id


# ============================== Fechamento =================================


async def _cenario_completo(engine, tenant_id):
    """Permissionário com um item obrigatório e um veículo com vistoria em dia
    — tudo pronto para deferir."""
    uid = await _um_usuario(engine, tenant_id)
    item = await _item(engine, tenant_id, descricao="CNH")
    p = await _permissionario(engine, tenant_id, nome="Fulano")
    veic = await _veiculo(engine, tenant_id, perm_id=p.id)
    await _vistoria(engine, tenant_id, veic.id, uid, validade=FIM)
    ciclo, conv = await _convocacao(engine, tenant_id, p)
    return uid, item, ciclo, conv


@pytest.mark.asyncio
async def test_deferir_exige_completude(admin_engine):
    t = await _provisionar(admin_engine)
    uid, item, _, conv = await _cenario_completo(admin_engine, t.id)

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.decidir_recadastramento(
                db, tenant_id=t.id, convocacao_id=conv.id, tipo="deferimento",
                payload=RecadastramentoDecisaoInput(parecer="Tudo certo"),
                usuario_id=uid,
            )
    assert exc.value.status_code == 409

    # Controle: marcado o obrigatório, defere.
    await _marcar(admin_engine, t.id, conv.id, item.id, True, uid)
    async with _sm(admin_engine)() as db:
        d = await tr.decidir_recadastramento(
            db, tenant_id=t.id, convocacao_id=conv.id, tipo="deferimento",
            payload=RecadastramentoDecisaoInput(parecer="Documentacao conferida"),
            usuario_id=uid,
        )
    assert d.tipo == "deferimento"
    assert d.id_usuario == uid

    async with _sm(admin_engine)() as db:
        atual = await tr.obter_convocacao(db, tenant_id=t.id, convocacao_id=conv.id)
    assert atual.situacao == "deferido"


@pytest.mark.asyncio
async def test_indeferir_sem_completude_e_permitido(admin_engine):
    """**A assimetria central.** Indeferir por falta de documento é o caso real;
    um sistema que exigisse completude para indeferir só saberia dizer sim."""
    t = await _provisionar(admin_engine)
    uid, item, _, conv = await _cenario_completo(admin_engine, t.id)

    # Nada marcado, e ainda assim indefere.
    async with _sm(admin_engine)() as db:
        d = await tr.decidir_recadastramento(
            db, tenant_id=t.id, convocacao_id=conv.id, tipo="indeferimento",
            payload=RecadastramentoDecisaoInput(parecer="Nao apresentou a CNH"),
            usuario_id=uid,
        )
    assert d.tipo == "indeferimento"

    async with _sm(admin_engine)() as db:
        atual = await tr.obter_convocacao(db, tenant_id=t.id, convocacao_id=conv.id)
    assert atual.situacao == "indeferido"


@pytest.mark.asyncio
async def test_vistoria_pendente_trava_o_deferimento(admin_engine):
    """Checklist completo não basta: a amarra da vistoria é a outra metade."""
    t = await _provisionar(admin_engine)
    uid = await _um_usuario(admin_engine, t.id)
    item = await _item(admin_engine, t.id, descricao="CNH")
    p = await _permissionario(admin_engine, t.id, nome="Fulano")
    veic = await _veiculo(admin_engine, t.id, perm_id=p.id)
    _, conv = await _convocacao(admin_engine, t.id, p)
    await _marcar(admin_engine, t.id, conv.id, item.id, True, uid)

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.decidir_recadastramento(
                db, tenant_id=t.id, convocacao_id=conv.id, tipo="deferimento",
                payload=RecadastramentoDecisaoInput(parecer="Documentos ok"),
                usuario_id=uid,
            )
    assert exc.value.status_code == 409

    # Controle: com a vistoria em dia, defere.
    await _vistoria(admin_engine, t.id, veic.id, uid, validade=FIM)
    async with _sm(admin_engine)() as db:
        d = await tr.decidir_recadastramento(
            db, tenant_id=t.id, convocacao_id=conv.id, tipo="deferimento",
            payload=RecadastramentoDecisaoInput(parecer="Tudo conferido"),
            usuario_id=uid,
        )
    assert d.tipo == "deferimento"


@pytest.mark.asyncio
async def test_item_nao_obrigatorio_e_item_inativo_nao_travam(admin_engine):
    t = await _provisionar(admin_engine)
    uid = await _um_usuario(admin_engine, t.id)
    obrigatorio = await _item(admin_engine, t.id, descricao="CNH")
    await _item(admin_engine, t.id, descricao="Foto", obrigatorio=False)
    await _item(admin_engine, t.id, descricao="Antigo", ativo=False)
    p = await _permissionario(admin_engine, t.id, nome="Fulano")
    veic = await _veiculo(admin_engine, t.id, perm_id=p.id)
    await _vistoria(admin_engine, t.id, veic.id, uid, validade=FIM)
    _, conv = await _convocacao(admin_engine, t.id, p)

    # Só o obrigatório marcado — e isso basta.
    await _marcar(admin_engine, t.id, conv.id, obrigatorio.id, True, uid)
    async with _sm(admin_engine)() as db:
        situacao = await tr.situacao_atendimento(
            db, tenant_id=t.id, convocacao_id=conv.id
        )
    assert situacao["pode_deferir"] is True
    assert situacao["itens_obrigatorios_pendentes"] == []
    # O inativo nem aparece na ficha.
    assert "Antigo" not in [i["descricao"] for i in situacao["itens"]]


@pytest.mark.asyncio
async def test_parecer_e_obrigatorio(admin_engine):
    t = await _provisionar(admin_engine)
    uid, item, _, conv = await _cenario_completo(admin_engine, t.id)

    with pytest.raises(ValueError):
        RecadastramentoDecisaoInput(parecer="     ")

    class _SemParecer:
        parecer = "   "

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.decidir_recadastramento(
                db, tenant_id=t.id, convocacao_id=conv.id, tipo="indeferimento",
                payload=_SemParecer(), usuario_id=uid,
            )
    assert exc.value.status_code == 400

    # Controle: com parecer, passa.
    async with _sm(admin_engine)() as db:
        assert await tr.decidir_recadastramento(
            db, tenant_id=t.id, convocacao_id=conv.id, tipo="indeferimento",
            payload=RecadastramentoDecisaoInput(parecer="Faltou documento"),
            usuario_id=uid,
        )


@pytest.mark.asyncio
async def test_reabrir_preserva_o_historico(admin_engine):
    """Reabrir existe para que um deferimento errado não vire dívida de SQL.
    E as decisões anteriores continuam lá — sem isso, reabrir pareceria não ter
    acontecido."""
    t = await _provisionar(admin_engine)
    uid, item, _, conv = await _cenario_completo(admin_engine, t.id)
    await _marcar(admin_engine, t.id, conv.id, item.id, True, uid)
    async with _sm(admin_engine)() as db:
        await tr.decidir_recadastramento(
            db, tenant_id=t.id, convocacao_id=conv.id, tipo="deferimento",
            payload=RecadastramentoDecisaoInput(parecer="Deferido por engano"),
            usuario_id=uid,
        )

    async with _sm(admin_engine)() as db:
        r = await tr.reabrir_recadastramento(
            db, tenant_id=t.id, convocacao_id=conv.id,
            payload=RecadastramentoDecisaoInput(parecer="Reaberto: documento falso"),
            usuario_id=uid,
        )
    assert r.tipo == "reabertura"

    async with _sm(admin_engine)() as db:
        atual = await tr.obter_convocacao(db, tenant_id=t.id, convocacao_id=conv.id)
        historico = await tr.listar_decisoes(
            db, tenant_id=t.id, convocacao_id=conv.id
        )
    assert atual.situacao == "em_analise"
    assert [d.tipo for d in historico] == ["deferimento", "reabertura"]

    # E depois de reaberta dá para decidir de novo.
    async with _sm(admin_engine)() as db:
        await tr.decidir_recadastramento(
            db, tenant_id=t.id, convocacao_id=conv.id, tipo="indeferimento",
            payload=RecadastramentoDecisaoInput(parecer="Indeferido apos revisao"),
            usuario_id=uid,
        )
    async with _sm(admin_engine)() as db:
        historico = await tr.listar_decisoes(
            db, tenant_id=t.id, convocacao_id=conv.id
        )
    assert [d.tipo for d in historico] == [
        "deferimento", "reabertura", "indeferimento"
    ]


@pytest.mark.asyncio
async def test_convocacao_decidida_recusa_marcacao_ate_reabrir(admin_engine):
    """Mexer no checklist depois do parecer mudaria a base da decisão sem mudar
    a decisão."""
    t = await _provisionar(admin_engine)
    uid, item, _, conv = await _cenario_completo(admin_engine, t.id)
    await _marcar(admin_engine, t.id, conv.id, item.id, True, uid)
    async with _sm(admin_engine)() as db:
        await tr.decidir_recadastramento(
            db, tenant_id=t.id, convocacao_id=conv.id, tipo="deferimento",
            payload=RecadastramentoDecisaoInput(parecer="Conferido"), usuario_id=uid,
        )

    with pytest.raises(HTTPException) as exc:
        await _marcar(admin_engine, t.id, conv.id, item.id, False, uid)
    assert exc.value.status_code == 409

    # Controle: depois de reabrir, marca de novo.
    async with _sm(admin_engine)() as db:
        await tr.reabrir_recadastramento(
            db, tenant_id=t.id, convocacao_id=conv.id,
            payload=RecadastramentoDecisaoInput(parecer="Reaberto para revisao"),
            usuario_id=uid,
        )
    assert await _marcar(admin_engine, t.id, conv.id, item.id, False, uid)


@pytest.mark.asyncio
async def test_ciclo_encerrado_recusa_marcar_decidir_e_reabrir(admin_engine):
    t = await _provisionar(admin_engine)
    uid, item, ciclo, conv = await _cenario_completo(admin_engine, t.id)
    # Controle: antes de encerrar, marca.
    await _marcar(admin_engine, t.id, conv.id, item.id, True, uid)

    async with _sm(admin_engine)() as db:
        await tr.atualizar_ciclo(
            db, tenant_id=t.id, ciclo_id=ciclo.id,
            payload=RecadastramentoCicloUpdate(situacao="encerrado"),
        )

    with pytest.raises(HTTPException) as exc:
        await _marcar(admin_engine, t.id, conv.id, item.id, False, uid)
    assert exc.value.status_code == 409

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.decidir_recadastramento(
                db, tenant_id=t.id, convocacao_id=conv.id, tipo="indeferimento",
                payload=RecadastramentoDecisaoInput(parecer="Tarde demais"),
                usuario_id=uid,
            )
    assert exc.value.status_code == 409

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.reabrir_recadastramento(
                db, tenant_id=t.id, convocacao_id=conv.id,
                payload=RecadastramentoDecisaoInput(parecer="Tarde demais"),
                usuario_id=uid,
            )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_reabrir_convocacao_nao_decidida_e_409(admin_engine):
    t = await _provisionar(admin_engine)
    uid, _, _, conv = await _cenario_completo(admin_engine, t.id)

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.reabrir_recadastramento(
                db, tenant_id=t.id, convocacao_id=conv.id,
                payload=RecadastramentoDecisaoInput(parecer="Nada a reabrir"),
                usuario_id=uid,
            )
    assert exc.value.status_code == 409


# ============================== Isolamento =================================


@pytest.mark.asyncio
async def test_item_de_outro_tenant_e_404(admin_engine):
    t1 = await _provisionar(admin_engine)
    t2 = await _provisionar(admin_engine)
    item = await _item(admin_engine, t1.id, descricao="CNH")

    with pytest.raises(HTTPException) as exc:
        async with _sm(admin_engine)() as db:
            await tr.obter_item_recadastramento(
                db, tenant_id=t2.id, item_id=item.id
            )
    assert exc.value.status_code == 404

    # Controle: o dono enxerga.
    async with _sm(admin_engine)() as db:
        assert (
            await tr.obter_item_recadastramento(db, tenant_id=t1.id, item_id=item.id)
        ).id == item.id


@pytest.mark.asyncio
async def test_catalogo_nao_vaza_entre_tenants(admin_engine):
    t1 = await _provisionar(admin_engine)
    t2 = await _provisionar(admin_engine)
    meu = await _item(admin_engine, t1.id, descricao="Meu documento")
    alheio = await _item(admin_engine, t2.id, descricao="Documento alheio")

    async with _sm(admin_engine)() as db:
        itens, total = await tr.listar_itens_recadastramento(db, tenant_id=t1.id)
    assert total == 1
    assert [i.id for i in itens] == [meu.id]
    assert alheio.id not in {i.id for i in itens}
