# Fechar a leitura por módulo — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recomendado) ou superpowers:executing-plans. Os passos usam checkbox (`- [ ]`).

**Goal:** Um tenant que não contratou o módulo deixa de **ler** os dados dele pela API, sem que
nenhum usuário perca leitura que tenha hoje.

**Architecture:** Uma dependência nova, `require_modulo(slug)`, que checa **só a contratação do
tenant** — não olha usuário, grupo, transação nem nível. Aplicada a 70 dos 76 GETs hoje sem gate. Os
outros 6 ficam sem gate por decisão registrada.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, pytest.

**Escopo aprovado:** `docs/superpowers/specs/2026-07-30-leitura-por-modulo-escopo.md` — a
classificação dos 76 e a evidência de consumo de cada decisão estão lá. **Não reclassificar
endpoint sem refazer a verificação de consumo descrita naquele documento.**

---

## Global Constraints

- **pt-BR** em tudo: código, comentários, docstrings, mensagens de commit.
- `require_modulo` **não pode olhar o usuário.** Se alguma versão consultar grupo, transação ou
  nível, ela deixou de ser esta fatia e virou mudança de política de acesso — que é o que a decisão
  do Jorge excluiu.
- **Nenhum endpoint de escrita muda.** A escrita já está gateada desde a F1.
- Testes: `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/<arquivo> -v`. O
  `PYTEST_DB_HOST` é obrigatório.
- **Não rodar a suíte completa em subagente** — leva ~10 min e o watchdog mata em 600s. O controller
  roda.
- **Não rodar `docker compose build`** — o antivírus da máquina intercepta HTTPS e nenhuma imagem
  rebuilda. O backend é bind-mount; `docker exec` já vê o código da branch.
- Testes não assumem banco vazio; e-mails em domínio `.test`; slug com prefixo + `uuid4().hex[:8]`;
  cleanup no teardown.
- **Ordem de fixture:** em teste que use `admin_session` **e** `two_tenants`, `two_tenants` vem
  **antes**. Ver o comentário em `tests/test_permissoes_modulo.py` — a ordem inversa pendura a suíte
  quando uma asserção falha.

## A ordem das tasks é load-bearing

A guarda `test_allowlist_nao_tem_entrada_obsoleta` reprova quando um endpoint do
`ENDPOINTS_LEITURA_SEM_GATE` **passa a ter** gate. Então gatear rota e tirar da allowlist têm de
acontecer **no mesmo commit**, e a guarda precisa reconhecer `require_modulo` **antes** de qualquer
rota ser gateada.

Na F1 esse cuidado faltou — o gate entrou numa task e o provisionamento que o alimentava em outra, e
a branch ficou vermelha por construção entre as duas, com 8 testes falhando sem que ninguém tivesse
errado. Aqui a sequência abaixo mantém a branch verde em todo commit.

---

### Task 1: `require_modulo` e o reconhecimento pela guarda

**Files:**
- Create: `backend/app/auth/modulos.py`
- Modify: `backend/tests/test_guarda_modularizacao.py` (constante de gates)
- Test: `backend/tests/test_require_modulo.py`

**Interfaces:**
- Produces: `require_modulo(slug: str)` — dependency factory, mesmo formato de
  `require_permission` (`backend/app/auth/perms.py:35`)
- Consumes: `services.modulos.slugs_contratados(db, tenant_id)` e `auth.deps.require_tenant_id`,
  ambos já existentes

- [ ] **Passo 1: Escrever o teste**

`backend/tests/test_require_modulo.py`:

