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


ENDPOINTS_LEITURA_SEM_GATE: set[tuple[str, str]] = {
    # DÍVIDA REGISTRADA, não absolvição. Estes endpoints PERTENCEM a um módulo
    # e hoje não têm gate porque os routers da geração protocolo seguem uma
    # convenção anterior à modularização: *escrita gateada, leitura liberada a
    # qualquer usuário autenticado do tenant*. Verificado router a router —
    # todo POST/PUT/DELETE vizinho exige `require_permission` com o código do
    # módulo, e nenhum GET exige. Os módulos novos (pagamentos, frota,
    # transporte) já gateiam leitura também: nenhum deles aparece aqui.
    #
    # Consequência real do que está registrado abaixo: tenant sem o módulo
    # contratado continua LENDO os dados do módulo. Fechar isso é mudança de
    # política de produto — tira leitura de quem tem hoje — e por isso ficou
    # fora da Task 8, que entrega as guardas.
    #
    # O código anotado em cada grupo é o que o endpoint deve receber quando a
    # dívida for paga. Ao gatear um item, REMOVA-O daqui: a guarda de higiene
    # abaixo reprova entrada obsoleta.

    # Task 2 (2026-07-30) pagou a dívida `protocolo`: as 58 rotas que estavam
    # aqui (processo/catalogo/assunto/manifestante/cidade/endereco/workflow +
    # relatórios + `/catalogo/prioridades`, que mudou de dono) ganharam
    # `require_modulo("protocolo")` no mesmo commit. Ficam só as que continuam
    # sem gate: `busca` (transversal) e `jobs` (administracao, Task 3).
    ("GET", "/api/v2/busca"),
    # Jobs assíncronos: os artefatos são todos de protocolo, mas o próprio
    # mecanismo de fila é administracao (mapa-rotas.md). Os POST que disparam
    # esses jobs já exigem `processo` desde a Task 8; a listagem e o download
    # do resultado ficam como leitura pendente para a Task 3.
    ("GET", "/api/v2/jobs"),
    ("GET", "/api/v2/jobs/agenda"),
    ("GET", "/api/v2/jobs/{job_id}"),
    ("GET", "/api/v2/jobs/{job_id}/resultado"),

    # administracao / código `usuario`
    ("GET", "/api/v2/usuarios"),
    ("GET", "/api/v2/usuarios/{usuario_id}"),
    ("GET", "/api/v2/grupos"),
    ("GET", "/api/v2/grupos/{grupo_id}"),
    ("GET", "/api/v2/grupos/{grupo_id}/transacoes"),

    # administracao / código `unidadeTrabalho`
    ("GET", "/api/v2/unidades-trabalho"),
    ("GET", "/api/v2/unidades-trabalho/{unidade_id}"),
    ("GET", "/api/v2/organograma"),

    # administracao / código `configuracao` — catálogos de apoio do cadastro de
    # usuário/grupo/unidade (níveis, sistemas, transações, tipos de unidade) e
    # a trilha de auditoria.
    ("GET", "/api/v2/catalogo/niveis"),
    ("GET", "/api/v2/catalogo/sistemas"),
    ("GET", "/api/v2/catalogo/transacoes"),
    ("GET", "/api/v2/catalogo/tipos-unidade"),
    # `/catalogo/prioridades` mudou de dono na Task 2: quem a consome é
    # AcoesProcesso.tsx (protocolo), não a tela de administração — já ganhou
    # require_modulo("protocolo") e saiu daqui.
    ("GET", "/api/v2/audit"),
}


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
