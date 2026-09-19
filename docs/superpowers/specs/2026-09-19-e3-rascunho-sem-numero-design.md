# E3 — Rascunho = processo sem número (desenho)

**Status:** desenho concluído, aguardando aprovação para implementar.
**Autoridade:** este documento, sobre o *como* implementar E3. A decisão de
*o quê* implementar já está fechada — plano
[`docs/superpowers/plans/2026-09-16-aproveitamento-suite.md`](../plans/2026-09-16-aproveitamento-suite.md)
§5/E3 e a resposta de Jorge a Q3 (§6, 2026-09-17): **rascunho é processo sem
número**, contra a recomendação de adiar que o próprio plano registrava.

**Por que este documento existe.** O plano diz explicitamente: "Nenhum
desenho de migração foi feito ainda; escopar antes de implementar." Este é
esse escopo — produto de um levantamento file:line de tudo que assume
`numero_processo`/`nup` não-nulos (backend, frontend, PDFs, busca, guardas de
teste). Nenhuma linha de código de implementação foi escrita ainda.

---

## 1. O que muda no domínio

Hoje `Processo` nasce sempre numerado — `abrir_processo()` gera
`numero_processo` (sequência global `protocolos.numero_processo`, via
`gerar_numero_processo_string()`) na própria criação, dentro da mesma
transação. Não existe hoje nenhum estado "processo existe mas ainda não tem
número".

Depois de E3, `Processo` ganha uma coluna nova `situacao`:

| Valor | Significado | `numero_processo` | `nup` |
|---|---|---|---|
| `rascunho` | Criado, nunca tramitou | `NULL` | `NULL` |
| `protocolado` | Numerado — hoje é o único estado que existe | preenchido | preenchido se `usar_nup_federal` |

