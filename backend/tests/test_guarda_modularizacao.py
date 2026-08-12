"""Guardas estruturais da modularização — pegam omissão, não comportamento."""
import pytest
from sqlalchemy import text

from app.config import get_settings


@pytest.mark.asyncio
async def test_toda_transacao_do_sistema_tem_modulo(admin_session):
    """Transação nossa sem módulo = fail-open silencioso. Reprova aqui.

    Escopo: só as transações ligadas ao sistema do app (`utils.sistema.app`
    igual a `get_settings().app_name`). O dump legado traz transações do PHP
    que não são nossas e não devem ser mapeadas — e o ambiente tem mais de uma
    linha em `utils.sistema`, então o `app` precisa vir do settings (mesma
    correção que a Task 3B aplicou; o brief trazia `'sistemas'` hardcoded).

    Esta guarda só tem valor encadeada com as da Task 3B
    (`tests/test_transacoes_rbac.py`), que garantem que todo código exigido por
    `require_permission` existe em `utils.transacao` E está ligado ao sistema.
    Juntas as três dizem: todo código que o app de fato enforça tem módulo.
    Sozinha, esta aqui cobriria só o que estivesse ligado ao sistema — que antes
    da 3B era uma linha.

    Se este teste falhar: acrescente o código em MODULO_TRANSACOES, em
    backend/app/cli/seed_bootstrap.py, e rode o seed.
    """
    app = get_settings().app_name

    # O escopo é medido antes da asserção principal: um JOIN vazio faria a
    # guarda passar sem verificar nada. Não é hipótese — era exatamente o que
    # aconteceria com o `s.app = 'sistemas'` literal do brief neste ambiente,
    # onde `utils.sistema` tem duas linhas e o app roda como 'aprimora'.
    total_no_escopo = (await admin_session.execute(text("""
        SELECT count(*)
          FROM utils.transacao t
          JOIN utils.sistema_transacao st ON st.id_transacao = t.id AND st.excluido = false
          JOIN utils.sistema s ON s.id = st.id_sistema AND s.app = :app
         WHERE t.excluido = false
    """), {"app": app})).scalar()
    assert total_no_escopo > 0, (
        "a guarda ficou vacuosa: nenhuma transação no escopo do sistema "
        f"'{app}'. Verifique APP_NAME e o vínculo em sistema_transacao."
    )

    orfas = (await admin_session.execute(text("""
        SELECT t.codigo
          FROM utils.transacao t
          JOIN utils.sistema_transacao st ON st.id_transacao = t.id AND st.excluido = false
          JOIN utils.sistema s ON s.id = st.id_sistema AND s.app = :app
         WHERE t.excluido = false
           AND NOT EXISTS (
               SELECT 1 FROM aprimora_py.modulo_transacao mt WHERE mt.id_transacao = t.id
           )
         ORDER BY t.codigo
    """), {"app": app})).scalars().all()
    assert not orfas, (
        f"Transações sem módulo: {orfas}. "
        "Mapeie em MODULO_TRANSACOES (app/cli/seed_bootstrap.py) e rode o seed."
    )


# ---------------------------------------------------------------------------
# Guarda 2 — endpoint sem gate reconhecido
#
# `require_permission` é o ponto onde o enforcement de módulo por PERMISSÃO
# acontece (Task 5: o gate roda antes até do bypass de super-usuário).
# `require_modulo` (auth/modulos.py) é o gate por CONTRATAÇÃO, que não olha
# usuário — só aceito em leitura (ver `endpoints_sem_gate`). Endpoint sem
# nenhum dos dois escapa do enforcement, e o esquecimento é silencioso.
#
# A varredura devolve todos os endpoints `/api/v2` sem gate aceito para o
# método. Cada um foi julgado individualmente e caiu num destes dois
# conjuntos. Os dois juntos formam a allowlist; qualquer endpoint fora deles
# reprova o PR.
#
# Os conjuntos são DOIS de propósito. Chamar de "transversal" um endpoint de
# módulo que só não tem gate por herança histórica seria maquiar a dívida:
# o segundo conjunto registra a dívida com nome, e diz qual código cada item
# deveria receber quando ela for paga.
# ---------------------------------------------------------------------------

