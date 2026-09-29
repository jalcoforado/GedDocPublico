"""Assistente global — IA-2: pergunta em linguagem natural que busca ENTRE processos.

Na IA-1 o modelo recebe UM processo que o usuário já abriu, depois de todos os
guards. Aqui é diferente, e é por isso que a fatia foi adiada (backlog §2.5):
o assistente **procura** processos a partir da pergunta, e um buscador pode
entregar numa frase o que a interface esconde. A regra que este módulo existe
para garantir:

    o assistente nunca devolve, cita, conta ou resume um processo que o mesmo
    usuário não veria em `GET /processos`.

Como ela é garantida — por construção, não por disciplina:

1. **A busca É a listagem.** `buscar()` chama `services.processos.list_processos`
   com os mesmos argumentos de contexto que `routers/processos.py::list_endpoint`
   passa (tenant, níveis de sigilo, usuário, lotação principal). Tenant vem do
   caller (`tenant_filter` dentro de `_base_select`), excluído e rascunho saem
   pelas mesmas cláusulas, e o sigilo é decidido por
   `services.sigilo.niveis_acesso_usuario` — a MESMA função que a listagem usa.
   Regra nova na listagem vale aqui sem ninguém lembrar.
2. **O LLM não monta consulta.** A primeira chamada ao modelo só traduz a
   pergunta em parâmetros, e a saída dele é tratada como entrada hostil
   (`validar_parametros`): whitelist de campos, tipo conferido campo a campo,
   tamanho limitado, o resto descartado em silêncio. Nenhum parâmetro aceito
   AMPLIA o conjunto — todos só recortam o que a listagem já devolveria. Não
   existe campo para tenant, sigilo, situação, página ou limite: o teto de
   resultados é constante deste módulo. Nada chega ao banco como SQL: os
   valores vão como parâmetros ligados do SQLAlchemy.
3. **O modelo não tem ferramenta.** A segunda chamada recebe a lista já
   filtrada no system prompt, como na IA-1. Não há o que ele possa chamar para
   alcançar outro processo.
4. **Números vêm do Python.** O total vem do `COUNT` da listagem e vai pronto
   no prompt e no evento `resultados` do SSE; o modelo é instruído a não
   contar (mesma decisão da IA-1, regra 4).

O que a fatia NÃO resolve, e está registrado no backlog §2.5: ela herda o
escopo da listagem, que é "todo processo do tenant até a minha credencial de
sigilo" para quem tem a transação `processo`. Se esse escopo for largo demais,
o conserto é na listagem (política 1.0.7), não aqui.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from ...schemas.processo import EscopoProcesso, ProcessoListItem
from ..processos import list_processos
from ..sigilo import niveis_acesso_usuario
from .assistente import PERGUNTA_MAX, PERGUNTA_MIN, AssistenteError
from .conhecimento import GLOSSARIO, REGRAS_BUSCA
from .llm_client import LLMClient

# Quantos processos entram no prompt. Constante, e de propósito fora do alcance
# do modelo: um "limite" vindo da saída do LLM seria a primeira coisa que uma
# pergunta maliciosa pediria para aumentar.
MAX_RESULTADOS = 10

# Teto do termo de busca. O `q` da listagem não tem teto próprio porque vem de
# um campo de tela; aqui vem de um modelo, que pode devolver um parágrafo.
BUSCA_MAX = 100

# Quanto da resposta do extrator lemos. Um JSON com seis campos cabe folgado; o
# resto é o modelo falando demais, e não há por que pagar por isso.
EXTRACAO_MAX_CHARS = 2000

CAMPOS_PERMITIDOS = frozenset(
    {"busca", "apenas_ativos", "escopo", "favoritos", "desde", "ate"}
)

# Ano plausível para filtro de data. Fora disso é alucinação ou tentativa de
# estourar o `datetime` — em ambos os casos, o campo cai.
_ANO_MIN, _ANO_MAX = 1900, 2100

_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class ParametrosBusca:
    """Os ÚNICOS parâmetros que o modelo consegue influenciar.

    Todos recortam. Nenhum amplia: não há como, a partir daqui, pedir outro
    tenant, outro nível de sigilo, rascunho, página ou mais resultados.
    """

    busca: str | None = None
    apenas_ativos: bool = False
    escopo: EscopoProcesso | None = None
    favoritos: bool = False
    desde: date | None = None
    ate: date | None = None

    def como_dict(self) -> dict:
        d = asdict(self)
        d["escopo"] = self.escopo.value if self.escopo else None
        d["desde"] = self.desde.isoformat() if self.desde else None
        d["ate"] = self.ate.isoformat() if self.ate else None
        return d


@dataclass
class ResultadoBusca:
    parametros: ParametrosBusca
    total: int
    processos: list[ProcessoListItem] = field(default_factory=list)


# ============================================================
# 1. Extração de parâmetros — a saída do modelo é entrada hostil
# ============================================================

SYSTEM_EXTRATOR = """\
Você converte uma pergunta sobre processos administrativos em filtros de busca.
Responda APENAS com um objeto JSON, sem texto antes ou depois, com estes campos
(omita os que a pergunta não pedir):

