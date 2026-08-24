# Pagamentos — Onda C2: integrações (contábil, bancária, API externa)

**Data:** 2026-08-24 · **Estado:** design aprovado em chat, spec para revisão · **Antecede:** plano de implementação

## O que é

A C2 destrava os três blocos que o backlog (§2.1) mantinha bloqueados em spec externa. As decisões
do Jorge (2026-08-24) removem o bloqueio trocando contrato externo por **formato próprio +
adaptador**:

- **Contábil**: sistema do outro lado **ainda não definido** → export em formato neutro versionado,
  com camada de adaptador para quando o piloto definir o sistema real.
- **Bancário**: o que existe é **arquivo de extrato** (OFX/CNAB240) baixado do internet banking →
  importador idempotente alimentando a conciliação existente (RF-EXT-01..10, RN-11/RN-14).
- **API externa nas duas direções**: escrita idempotente (sistemas municipais nos empurram débitos/
  liquidações) e leitura estável por cursor (contábil/ETL nos puxa). Autenticação por **API key por
  sistema/tenant** — um realm máquina-a-máquina novo.
- **Export contábil cobre o ciclo inteiro**: empenho, liquidação, pagamento/baixa e desfazimentos.

Vocabulário herdado (o "fóssil" da spec municipal, já no código): RN-01 (só autoriza com liquidação
e nº de empenho), RN-02/05 (fonte do empenho vinculante), RN-06 (conta pagadora pertence à fonte),
RN-11/RN-14 (conciliação na mesma conta, sem dupla conciliação), RN-15 (exceção de saldo com
justificativa — coluna estruturada desde a 0091), RF-EXT-01..10 (extrato), RF-VAL-02 (liquidação).

**Restrição de fidelidade ao domínio:** empenho NÃO é entidade — é `numero_empenho` + fonte no
débito. Os desfazimentos que existem são `estornar_parcela` e `cancelar` (débito). A spec exporta o
que o domínio registra; não inventa entidade contábil.

## Fora de escopo, explicitamente

- **API bancária, PIX, remessa/retorno CNAB** — a "3ª etapa" do spec municipal. O pagamento continua
  sendo executado fora (internet banking); nós conciliamos.
- **XLSX** — decisão da C1 mantida (CSV abre no Excel; PDF só onde há leitura de conferência).
- **Anulação de empenho como ato novo** — sem entidade empenho, não há o que anular além do
  cancelamento de débito que já existe.
- **Push para o sistema contábil** — enquanto não houver contrato real, quem integra puxa (leitura
  por cursor) ou consome o arquivo de lote.
- **Adaptador para sistema contábil específico** — nasce quando o piloto definir o sistema; a C2
  entrega o neutro e o ponto de plug.

## C2.1 — Export contábil neutro com lotes imutáveis

### Formato `aprimora-contabil v1`

CSV com dicionário de dados fixo (a versão do formato vai no nome do arquivo e no cabeçalho do
lote). Um registro por **evento**, cinco tipos:

| `tipo_evento` | Origem no domínio | Campos além dos comuns |
|---|---|---|
| `debito_empenhado` | débito com `numero_empenho` preenchido | nº empenho, fonte, credor (CNPJ/CPF+nome), valor, vencimento |
| `liquidacao` | confirmação de liquidação do débito (RF-VAL-02/RN-01) | data da liquidação, usuário |
| `pagamento` | ordem de pagamento executada + baixa | nº ordem, conta pagadora, data, valor pago, `excecao_saldo` (RN-15) + justificativa |
| `estorno_parcela` | `estornar_parcela` | parcela, valor estornado, motivo |
| `cancelamento_debito` | `cancelar` débito | motivo |

Campos comuns: `tenant`, `tipo_evento`, `id_evento` (estável e único por tenant — chave para o
contábil deduplicar), `id_debito`, `ocorrido_em`, `lote`.

### Lote numerado e imutável

Tabela nova `pagamentos.export_contabil_lote` (tenant_id, numero sequencial por tenant, período
solicitado, gerado_em, id_usuario, qtd_eventos, formato_versao, hash do conteúdo). Regras:

- **Evento pertence a exatamente um lote.** Marcação por tabela de junção
  `pagamentos.export_contabil_evento` (lote, tipo_evento, id_evento único por tenant) — é ela que
  garante o "nunca duplica" e permite o complemento.
- **Reemitir o mesmo período NÃO regera**: devolve o arquivo do lote existente (o conteúdo é
  reconstruível por consulta — armazenamos a marcação, não o CSV; o hash gravado prova que a
  reconstrução é fiel).
- **Evento retardatário** (registrado depois do lote do seu período) entra no PRÓXIMO lote como
  complemento — é assim que o contábil fecha sem furo nem duplicata.
- Geração pela tela de pagamentos (botão no padrão dos exports da C1.3) e pelo endpoint de leitura
  (C2.3), sempre sob `require_permission` de pagamentos.

### Camada de adaptador

`services/pagamentos_contabil.py`: `ContabilAdapter` (protocolo: recebe a lista de eventos do lote,
devolve bytes + content-type + extensão) com `AdapterNeutroCSV` como default e único da C2. Registro
por slug (`neutro-csv-v1`) em dict — adaptador futuro é uma classe nova + entrada no dict, zero
mudança no core. Mesmo espírito do adapter de DAM do plano do transporte.

## C2.2 — Importador de extrato OFX/CNAB240

Formaliza a porta de entrada da conciliação existente. Tela de extrato ganha upload de arquivo;
backend:

1. **Detecção de formato** (OFX primeiro; CNAB240 de extrato na sequência — dois parsers, um
   contrato interno: lista de lançamentos `(conta, data, valor, tipo, descricao, id_externo)`).
