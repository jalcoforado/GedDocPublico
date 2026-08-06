"""Transporte P6 — pontos e vagas.

Spec: `docs/superpowers/specs/2026-08-05-transporte-p6-pontos-design.md`.

Três testes carregam esta fatia, e vale saber por quê antes de mexer neles.

`test_o_banco_barra_sem_passar_pelo_servico` — a prova de que a exclusividade
mora nos índices únicos parciais da `0084`, e não nas checagens de
`ocupar_vaga`. Ele insere a segunda ocupação **direto pelo banco**, contornando
o serviço inteiro, e espera `IntegrityError`. Sem ele, alguém poderia remover os
índices, deixar só o `if` do serviço, e toda a bateria continuaria verde — com
duas requisições concorrentes gravando na mesma vaga em produção, porque entre
o `SELECT` e o `INSERT` de uma checagem não há nada segurando.

`test_alvara_para_permissionario_sem_vaga_continua_emitindo` — a P6 **não
gateia nada**, por decisão do Jorge e pelo mesmo motivo da P5.3 com o atraso: o
cadastro herdado não tem ponto nenhum, então amarrar o alvará à vaga travaria
emissão no dia seguinte ao deploy. Comportamento que ninguém escreveu é o que
some no próximo refactor; fica afirmado.

`test_mapa_devolve_vagas_livres` — o mapa entrega as `vagas_total` vagas, não só
as ocupadas. Devolver só as ocupadas obrigaria a tela a deduzir os buracos, e
"a vaga 7 sumiu" é defeito que ninguém vê até alguém reclamar.

As fixtures vêm do arquivo da P5.2, como as da P5.3 — duplicá-las faria as
baterias divergirem em silêncio sobre o que é um cenário válido.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.models import PontoOcupacao
from app.schemas.transporte_regulado import (
    AlvaraCreate,
    PontoCreate,
    PontoLiberarInput,
    PontoOcuparInput,
    PontoUpdate,
)
from app.services import transporte_regulado as tr
from app.services.modulos import contratar
from tests.test_transporte_p5_2_atendimento import (
    _as_user,
    _cria_usuario_comum_transporte,
    _permissionario,
    _provisionar,
    _sm,
)

HOJE = date.today()


async def _ponto(engine, tenant_id: int, *, nome=None, vagas=4, situacao="ativo"):
    async with _sm(engine)() as db:
        async with db.begin():
            return await tr.criar_ponto(
                db,
                tenant_id=tenant_id,
                payload=PontoCreate(
                    nome=nome or f"Ponto {uuid.uuid4().hex[:6]}",
                    tipo_servico="taxi",
                    vagas_total=vagas,
                    situacao=situacao,
                ),
            )


async def _ocupar(engine, tenant_id: int, ponto_id: int, vaga: int, perm_id: int,
                  desde: date | None = None):
    async with _sm(engine)() as db:
        async with db.begin():
            return await tr.ocupar_vaga(
                db,
                tenant_id=tenant_id,
                ponto_id=ponto_id,
                payload=PontoOcuparInput(
                    numero_vaga=vaga, id_permissionario=perm_id, desde=desde
                ),
            )


async def _limpar(engine, tenant_id: int) -> None:
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM transporte_regulado.ponto_ocupacao WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.ponto WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.alvara WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.permissionario WHERE tenant_id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


# ------------------------------------------------------------------ cadastro


@pytest.mark.asyncio
async def test_nome_de_ponto_e_unico_por_tenant(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        await _ponto(admin_engine, t.id, nome="Praça do Patrocínio")
        with pytest.raises(HTTPException) as e:
            # Caixa diferente: o índice é sobre `lower(nome)`, porque a
            # diferença de caixa não distingue nada para quem lê a lista.
            await _ponto(admin_engine, t.id, nome="praça do patrocínio")
        assert e.value.status_code == 409
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_ponto_excluido_libera_o_nome(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, t.id, nome="Rodoviária")
        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.excluir_ponto(db, tenant_id=t.id, ponto_id=p.id)
        # O índice é parcial (`WHERE excluido = false`); sem isso, soft-delete
        # bloquearia o nome para sempre.
        novo = await _ponto(admin_engine, t.id, nome="Rodoviária")
        assert novo.id != p.id
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_ponto_de_outro_tenant_da_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, a.id)
        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.obter_ponto(db, tenant_id=b.id, ponto_id=p.id)
        # 404, não 403: 403 confirmaria que o ponto existe noutro tenant.
        assert e.value.status_code == 404
    finally:
        await _limpar(admin_engine, a.id)
        await _limpar(admin_engine, b.id)


# ------------------------------------------------------------------- ocupar


@pytest.mark.asyncio
async def test_ocupar_e_contar(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, t.id, vagas=3)
        perm = await _permissionario(admin_engine, t.id, nome="Fulano")
        oc = await _ocupar(admin_engine, t.id, p.id, 2, perm.id)
        assert oc.numero_vaga == 2 and oc.ate is None

        async with _sm(admin_engine)() as db:
            _, ocupadas = await tr.obter_ponto(db, tenant_id=t.id, ponto_id=p.id)
        assert ocupadas == 1
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_vaga_fora_da_faixa_do_ponto(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, t.id, vagas=3)
        perm = await _permissionario(admin_engine, t.id)
        with pytest.raises(HTTPException) as e:
            await _ocupar(admin_engine, t.id, p.id, 4, perm.id)
        assert e.value.status_code == 400
        assert "3 vaga" in e.value.detail
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_vaga_ocupada_recusa_segundo_ocupante(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, t.id)
        um = await _permissionario(admin_engine, t.id, nome="Um")
        dois = await _permissionario(admin_engine, t.id, nome="Dois")
        await _ocupar(admin_engine, t.id, p.id, 1, um.id)
        with pytest.raises(HTTPException) as e:
            await _ocupar(admin_engine, t.id, p.id, 1, dois.id)
        assert e.value.status_code == 409
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_permissionario_lotado_recusa_e_a_mensagem_diz_onde(admin_engine):
    """A mensagem tem de nomear o ponto atual.

    Sem isso o atendente recebe "já tem vaga" e não sabe o que fazer: teria de
    procurar à mão em que ponto o regulado está para liberar. É o atrito que
    faz o operador desistir do sistema.
    """
    t = await _provisionar(admin_engine)
    try:
        origem = await _ponto(admin_engine, t.id, nome="Ponto da Matriz")
        destino = await _ponto(admin_engine, t.id, nome="Ponto do Mercado")
        perm = await _permissionario(admin_engine, t.id, nome="Fulano de Tal")
        await _ocupar(admin_engine, t.id, origem.id, 3, perm.id)

        with pytest.raises(HTTPException) as e:
            await _ocupar(admin_engine, t.id, destino.id, 1, perm.id)
        assert e.value.status_code == 409
        assert "Ponto da Matriz" in e.value.detail
        assert "3" in e.value.detail
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_permissionario_de_outro_tenant_da_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, a.id)
        alheio = await _permissionario(admin_engine, b.id)
        with pytest.raises(HTTPException) as e:
            await _ocupar(admin_engine, a.id, p.id, 1, alheio.id)
        # A FK do Postgres não filtra por tenant; a validação same-tenant é do
        # serviço, e sem ela isto gravaria.
        assert e.value.status_code == 404
    finally:
        await _limpar(admin_engine, a.id)
        await _limpar(admin_engine, b.id)


@pytest.mark.asyncio
async def test_ponto_inativo_nao_recebe_ocupacao(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, t.id, situacao="inativo")
        perm = await _permissionario(admin_engine, t.id)
        with pytest.raises(HTTPException) as e:
            await _ocupar(admin_engine, t.id, p.id, 1, perm.id)
        assert e.value.status_code == 409
    finally:
        await _limpar(admin_engine, t.id)


# ------------------------------------------------------------------ liberar


@pytest.mark.asyncio
async def test_liberar_encerra_e_a_vaga_volta_a_ficar_ocupavel(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, t.id)
        um = await _permissionario(admin_engine, t.id, nome="Um")
        dois = await _permissionario(admin_engine, t.id, nome="Dois")
        oc = await _ocupar(admin_engine, t.id, p.id, 1, um.id,
                           desde=HOJE - timedelta(days=30))

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.liberar_vaga(
                    db, tenant_id=t.id, ponto_id=p.id, ocupacao_id=oc.id,
                    payload=PontoLiberarInput(motivo_liberacao="transferencia"),
                )

        nova = await _ocupar(admin_engine, t.id, p.id, 1, dois.id)
        assert nova.id != oc.id

        # A ocupação antiga continua VISÍVEL no histórico. A afirmação é feita
        # pela mesma via que a tela usa (`listar_ocupacoes`, que filtra
        # `excluido`), e não por SELECT cru na tabela.
        #
        # Isto não é preciosismo: a primeira versão deste teste consultava
        # `PontoOcupacao` direto, sem filtrar `excluido`, e por isso **passava
        # mesmo com `liberar_vaga` marcando a linha como excluída**. Ou seja,
        # a guarda que existia para provar "liberar não apaga" não provava
        # nada — só descobri invertendo-a.
        async with _sm(admin_engine)() as db:
            historico, total = await tr.listar_ocupacoes(
                db, tenant_id=t.id, ponto_id=p.id
            )
        assert total == 2, "a ocupação liberada sumiu do histórico"
        antiga = [h for h in historico if h["id"] == oc.id]
        assert antiga, "a ocupação liberada não aparece no histórico"
        assert antiga[0]["ate"] is not None
        assert antiga[0]["motivo_liberacao"] == "transferencia"
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_liberar_duas_vezes_recusa(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, t.id)
        perm = await _permissionario(admin_engine, t.id)
        oc = await _ocupar(admin_engine, t.id, p.id, 1, perm.id)
        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.liberar_vaga(
                    db, tenant_id=t.id, ponto_id=p.id, ocupacao_id=oc.id,
                    payload=PontoLiberarInput(),
                )
        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.liberar_vaga(
                    db, tenant_id=t.id, ponto_id=p.id, ocupacao_id=oc.id,
                    payload=PontoLiberarInput(),
                )
        assert e.value.status_code == 409
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_liberacao_anterior_ao_inicio_recusa(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, t.id)
        perm = await _permissionario(admin_engine, t.id)
        oc = await _ocupar(admin_engine, t.id, p.id, 1, perm.id, desde=HOJE)
        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.liberar_vaga(
                    db, tenant_id=t.id, ponto_id=p.id, ocupacao_id=oc.id,
                    payload=PontoLiberarInput(ate=HOJE - timedelta(days=1)),
                )
        assert e.value.status_code == 400
    finally:
        await _limpar(admin_engine, t.id)


# ------------------------------------------------------- capacidade e exclusão


@pytest.mark.asyncio
async def test_reduzir_vagas_abaixo_da_maior_ocupada_recusa(admin_engine):
    """Permitir silenciosamente deixaria ocupação fora do mapa da tela.

    Presente no banco, invisível na interface — o pior dos dois mundos, porque
    a vaga pareceria livre e não seria.
    """
    t = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, t.id, vagas=5)
        perm = await _permissionario(admin_engine, t.id)
        await _ocupar(admin_engine, t.id, p.id, 5, perm.id)

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.atualizar_ponto(
                    db, tenant_id=t.id, ponto_id=p.id,
                    payload=PontoUpdate(vagas_total=3),
                )
        assert e.value.status_code == 409
        assert "vaga 5" in e.value.detail

        # Reduzir até a maior ocupada é permitido.
        async with _sm(admin_engine)() as db:
            async with db.begin():
                atualizado = await tr.atualizar_ponto(
                    db, tenant_id=t.id, ponto_id=p.id,
                    payload=PontoUpdate(vagas_total=5),
                )
        assert atualizado.vagas_total == 5
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_excluir_recusa_mas_inativar_permite(admin_engine):
    """Inativar com ocupação vigente É permitido, e não é descuido.

    Ponto inativo é ponto que não recebe NOVOS ocupantes. Desalojar todo mundo
    como efeito colateral de uma mudança de situação seria destrutivo e não foi
    pedido.
    """
    t = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, t.id)
        perm = await _permissionario(admin_engine, t.id)
        await _ocupar(admin_engine, t.id, p.id, 1, perm.id)

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.excluir_ponto(db, tenant_id=t.id, ponto_id=p.id)
        assert e.value.status_code == 409

        async with _sm(admin_engine)() as db:
            async with db.begin():
                inativo = await tr.atualizar_ponto(
                    db, tenant_id=t.id, ponto_id=p.id,
                    payload=PontoUpdate(situacao="inativo"),
                )
        assert inativo.situacao == "inativo"
    finally:
        await _limpar(admin_engine, t.id)


# ---------------------------------------------------------------------- mapa


@pytest.mark.asyncio
async def test_mapa_devolve_vagas_livres(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, t.id, vagas=4)
        perm = await _permissionario(admin_engine, t.id, nome="Sicrano")
        await _ocupar(admin_engine, t.id, p.id, 3, perm.id)

        async with _sm(admin_engine)() as db:
            mapa = await tr.mapa_de_vagas(db, tenant_id=t.id, ponto_id=p.id)

        assert mapa["vagas_total"] == 4
        assert mapa["vagas_ocupadas"] == 1
        assert [v["numero_vaga"] for v in mapa["vagas"]] == [1, 2, 3, 4]
        assert [v["numero_vaga"] for v in mapa["vagas"] if v["ocupacao"]] == [3]
        assert mapa["vagas"][2]["ocupacao"]["nome_permissionario"] == "Sicrano"
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_mapa_ignora_ocupacao_encerrada(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, t.id, vagas=2)
        perm = await _permissionario(admin_engine, t.id)
        oc = await _ocupar(admin_engine, t.id, p.id, 1, perm.id)
        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.liberar_vaga(
                    db, tenant_id=t.id, ponto_id=p.id, ocupacao_id=oc.id,
                    payload=PontoLiberarInput(),
                )
        async with _sm(admin_engine)() as db:
            mapa = await tr.mapa_de_vagas(db, tenant_id=t.id, ponto_id=p.id)
            historico, total = await tr.listar_ocupacoes(
                db, tenant_id=t.id, ponto_id=p.id
            )
        assert mapa["vagas_ocupadas"] == 0
        # Mas o histórico continua lá — é o ponto do log.
        assert total == 1 and historico[0]["ate"] is not None
    finally:
        await _limpar(admin_engine, t.id)


# ------------------------------------------------- as duas provas estruturais


@pytest.mark.asyncio
async def test_o_banco_barra_sem_passar_pelo_servico(admin_engine):
    """A exclusividade é dos índices da `0084`, não do `if` de `ocupar_vaga`.

    Este teste contorna o serviço inteiro e insere direto. Sem ele, alguém
    poderia apagar os índices únicos parciais e a bateria continuaria verde —
    enquanto em produção duas requisições concorrentes gravariam na mesma vaga,
    porque entre o `SELECT` e o `INSERT` da checagem não há nada segurando.
    """
    t = await _provisionar(admin_engine)
    try:
        p = await _ponto(admin_engine, t.id, vagas=3)
        um = await _permissionario(admin_engine, t.id, nome="Um")
        dois = await _permissionario(admin_engine, t.id, nome="Dois")
        await _ocupar(admin_engine, t.id, p.id, 1, um.id)

        # (a) mesma vaga, outro ocupante
        with pytest.raises(IntegrityError):
            async with _sm(admin_engine)() as db:
                async with db.begin():
                    db.add(
                        PontoOcupacao(
                            tenant_id=t.id, id_ponto=p.id, numero_vaga=1,
                            id_permissionario=dois.id, desde=HOJE,
                            criado_em=datetime.utcnow(),
                        )
                    )

        # (b) mesmo ocupante, outra vaga
        with pytest.raises(IntegrityError):
            async with _sm(admin_engine)() as db:
                async with db.begin():
                    db.add(
                        PontoOcupacao(
                            tenant_id=t.id, id_ponto=p.id, numero_vaga=2,
                            id_permissionario=um.id, desde=HOJE,
                            criado_em=datetime.utcnow(),
                        )
                    )
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_alvara_para_permissionario_sem_vaga_continua_emitindo(admin_engine):
    """A P6 não gateia nada, e isso é decisão, não omissão.

    O cadastro herdado não tem ponto nenhum: amarrar o alvará à vaga travaria
    emissão no dia seguinte ao deploy, para todo mundo. Mesma escolha da P5.3
    com o atraso. Se um dia a regra mudar, que mude com este teste vermelho na
    frente, e não de raspão.
    """
    t = await _provisionar(admin_engine)
    try:
        perm = await _permissionario(admin_engine, t.id, nome="Sem vaga")
        # Sem `db.begin()`: `criar_alvara` faz o próprio `commit`, ao contrário
        # das funções da P6, que só dão `flush` e deixam a transação com o
        # chamador. A inconsistência é antiga e não é desta fatia.
        async with _sm(admin_engine)() as db:
            alvara = await tr.criar_alvara(
                db,
                tenant_id=t.id,
                payload=AlvaraCreate(
                    numero_alvara=f"ALV-{uuid.uuid4().hex[:8]}",
                    tipo_servico="taxi",
                    id_permissionario=perm.id,
                ),
            )
        assert alvara.id is not None
    finally:
        await _limpar(admin_engine, t.id)


# ----------------------------------------------------------------- HTTP


@pytest.mark.asyncio
async def test_http_usuario_comum_ocupa_e_le_o_mapa(admin_engine):
    """Usuário COMUM, não super-usuário.

    O bypass de SU em `auth/perms.py` retorna antes do `getattr(item, action)`,
    e foi assim que dez rotas do transporte ficaram devolvendo 500 para
    operador não-SU sem a suíte notar. Toda rota nova precisa de um teste que
    passe por este caminho.
    """
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            async with s.begin():
                # `contratar` RECONCILIA: passar só `["transporte"]`
                # descontrata os demais. É o que se quer num tenant de teste, e
                # é como a P5.2 faz.
                await contratar(s, t.id, ["transporte"])

        p = await _ponto(admin_engine, t.id, nome="Ponto HTTP", vagas=2)
        perm = await _permissionario(admin_engine, t.id, nome="Beltrano")
        uid = await _cria_usuario_comum_transporte(admin_engine, t.id)
        _as_user(admin_engine, uid, t.id, t.slug)()
        base = "/api/v2/transporte-regulado/pontos"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get(base)
            assert r.status_code == 200, r.text
            # Envelope paginado, não array: declarar `X[]` no `api.ts` deixaria
            # o tsc verde e a tela diria "nenhum registro" com dado no banco.
            assert set(r.json()) >= {"items", "total", "page", "page_size"}

            r = await c.post(
                f"{base}/{p.id}/ocupacoes",
                json={"numero_vaga": 1, "id_permissionario": perm.id},
            )
            assert r.status_code in (200, 201), r.text

            r = await c.get(f"{base}/{p.id}/mapa")
            assert r.status_code == 200, r.text
            mapa = r.json()
            assert mapa["vagas_ocupadas"] == 1
            assert len(mapa["vagas"]) == 2
    finally:
        await _limpar(admin_engine, t.id)


# ------------------------------------------- busca de permissionario (P6)


@pytest.mark.asyncio
async def test_busca_de_permissionario_por_nome_e_cpf(admin_engine):
    """`q` entrou pela P6: sem ela o seletor de ocupante só enxerga os 50
    primeiros, e a tela fica inutilizável em município com cadastro grande.

    Afirma também que `total` acompanha o filtro. As condições eram escritas
    DUAS vezes nesse service — na consulta e na contagem — e acrescentar `q` a
    só uma das cópias faria a tela mostrar 1 resultado dizendo "de 300".
    """
    t = await _provisionar(admin_engine)
    try:
        alvo = await _permissionario(admin_engine, t.id, nome="Joaquim Nabuco")
        await _permissionario(admin_engine, t.id, nome="Maria da Silva")

        async with _sm(admin_engine)() as db:
            itens, total = await tr.listar_permissionarios(
                db, tenant_id=t.id, q="nabuco"
            )
            assert [i.id for i in itens] == [alvo.id]
            assert total == 1, "o total tem de acompanhar o filtro"

            # Por CPF, que é o que o atendente tem no documento em mãos.
            por_cpf, total_cpf = await tr.listar_permissionarios(
                db, tenant_id=t.id, q=alvo.cpf[:6]
            )
            assert alvo.id in [i.id for i in por_cpf] and total_cpf >= 1

            # Sem `q`, os dois voltam.
            todos, total_todos = await tr.listar_permissionarios(db, tenant_id=t.id)
            assert total_todos == 2 and len(todos) == 2
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_a_busca_de_permissionario_chega_ao_service(admin_engine):
    """Prova a FIAÇÃO, não a regra.

    Um `q` declarado no router e esquecido na chamada ao service passaria em
    toda a bateria de service acima. Foi exatamente esse defeito que a busca de
    alvarás teve: o termo estava na `queryKey` sem ir para a API.
    """
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            async with s.begin():
                await contratar(s, t.id, ["transporte"])
        await _permissionario(admin_engine, t.id, nome="Joaquim Nabuco")
        await _permissionario(admin_engine, t.id, nome="Maria da Silva")
        uid = await _cria_usuario_comum_transporte(admin_engine, t.id)
        _as_user(admin_engine, uid, t.id, t.slug)()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get(
                "/api/v2/transporte-regulado/permissionarios", params={"q": "nabuco"}
            )
            assert r.status_code == 200, r.text
            corpo = r.json()
            assert corpo["total"] == 1, corpo
            assert corpo["items"][0]["nome"] == "Joaquim Nabuco"
    finally:
        await _limpar(admin_engine, t.id)
