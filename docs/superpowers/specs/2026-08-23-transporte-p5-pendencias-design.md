# Transporte Regulado — Fase C: pendências do recadastramento (P5)

**Data:** 2026-08-23 · **Estado:** decisões aprovadas em chat, spec para revisão · **Antecede:** plano de implementação

## O que é

As duas pendências que a P5.3 deixou registradas no backlog: **o efeito da suspensão sobre o
alvará** e **a notificação automática por job** (o registro de envio existe desde a P5.3,
esperando o gatilho — o docstring de `RecadastramentoNotificacao` diz "a automação por job,
quando vier, escreve nesta mesma tabela").

Decisões do Jorge (2026-08-23):

- **Suspensão bloqueia SÓ a renovação de alvará.** Alvará vigente continua válido; emissão nova
  continua livre. É o **primeiro gate real do módulo** — estreito e reversível de propósito, e
  quebra deliberadamente o "nada gateia nada" que valeu até aqui: a partir desta fatia, a frase
  certa é "só a renovação gateia, e só pela suspensão".
- **O job cobre 4 gatilhos**: convocação gerada, lembrete de prazo próximo, aviso de atraso, e
  suspensão/reativação com parecer.

## Fora de escopo, explicitamente

- **Bloquear emissão de alvará novo, ou suspender o alvará em cascata.** Oferecido e descartado.
- **WhatsApp/in-app para o regulado.** Só e-mail (permissionário/empresa têm `email` no cadastro;
  quem não tem, não recebe — mesmo limite conhecido da P7).
- **Parametrização por tenant** dos dias de antecedência do lembrete. Constante no beat
  (`dias_antes=5`); virar configuração é fatia própria se algum município pedir.
- **Reprocessar/reenviar por interface.** O reenvio manual da P5.3 continua existindo e cobre isso.

## Fatia C1 — o gate de renovação

### Regra

`renovar_alvara` (`services/transporte_regulado.py`) passa a recusar com **409** quando o titular
do alvará (permissionário OU empresa) tem **convocação de recadastramento com
`situacao = 'suspenso'`** não excluída. A mensagem aponta o caminho de volta: *"Titular com
recadastramento suspenso — a renovação fica bloqueada até a reativação (Recadastramento →
atendimento da convocação)"*. Mensagem que manda para a porta errada custa um chamado por
ocorrência (lição da P5.3).

Contornos deliberados:

- **Qualquer convocação suspensa bloqueia**, de qualquer ciclo. Suspensão é ato com parecer e tem
  reativação como saída; ciclo antigo com suspensão pendurada é exatamente o caso que o município
  quer segurar. (Se isso apertar demais na prática, o ajuste é filtrar por ciclo ativo — uma
  cláusula.)
- **Emitir alvará novo NÃO passa pelo gate** — só `renovar_alvara`. Há teste afirmando as duas
  coisas, porque "melhorar" o gate para cobrir emissão é a deriva mais provável.
- **A checagem é no service**, não no banco: é política de negócio (o inverso das exclusividades
  P6/P6b — aqui não há corrida que interesse: renovar duas vezes em paralelo já é barrado pelas
  regras existentes de renovação).

### Testes (C1)

- Suspende → renovar → **409 com a mensagem apontando reativação** (asserção na substring).
- Reativa → renovar → passa.
- Suspenso → **emitir alvará novo → continua passando** (o anti-deriva).
- Empresa suspensa bloqueia renovação de alvará de empresa (o vocabulário feminino `suspensa` ×
  masculino `suspenso` da convocação — conferir o valor real gravado pela P5.3 e afirmar o exato;
  a armadilha nº 1 do módulo).
- HTTP com usuário comum no caminho do 409.

## Fatia C2 — notificação automática

### Migration 0094

Duas mudanças em `transporte_regulado.recadastramento_notificacao` + grants:

1. **`id_usuario` vira NULLABLE.** O NOT NULL dizia "envio é ato de operador"; agora envio também
   é ato do sistema, e `NULL` significa exatamente isso. O downgrade só volta o NOT NULL se não
   houver linha NULL (documentar no docstring).
2. **Coluna nova `gatilho` varchar(30) NULL** com CHECK
   `gatilho IN ('convocacao', 'lembrete', 'atraso', 'suspensao', 'reativacao')` (NULL = linhas
   manuais antigas da P5.3, que não sabiam seu gatilho). É a chave da **idempotência**: o job não
   repete `(id_convocacao, gatilho)` já registrado.
3. **Grants ao `aprimora_worker`** — primeira vez que o worker toca o módulo (enumerado, nunca
   cobertor): `SELECT` em `recadastramento_ciclo`, `recadastramento_convocacao`,
   `permissionario`, `empresa`; `SELECT, INSERT` em `recadastramento_notificacao` (+ sequence);
   e conferir/garantir `SELECT, INSERT, UPDATE` em `aprimora_py.notificacao` (+ sequence) — o
   motor `notificacoes.enviar` grava e atualiza `enviado_em`/`erro`.

### A task

`app/tasks/notificar_recadastramento.py`, registrada no `beat_schedule` de `celery_app.py`:

```python
"notificar-recadastramento-diario": {
    "task": "app.tasks.notificar_recadastramento.run",
    "schedule": crontab(hour=7, minute=0),  # começo do expediente
    "kwargs": {"dias_antes": 5},
},
```

Usa a sessão do worker (`app/tasks/_task_db.py`, papel `aprimora_worker`) e o motor
`services/notificacoes.enviar` (canal email, destinatário = e-mail do permissionário/empresa da
convocação). Varre **todos os tenants** (tarefa de plataforma, como as demais do beat), tenant a
tenant, e por convocação decide no máximo UM gatilho por rodada, nesta precedência:

1. **`atraso`** — prazo vencido, situação aberta, sem registro `(convocacao, 'atraso')`.
2. **`lembrete`** — prazo a ≤ `dias_antes` dias, situação aberta, sem `(convocacao, 'lembrete')`.
3. **`convocacao`** — convocação de ciclo gerado sem NENHUM registro de gatilho `'convocacao'`
   (cobre o backlog de convocações geradas antes desta fatia e as novas — geração continua
   rápida; o aviso sai na próxima rodada do job, eventualmente-consistente por decisão).

Cada envio: `enviar(...)` → gravar `RecadastramentoNotificacao(id_usuario=None, gatilho=...)`
apontando a `Notificacao` criada. Convocado **sem e-mail**: pula sem erro e sem registro (na
próxima rodada tenta de novo — se o cadastro ganhar e-mail, o aviso sai; registrar linha sem
notificação mataria essa recuperação).

Textos: neutros e com o dado que importa (janela/prazo da convocação), link
`/m/transporte/recadastramento`.

### Suspensão/reativação — no ato, não no job

O e-mail desses dois sai do **router** dos atos da P5.3, após o commit (mesmo desenho pós-commit
da P7: `try/except` + `db.rollback()` no except; falha de e-mail nunca desfaz o ato), com o
**parecer no corpo** — aqui o destinatário é o próprio suspenso e o parecer é dele. Registra
`RecadastramentoNotificacao(gatilho='suspensao'|'reativacao', id_usuario=<operador>)`.

### Testes (C2)

- Migration: upgrade/downgrade; a varredura RLS continua verde; **teste de grant**: sob o papel
  `aprimora_worker`, SELECT nas tabelas listadas funciona e INSERT em
  `recadastramento_notificacao` funciona (molde: `tests/test_rls_papeis_minimos.py`).
- Task (chamando a função da task diretamente com sessão de teste): convocação vencida ganha
  `atraso`; rodar DUAS vezes não duplica (idempotência pelo `(convocacao, gatilho)`); prazo
  próximo ganha `lembrete` e não `atraso`; recém-gerada ganha `convocacao`; sem e-mail → pula sem
  registro e sem erro; segunda rodada após cadastrar e-mail → envia.
- Precedência: convocação vencida E nunca avisada recebe SÓ `atraso` nesta rodada.
- Suspensão via HTTP → `Notificacao` criada com parecer no corpo + registro com
  `gatilho='suspensao'` e `id_usuario` do operador.
- **Isolamento**: a task de um banco com dois tenants notifica os dois, cada qual só com as suas
  convocações (a task roda com `aprimora_worker`, NOBYPASSRLS — o teste prova que o `SET LOCAL`
  por tenant dentro da task funciona).

## Assunções que valem conferir

- **Precedência atraso > lembrete > convocacao com no máximo um aviso por rodada** — evita
  metralhar o convocado no primeiro dia do job em cima de backlog antigo. Se o município quiser
  os três de uma vez, é inverter um `elif`.
- **`dias_antes=5`** fixo no beat. Mudar é editar o kwargs.
- **Convocação suspensa não recebe lembrete nem atraso** (situação não-aberta já sai do filtro —
  conferir `SITUACOES_ABERTAS` da P5.3 na implementação).