A emissão do número migra do ato de **abrir** para o ato de **encaminhar**
(primeira tramitação) — é o ponto que a captura 09 do SUiTE descreve ("NUP
será gerado após a tramitação") e o único lugar do código hoje que
representa "tramitar" no sentido dessa frase (`receber` é o destinatário
confirmando chegada, não o ato de sair da unidade de origem).

## 2. Escopo desta fatia — o que ENTRA e o que FICA FORA

**Entra:**
- `numero_processo` nullable; novo estado `situacao`.
- Emissão de número no primeiro `encaminhar()`, não mais em `abrir_processo()`.
- Opção de criar como rascunho nos dois pontos de entrada **internos**
  (form "Novo processo" e balcão — ambos já chamam `abrir_processo`).
- PDFs recusam gerar para rascunho (ver §6) em vez de aprender fallback para
  "sem número nenhum".
- Listagem/busca excluem rascunho por padrão (ver §7), com filtro explícito
  para vê-los.
- Guarda de teste nova para o invariante `situacao ⇔ numero_processo IS NULL`.

**Fica fora, deliberadamente — não construir para hipótese:**
- **Portal do cidadão não ganha rascunho.** `cidadao_processos.py` já é um
  caminho de criação **duplicado** de `abrir_processo` (achado pré-existente,
  não desta fatia) e continua numerando imediatamente, como hoje. Um
  protocolo aberto pelo cidadão é, por natureza, já uma submissão completa —
  não existe "rascunho de cidadão" na captura do SUiTE nem foi pedido.
- **Campos obrigatórios do processo não mudam.** Rascunho = falta só o
  número. `id_assunto`, `id_manifestante`, `id_unidade_proprietaria`
  continuam exigidos na criação, exatamente como hoje. Permitir salvar com
  esses campos incompletos é um problema diferente (formulário
  multi-etapa/autosave) que ninguém pediu — se isso for o que a ata do
  SUiTE realmente queria dizer com "edições em andamento" (a alternativa que
  a §5/E3 original cogitava e Q3 descartou), é uma fatia nova, não esta.
- **Sem workflow BPM para rascunho.** `auto_iniciar_workflow_se_aplicavel`
  não dispara na criação de um rascunho — dispara junto com a emissão do
  número, no primeiro `encaminhar()`. Workflow rastreia processo "de
  verdade"; instanciá-lo antes de existir número seria estado inconsistente
  sem necessidade comprovada.
- **Sem transação/permissão nova.** Rascunho é `Processo` com `situacao`
  diferente — `require_permission("processo.*")` e `assert_acesso_processo`
  (sigilo) continuam se aplicando sem alteração. Não introduzir código de
  transação novo só para isso.
- **Sequência de numeração continua global** (todos os tenants compartilham
  `protocolos.numero_processo` — pré-existente, E3 não mexe nisso).

## 3. Migration (nova, `0119_processo_rascunho.py` — depende de `0118`)

```
ALTER TABLE protocolos.processo ALTER COLUMN numero_processo DROP NOT NULL;
```

**Decisão deliberada: NÃO fazer `DROP DEFAULT`.** A coluna mantém
`DEFAULT protocolos.gerar_numero_processo_string()`. Motivo: o app Python
sempre passa `numero_processo` explicitamente (inclusive `None` para
rascunho) — um valor explícito, mesmo `NULL`, vai para o `INSERT` e o
`DEFAULT` do servidor nunca entra em jogo para esse caminho. Mas o schema é
**compartilhado** com o monólito PHP legado (`ci/legacy-schema.sql`), e não
temos garantia de que todo INSERT feito fora do ORM Python declare a coluna
— manter o `DEFAULT` é rede de segurança de graça, sem custo. Reverter isso
depois é fácil; assumir e estar errado não é.

```
ALTER TABLE protocolos.processo
    ADD COLUMN situacao character varying(20) NOT NULL DEFAULT 'protocolado';

ALTER TABLE protocolos.processo
    ADD CONSTRAINT ck_processo_situacao
    CHECK (situacao IN ('rascunho', 'protocolado'));

-- Invariante cruzado, opcional mas recomendado (nível de proteção que o
-- projeto já usa em outras colunas cross-checadas — ver nivel_sigilo):
ALTER TABLE protocolos.processo
    ADD CONSTRAINT ck_processo_situacao_numero
    CHECK ((situacao = 'rascunho') = (numero_processo IS NULL));

CREATE INDEX ix_processo_situacao
    ON protocolos.processo (tenant_id, situacao, id_usuario);
```

O `server_default='protocolado'` faz o backfill de toda linha existente
automaticamente (todo processo hoje já tem número, então já nasce
consistente com o `CHECK` cruzado acima).

**Não tocar a constraint `UNIQUE (numero_processo)` existente.** Já é
não-parcial, e Postgres trata cada `NULL` como distinto nela — múltiplos
rascunhos com `numero_processo IS NULL` não colidem. Convertê-la para índice
parcial (no padrão que `uq_processo_nup_global` usa para `nup`) resolveria
um problema que não existe aqui; deixar fora do escopo desta migration.

**Reversibilidade.** `downgrade()` é direto (`DROP COLUMN situacao`, `ADD
CONSTRAINT NOT NULL` de volta) **só se não houver rascunho vivo** — com
`situacao='rascunho'` gravado, `numero_processo` é `NULL` e o `ALTER COLUMN
... SET NOT NULL` falha (correto: falhar é melhor que inventar um número na
volta). Documentar isso no docstring da migration, no padrão de outras
migrations de alto risco do repo — não tentar "consertar" no downgrade.

## 4. Serviço — de onde a emissão do número se move

`abertura_processo.py:32-37` (gera `numero_processo`) e `:125-150` (gera
`nup` se `usar_nup_federal`) saem de `abrir_processo()` e viram uma função
nova e reutilizável:

```python
# services/numeracao_processo.py
async def emitir_numero(db, processo: Processo, *, tenant: Tenant, usuario_id: int, now: datetime) -> None:
    """Atribui numero_processo (+ nup se opt-in). Idempotente: não faz nada
    se o processo já tem número — chamador não precisa checar antes."""
```

Reaproveitada em três pontos (hoje a lógica já está **duplicada** entre
`abertura_processo.py` e `cidadao_processos.py:369-453` — achado
pré-existente; a extração resolve os dois primeiros, o terceiro fica igual
por estar fora do escopo do §2):

1. `abrir_processo()`, quando `payload.rascunho` é falso (comportamento
   de hoje, só que via função extraída) — chama e segue exatamente como
   agora.
2. `abrir_processo()`, quando `payload.rascunho` é verdadeiro — **não**
   chama; cria `Processo(numero_processo=None, situacao="rascunho", ...)`;
   **não** chama `auto_iniciar_workflow_se_aplicavel`.
3. `acoes_processo.py::encaminhar()`, logo após `_get_processo` (linha 91,
   antes da validação de workflow strict): se
   `processo.situacao == "rascunho"`, chama `emitir_numero(...)`, seta
   `processo.situacao = "protocolado"`, grava audit
   `processo.numerado_na_tramitacao` com o número emitido, e só então chama
   `auto_iniciar_workflow_se_aplicavel` (que hoje só roda na abertura) —
   tudo no mesmo commit do encaminhamento em si (linha 193), preservando o
   padrão de uma transação por ação que o arquivo já segue.

`cidadao_processos.py` fica de fora (ver §2) — continua numerando
imediatamente, sem chamar o parâmetro `rascunho`.

Concorrência: `gerar_numero_processo_string()` usa `nextval()` sobre uma
sequência real do Postgres — atômico por construção, sem lock de aplicação
necessário. Isso já vale hoje; E3 não muda a garantia.

## 5. Schemas

- `ProcessoCreate` ganha `rascunho: bool = False`. Continua exigindo
  `id_assunto`/`id_manifestante`/`id_unidade_proprietaria` — ver §2.
- `numero_processo: str` → `numero_processo: str | None` em:
  `ProcessoListItem`, `ProtocoloBalcaoResponse`, `cidadao.py` (mesmo sem
  suporte a rascunho, o campo precisa aceitar o tipo mais amplo do model),
  `apensamento.py`, `assinatura.py::PendenciaAssinatura`.
- `ProcessoListItem` ganha `situacao: str = "protocolado"` (default por
  compat com quem monta o schema à mão em teste/fixture, mesmo padrão já
  usado para `favorito`/`marcadores` nesse arquivo).

## 6. PDFs — recusar em vez de aprender fallback

Achado do levantamento: hoje já existem *dois* padrões de fallback
divergentes e nenhum cobre "os dois são `None`" (`pdf_folha_ocorrencias.py`,
`pdf_termos.py`, `pdf_protocolo.py` fazem `nup or numero_processo`, que
quebra se ambos forem `None`; a etiqueta usa `numero_processo` direto num
Code128 — string vazia quebra a geração do barcode).

**Decisão:** em vez de ensinar cada gerador de PDF a lidar com "sem
identificador nenhum", os endpoints de PDF em `routers/processos.py`
(capa, etiqueta, termos, folha de ocorrências, completo) recusam com `409`
quando `processo.situacao == "rascunho"` — mensagem tipo "Processo ainda é
rascunho — tramite para gerar o número antes de emitir {documento}". Um
rascunho não é um protocolo oficial; documento oficial numerado para algo
sem número não faz sentido, e a recusa explícita é mais clara que um PDF com
campo vazio ou "None" impresso.

`placeholders.py:127` (token `{{processo.numero}}` usado em minutas) já tem
fallback `or ""` — mantém como está; minuta em rascunho de processo em
rascunho é caso raro e não crítico o bastante para forçar decisão agora.

## 7. Busca e listagem — rascunho é só a aba dele

`routers/busca.py` (busca global) já não vai achar rascunho por número
(`ILIKE` contra `NULL` nunca casa) — nenhuma mudança necessária, e não vamos
fazer a busca global também indexar rascunho por assunto/manifestante: no
SUiTE, rascunho se acha pela aba dedicada, não pela busca geral.

`services/processos.py::list_processos` ganha filtro: por padrão, **exclui**
`situacao='rascunho'` da listagem (mesmo padrão de "oculto até pedir" que
`apenas_raiz`/`id_assunto_pai` usaram em E2) — novo parâmetro de query
`situacao: str | None = None` (`None` = comportamento atual, filtra
`protocolado`; `"rascunho"` = só rascunhos; `"todos"` = sem filtro). A tela
"Meus rascunhos" no frontend chama com `situacao=rascunho`.

`ProcessoApensados.tsx` (autocomplete de apensamento) exclui rascunho da
lista de candidatos — apensar a um processo sem número não faz sentido
(rascunho ainda não é uma "peça" protocolada).

## 8. `link_url` / notificações — não é risco

Achado do levantamento: **nenhum** `link_url` no sistema é derivado de
`numero_processo`/`nup` — todos usam `processo.id`
(`tasks/verificar_sla_workflows.py:209` e o resto do motor de notificações
tratam `link_url` como string opaca). O item (d) do plano original listava
notificações como superfície de risco; na prática não é — registrado aqui
para não redescobrir isso na hora de implementar.

## 9. Guarda de teste nova

Não existe hoje nenhum `test_guarda_nup*.py` — a garantia de "número sempre
presente" era 100% estrutural (`NOT NULL` + `str` não-Optional), nunca
reforçada por teste dedicado. E3 introduz o primeiro:
`tests/test_guarda_processo_rascunho.py`, cobrindo:

- `CHECK ck_processo_situacao_numero` barra `situacao='rascunho'` com
  `numero_processo` preenchido e vice-versa (teste de banco, via SQL bruto
  — não passa pela camada de service).
- HTTP: criar rascunho → `numero_processo`/`nup` nulos,
  `situacao='rascunho'`; `encaminhar()` sobre rascunho → emite número, muda
  `situacao`, e o `encaminhar()` sobre processo já protocolado continua
  idêntico a hoje (não re-emite).
- PDFs recusam com 409 para rascunho (pelo menos um endpoint representativo).
- Listagem/busca excluem rascunho por padrão; filtro explícito devolve.
- Teste HTTP com usuário comum (não só SU) — lição já registrada no
  `CLAUDE.md` sobre bypass de SU esconder `AttributeError`/500.

## 10. Frontend — inventário do que precisa do fallback `"(rascunho)"`

Lista já levantada, vira checklist do PR de frontend (arquivo:linha do
levantamento original, não repetido aqui por brevidade — ver histórico desta
sessão/PR):

- Tela de detalhe do processo: breadcrumb, título/subtítulo, títulos dos
  modais de PDF (que passam a vir desabilitados/ocultos para rascunho, não
  só com texto de fallback — ver §6).
- Listagem de processos: nova aba/filtro "Rascunhos"; badge visual
  "RASCUNHO" quando `situacao !== "protocolado"`.
- Form "Novo processo": segundo botão de submit, "Salvar rascunho" (chama
  com `rascunho: true`) ao lado do "Protocolar" existente.
- **Balcão não ganhou a opção, na implementação** (ajuste sobre o que esta
  seção previa). `ProtocoloBalcaoResponse` já se documenta como "retorno
  enxuto pra UI focar em número + ID pra etiqueta" — o próprio contrato
  assume número na hora. Balcão é atendimento presencial síncrono: o cidadão
  sai com o recibo numerado. `services/protocolo.py` monta o
  `ProcessoCreate` sem o campo `rascunho`, então usa o default `False`
  automaticamente — nenhuma mudança de código foi necessária ali.
- `ProcessoApensados.tsx`: autocomplete exclui rascunho (ver §7).
- Portal do cidadão: **nenhuma mudança** — nunca recebe rascunho (ver §2),
  mas os dois lugares que hoje fazem `nup ?? numero_processo` sem
  considerar `null` final continuam seguros porque o backend nunca devolve
  um rascunho para esse portal.
- Fila "para assinar" e dashboard: qualquer processo ali já tramitou (tem
  fluxo de assinatura), então na prática nunca é rascunho — sem mudança
  funcional, só o tipo TypeScript (`numero_processo: string | null` em
  `api.ts`) precisa acompanhar o schema do backend para o `tsc` continuar
  honesto (mesma lição do §"Adicionando um módulo" item 7 do CLAUDE.md).

## 11. Ordem de implementação sugerida

1. Migration `0119` + model (`situacao`, `numero_processo` nullable).
2. `services/numeracao_processo.py` (extrai emissão) + `abertura_processo.py`
   (parâmetro `rascunho`) + `acoes_processo.py::encaminhar` (emite na
   tramitação) + schemas.
3. Guarda de teste `test_guarda_processo_rascunho.py` (backend fecha aqui,
   testável e mergeável sozinho — frontend pode vir em PR separado como E1
   fez com o context-switcher, se o volume justificar).
4. PDFs: 409 para rascunho.
5. Listagem/busca: filtro de `situacao`.
6. Frontend: aba de rascunhos, form, badges, autocomplete.

## 12. Perguntas que ficaram documentadas mas não bloqueiam início

- Nome dos dois valores de `situacao` (`rascunho`/`protocolado`) — escolha
  meu, alinhada ao vocabulário do produto ("protocolo"). Trocável sem custo
  antes do merge se Jorge preferir outro par de termos.
- Se "edições em andamento" da ata (§32) for sobre outra coisa (documento em
  edição, que `models/minuta.py` já cobre) e não sobre isto — já descartado
  por Q3, registrado aqui só para não reabrir a dúvida por engano.
