# PR 4d - Escopo implementavel: complementacao documental formal

Status: escopo consolidado, aguardando autorizacao para implementar.

Base: `docs/codex-avaliacao-geral-roadmap-pr4d.md`.

Observacao de estado real: o worktree ja contem uma implementacao backend parcial de PR 4d (migration `0027`, modelo, schema, service, endpoints servidor e integracao parcial com checklist). Este escopo assume que essas alteracoes serao revisadas, completadas e validadas como parte do PR 4d. O PR nao deve recomecar do zero.

## 1. Objetivo do PR

Permitir que o servidor solicite complementacao documental formal em um processo aberto por servico, com mensagem e lista de documentos solicitados, e que o cidadao responda explicitamente pelo portal.

O PR fecha o ciclo:

1. Carta de Servicos define documentos exigidos.
2. Cidadao abre protocolo por servico.
3. Checklist documental mostra enviados e pendentes.
4. Servidor solicita complementacao formal quando necessario.
5. Cidadao anexa documentos pelo fluxo existente e clica em "Responder complementacao".
6. Servidor visualiza historico e status da complementacao.

O PR deve reusar o que ja existe: `Servico.documentos_exigidos`, `Anexo.documento_exigido_key`, checklist documental, `_verificar_dono`, `require_acesso_processo`, RLS e `audit_log`.

Nao evoluir assinatura, admin SaaS, billing, dominios customizados, notificacoes externas, OCR, IA, GED completo, SLA ou dashboard neste PR.

## 2. Decisoes tecnicas travadas

| Decisao | Veredito |
|---|---|
| Modelo de dados | Usar tabela propria `protocolos.complementacao_documental`, nao campos soltos em `processo`. |
| Status | Usar status proprio `aberta`, `respondida`, `cancelada`; nao alterar `StatusDocumental`. |
| Relacao com checklist | Checklist continua calculado; `complementacao_aberta` e campo informativo. |
| Resposta do cidadao | Resposta explicita por botao "Responder complementacao". |
| Resposta parcial | Permitida. Nao exigir que todos os documentos estejam anexados. |
| Concorrencia | Permitir apenas uma complementacao aberta por processo. Historico pode ter varias finalizadas. |
| Mensagem/motivo | Persistir na tabela, sob RLS; nunca registrar texto no `audit_log`. |
| Permissao servidor | Reusar `processo:atualizar`; nao criar permissao nova neste PR. |
| Acesso servidor | Sempre usar `require_acesso_processo` para respeitar tenant e sigilo. |
| Acesso cidadao | Sempre usar `_verificar_dono`. |
| Cross-tenant/nao dono | Retornar 404 neutro, nao 403. |
| Notificacao externa | Fora de escopo. Cidadao ve a pendencia no portal. |
| Upload | Nao criar novo upload; reusar upload PR 4c com `documento_exigido_key`. |

## 3. Migration proposta

Migration: `backend/alembic/versions/0027_complementacao_documental.py`.

Tabela: `protocolos.complementacao_documental`.

DDL conceitual:

```sql
CREATE TABLE protocolos.complementacao_documental (
    id                     SERIAL PRIMARY KEY,
    tenant_id              INTEGER NOT NULL REFERENCES aprimora_py.tenant(id),
    id_processo            INTEGER NOT NULL REFERENCES protocolos.processo(id),
    id_usuario_solicitante INTEGER NOT NULL REFERENCES utils.usuario(id),
    status                 VARCHAR(20) NOT NULL DEFAULT 'aberta',
    mensagem               TEXT NOT NULL,
    documentos_solicitados JSONB NOT NULL,
    motivo_cancelamento    TEXT NULL,
    criado_em              TIMESTAMP NOT NULL DEFAULT NOW(),
    atualizado_em          TIMESTAMP NULL,
    respondido_em          TIMESTAMP NULL,
    cancelado_em           TIMESTAMP NULL,
    excluido               BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT ck_complementacao_status
      CHECK (status IN ('aberta', 'respondida', 'cancelada'))
);

CREATE INDEX ix_complementacao_processo
    ON protocolos.complementacao_documental(id_processo, criado_em DESC);

CREATE UNIQUE INDEX uq_complementacao_aberta_por_processo
    ON protocolos.complementacao_documental(id_processo)
    WHERE status = 'aberta' AND excluido = FALSE;
```