```python
"""`require_modulo` barra por CONTRATAÇÃO do tenant, não por permissão do usuário.

A propriedade central desta fatia está no último teste: usuário sem permissão
nenhuma continua lendo, desde que o tenant tenha o módulo. Se algum dia alguém
"melhorar" a dependência para também exigir permissão, esse teste reprova — e é
o único aviso de que a fatia mudou de natureza.
"""
import uuid

import pytest
from fastapi import HTTPException

from app.auth.modulos import require_modulo
from app.services.modulos import contratar


@pytest.mark.asyncio
async def test_barra_tenant_sem_o_modulo(two_tenants, admin_session):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()

    check = require_modulo("pagamentos")
    with pytest.raises(HTTPException) as e:
        await check(tenant_id=tid, db=admin_session)
    assert e.value.status_code == 403
    assert "pagamentos" in str(e.value.detail)
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_passa_com_o_modulo_contratado(two_tenants, admin_session):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()

    check = require_modulo("frota")
    assert await check(tenant_id=tid, db=admin_session) is None
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_modulo_nao_contratavel_nunca_barra(two_tenants, admin_session):
    """`comum` está sempre disponível — nem contratando zero módulos ele cai."""
    tid, _ = two_tenants
    await contratar(admin_session, tid, [])
    await admin_session.flush()

    check = require_modulo("comum")
    assert await check(tenant_id=tid, db=admin_session) is None
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_nao_consulta_permissao_do_usuario(two_tenants, admin_session):
    """A PROPRIEDADE DA FATIA: a dependência não recebe usuário e não o consulta.

    Se a assinatura passar a exigir `user`, este teste quebra na chamada — de
    propósito. A decisão registrada no escopo é que esta fatia fecha SÓ a
    contratação; exigir permissão de leitura é outra decisão, do dono do produto.
    """
    import inspect

    params = set(inspect.signature(require_modulo("frota")).parameters)
    assert params == {"tenant_id", "db"}, (
        "require_modulo passou a depender de algo além de tenant/db — se for o "
        "usuário, a fatia virou mudança de política de acesso"
    )
```

- [ ] **Passo 2: Rodar e ver falhar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_require_modulo.py -v
```

Esperado: `ModuleNotFoundError: No module named 'app.auth.modulos'`.

- [ ] **Passo 3: Implementar**

`backend/app/auth/modulos.py`:

```python
"""Gate de CONTRATAÇÃO de módulo, sem olhar o usuário.

Diferença para `require_permission` (auth/perms.py): aquele responde "este
usuário pode fazer isto?"; este responde "este tenant contratou este módulo?".
São perguntas diferentes e esta fatia responde só a segunda — por decisão
registrada em docs/superpowers/specs/2026-07-30-leitura-por-modulo-escopo.md.

Consequência deliberada: um usuário sem permissão nenhuma continua lendo o que
lê hoje, desde que o tenant tenha o módulo. Fechar isso é mudança de política
de acesso e tem item próprio no backlog.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services.modulos import slugs_contratados
from .deps import require_tenant_id


def require_modulo(slug: str):
    """Cria uma dependency que exige o módulo `slug` contratado pelo tenant."""

    async def _check_modulo(
        tenant_id: int = Depends(require_tenant_id),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        disponiveis = await slugs_contratados(db, tenant_id)
        if not disponiveis:
            # Mesma guarda de services/modulos.codigos_bloqueados: catálogo
            # corrompido (nem os não-contratáveis existem) tem de gritar, não
            # bloquear todo mundo em silêncio.
            raise RuntimeError(
                f"Nenhum módulo disponível para o tenant {tenant_id} — nem os "
                "não-contratáveis. Catálogo corrompido; verifique se 'comum' "
                "existe e está ativo."
            )
        if slug not in disponiveis:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Módulo '{slug}' não contratado para este tenant",
            )

    return _check_modulo
```

- [ ] **Passo 4: A guarda passa a reconhecer o gate novo**

Em `backend/tests/test_guarda_modularizacao.py`, acrescentar o par
`("app.auth.modulos", "require_modulo.<locals>._check_modulo")` à constante `GATES_DE_PERMISSAO`
(procure-a no arquivo; ela casa `(module, qualname)` **exato**, e existe um teste que a compara com
o que `auth/perms.py` realmente exporta — estenda-o para cobrir `auth/modulos.py` também).

**Ainda não mova nada da allowlist nesta task.** Nenhuma rota foi gateada; a allowlist continua
correta e a guarda continua verde.

- [ ] **Passo 5: Verificar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_require_modulo.py tests/test_guarda_modularizacao.py -v
```

Esperado: 4 novos passando + as guardas passando sem alteração de contagem.

- [ ] **Passo 6: Commit**

```bash
git add backend/app/auth/modulos.py backend/tests/test_require_modulo.py backend/tests/test_guarda_modularizacao.py
git commit -m "feat(modulos): dependencia require_modulo, que checa contratacao sem olhar usuario"
```

---

### Task 2: Gatear os 58 de `protocolo`

**Files:**
- Modify: os routers que servem os 58 GETs classificados como `protocolo` no escopo
- Modify: `backend/tests/test_guarda_modularizacao.py` (tirar os 58 da allowlist, **no mesmo commit**)
- Test: `backend/tests/test_leitura_por_modulo.py` (criar)

**Interfaces:** consome `require_modulo` da Task 1.

A lista canônica dos 58 está na tabela do escopo. Inclui `/catalogo/prioridades`, que **muda de
dono** — está agrupado sob administração no `ENDPOINTS_LEITURA_SEM_GATE`, mas quem o consome é
`AcoesProcesso.tsx`, tela de protocolo. Gateá-lo como administração daria 403 nas ações de processo
de um tenant sem administração.

- [ ] **Passo 1: Escrever o teste HTTP**

```python
"""Tenant sem o módulo não LÊ os dados dele — e usuário sem permissão continua lendo.