ENDPOINTS_TRANSVERSAIS: set[tuple[str, str]] = {
    # -- Admin de PLATAFORMA: gateado por `require_platform_admin`, um sujeito
    # acima do tenant. São justamente os endpoints que contratam módulo —
    # exigir módulo contratado aqui seria circular.
    ("GET", "/api/v2/admin/me"),
    ("GET", "/api/v2/admin/tenants"),
    ("GET", "/api/v2/admin/tenants/{tenant_id}"),
    ("PUT", "/api/v2/admin/tenants/{tenant_id}"),
    ("GET", "/api/v2/admin/tenants/{tenant_id}/modulos"),
    ("PUT", "/api/v2/admin/tenants/{tenant_id}/modulos"),
    ("POST", "/api/v2/admin/tenants"),
    ("POST", "/api/v2/admin/tenants/{tenant_id}/ativar"),
    ("POST", "/api/v2/admin/tenants/{tenant_id}/desativar"),

    # -- Autenticação e sessão: rodam antes de haver permissão para consultar.
    ("POST", "/api/v2/auth/login"),
    ("POST", "/api/v2/auth/logout"),
    # Senha própria sob `must_change_password` (SEC-1): o usuário está bloqueado
    # justamente para trocar a senha; gatear por módulo o prenderia fora.
    ("POST", "/api/v2/auth/alterar-senha"),
    ("GET", "/api/v2/auth/me"),
    # OAuth do Google: vincula a conta pessoal do próprio usuário. A credencial
    # é do usuário, não do módulo que a consome depois (minutas).
    ("GET", "/api/v2/auth/google"),
    ("GET", "/api/v2/auth/google/callback"),

    # -- Infra e identidade visual: sem auth, consumidos na tela de login.
    ("GET", "/api/v2/health"),
    ("GET", "/api/v2/branding/me"),

    # -- Tenant próprio (leitura): o app precisa saber onde está antes de
    # saber o que pode. As escritas do mesmo router já exigem `configuracao`.
    ("GET", "/api/v2/tenants/me"),
    ("GET", "/api/v2/tenants/me/onboarding"),

    # -- Autodescrição do próprio usuário. `/modulos/me` é o que o launcher
    # consulta para saber o que mostrar: gatear por módulo seria circular.
    ("GET", "/api/v2/permissoes/me"),
    ("GET", "/api/v2/modulos/me"),

    # -- Notificações do PRÓPRIO usuário (caixa, leitura e preferências de
    # entrega). Não pertencem a módulo nenhum: quem recebe notificação de
    # protocolo é o mesmo sujeito que recebe de pagamentos.
    ("GET", "/api/v2/notificacoes/me"),
    ("GET", "/api/v2/notificacoes/preferencias"),
    ("PUT", "/api/v2/notificacoes/preferencias"),
    ("GET", "/api/v2/notificacoes/telefone"),
    ("PUT", "/api/v2/notificacoes/telefone"),
    ("POST", "/api/v2/notificacoes/marcar-todas-lidas"),
    ("POST", "/api/v2/notificacoes/{notif_id}/marcar-lida"),
    # Envio de teste de WhatsApp: valida a configuração de infraestrutura do
    # tenant (driver Zenvia), que é transversal como o resto deste router.
    # Chegou a receber `configuracao` na primeira rodada da Task 8 e foi
    # revertido: esse código mora no módulo `administracao`, então um tenant
    # sem `administracao` não conseguiria validar a própria configuração.
    # Fica registrado que sobra aqui uma questão de AUTORIZAÇÃO, não de
    # módulo — qualquer usuário autenticado do tenant dispara um envio com a
    # credencial dele. Fechar isso pede um gate de super-usuário de tenant,
    # que não existe hoje como dependency; ver relatório da Task 8.
    ("POST", "/api/v2/notificacoes/whatsapp-test"),

    # -- Fila de assinatura do próprio usuário: lista o que foi endereçado a
    # ele. O ato de assinar/recusar é que exige `processo`+`atualizar`.
    ("GET", "/api/v2/solicitacoes-assinatura/me/pendentes"),

    # -- Superfície pública, sem autenticação alguma: portal de serviços e
    # validação de assinatura por código. Não há usuário para permissionar.
    ("GET", "/api/v2/portal/servicos"),
    ("GET", "/api/v2/portal/servicos/{slug}"),
    ("GET", "/api/v2/publico/validacao/{codigo}"),
    ("GET", "/api/v2/publico/validacao/{codigo}/comprovante.pdf"),

    # -- Portal do CIDADÃO: autenticado por `get_current_cidadao`, um sujeito
    # que não existe no RBAC de servidor (não tem grupo nem transação em
    # `utils.transacao`). `require_permission` depende de `get_current_user` e
    # rejeitaria todo cidadão. Gate aqui é o escopo do próprio processo, feito
    # no service. O enforcement de módulo do portal, se algum dia for
    # desejado, tem de ser outro mecanismo — vide relatório da Task 8.
    ("GET", "/api/v2/cidadao/me"),
    ("GET", "/api/v2/cidadao/assuntos"),
    ("GET", "/api/v2/cidadao/especies"),
    ("GET", "/api/v2/cidadao/processos"),
    ("GET", "/api/v2/cidadao/processos/{processo_id}"),
    ("GET", "/api/v2/cidadao/processos/{processo_id}/checklist-documentos"),
    ("GET", "/api/v2/cidadao/processos/{processo_id}/complementacoes"),
    ("POST", "/api/v2/cidadao/cadastrar"),
    ("POST", "/api/v2/cidadao/login"),
    ("POST", "/api/v2/cidadao/logout"),
    ("POST", "/api/v2/cidadao/processos"),
    ("POST", "/api/v2/cidadao/processos/{processo_id}/anexos"),
    ("POST", "/api/v2/cidadao/processos/{processo_id}/complementacoes/{complementacao_id}/responder"),
    ("POST", "/api/v2/cidadao/servicos/{slug}/abrir"),
}