- "busca": texto curto para procurar em número do processo, número de origem,
  nome ou CPF/CNPJ do manifestante, ou assunto. Ex.: "poda", "Maria Silva".
- "apenas_ativos": true se a pergunta pedir só processos ativos/em andamento.
- "escopo": "meus" (sob minha responsabilidade), "unidade" (no meu setor) ou
  "unidade_e_subordinadas".
- "favoritos": true se a pergunta pedir só os favoritos.
- "desde" / "ate": datas de abertura no formato AAAA-MM-DD.

Exemplo: {"busca": "poda", "apenas_ativos": true}
Se nada disso se aplicar, responda {}."""


def _termo_busca(valor) -> str | None:
    if not isinstance(valor, str):
        return None
    termo = " ".join(_CONTROLE.sub(" ", valor).split())
    if not termo:
        return None
    return termo[:BUSCA_MAX]


def _data(valor) -> date | None:
    if not isinstance(valor, str) or len(valor) != 10:
        return None
    try:
        d = date.fromisoformat(valor)
    except ValueError:
        return None
    return d if _ANO_MIN <= d.year <= _ANO_MAX else None


def validar_parametros(bruto) -> ParametrosBusca:
    """Converte o que o modelo devolveu em `ParametrosBusca`, ou em nada.

    Campo fora da whitelist é ignorado; campo da whitelist com tipo errado
    também — sem coerção: `"true"` não vira `True`, `"1"` não vira nada. Um
    campo inválido não derruba os outros, e nada aqui levanta: a pior saída do
    modelo produz a busca padrão, que é a própria listagem.
    """
    if not isinstance(bruto, dict):
        return ParametrosBusca()

    busca = _termo_busca(bruto.get("busca"))

    # `is True`, não truthiness: `"sim"`, `1` e `[0]` não são booleano.
    apenas_ativos = bruto.get("apenas_ativos") is True
    favoritos = bruto.get("favoritos") is True

    escopo = None
    if isinstance(bruto.get("escopo"), str):
        try:
            escopo = EscopoProcesso(bruto["escopo"])
        except ValueError:
            escopo = None

    desde = _data(bruto.get("desde"))
    ate = _data(bruto.get("ate"))
    if desde and ate and desde > ate:
        # Intervalo invertido não é filtro, é engano — descartar os dois é
        # mais honesto que "consertar" adivinhando qual das datas vale.
        desde = ate = None

    return ParametrosBusca(
        busca=busca,
        apenas_ativos=apenas_ativos,
        escopo=escopo,
        favoritos=favoritos,
        desde=desde,
        ate=ate,
    )


def _primeiro_objeto_json(texto: str):
    """Primeiro objeto JSON do texto, ou None. O modelo às vezes embrulha em
    ```json ... ``` ou antepõe uma frase; `raw_decode` a partir da primeira
    chave pega o objeto e ignora o resto."""
    inicio = texto.find("{")
    if inicio < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(texto[inicio:])
    except json.JSONDecodeError:
        return None
    return obj


async def extrair_parametros(pergunta: str, cliente: LLMClient) -> ParametrosBusca:
    """Pergunta ao modelo quais filtros aplicar e valida a resposta.

    O extrator recebe SÓ a pergunta — nenhum dado de processo. Erro de rede ou
    de provedor NÃO é engolido aqui (o router o transforma em 503/500); só a
    resposta malformada vira "sem filtro".
    """
    texto = ""
    async for pedaco in cliente.stream(system=SYSTEM_EXTRATOR, pergunta=pergunta):
        texto += pedaco
        if len(texto) >= EXTRACAO_MAX_CHARS:
            break
    return validar_parametros(_primeiro_objeto_json(texto[:EXTRACAO_MAX_CHARS]))


# ============================================================
# 2. Busca — a listagem de processos, com o contexto do usuário
# ============================================================


async def buscar(
    db: AsyncSession,
    *,
    parametros: ParametrosBusca,
    tenant_id: int,
    usuario,
) -> ResultadoBusca:
    """Executa a busca exatamente como `GET /processos` executaria.

    Os argumentos de CONTEXTO (tenant, sigilo, usuário, lotação) espelham
    `routers/processos.py::list_endpoint` um a um. `situacao` fica no default
    (`None` = exclui rascunho), igual à tela sem filtro.
    """
    niveis = await niveis_acesso_usuario(db, usuario, tenant_id=tenant_id)
    itens, total = await list_processos(
        db,
        tenant_id=tenant_id,
        page=1,
        page_size=MAX_RESULTADOS,
        q=parametros.busca,
        apenas_ativos=parametros.apenas_ativos,
        desde=(
            datetime.combine(parametros.desde, time.min) if parametros.desde else None
        ),
        ate=datetime.combine(parametros.ate, time.max) if parametros.ate else None,
        niveis_permitidos=niveis,
        escopo=parametros.escopo,
        favoritos=parametros.favoritos,
        id_usuario_contexto=usuario.id,
        id_unidade_contexto=usuario.id_unidade_trabalho,
    )
    return ResultadoBusca(parametros=parametros, total=total, processos=itens)


def _linha(valor) -> str:
    """Campo digitado por terceiro, achatado numa linha.

    Sem isto, um assunto com quebra de linha poderia forjar um cabeçalho
    ("## Resultado", "REGRAS") dentro do bloco de dados.
    """
    if valor is None:
        return "—"
    return " ".join(_CONTROLE.sub(" ", str(valor)).split()) or "—"


def montar_contexto_busca(resultado: ResultadoBusca) -> str:
    """Texto do resultado que vai ao modelo.

    Só campos que a tela de listagem já mostra. CPF/CNPJ do manifestante fica
    de fora mesmo sendo exibido lá: não ajuda a responder e seria dado pessoal
    saindo para um provedor externo sem necessidade.
    """
    mostrados = len(resultado.processos)
    linhas = [
        "## Resultado da busca (calculado pelo sistema)",
        f"- Total de processos encontrados: {resultado.total}",
        f"- Listados abaixo: {mostrados} (os mais recentes)",
    ]
    if resultado.total > mostrados:
        linhas.append(
            f"- Há {resultado.total - mostrados} processo(s) além destes que "
            "não foram listados; oriente o servidor a refinar a pergunta ou "
            "usar a tela de processos."
        )
    linhas.append("")
    linhas.append("## Processos")
    for p in resultado.processos:
        linhas.append(
            f"- Processo {_linha(p.numero_processo)}"
            f" | aberto em {p.data_hora_abertura.strftime('%d/%m/%Y')}"
            f" | assunto: {_linha(p.assunto)}"
            f" | tipo: {_linha(p.tipo_processo)}"
            f" | manifestante: {_linha(p.manifestante)}"
            f" | local atual: {_linha(p.local_atual)}"
            f" | responsável: {_linha(p.responsavel)}"
            f" | {'ativo' if p.ativo else 'encerrado'}"
            f" | sigilo: {p.nivel_sigilo}"
        )
    return "\n".join(linhas)


def montar_system_prompt_busca(resultado: ResultadoBusca) -> str:
    """Regras → glossário → dados, na ordem da IA-1 e pelo mesmo motivo."""
    return f"{REGRAS_BUSCA}\n\n{GLOSSARIO}\n\n---\n\n{montar_contexto_busca(resultado)}"


# ============================================================
# 3. Orquestração
# ============================================================

RESPOSTA_SEM_RESULTADO = (
    "Não encontrei processos que você possa ver com esses critérios. "
    "Tente outros termos ou consulte a tela de processos."
)


def validar_pergunta(pergunta: str | None) -> str:
    pergunta = (pergunta or "").strip()
    if len(pergunta) < PERGUNTA_MIN:
        raise AssistenteError("Escreva uma pergunta.")
    if len(pergunta) > PERGUNTA_MAX:
        raise AssistenteError(
            f"Pergunta muito longa (máximo {PERGUNTA_MAX} caracteres)."
        )
    return pergunta


async def preparar(
    db: AsyncSession,
    *,
    pergunta: str,
    tenant_id: int,
    usuario,
    cliente: LLMClient,
) -> tuple[str, ResultadoBusca]:
    """Valida a pergunta, extrai os filtros e busca. Tudo que pode falhar com
    status HTTP falha AQUI, antes de qualquer byte do stream sair."""
    pergunta = validar_pergunta(pergunta)
    parametros = await extrair_parametros(pergunta, cliente)
    resultado = await buscar(
        db, parametros=parametros, tenant_id=tenant_id, usuario=usuario
    )
    return pergunta, resultado


async def responder_sobre(
    resultado: ResultadoBusca, *, pergunta: str, cliente: LLMClient
) -> AsyncIterator[str]:
    """Resposta em pedaços sobre um resultado JÁ filtrado.

    Sem resultado, o modelo nem é chamado: não há o que resumir, e a resposta
    fixa não distingue "não existe" de "existe, mas você não vê" — distinção
    que o sigilo existe para esconder.
    """
    if not resultado.processos:
        yield RESPOSTA_SEM_RESULTADO
        return
    system = montar_system_prompt_busca(resultado)
    async for pedaco in cliente.stream(system=system, pergunta=pergunta):
        yield pedaco


async def responder_global(
    db: AsyncSession,
    *,
    pergunta: str,
    tenant_id: int,
    usuario,
    cliente: LLMClient,
) -> AsyncIterator[str]:
    """Conveniência para uso fora do HTTP: `preparar` + `responder_sobre`."""
    pergunta, resultado = await preparar(
        db, pergunta=pergunta, tenant_id=tenant_id, usuario=usuario, cliente=cliente
    )
    async for pedaco in responder_sobre(resultado, pergunta=pergunta, cliente=cliente):
        yield pedaco