RLS e GRANTs:

```sql
GRANT SELECT, INSERT, UPDATE, DELETE
  ON protocolos.complementacao_documental TO aprimora_app;

GRANT USAGE, SELECT
  ON protocolos.complementacao_documental_id_seq TO aprimora_app;

ALTER TABLE protocolos.complementacao_documental ENABLE ROW LEVEL SECURITY;
ALTER TABLE protocolos.complementacao_documental FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_select
  ON protocolos.complementacao_documental
  FOR SELECT
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int);

CREATE POLICY tenant_isolation_modify
  ON protocolos.complementacao_documental
  FOR ALL
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int);
```

Revisoes antes de fechar:

- Confirmar se a migration atual ja inclui `CHECK status IN (...)`; se nao, adicionar.
- Confirmar downgrade limpo com `drop_table`.
- Confirmar que o CI aplica `0027` a partir do baseline atual.
- Confirmar que o indice unico parcial mapeia corrida para erro amigavel 409 no service/router.

## 4. Modelo SQLAlchemy

Arquivo: `backend/app/models/complementacao_documental.py`.

Modelo:

```py
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ComplementacaoDocumental(Base):
    __tablename__ = "complementacao_documental"
    __table_args__ = {"schema": "protocolos"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_processo: Mapped[int] = mapped_column(
        ForeignKey("protocolos.processo.id"), nullable=False
    )
    id_usuario_solicitante: Mapped[int] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="aberta")
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    documentos_solicitados: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False
    )
    motivo_cancelamento: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    respondido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

Tambem:

- registrar em `backend/app/models/__init__.py`;
- manter sem relacionamentos ORM complexos neste PR;
- manter `criado_em` como data da solicitacao por convencao.

## 5. Schemas Pydantic

Arquivo: `backend/app/schemas/complementacao_documental.py`.

Schemas:

```py
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


StatusComplementacao = Literal["aberta", "respondida", "cancelada"]


class SolicitarComplementacaoRequest(BaseModel):
    mensagem: str = Field(min_length=1, max_length=2000)
    documentos_solicitados: list[str] = Field(min_length=1)


class CancelarComplementacaoRequest(BaseModel):
    motivo: str | None = Field(default=None, max_length=500)


class ComplementacaoDocSolicitadoOut(BaseModel):
    key: str
    nome: str
    descricao: str | None = None
    enviado: bool


class ComplementacaoOut(BaseModel):
    id: int
    status: StatusComplementacao
    mensagem: str
    documentos_solicitados: list[ComplementacaoDocSolicitadoOut]
    id_usuario_solicitante: int
    nome_solicitante: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None
    respondido_em: datetime | None = None
    cancelado_em: datetime | None = None
    motivo_cancelamento: str | None = None
```

Estender `backend/app/schemas/checklist_documentos.py`:

```py
class ChecklistDocumentosResponse(BaseModel):
    id_processo: int
    id_servico: int | None = None
    status_documental: StatusDocumental
    obrigatorios_total: int
    obrigatorios_enviados: int
    itens: list[ChecklistItem]
    complementacao_aberta: ComplementacaoOut | None = None