ENDPOINTS_LEITURA_SEM_GATE: set[tuple[str, str]] = set()
"""VAZIA desde 2026-08-11 (item 1.0.8) — e isso é o fim de uma história.

Em 2026-07-29 esta lista tinha **76** entradas: GETs que pertenciam a um módulo
e não tinham gate nenhum, porque os routers da geração protocolo seguiam uma
convenção anterior à modularização — *escrita gateada, leitura liberada a
qualquer autenticado do tenant*. A fatia `leitura-por-modulo` (2026-07-30) deu
`require_modulo` a 69 e deixou 7, cada uma com a razão escrita ao lado: consumo
cruzado comprovado entre módulos, ou decisão humana de que o recurso é do
sistema.

Aquelas 7 razões eram todas sobre **contratação de módulo** — e continuam
válidas: `/organograma` e `/unidades-trabalho` alimentam o `UnidadePicker` de
telas de PROTOCOLO, e gateá-las com `administracao` impediria a abertura de
processo num tenant que não contratou administração. O item 1.0.8 não as
contradiz: ele acrescenta a pergunta ORTOGONAL, a de autorização, que nenhuma
delas respondia. As 7 ganharam `require_permission` de leitura e saíram daqui
por terem gate, não por terem perdido a razão.

A lista fica declarada, vazia, de propósito: o par de testes abaixo continua
valendo e é o que impede que ela volte a crescer em silêncio.
"""

# Snapshot da decisão humana, e o par obrigatório da lista acima: as duas
# mudam no mesmo commit, nunca uma só. Vazio aqui não é "ninguém decidiu
# nada" — é "a decisão é que não sobrou exceção de gate de módulo".
ENDPOINTS_LEITURA_SEM_GATE_DECIDIDOS: frozenset[tuple[str, str]] = frozenset()


# Leitura que NÃO exige transação — a decisão registrada do item 1.0.8. Não é
# dívida: é a resposta a "quem pode ler isto?" para os casos em que exigir
# permissão não protegeria nada e cobraria caro.
LEITURA_SEM_PERMISSAO_DECIDIDA: frozenset[tuple[str, str]] = frozenset({
    # -- Catálogos de formulário. São as listas que preenchem `<select>` em
    # todo módulo. Exigir transação para ler "a lista de estados" não protege
    # dado sensível nenhum e obrigaria todo grupo futuro a receber `catalogo`
    # só para abrir uma tela. O gate de MÓDULO continua valendo neles.
    ("GET", "/api/v2/estados"),
    ("GET", "/api/v2/cidades"),
    ("GET", "/api/v2/bairros"),
    ("GET", "/api/v2/enderecos"),
    ("GET", "/api/v2/tipos-processo"),
    ("GET", "/api/v2/tipos-anexo"),
    ("GET", "/api/v2/tipos-manifestante"),
    ("GET", "/api/v2/assunto-tipo-anexo"),
    ("GET", "/api/v2/catalogo/niveis"),
    ("GET", "/api/v2/catalogo/prioridades"),
    ("GET", "/api/v2/catalogo/sistemas"),
    ("GET", "/api/v2/catalogo/tipos-unidade"),
    ("GET", "/api/v2/catalogo/transacoes"),
    ("GET", "/api/v2/protocolo/ccd-classes"),
    ("GET", "/api/v2/protocolo/ccd-classes/tree"),
    ("GET", "/api/v2/protocolo/especies-documentais"),
    ("GET", "/api/v2/protocolo/ttd-regras"),
    ("GET", "/api/v2/protocolo/sugerir-ccd"),

    # -- De si-mesmo. O sujeito da consulta é o próprio requisitante; exigir
    # transação para alguém ler os próprios dados não protege ninguém dele
    # mesmo. `/permissoes/me` é o caso extremo: exigir permissão para ler as
    # próprias permissões seria circular.
    ("GET", "/api/v2/auth/me"),
    ("GET", "/api/v2/auth/google"),
    ("GET", "/api/v2/auth/google/callback"),
    ("GET", "/api/v2/permissoes/me"),
    ("GET", "/api/v2/modulos/me"),
    ("GET", "/api/v2/notificacoes/me"),
    ("GET", "/api/v2/notificacoes/preferencias"),
    ("GET", "/api/v2/notificacoes/telefone"),
    ("GET", "/api/v2/solicitacoes-assinatura/me/pendentes"),
    ("GET", "/api/v2/tenants/me/onboarding"),
    # Resposta constante sobre a própria sessão (`is_platform_admin` é `false`
    # fixo desde SEC-01A). Não lê dado de ninguém.
    ("GET", "/api/v2/admin/me"),
})