2. **Idempotência em duas camadas**:
   - arquivo: hash SHA-256 do conteúdo em `pagamentos.extrato_importacao` — mesmo arquivo de novo →
     resposta "já importado", zero efeito;
   - lançamento: chave natural `(conta, id_externo)` quando o formato dá id (FITID no OFX; nº do
     documento no CNAB) — arquivo que sobrepõe período importa só o que falta. **Sem `id_externo`
     não se pula linha**: pagamentos de mesmo valor no mesmo dia são legítimos, e pular por
     `(data, valor)` esconderia lançamento real; a coincidência vira AVISO de "possível duplicata"
     no relato do import, decisão do tesoureiro.
3. Lançamentos entram nas MESMAS tabelas que a conciliação RN-11/RN-14 já lê — a conciliação não
   muda uma linha.
4. Relato do import na resposta e na tela: total do arquivo, importados, ignorados por duplicata,
   rejeitados (com motivo linha a linha).

Erros de parse são 422 com a linha/campo; arquivo de banco/conta que não existe no tenant é 422
apontando o cadastro (nunca cria conta implícita).

## C2.3 — API externa: realm M2M, escrita idempotente, leitura por cursor

### Realm novo: sistema integrado

- Tabela `pagamentos.sistema_integrado` (tenant_id, nome, prefixo público da chave, hash da chave,
  escopos `leitura`/`escrita`, ativo, criado/revogado, id_usuario_criador). A chave completa aparece
  UMA vez, na criação (padrão de API key: prefixo identificável `apy_...` + segredo; hash com o
  mesmo custo do bcrypt de senha).
- Dependency própria `get_current_sistema_integrado` (header `X-Api-Key`): resolve tenant + sistema
  + escopos. **Nunca** passa por `require_permission` de usuário — é outro realm, como o cidadão. O
  gate de módulo (`pagamentos` contratado) SE aplica.
- Gestão (criar/listar/revogar) pelo admin do tenant, no realm admin normal, sob a permissão de
  gestão de pagamentos.
- Rate limit básico no nginx para o prefixo das rotas M2M.

### Escrita idempotente (escopo `escrita`)

- `POST /api/v2/integracao/pagamentos/debitos` (e liquidação do débito) com header
  **`Idempotency-Key` obrigatório** (UUID; 422 sem ele).
- Tabela `pagamentos.idempotencia` (tenant_id, id_sistema, chave, hash do payload, status_code e
  corpo da resposta gravados, criado_em): chave repetida → devolve a MESMA resposta gravada, sem
  reexecutar; chave igual com payload diferente → **409**; execução concorrente da mesma chave é
  serializada por unique (o segundo request espera/recebe a resposta gravada).
- O POST reusa os services existentes de débito (validações RN-01/02/06 intactas) — a API é uma
  porta nova para os mesmos atos, nunca um caminho paralelo de regra.

### Leitura estável (escopo `leitura`)

- `GET /api/v2/integracao/pagamentos/{debitos|ordens|baixas}` paginados por **cursor** (id
  ascendente; `?cursor=<ultimo_id>&limite=`), com `?alterado_desde=<timestamp>` para ETL
  incremental — offset não existe nessas rotas (cursor não perde nem repete linha quando a base
  cresce durante a varredura).
- Respostas com os mesmos campos dos `*Out` internos (subconjunto documentado) + `id_evento` do
  export contábil onde aplicável, para o ETL cruzar com os lotes.

## Multi-tenant, segurança, migrations

- Tabelas novas (`export_contabil_lote`, `export_contabil_evento`, `extrato_importacao`,
  `sistema_integrado`, `idempotencia`) com o boilerplate completo: `tenant_id` NOT NULL, RLS
  ENABLE+FORCE com as duas policies, grants enumerados a `aprimora_app` (tabela + sequence). Worker
  não toca nenhuma — sem grant de worker.
- `tenant_id` sempre do realm (API key resolve o tenant; nunca do payload). 404 cross-tenant.
- A chave de API nunca é logada; o `RequestLoggingMiddleware` já não loga headers de autorização —
  confirmar que `X-Api-Key` entra na lista de redação.
- Testes de realm: API key de um tenant não lê nem escreve em outro (par de tenants da fixture);
  escopo `leitura` não escreve (403); chave revogada → 401.

## Fatiamento (cada fatia entregável e testável sozinha)

- **C2.1** — export neutro + lotes imutáveis + botão na tela.
- **C2.2** — importador OFX/CNAB240 idempotente + upload na tela de extrato.
- **C2.3** — realm M2M + escrita idempotente + leitura por cursor + gestão de chaves na tela.

Ordem sugerida: C2.2 → C2.1 → C2.3 (o importador destrava valor imediato para o tesoureiro; o
export depende só do domínio; a API por último por ter a maior superfície de segurança).

## Assunções que valem conferir

- OFX na prática dos bancos brasileiros é OFX 1.x SGML (não XML estrito) — o parser precisa aceitar
  os dois; provar com arquivo real do banco do piloto antes de fechar a C2.2.
- CNAB240 de **extrato** (não de retorno de remessa) varia por banco no uso dos segmentos — começar
  pelo layout FEBRABAN genérico e registrar desvios por banco como adaptação pontual.
- A conciliação atual (RN-11/RN-14) consome lançamentos de uma tabela que o import manual já
  alimenta — o plano deve confirmar o nome/forma reais antes de desenhar o parser (o contrato
  interno do parser espelha essa tabela, não o contrário).
- `id_evento` estável por tenant precisa sobreviver a reprocessamento — derivar do par
  `(tipo_evento, id da linha de origem)`, nunca de sequência própria do export.