```

No frontend, espelhar os mesmos tipos em `frontend/lib/api.ts`.

## 6. Service layer

Arquivo: `backend/app/services/complementacao_documental.py`.

Excecao:

```py
class ComplementacaoError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
```

Funcoes obrigatorias:

### `solicitar`

Assinatura:

```py
async def solicitar(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
    id_usuario_solicitante: int,
    mensagem: str,
    documentos_solicitados_keys: list[str],
) -> ComplementacaoDocumental:
```

Regras:

1. Carregar processo por `id`, `tenant_id`, `excluido=False`; se nao achar, 404.
2. Exigir `processo.id_servico`; se ausente, 400.
3. Carregar servico do mesmo tenant; se nao houver documentos exigidos, 400.
4. Deduplicar keys preservando ordem.
5. Rejeitar key fora de `servico.documentos_exigidos[*].key`, 400.
6. Rejeitar se ja existir `status='aberta'` para o processo, 409.
7. Criar linha `aberta`.
8. Auditar `complementacao.solicitada` com payload minimizado.
9. Nao fazer commit dentro do service; router controla transacao.

### `responder`

Assinatura:

```py
async def responder(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
    complementacao_id: int,
) -> ComplementacaoDocumental:
```

Regras:

1. Carregar complementacao por `id`, `id_processo`, `tenant_id`, `excluido=False`; se nao achar, 404.
2. Se status nao for `aberta`, retornar 409.
3. Setar `status='respondida'`, `respondido_em`, `atualizado_em`.
4. Nao validar quantidade de anexos.
5. Auditar `complementacao.respondida` com payload minimizado.

### `cancelar`

Assinatura:

```py
async def cancelar(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
    complementacao_id: int,
    id_usuario_responsavel: int,
    motivo: str | None,
) -> ComplementacaoDocumental:
```

Regras:

1. Carregar complementacao por `id`, `id_processo`, `tenant_id`, `excluido=False`; se nao achar, 404.
2. Se status nao for `aberta`, retornar 409.
3. Setar `status='cancelada'`, `cancelado_em`, `atualizado_em`, `motivo_cancelamento`.
4. Auditar `complementacao.cancelada` sem texto do motivo.

### `listar`

Assinatura:

```py
async def listar(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
) -> list[ComplementacaoDocumental]:
```

Ordenar por `criado_em DESC`, sem paginacao neste PR.

### `obter_aberta`

Assinatura:

```py
async def obter_aberta(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
) -> ComplementacaoDocumental | None:
```

Usado pelo checklist.

### Serializacao

Expor helper publico para montar outputs, evitando que routers usem helpers privados:

```py
async def montar_out(...) -> ComplementacaoOut