def gets_sem_permissao(app=None) -> set[tuple[str, str]]:
    """GETs de usuário municipal autenticado que não exigem transação.

    Deliberadamente NÃO conta o que não tem sujeito municipal: rota pública,
    de cidadão (credencial própria, escopo próprio) e de plataforma são outro
    realm — cobrá-las por `utils.transacao` não faria sentido.
    """
    if app is None:
        from app.main import app

    # Prefixo, e não identidade com `get_current_user`: existe a variante
    # `get_current_user_no_password_gate` (whitelist do SEC-1, usada por
    # `/permissoes/me` e `/auth/me`). Casar só a função principal deixaria
    # essas rotas fora da varredura — invisíveis para a guarda.
    achados: set[tuple[str, str]] = set()
    for rota in getattr(app, "routes", []):
        caminho = getattr(rota, "path", "")
        if not caminho.startswith("/api/v2") or "GET" not in getattr(rota, "methods", set()):
            continue

        origens: set[tuple[str, str]] = set()
        municipal = False

        def anda(dep, prof=0):
            nonlocal municipal
            if prof > 5 or getattr(dep, "call", None) is None:
                return
            origens.add(
                (getattr(dep.call, "__module__", ""), getattr(dep.call, "__qualname__", ""))
            )
            if getattr(dep.call, "__name__", "").startswith("get_current_user"):
                municipal = True
            for sub in getattr(dep, "dependencies", []):
                anda(sub, prof + 1)

        for d in getattr(getattr(rota, "dependant", None), "dependencies", []):
            anda(d)

        # Sujeito municipal é `get_current_user`. Rota pública e de cidadão
        # não têm nenhum, e a de plataforma tem outro (`require_platform_admin`,
        # RS256) — nenhum deles é cobrável por `utils.transacao`.
        if not municipal:
            continue
        if any(q == "require_platform_admin" for _, q in origens):
            continue
        if origens & GATES_DE_PERMISSAO:
            continue
        achados.add(("GET", caminho))
    return achados


def test_leitura_sem_permissao_nao_cresce_sem_decisao():
    """Item 1.0.8: GET novo nasce exigindo transação, ou a isenção é registrada.

    Este é o teste que a fatia de 2026-07-30 não tinha como escrever: naquele
    momento 76 GETs estavam de fora, e uma guarda nesse estado só teria como
    congelar a dívida. Hoje a dívida é zero e a lista é a decisão.

    Se falhar porque você ACRESCENTOU um GET: o caminho normal é dar-lhe
    `require_permission("<codigo>")` — leitura, sem `action` —, herdando o
    código dos irmãos de escrita do mesmo router. Só registre a isenção aqui
    se o endpoint for catálogo de formulário ou de si-mesmo, e escreva a razão
    ao lado da entrada.

    Se falhar porque uma entrada VIROU obsoleta (o endpoint ganhou permissão ou
    sumiu): tire a linha. Uma isenção que apodrece deixa de ser decisão e vira
    ruído — e ruído é o que faz a próxima pessoa parar de ler a lista.
    """
    reais = gets_sem_permissao()
    novos = reais - LEITURA_SEM_PERMISSAO_DECIDIDA
    obsoletos = LEITURA_SEM_PERMISSAO_DECIDIDA - reais
    assert not novos and not obsoletos, (
        f"GETs sem permissão fora da lista: {sorted(novos)}. "
        f"Entradas obsoletas na lista: {sorted(obsoletos)}."
    )


def test_a_guarda_de_permissao_enxerga_ausencia_de_gate():
    """Prova por inversão: numa app fake sem gate, a varredura ACUSA.

    Sem este par, `gets_sem_permissao()` poderia estar devolvendo conjunto
    vazio por defeito próprio — um `continue` a mais, um atributo trocado — e
    o teste acima passaria verde para sempre, dizendo exatamente nada.
    """
    from fastapi import APIRouter, Depends, FastAPI

    from app.auth.deps import get_current_user

    fake = FastAPI()
    r = APIRouter()

    # Com `get_current_user` e sem permissão: é exatamente a forma do defeito
    # que a guarda persegue — autenticado, municipal, e nada mais.
    @r.get("/api/v2/inventado")
    async def _inventado(_=Depends(get_current_user)):  # pragma: no cover
        return {}

    fake.include_router(r)
    assert ("GET", "/api/v2/inventado") in gets_sem_permissao(app=fake)


