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
    """), {"app": get_settings().app_name})).scalars().all()
    assert not orfas, (
        f"Transações sem módulo: {orfas}. "
        "Mapeie em MODULO_TRANSACOES (app/cli/seed_bootstrap.py) e rode o seed."
    )


# ---------------------------------------------------------------------------
# Guarda 2 — endpoint sem require_permission
#
# `require_permission` é o único ponto onde o enforcement de módulo acontece
# (Task 5: o gate roda antes até do bypass de super-usuário). Endpoint sem essa
# dependência escapa do enforcement, e o esquecimento é silencioso.
#
# A varredura devolve todos os endpoints `/api/v2` sem o gate. Cada um foi
# julgado individualmente e caiu num destes dois conjuntos. Os dois juntos
# formam a allowlist; qualquer endpoint fora deles reprova o PR.
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

    # protocolo / código `processo` — leitura de processo e seus artefatos
    ("GET", "/api/v2/processos"),
    ("GET", "/api/v2/processos/{processo_id}"),
    ("GET", "/api/v2/processos/{processo_id}/capa.pdf"),
    ("GET", "/api/v2/processos/{processo_id}/completo.pdf"),
    ("GET", "/api/v2/processos/{processo_id}/etiqueta-dupla.pdf"),
    ("GET", "/api/v2/processos/{processo_id}/etiqueta-unica.pdf"),
    ("GET", "/api/v2/processos/{processo_id}/trail"),
    ("GET", "/api/v2/processos/{processo_id}/volumes"),
    ("GET", "/api/v2/processos/{processo_id}/apensados"),
    ("GET", "/api/v2/processos/{processo_id}/apensamentos"),
    ("GET", "/api/v2/processos/{processo_id}/complementacoes"),
    ("GET", "/api/v2/processos/{processo_id}/checklist-documentos"),
    ("GET", "/api/v2/processos/{processo_id}/temporalidade"),
    ("GET", "/api/v2/processos/{processo_id}/workflow"),
    ("GET", "/api/v2/processos/{processo_id}/solicitacoes-assinatura"),
    ("GET", "/api/v2/processos/apensamentos/{apensamento_id}/termo.pdf"),
    ("GET", "/api/v2/processos/encaminhamentos/{encaminhamento_id}/comprovante.pdf"),
    ("GET", "/api/v2/processos/{processo_id}/anexos/{anexo_processo_id}/termo-desentranhamento.pdf"),
    ("GET", "/api/v2/protocolo/{processo_id}/comprovante.pdf"),
    ("GET", "/api/v2/protocolo/{processo_id}/etiqueta.pdf"),
    ("GET", "/api/v2/protocolo/vencendo-prazo"),
    ("GET", "/api/v2/anexos/{anexo_id}/download"),
    ("GET", "/api/v2/anexos/{anexo_id}/carimbado.pdf"),
    ("GET", "/api/v2/assinaturas/{assinatura_anexo_id}/validar"),
    ("GET", "/api/v2/assinaturas/{assinatura_anexo_id}/evidencias"),
    ("GET", "/api/v2/assinaturas/{assinatura_anexo_id}/comprovante.pdf"),
    ("GET", "/api/v2/busca"),
    # Relatórios são recorte de processo/assinatura/tramitação — mesmo código.
    ("GET", "/api/v2/relatorios/processos.csv"),
    ("GET", "/api/v2/relatorios/processos.json"),
    ("GET", "/api/v2/relatorios/processos.pdf"),
    ("GET", "/api/v2/relatorios/tramitacao.csv"),
    ("GET", "/api/v2/relatorios/tramitacao.json"),
    ("GET", "/api/v2/relatorios/tramitacao.pdf"),
    ("GET", "/api/v2/relatorios/assinaturas.csv"),
    ("GET", "/api/v2/relatorios/assinaturas.json"),
    ("GET", "/api/v2/relatorios/assinaturas.pdf"),
    # Jobs assíncronos: os artefatos são todos de protocolo. Os POST que
    # disparam esses jobs passaram a exigir `processo`/`configuracao` na
    # Task 8; a listagem e o download do resultado ficaram como leitura.
    ("GET", "/api/v2/jobs"),
    ("GET", "/api/v2/jobs/agenda"),
    ("GET", "/api/v2/jobs/{job_id}"),
    ("GET", "/api/v2/jobs/{job_id}/resultado"),

    # protocolo / código `catalogo` — tipos e classificação documental
    ("GET", "/api/v2/tipos-processo"),
    ("GET", "/api/v2/tipos-anexo"),
    ("GET", "/api/v2/protocolo/ccd-classes"),
    ("GET", "/api/v2/protocolo/ccd-classes/tree"),
    ("GET", "/api/v2/protocolo/especies-documentais"),
    ("GET", "/api/v2/protocolo/ttd-regras"),
    ("GET", "/api/v2/protocolo/sugerir-ccd"),

    # protocolo / código `assunto`
    ("GET", "/api/v2/assuntos"),
    ("GET", "/api/v2/assunto-tipo-anexo"),

    # protocolo / código `manifestante`
    ("GET", "/api/v2/manifestantes"),
    ("GET", "/api/v2/tipos-manifestante"),

    # protocolo / códigos `cidade` e `endereco`
    ("GET", "/api/v2/estados"),
    ("GET", "/api/v2/cidades"),
    ("GET", "/api/v2/bairros"),
    ("GET", "/api/v2/enderecos"),

    # protocolo / código `workflow` — leitura do desenho e das instâncias
    ("GET", "/api/v2/workflow-definitions"),
    ("GET", "/api/v2/workflow-definitions/{wf_id}"),
    ("GET", "/api/v2/workflow-definitions/{wf_id}/versoes"),
    ("GET", "/api/v2/workflow-instances"),
    ("GET", "/api/v2/workflow-instances/{instance_id}"),
    ("GET", "/api/v2/workflow-alertas"),
    ("GET", "/api/v2/tipo-processo-workflow"),

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
    ("GET", "/api/v2/catalogo/prioridades"),
    ("GET", "/api/v2/audit"),
}


def endpoints_sem_permissao() -> set[tuple[str, str]]:
    """Varre o app e devolve (método, caminho) sem gate de permissão.

    `dependant.dependencies` cobre tanto `dependencies=[...]` da rota/router
    quanto os `Depends()` da assinatura do endpoint, que é onde a maioria dos
    routers deste repo põe o gate. `require_permission` e
    `require_any_permission` devolvem uma closure chamada `_check` — daí o
    critério pelo `__qualname__`.
    """
    from app.main import app

    desprotegidos: set[tuple[str, str]] = set()
    for rota in app.routes:
        caminho = getattr(rota, "path", "")
        if not caminho.startswith("/api/v2"):
            continue
        deps = [
            d.call.__qualname__
            for d in getattr(getattr(rota, "dependant", None), "dependencies", [])
            if getattr(d, "call", None) is not None
        ]
        tem_perm = any("_check" in q or "require_permission" in q for q in deps)
        if not tem_perm:
            for metodo in getattr(rota, "methods", set()):
                desprotegidos.add((metodo, caminho))
    return desprotegidos


def test_nenhum_endpoint_novo_sem_permissao():
    """Endpoint sem require_permission escapa do enforcement de módulo.

    As duas allowlists acima são a decisão humana registrada. Endpoint novo que
    caia fora delas reprova o PR — ou ganha require_permission, ou entra na
    lista com justificativa.
    """
    allowlist = ENDPOINTS_TRANSVERSAIS | ENDPOINTS_LEITURA_SEM_GATE
    novos = endpoints_sem_permissao() - allowlist
    assert not novos, (
        f"Endpoints sem require_permission fora da allowlist: {sorted(novos)}. "
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
    obsoletos = allowlist - endpoints_sem_permissao()
    assert not obsoletos, (
        f"Entradas obsoletas na allowlist: {sorted(obsoletos)}. "
        "O endpoint ganhou require_permission ou deixou de existir — remova a linha."
    )