async def listar_out(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
) -> list[ComplementacaoOut]
```

O output deve cruzar:

- keys solicitadas em `documentos_solicitados`;
- metadata de `servico.documentos_exigidos` para `nome` e `descricao`;
- anexos vivos do processo por `documento_exigido_key` para `enviado`;
- `utils.usuario.nome` do solicitante.

## 7. Endpoints servidor

Arquivo: `backend/app/routers/processos.py`.

### Solicitar complementacao

```http
POST /api/v2/processos/{processo_id}/complementacoes
```

Auth:

- `require_acesso_processo`;
- `require_permission("processo", "atualizar")`.

Body:

```json
{
  "mensagem": "Envie comprovante atualizado.",
  "documentos_solicitados": ["comprovante_residencia"]
}
```

Respostas:

- 201 com `ComplementacaoOut`;
- 400 para processo sem servico, servico sem docs ou key invalida;
- 403 para servidor sem `processo:atualizar`;
- 404 para processo inexistente, outro tenant ou sem acesso por sigilo;
- 409 para ja existir aberta.

### Listar complementacoes

```http
GET /api/v2/processos/{processo_id}/complementacoes
```

Auth:

- `require_acesso_processo`.

Resposta:

- 200 com `list[ComplementacaoOut]`, ordenado por `criado_em DESC`;
- 404 para processo inexistente, outro tenant ou sem acesso por sigilo.

### Cancelar complementacao

```http
POST /api/v2/processos/{processo_id}/complementacoes/{complementacao_id}/cancelar
```

Auth:

- `require_acesso_processo`;
- `require_permission("processo", "atualizar")`.

Body:

```json
{
  "motivo": "Solicitacao aberta por engano."
}
```

Respostas:

- 200 com `ComplementacaoOut`;
- 404 para processo/complementacao inexistente ou fora do tenant;
- 409 se complementacao nao estiver aberta.

## 8. Endpoints cidadao

Arquivo: `backend/app/routers/cidadao.py`.

Todos os endpoints devem chamar `_verificar_dono(db, cidadao, processo_id, tenant_id)` antes de listar ou responder.

### Listar complementacoes do proprio processo

```http
GET /api/v2/cidadao/processos/{processo_id}/complementacoes
```

Auth:

- `get_current_cidadao`;
- `require_tenant_id`;
- `_verificar_dono`.

Resposta:

- 200 com `list[ComplementacaoOut]`;
- 404 se processo nao existir, nao pertencer ao cidadao ou for de outro tenant.

### Responder complementacao

```http
POST /api/v2/cidadao/processos/{processo_id}/complementacoes/{complementacao_id}/responder
```

Auth:

- `get_current_cidadao`;
- `require_tenant_id`;
- `_verificar_dono`.

Body:

- Sem body neste PR.

Respostas:

- 200 com `ComplementacaoOut` respondida;
- 404 se processo/complementacao nao existir ou nao pertencer ao cidadao;
- 409 se complementacao ja estiver respondida/cancelada.

## 9. Integracao com checklist documental

Arquivo: `backend/app/services/checklist_documentos.py`.

Regras:

- `status_documental` continua sendo apenas:
  - `sem_documentos_exigidos`;
  - `pendente`;
  - `parcial`;
  - `completo`.
- `complementacao_aberta` e informativo e nao altera o status documental.
- Quando existir complementacao aberta, o checklist deve retornar `ComplementacaoOut` em `complementacao_aberta`.
- `ComplementacaoOut.documentos_solicitados[*].enviado` deve refletir anexos vivos com `Anexo.documento_exigido_key` correspondente.
- Apos resposta ou cancelamento, `complementacao_aberta` deve voltar a `null`.

Nao alterar `upload_anexo`. O upload PR 4c continua sendo o unico caminho para anexar documento exigido.

## 10. Frontend servidor

Arquivos esperados:

- `frontend/lib/api.ts`;
- `frontend/app/(app)/processos/[id]/page.tsx`;
- novos componentes compartilhados em `frontend/components/`.

Tipos e API em `frontend/lib/api.ts`:

- `StatusComplementacao`;
- `ComplementacaoDocSolicitado`;
- `ComplementacaoOut`;
- `ChecklistDocumentosResponse.complementacao_aberta`;
- `api.processos.solicitarComplementacao`;
- `api.processos.listarComplementacoes`;
- `api.processos.cancelarComplementacao`.

UI na aba Documentos do detalhe do processo:

- Buscar checklist e complementacoes.
- Mostrar bloco "Complementacao documental" acima do checklist.
- Se nao houver aberta:
  - mostrar botao "Solicitar complementacao";
  - abrir dialog com textarea `mensagem` obrigatoria;
  - listar checkboxes de documentos do checklist;
  - pre-marcar documentos nao enviados;
  - exigir ao menos um documento selecionado.
- Se houver aberta:
  - mostrar card com mensagem, data, solicitante, status e documentos solicitados;
  - mostrar badge `Enviado`/`Pendente` por item;
  - mostrar botao "Cancelar complementacao";
  - dialog de cancelamento com motivo opcional.
- Mostrar historico de respondidas/canceladas.
- Invalidar queries de checklist e complementacoes apos solicitar/cancelar.

Componentes sugeridos:

- `ComplementacaoAbertaCard.tsx`;
- `ComplementacoesHistoricoLista.tsx`;
- `SolicitarComplementacaoDialog.tsx`;
- `CancelarComplementacaoDialog.tsx`.

## 11. Frontend cidadao

Arquivos esperados:

- `frontend/lib/api.ts`;
- `frontend/app/cidadao/processos/[id]/page.tsx`;
- componentes compartilhados criados para o servidor, em modo cidadao.

Tipos e API em `frontend/lib/api.ts`:

- `api.cidadao.listarComplementacoes`;
- `api.cidadao.responderComplementacao`;
- `ChecklistDocumentosResponse.complementacao_aberta`.

UI no detalhe do processo do cidadao:

- Ler `checklistQ.data?.complementacao_aberta`.
- Quando houver aberta, renderizar card destacado acima do checklist.
- Card mostra:
  - titulo "Complementacao solicitada";
  - mensagem do servidor;
  - data e solicitante;
  - documentos solicitados com badge `Enviado`/`Pendente`;
  - botao "Anexar" por item pendente, reusando o dialog de upload PR 4c;
  - botao "Responder complementacao".
- Responder nao exige todos os documentos anexados.
- Ao responder:
  - chamar endpoint cidadao;
  - mostrar toast;
  - invalidar processo, checklist e complementacoes;
  - remover destaque quando `complementacao_aberta` virar `null`.
- Mostrar historico de complementacoes anteriores abaixo do checklist.

## 12. Auditoria

Usar `backend/app/services/audit.py`.

Eventos:

### `complementacao.solicitada`

Quando: servidor cria complementacao.

Payload permitido:

```json
{
  "id_processo": 123,
  "id_complementacao": 456,
  "documentos_solicitados_keys": ["rg", "cpf"],
  "canal": "interno",
  "id_usuario_responsavel": 10
}
```

### `complementacao.respondida`

Quando: cidadao clica em "Responder complementacao".

Payload permitido:

```json
{
  "id_processo": 123,
  "id_complementacao": 456,
  "canal": "portal"
}
```

### `complementacao.cancelada`

Quando: servidor cancela complementacao aberta.

Payload permitido:

```json
{
  "id_processo": 123,
  "id_complementacao": 456,
  "canal": "interno",
  "id_usuario_responsavel": 10
}
```

Nunca registrar no audit:

- CPF/CNPJ;
- nome do cidadao;
- mensagem da complementacao;
- motivo de cancelamento;
- nome original de arquivo;
- conteudo de documento;
- dados pessoais sensiveis.

## 13. Seguranca/LGPD

Regras obrigatorias:

- Toda query filtra `tenant_id`.
- Tabela nova tem RLS `ENABLE` e `FORCE`.
- Servidor so acessa via `require_acesso_processo`.
- Mutacoes do servidor exigem `processo:atualizar`.
- Cidadao so acessa via `_verificar_dono`.
- Cross-tenant e nao dono retornam 404.
- Mensagem e motivo ficam na tabela, protegidos por RLS, nao em logs.
- Validacao de keys impede anexar/solicitar documento fora do servico.
- Upload permanece com limite de tamanho/extensao existente.
- Nao incluir notificacao externa neste PR para evitar nova superficie LGPD.

Riscos tratados:

- Vazamento por audit minimizado.
- Vazamento cross-tenant por RLS e 404 neutro.
- Vazamento entre cidadaos por `_verificar_dono`.
- Confusao de status por separacao entre status documental e status da complementacao.

## 14. Testes obrigatorios

### Backend

Criar `backend/tests/test_pr4d_complementacao.py`.

Cobrir:

1. Servidor solicita complementacao valida: 201, linha aberta, audit minimizado.
2. Key invalida retorna 400.
3. Processo sem `id_servico` retorna 400.
4. Servico sem `documentos_exigidos` retorna 400.
5. Lista vazia retorna 422 ou 400, conforme camada acionada.
6. Ja existe aberta retorna 409.
7. Indice unico parcial impede segunda aberta em corrida ou SQL direto.
8. Servidor sem `processo:atualizar` retorna 403.
9. Servidor sem acesso por sigilo retorna 404.
10. Cross-tenant retorna 404 em solicitar/listar/cancelar/responder.
11. Servidor lista historico ordenado por `criado_em DESC`.
12. Servidor cancela aberta com motivo.
13. Servidor cancela aberta sem motivo.
14. Cancelar respondida/cancelada retorna 409.
15. Cidadao lista complementacoes do proprio processo.
16. Cidadao de outro processo recebe 404.
17. Cidadao responde aberta.
18. Cidadao responde sem anexar todos os docs.
19. Cidadao responde respondida/cancelada e recebe 409.
20. Apos respondida/cancelada, nova solicitacao pode ser aberta.
21. Checklist traz `complementacao_aberta` quando existe aberta.
22. Checklist retorna `complementacao_aberta = None` apos resposta/cancelamento.
23. `StatusDocumental` nao muda por causa da complementacao aberta.
24. `documentos_solicitados[*].enviado` reflete upload PR 4c.
25. Audit dos tres eventos nao contem CPF, nome, mensagem, motivo, arquivo ou conteudo.
26. RLS: sessao com `app.tenant_id` errado nao le linhas de outro tenant.
27. Migration 0027 aplica em banco limpo a partir do baseline CI.

### Frontend

Vitest:

1. `ComplementacaoAbertaCard` modo servidor renderiza docs e cancelar.
2. `ComplementacaoAbertaCard` modo cidadao renderiza docs, anexar e responder.
3. `SolicitarComplementacaoDialog` valida mensagem obrigatoria.
4. `SolicitarComplementacaoDialog` valida ao menos um documento.
5. Dialog pre-marca documentos nao enviados.
6. `CancelarComplementacaoDialog` aceita motivo vazio.
7. Historico renderiza status e datas.
8. Pagina servidor chama APIs e invalida checklist/complementacoes.
9. Pagina cidadao mostra card quando `complementacao_aberta` existe.
10. Pagina cidadao responde complementacao e remove destaque apos refetch.

### E2E

Adicionar fluxo Playwright preferencial:

1. Servidor solicita complementacao.
2. Cidadao abre processo no portal.
3. Cidadao anexa parte dos documentos solicitados.
4. Cidadao responde complementacao.
5. Servidor ve historico com status `respondida`.

## 15. Criterios de aceite

- Migration 0027 revisada com RLS, GRANTs, indice unico parcial e check de status.
- Backend expõe endpoints servidor e cidadao.
- Frontend tipa `complementacao_aberta` e expõe APIs PR4d.
- Tela servidor permite solicitar, ver aberta, cancelar e ver historico.
- Tela cidadao permite ver aberta, anexar documentos pelo fluxo PR4c, responder e ver historico.
- Apenas uma complementacao aberta por processo.
- Resposta parcial permitida.
- `StatusDocumental` permanece inalterado.
- Cross-tenant, nao dono e sem acesso por sigilo retornam 404.
- Servidor sem permissao retorna 403.
- Audit minimizado validado por teste.
- Mensagem e motivo nao aparecem no audit.
- Testes backend PR4d passam.
- Testes frontend PR4d passam.
- E2E essencial passa ou fica explicitamente justificado se adiado.
- Nenhum item fora de escopo implementado.
- Assinatura v2 nao alterada.
- Documentacao deixa de contradizer o estado real do codigo.

## 16. Fora de escopo

- E-mail.
- SMS.
- WhatsApp.
- Push.
- Novo `in_app`.
- Prazo formal de complementacao.
- SLA.
- Dashboard.
- Indeferimento automatico.
- OCR.
- IA.
- Validacao automatica de documentos.
- GED completo.
- Versionamento documental.
- Assinatura de anexos do cidadao.
- Gov.br.
- ICP-Brasil.
- Pagamento/taxa.
- Mensagem textual do cidadao na resposta.
- Reabertura de complementacao `respondida` ou `cancelada`.
- Paginacao/filtros avancados no historico.
- Refactor amplo de `frontend/lib/api.ts`.
- Mudancas em assinatura v2, admin SaaS, billing ou dominio customizado.

## 17. Riscos remanescentes

- PR4d ja esta parcialmente no backend; se o time nao assumir essas alteracoes como base, sera preciso reverter ou separar antes de implementar.
- O frontend ainda nao conhece `complementacao_aberta`; enquanto isso, a feature fica invisivel ou subtipada.
- Sem notificacao externa, o cidadao precisa acessar o portal para ver a pendencia.
- Mensagem livre do servidor pode conter dados pessoais; mitigacao e RLS + nao auditar texto + limite de tamanho.
- Corrida de duas solicitacoes simultaneas pode gerar erro de constraint; precisa mapeamento amigavel para 409.
- Router usando helper privado de service pode virar divida. Preferir helper publico `listar_out`.
- CI principal ainda e mais forte no backend do que no frontend/e2e.
- Sem dashboard, complementacoes abertas podem ficar operacionalmente esquecidas em piloto.

## 18. Gancho para o proximo PR

Depois de fechar PR4d, o proximo PR recomendado e um PR de observabilidade e operacao da complementacao documental:

- indicadores de complementacoes abertas/respondidas/canceladas;
- pendencias por servico;
- pendencias por unidade;
- tempo medio ate resposta;
- alertas internos simples para servidor;
- eventual notificacao ao cidadao, somente depois de discutir opt-in, templates, LGPD, entregabilidade e canal.

Alternativa, se o piloto exigir primeiro: PR de hardening operacional com CI frontend/e2e basico, audit fail-closed para atos criticos e revisao de endpoints sensiveis.

Parar aqui. Este documento define o escopo; nenhuma implementacao deve ser feita sem autorizacao explicita.