def test_endpoints_leitura_sem_gate_nao_cresce_sem_decisao():
    """ENDPOINTS_LEITURA_SEM_GATE só muda junto com ENDPOINTS_LEITURA_SEM_GATE_DECIDIDOS.

    Diferente de `test_allowlist_nao_tem_entrada_obsoleta` (que pega entrada
    que já ganhou gate e devia ter saído), este teste pega o caso oposto:
    entrada NOVA aparecendo aqui sem que ninguém tenha registrado por que ela
    é transversal permanente, e não só mais um GET que ainda não foi gateado.

    Se este teste falhar porque você ACRESCENTOU uma entrada: pare antes de
    "corrigir" o teste. Volte ao escopo aprovado
    (docs/superpowers/specs/2026-07-30-leitura-por-modulo-escopo.md) e decida,
    com o dono do produto, se o endpoint tem consumo cruzado comprovado por
    módulo ou é decisão humana explícita de recurso do sistema. Se sim,
    escreva a razão como comentário ao lado da entrada, ali em cima, E
    acrescente a mesma entrada em ENDPOINTS_LEITURA_SEM_GATE_DECIDIDOS — as
    duas mudam no mesmo commit. Se não for nenhum dos dois casos, o endpoint
    não pertence a esta lista: ele precisa de `require_modulo`.

    Se este teste falhar porque você REMOVEU uma entrada (por exemplo: ela
    ganhou `require_modulo` porque deixou de ser transversal): isso é
    esperado e correto, não um obstáculo. Tire a entrada também de
    ENDPOINTS_LEITURA_SEM_GATE_DECIDIDOS aqui embaixo. O teste não protege a
    lista contra encolher — só exige que crescer ou encolher seja visível e
    deliberado no diff do PR, nunca um efeito colateral silencioso.
    """
    assert ENDPOINTS_LEITURA_SEM_GATE == ENDPOINTS_LEITURA_SEM_GATE_DECIDIDOS, (
        "ENDPOINTS_LEITURA_SEM_GATE divergiu do snapshot decidido na Task 4. "
        f"Adicionadas sem decisão registrada: "
        f"{sorted(ENDPOINTS_LEITURA_SEM_GATE - ENDPOINTS_LEITURA_SEM_GATE_DECIDIDOS)}. "
        f"Removidas do snapshot mas ainda na lista: "
        f"{sorted(ENDPOINTS_LEITURA_SEM_GATE_DECIDIDOS - ENDPOINTS_LEITURA_SEM_GATE)}. "
        "Leia o docstring deste teste antes de editar qualquer um dos dois conjuntos."
    )


# Origem exata das closures que fazem o enforcement. `require_permission` e
# `require_any_permission` devolvem uma função interna chamada `_check`; é o
# par (módulo, qualname) que identifica o gate de verdade.
#
# Casar por substring (`"_check" in qualname`) seria um falso-NEGATIVO
# esperando acontecer, e falso-negativo é o erro que mata esta guarda: uma
# dependency futura chamada `_check_ip_permitido` ou `_check_captcha` contaria
# como gate de permissão sem verificar permissão nenhuma, e o endpoint
# escaparia do CI. O repo já tem `_check_processo` (services/volumes.py) com
# essa convenção de nome, sem relação com RBAC.
GATES_DE_PERMISSAO: set[tuple[str, str]] = {
    ("app.auth.perms", "require_permission.<locals>._check"),
    ("app.auth.perms", "require_any_permission.<locals>._check"),
}


# Gate de CONTRATAÇÃO de módulo (auth/modulos.py). NÃO é gate de permissão: não
# olha usuário, grupo nem transação. Fica em conjunto separado de propósito —
# ver `endpoints_sem_gate()`, que só o aceita em leitura.
GATES_DE_MODULO: set[tuple[str, str]] = {
    ("app.auth.modulos", "require_modulo.<locals>._check_modulo"),
}