Os dois lados da decisão desta fatia, no mesmo arquivo de propósito: quem mexer
num vê o outro.
"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.modulos import contratar

# Um representativo por grupo de rota — a cobertura de todos os 58 é estrutural,
# feita pela guarda, não por teste HTTP rota a rota.
ROTAS_PROTOCOLO = [
    "/api/v2/processos",
    "/api/v2/assuntos",
    "/api/v2/manifestantes",
    "/api/v2/cidades",
    "/api/v2/workflow-definitions",
    "/api/v2/catalogo/prioridades",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("rota", ROTAS_PROTOCOLO)
async def test_sem_protocolo_contratado_leitura_da_403(rota, tenant_sem_protocolo):
    token, _ = tenant_sem_protocolo
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(rota, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403, f"{rota} deveria estar barrada: {r.status_code}"


@pytest.mark.asyncio
@pytest.mark.parametrize("rota", ROTAS_PROTOCOLO)
async def test_com_protocolo_contratado_leitura_passa(rota, tenant_com_protocolo):
    token, _ = tenant_com_protocolo
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(rota, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code != 403, f"{rota} não deveria estar barrada: {r.status_code}"


@pytest.mark.asyncio
async def test_usuario_sem_permissao_continua_lendo(tenant_com_protocolo_usuario_nu):
    """A PROPRIEDADE DA FATIA. Se este teste falhar, alguém trocou require_modulo
    por require_permission e a fatia virou mudança de política de acesso."""
    token, _ = tenant_com_protocolo_usuario_nu
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v2/processos", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code != 403, (
        "usuário sem permissão perdeu leitura — esta fatia fecha contratação, "
        "não autorização"
    )
```

As três fixtures (`tenant_sem_protocolo`, `tenant_com_protocolo`,
`tenant_com_protocolo_usuario_nu`) provisionam tenant + emitem token. Espelhe o padrão de
`tests/test_permissoes_modulo.py::test_http_su_sem_modulo_recebe_403`, que já faz exatamente isso —
inclusive o `_cleanup_tenant` do teardown. Para o "usuário nu", crie usuário em grupo de nível **≠
0** sem nenhuma linha em `grupo_transacao`; use o get-or-create de nível daquele arquivo, porque
**o bootstrap garante só o nível 0** e em banco limpo o nível operacional não existe.

- [ ] **Passo 2: Rodar e ver falhar** — as rotas ainda respondem 200 sem contratação.

- [ ] **Passo 3: Gatear as 58 rotas**

Em cada router, acrescentar à rota:

```python
dependencies=[Depends(require_modulo("protocolo"))]
```

Onde a rota já tem `dependencies=[...]`, **acrescentar** ao final da lista, não substituir.

- [ ] **Passo 4: Tirar as 58 da allowlist** — no mesmo commit. A guarda reprova entrada obsoleta.

- [ ] **Passo 5: Verificar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_leitura_por_modulo.py tests/test_guarda_modularizacao.py -v
```

- [ ] **Passo 6: Commit** com os routers, a allowlist e o teste juntos.

---

### Task 3: Gatear os 12 de `administracao`

Mesma mecânica da Task 2, com `require_modulo("administracao")`, sobre: `/grupos`,
`/grupos/{id}`, `/grupos/{id}/transacoes`, `/organograma`, `/catalogo/niveis`,
`/catalogo/sistemas`, `/catalogo/transacoes`, `/catalogo/tipos-unidade`, `/jobs`, `/jobs/agenda`,
`/jobs/{job_id}`, `/jobs/{job_id}/resultado`.

- [ ] **Passo 1**: acrescentar ao teste da Task 2 um `ROTAS_ADMINISTRACAO` com representativos
  (`/grupos`, `/catalogo/niveis`, `/jobs`) e as fixtures equivalentes de tenant sem/com
  administração.
- [ ] **Passo 2**: rodar e ver falhar.
- [ ] **Passo 3**: gatear as 12.
- [ ] **Passo 4**: tirar as 12 da allowlist, mesmo commit.
- [ ] **Passo 5**: verificar.
- [ ] **Passo 6**: commit.

> **Os 4 de `/jobs` carregam uma inconsistência aceita**, registrada no escopo: o POST
> `/jobs/limpar-antigos` exige `processo` (protocolo) desde a Task 8 da F1, enquanto estes GETs
> passam a exigir administração. Um tenant com protocolo e sem administração dispara o job e não lê
> o resultado. Foi decisão do Jorge em 2026-07-30. **Não "corrigir" isso sem falar com ele.**

---

### Task 4: Os 6 transversais ganham razão escrita

**Files:** `backend/tests/test_guarda_modularizacao.py`

Sobram na allowlist exatamente 6 entradas. Cada uma recebe o motivo **de não ter gate**, no lugar do
comentário atual (que diz "dívida a pagar" — deixou de ser verdade para estas):

- `/usuarios`, `/usuarios/{usuario_id}` — consumo cruzado comprovado: protocolo (relatório de
  assinaturas, `AssinaturasProcesso`), transporte (alvarás) e administração. Gatear quebraria os
  dois primeiros.
- `/unidades-trabalho`, `/unidades-trabalho/{unidade_id}` — consumo cruzado por **4** módulos:
  administração, frota (motoristas, solicitações, veículos) e protocolo (processos, relatórios,
  tramitação, serviços, `AcoesProcesso`).
- `/busca` — decisão do Jorge: recurso do sistema, não do módulo; vai indexar outros módulos.
- `/audit` — decisão do Jorge: compliance registra ações de todos os módulos, e o tenant não pode
  perder a leitura da própria trilha por não ter contratado administração.

- [ ] **Passo 1**: reescrever o cabeçalho do `ENDPOINTS_LEITURA_SEM_GATE` — de "dívida registrada"
  para "decisões registradas", com o motivo por entrada.
- [ ] **Passo 2**: acrescentar teste que reprova se a lista crescer: hoje são 6, e entrada nova
  exige justificativa explícita no mesmo commit.
- [ ] **Passo 3**: verificar e commitar.

---

### Task 5: Medir o custo e decidir a memoização

Cada rota gateada passa a resolver a contratação — duas consultas por request
(`slugs_contratados` faz dois `SELECT`). São 70 rotas, várias de listagem quente.

- [ ] **Passo 1**: medir. Rodar `tests/test_leitura_por_modulo.py` com `--durations=10` antes e
  depois do gate, e cronometrar um `GET /api/v2/processos` pelo nginx com e sem a dependência.
- [ ] **Passo 2**: **se e só se** a medição mostrar custo relevante, memoizar por request:
  guardar o resultado de `slugs_contratados` em `request.state` na primeira chamada.
  Não implementar antes de medir — otimização sem medida é chute, e o custo pode ser irrelevante
  perto do resto da query da listagem.
- [ ] **Passo 3**: registrar o número medido no escopo, para a próxima pessoa não refazer a conta.

---

## Critério de aceite da fatia

- Tenant sem `protocolo`: os representativos de leitura de protocolo devolvem **403**
- Tenant sem `administracao`: idem para os de administração
- **Usuário sem permissão nenhuma, tenant com o módulo: continua lendo** — a propriedade da fatia
- Super-usuário de tenant sem o módulo: **403** (a dependência não tem bypass)
- `ENDPOINTS_LEITURA_SEM_GATE` com exatamente **6** entradas, cada uma com o motivo escrito
- Suíte completa nas 2 falhas pré-existentes conhecidas — nada a mais
- Nenhum endpoint de escrita alterado

## Fora de escopo

O buraco de autorização — `/usuarios`, `/grupos`, `/audit` seguem legíveis por qualquer autenticado
do tenant. Vira item de backlog. Concessão das 9 transações a grupos (item 1.0.7): esta fatia
deliberadamente **não** depende dela.