# Qual módulo cada rota de leitura gateada exige. `GATES_DE_MODULO` só
# consegue dizer "tem gate de módulo" — o par (módulo, qualname) da closure é
# IGUAL para qualquer slug (`require_modulo("frota")` e
# `require_modulo("protocolo")` produzem a mesma `_check_modulo`). Sem esta
# tabela, `require_modulo("frota")` colado por engano numa rota de protocolo
# passaria batido em `test_nenhum_endpoint_novo_sem_permissao`,
# `test_allowlist_nao_tem_entrada_obsoleta` e nos testes HTTP (que amostram só
# 6 das 58). O risco é concreto: a Task 3 gateia `administracao` nos MESMOS
# arquivos (`catalogo.py` já mistura os dois módulos) — é o cenário exato de
# copy-paste que só esta tabela pega.
#
# As 58 são as gateadas por `require_modulo("protocolo")` na Task 2
# (2026-07-30); as 11 seguintes são as gateadas por `require_modulo("administracao")`
# na Task 3 (mesmo dia). `/organograma` saiu deste segundo grupo no review
# final (2026-07-30): ver a razão completa junto da entrada dela em
# ENDPOINTS_LEITURA_SEM_GATE. `test_rotas_por_modulo_bate_com_a_implementacao`,
# logo abaixo, lê `modulo_slug` de cada dependência real e reprova nos dois
# sentidos: rota gateada fora daqui, e rota daqui com slug diferente do que a
# rota realmente exige.
ROTAS_POR_MODULO: dict[tuple[str, str], str] = {
    ("GET", "/api/v2/anexos/{anexo_id}/carimbado.pdf"): "protocolo",
    ("GET", "/api/v2/anexos/{anexo_id}/download"): "protocolo",
    ("GET", "/api/v2/assinaturas/{assinatura_anexo_id}/comprovante.pdf"): "protocolo",
    ("GET", "/api/v2/assinaturas/{assinatura_anexo_id}/evidencias"): "protocolo",
    ("GET", "/api/v2/assinaturas/{assinatura_anexo_id}/validar"): "protocolo",
    ("GET", "/api/v2/assunto-tipo-anexo"): "protocolo",
    ("GET", "/api/v2/assuntos"): "protocolo",
    ("GET", "/api/v2/bairros"): "protocolo",
    ("GET", "/api/v2/catalogo/prioridades"): "protocolo",
    ("GET", "/api/v2/cidades"): "protocolo",
    ("GET", "/api/v2/enderecos"): "protocolo",
    ("GET", "/api/v2/estados"): "protocolo",
    ("GET", "/api/v2/manifestantes"): "protocolo",
    ("GET", "/api/v2/processos"): "protocolo",
    ("GET", "/api/v2/processos/apensamentos/{apensamento_id}/termo.pdf"): "protocolo",
    ("GET", "/api/v2/processos/encaminhamentos/{encaminhamento_id}/comprovante.pdf"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/anexos/{anexo_processo_id}/termo-desentranhamento.pdf"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/apensados"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/apensamentos"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/capa.pdf"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/checklist-documentos"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/complementacoes"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/completo.pdf"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/etiqueta-dupla.pdf"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/etiqueta-unica.pdf"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/solicitacoes-assinatura"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/temporalidade"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/trail"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/volumes"): "protocolo",
    ("GET", "/api/v2/processos/{processo_id}/workflow"): "protocolo",
    ("GET", "/api/v2/protocolo/ccd-classes"): "protocolo",
    ("GET", "/api/v2/protocolo/ccd-classes/tree"): "protocolo",
    ("GET", "/api/v2/protocolo/especies-documentais"): "protocolo",
    ("GET", "/api/v2/protocolo/sugerir-ccd"): "protocolo",
    ("GET", "/api/v2/protocolo/ttd-regras"): "protocolo",
    ("GET", "/api/v2/protocolo/vencendo-prazo"): "protocolo",
    ("GET", "/api/v2/protocolo/{processo_id}/comprovante.pdf"): "protocolo",
    ("GET", "/api/v2/protocolo/{processo_id}/etiqueta.pdf"): "protocolo",
    ("GET", "/api/v2/relatorios/assinaturas.csv"): "protocolo",
    ("GET", "/api/v2/relatorios/assinaturas.json"): "protocolo",
    ("GET", "/api/v2/relatorios/assinaturas.pdf"): "protocolo",
    ("GET", "/api/v2/relatorios/processos.csv"): "protocolo",
    ("GET", "/api/v2/relatorios/processos.json"): "protocolo",
    ("GET", "/api/v2/relatorios/processos.pdf"): "protocolo",
    ("GET", "/api/v2/relatorios/tramitacao.csv"): "protocolo",
    ("GET", "/api/v2/relatorios/tramitacao.json"): "protocolo",
    ("GET", "/api/v2/relatorios/tramitacao.pdf"): "protocolo",
    ("GET", "/api/v2/tipo-processo-workflow"): "protocolo",
    ("GET", "/api/v2/tipos-anexo"): "protocolo",
    ("GET", "/api/v2/tipos-manifestante"): "protocolo",
    ("GET", "/api/v2/tipos-processo"): "protocolo",
    ("GET", "/api/v2/workflow-alertas"): "protocolo",
    ("GET", "/api/v2/workflow-definitions"): "protocolo",
    ("GET", "/api/v2/workflow-definitions/{wf_id}"): "protocolo",
    ("GET", "/api/v2/workflow-definitions/{wf_id}/versoes"): "protocolo",
    ("GET", "/api/v2/workflow-instances"): "protocolo",
    ("GET", "/api/v2/workflow-instances/{instance_id}"): "protocolo",

    # Task 3 (2026-07-30) — as 12 de administracao originais. `/organograma`
    # saiu deste grupo no review final e voltou para ENDPOINTS_LEITURA_SEM_GATE
    # (transversal); ficam 11.
    ("GET", "/api/v2/catalogo/niveis"): "administracao",
    ("GET", "/api/v2/catalogo/sistemas"): "administracao",
    ("GET", "/api/v2/catalogo/tipos-unidade"): "administracao",
    ("GET", "/api/v2/catalogo/transacoes"): "administracao",
    ("GET", "/api/v2/grupos"): "administracao",
    ("GET", "/api/v2/grupos/{grupo_id}"): "administracao",
    ("GET", "/api/v2/grupos/{grupo_id}/transacoes"): "administracao",
    ("GET", "/api/v2/jobs"): "protocolo",
    ("GET", "/api/v2/jobs/agenda"): "protocolo",
    ("GET", "/api/v2/jobs/{job_id}"): "protocolo",
    ("GET", "/api/v2/jobs/{job_id}/resultado"): "protocolo",
}


def slugs_de_modulo_por_rota(app=None) -> dict[tuple[str, str], str]:
    """Para cada rota GET com gate de módulo, devolve o slug que ela exige.

    Lê `modulo_slug`, atributo exposto por `require_modulo` na própria
    closure (`app/auth/modulos.py`) — é o único jeito de diferenciar
    `require_modulo("protocolo")` de `require_modulo("frota")` de fora, já
    que ambos compilam para o mesmo `(__module__, __qualname__)`.
    """
    if app is None:
        from app.main import app

    resultado: dict[tuple[str, str], str] = {}
    for rota in app.routes:
        caminho = getattr(rota, "path", "")
        if not caminho.startswith("/api/v2"):
            continue
        deps = getattr(getattr(rota, "dependant", None), "dependencies", [])
        for metodo in getattr(rota, "methods", set()):
            if metodo != "GET":
                continue
            for d in deps:
                slug = getattr(getattr(d, "call", None), "modulo_slug", None)
                if slug is not None:
                    resultado[(metodo, caminho)] = slug
    return resultado


def test_rotas_por_modulo_bate_com_a_implementacao():
    """ROTAS_POR_MODULO é a decisão humana de QUAL módulo — não só QUE há gate.

    Reprova nos dois sentidos: rota com gate de módulo fora da tabela (nova e
    não registrada), e rota da tabela com slug diferente do que a rota
    realmente exige (copy-paste do slug errado).
    """
    reais = slugs_de_modulo_por_rota()

    fora_da_tabela = set(reais) - set(ROTAS_POR_MODULO)
    assert not fora_da_tabela, (
        f"Rotas com gate de módulo sem entrada em ROTAS_POR_MODULO: "
        f"{sorted(fora_da_tabela)}. Registre qual módulo cada uma exige."
    )

    divergentes = {
        rota: {"esperado": esperado, "real": reais.get(rota)}
        for rota, esperado in ROTAS_POR_MODULO.items()
        if reais.get(rota) != esperado
    }
    assert not divergentes, (
        f"Rotas com slug diferente do declarado em ROTAS_POR_MODULO: {divergentes}"
    )


def endpoints_sem_gate(app=None) -> set[tuple[str, str]]:
    """Varre `app` e devolve (método, caminho) sem gate reconhecido.

    `app=None` (default) resolve `app.main.app` — a aplicação real. Parâmetro
    existe para o teste de assimetria poder passar uma app fake e exercitar
    esta função de verdade, em vez de reimplementar o laço por conta própria
    (reimplementação que não pega regressão nesta função).

    `dependant.dependencies` cobre tanto `dependencies=[...]` da rota/router
    quanto os `Depends()` da assinatura do endpoint, que é onde a maioria dos
    routers deste repo põe o gate.
    """
    if app is None:
        from app.main import app

    desprotegidos: set[tuple[str, str]] = set()
    for rota in app.routes:
        caminho = getattr(rota, "path", "")
        if not caminho.startswith("/api/v2"):
            continue
        origens = {
            (getattr(d.call, "__module__", ""), getattr(d.call, "__qualname__", ""))
            for d in getattr(getattr(rota, "dependant", None), "dependencies", [])
            if getattr(d, "call", None) is not None
        }
        for metodo in getattr(rota, "methods", set()):
            # Leitura pode ser protegida só pela contratação do módulo (esta fatia).
            # Escrita, não: afrouxar aqui deixaria um POST com require_modulo e sem
            # require_permission passar no CI, que é justamente o falso-negativo que
            # a nota de GATES_DE_PERMISSAO descreve.
            aceitos = (
                GATES_DE_PERMISSAO | GATES_DE_MODULO
                if metodo == "GET"
                else GATES_DE_PERMISSAO
            )
            if not (origens & aceitos):
                desprotegidos.add((metodo, caminho))
    return desprotegidos


def test_gates_de_permissao_batem_com_a_implementacao():
    """Se `perms.py`/`modulos.py` renomear a closure, a varredura silencia — trava isso.

    Sem este teste, `GATES_DE_PERMISSAO`/`GATES_DE_MODULO` desatualizados fariam
    `endpoints_sem_gate()` considerar TODOS os endpoints desprotegidos
    (falso-positivo ruidoso) ou — pior, se alguém "consertasse" relaxando o
    critério — nenhum. O casamento exato só é seguro se for verificado. Cobre
    também `auth/modulos.py`: um rename silencioso de `_check_modulo`
    desligaria o reconhecimento do gate de leitura sem ninguém notar.
    """
    from app.auth.modulos import require_modulo
    from app.auth.perms import require_any_permission, require_permission

    reais_permissao = {
        (fabrica("x").__module__, fabrica("x").__qualname__)
        for fabrica in (require_permission, require_any_permission)
    }
    assert reais_permissao == GATES_DE_PERMISSAO, (
        f"As closures de perms.py mudaram: {sorted(reais_permissao)} != "
        f"{sorted(GATES_DE_PERMISSAO)}. Atualize GATES_DE_PERMISSAO."
    )

    reais_modulo = {
        (require_modulo("x").__module__, require_modulo("x").__qualname__)
    }
    assert reais_modulo == GATES_DE_MODULO, (
        f"A closure de modulos.py mudou: {sorted(reais_modulo)} != "
        f"{sorted(GATES_DE_MODULO)}. Atualize GATES_DE_MODULO."
    )


def test_nenhum_endpoint_novo_sem_permissao():
    """Endpoint sem gate reconhecido escapa do enforcement de módulo.

    As duas allowlists acima são a decisão humana registrada. Endpoint novo que
    caia fora delas reprova o PR — ou ganha require_permission (ou, em
    leitura, require_modulo), ou entra na lista com justificativa.
    """
    allowlist = ENDPOINTS_TRANSVERSAIS | ENDPOINTS_LEITURA_SEM_GATE
    novos = endpoints_sem_gate() - allowlist
    assert not novos, (
        f"Endpoints sem gate fora da allowlist: {sorted(novos)}. "
        "Acrescente a dependência ou registre em ENDPOINTS_TRANSVERSAIS / "
        "ENDPOINTS_LEITURA_SEM_GATE com justificativa."
    )


def test_allowlist_nao_tem_entrada_obsoleta():
    """Allowlist que apodrece deixa de ser decisão e passa a ser ruído.

    Endpoint que ganhou gate — ou que foi removido — tem de sair da lista.
    Sem isto, a dívida de ENDPOINTS_LEITURA_SEM_GATE parece do mesmo tamanho
    para sempre, mesmo depois de paga.
    """
    allowlist = ENDPOINTS_TRANSVERSAIS | ENDPOINTS_LEITURA_SEM_GATE
    obsoletos = allowlist - endpoints_sem_gate()
    assert not obsoletos, (
        f"Entradas obsoletas na allowlist: {sorted(obsoletos)}. "
        "O endpoint ganhou require_permission ou deixou de existir — remova a linha."
    )


def test_escrita_so_com_require_modulo_continua_desprotegida():
    """Trava a assimetria: `require_modulo` sozinho NUNCA basta para escrita.

    Constrói uma app FastAPI isolada com uma rota POST protegida só por
    `require_modulo` (sem `require_permission`) e chama `endpoints_sem_gate`
    de VERDADE sobre ela (via o parâmetro `app`) — não uma cópia do laço.
    Uma cópia local não pegaria regressão na função de produção; é ela que
    tem de continuar reportando a rota como desprotegida. Sem este teste,
    alguém "simplifica" `endpoints_sem_gate` de volta para um único conjunto
    aceito em qualquer método, e o afrouxamento de escrita volta sem aviso —
    é exatamente o falso-negativo que a nota de `GATES_DE_PERMISSAO` descreve.
    """
    from fastapi import Depends, FastAPI

    from app.auth.modulos import require_modulo

    app_fake = FastAPI()

    @app_fake.post("/api/v2/_fake/so-modulo", dependencies=[Depends(require_modulo("frota"))])
    async def _rota_fake():
        return None

    desprotegidos = endpoints_sem_gate(app=app_fake)

    assert ("POST", "/api/v2/_fake/so-modulo") in desprotegidos, (
        "Uma rota POST protegida só por require_modulo deveria continuar "
        "desprotegida — a varredura não pode aceitar GATES_DE_MODULO fora de GET."
    )


def test_leitura_so_com_require_modulo_nao_fica_desprotegida():
    """Metade complementar da assimetria: em GET, `require_modulo` sozinho BASTA.

    É exatamente o mecanismo que a Task 2 usa nas 58 rotas de leitura de
    `protocolo` — sem este teste, só a metade POST da assimetria estaria
    coberta e uma regressão que removesse GATES_DE_MODULO do lado GET (ou
    que trocasse `if metodo == "GET"` por outra condição) passaria batida.
    """
    from fastapi import Depends, FastAPI

    from app.auth.modulos import require_modulo

    app_fake = FastAPI()

    @app_fake.get("/api/v2/_fake/leitura-so-modulo", dependencies=[Depends(require_modulo("frota"))])
    async def _rota_fake():
        return None

    desprotegidos = endpoints_sem_gate(app=app_fake)

    assert ("GET", "/api/v2/_fake/leitura-so-modulo") not in desprotegidos, (
        "Uma rota GET protegida só por require_modulo NÃO pode aparecer como "
        "desprotegida — GATES_DE_MODULO existe justamente para isso."
    )
