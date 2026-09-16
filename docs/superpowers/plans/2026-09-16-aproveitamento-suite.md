# Plano de trabalho — o que aplicar do SUiTE no Aprimora

> **Status:** plano de diagnóstico · **Autoridade sobre:** nada executável ainda.
> **Última verificação:** 2026-09-16, contra `main` em `e4a41ee`.
> Complementa [a spec de 2026-08-28](../specs/2026-08-28-reuniao-as-is-to-be-design.md).

---

## 1. Método e cobertura

**44 de 44 capturas vistas.** `Suite-20260916T213422Z-1-001.zip`, SUiTE v1.40.0
(Governo do Ceará), feitas em 2026-08-27 entre 14:15 e 15:20 — a tarde da
reunião. Usuário: Luiz Ramom Teixeira Carvalho, SEAS/ASCOI, Coordenador.

Telas cobertas: painel (2 escopos), painel de processos (6 abas), abertura,
editor de documento, modelos, detalhe (6 abas), visualizador em árvore, capa,
folha de ocorrências, arquivar, atribuir, encaminhar, despacho, juntadas, área
do usuário, preferências de notificação, administração (4 seções).

**Nenhuma captura tem marcação ou comentário.** É a demonstração do sistema,
não o feedback anotado que a ata de 27/08 prometia ("prints das telas com
marcações e observações"). Aquele material continua não tendo chegado.

### 1.1 Correção de uma premissa do prompt

O prompt listava, entre as "perguntas já respondidas — não reabrir":

> Troca de lotação: seletor de contexto ("alterar setor" no menu do usuário),
> **não segunda lotação**.

**Está errado, e a prova está na captura 38**, que é uma das 27 que ninguém
tinha visto. "Configurações de usuário → Meu perfil" mostra:

- **Lotação Principal** — SEAS/ASCOI, Cargo Coordenador, Vínculo SERVIDOR
- **cinco Lotações Secundárias** — SEAS/CSIN, SEAS/CAGGP, SEAS/CSPAM,
  SEAS/CSPD e outra, cada uma com toggle *Habilitada* e botão *Remover lotação*

É multi-lotação de verdade. O "alterar setor" da captura 37 é o seletor da
lotação **ativa** entre as que o usuário já tem — as duas leituras são metades
da mesma coisa, e a minha anterior parou na primeira.

A premissa veio da minha própria leitura parcial de 17 capturas, que o prompt
absorveu como fato. Registro porque é o argumento a favor de ter olhado as 27:
a instrução "não reabrir" protegia uma conclusão errada.

### 1.2 O achado que vem junto

Cada lotação carrega **seu próprio conjunto de perfis**:

```
Principal   (SEAS/ASCOI):  Distribuidor · Analisar Processo Sigiloso ·
                           Administrador de Unidade · Default Nível 2
Secundária  (SEAS/CSIN):   Gestor de modelos da unidade · Alterar nível de
                           prioridade · Distribuidor · Analisar Processo
                           Sigiloso · Administrador de Unidade · Gestor de
                           modelos setoriais · Protocolador · Validador ·
                           Publicar DOE
```

São **capacidades nomeadas por (usuário, lotação)** — não quatro papéis fixos.
Isso importa diretamente para o item 1.0.7 do backlog ("as 9 transações da 0074
não estão concedidas a nenhum grupo"), e é um recorte melhor do que o
`Tenant Admin / Gerente / Operador / Visualizador` que eu tinha visto num print
solto de outro sistema.

---

## 2. Inventário de candidatos

Evidência do nosso lado conferida em `main` hoje. "—" = não existe.

### 2.1 Tempo e visibilidade operacional

| # | Candidato | Captura | AS-IS nosso | Vale? | Custo |
|---|---|---|---|---|---|
| 1 | **Permanência por etapa** (`04 horas 54 min` em cada nó da linha do tempo) | 21,22,26 | `models/processo.py:143` `data_hora_movimentacao`, `:192` `data_hora_recebimento` — **o dado existe**, não é calculado | **SIM** | Cálculo puro |
| 2 | **Tempo total ativo + contagem de tramitações** | 21,22,26 | `services/processo_trail.py` monta a trilha sem agregar | **SIM** | Cálculo puro |
| 3 | **Tempo decorrido na linha da lista** (`70d 03h 17m`) | 03,06,07 | lista mostra data | **SIM** | Front puro |
| 4 | **Situação textual**: "Aguardando análise no(a) UNIDADE" × "Em análise por PESSOA" | 06,07 | depende do #5 | **SIM** | Depende |
| 5 | **Responsável-pessoa** | 34,38 | `processo.id_unidade_responsavel` é **unidade**; não há `id_usuario_responsavel` | **SIM** | 1 coluna |
| 6 | **"Atribuir para mim"** como botão próprio | 34 | — | **SIM** | Botão |
| 7 | **Escopo Individual / Setor / Setor e subordinadas** | 01,02,06,07,08 | `routers/processos.py:166` filtra `id_unidade`; `unidade_trabalho.id_unidade_pai` **já existe** (`models/unidade_trabalho.py:17`) | **SIM** | Query recursiva |
| 8 | **Painel troca o CONJUNTO de KPI conforme o escopo** ("Documentos para assinar" vira "Processos sem responsáveis") | 01 vs 02 | `schemas/dashboard.py` tem 11 grupos fixos | **SIM com adaptação** | Service + front |

### 2.2 Tramitação

| # | Candidato | Captura | AS-IS nosso | Vale? | Custo |
|---|---|---|---|---|---|
| 9 | **Protocolo central = marca na unidade**; o picker só oferece as marcadas e o rótulo `(PROTOCOLO CENTRAL)` aparece na opção | 10 | — | **SIM** | 1 coluna + filtro |
| 10 | **Encaminhar multi-processo** (tabela de NUPs no diálogo) | 36 | encaminhamento 1-a-1 (`services/acoes_processo.py`) | **SIM** | Endpoint |
| 11 | **Justificativa pré-preenchida editável** ("O presente processo foi encaminhado a esta unidade para análise e providências cabíveis.") | 36 | — | **SIM** | Constante + campo |
| 12 | **Grupos de envio = natureza jurídica do órgão** (Fundação, Autarquia, Empresa Pública, Economia Mista, Administração Direta, Outros) | 11 | — | **SIM com adaptação** | 1 coluna |
| 13 | **Botão primário desabilitado até o formulário valer** | 12,18 | parcial | **SIM** | Front |
| 14 | **Aviso de desistência** ("excluirá as informações e os documentos") | 18 | — | **SIM** | Diálogo |
| 15 | **Despacho reusa o formato de Novo Processo** (Para → documento → anexos → Tramitar) | 24 | telas distintas | **SIM com adaptação** | Front |

### 2.3 Autos e documentos

| # | Candidato | Captura | AS-IS nosso | Vale? | Custo |
|---|---|---|---|---|---|
| 16 | **Documento Nº sequencial no processo + Página do processo** (`Documento Nº: 2 · Página do processo: 4`, e 70 depois de um anexo de 66 páginas) | 20,25,31 | `pdf_montagem.py` numera só no PDF final | **SIM** | Coluna + contagem |
| 17 | **Árvore por TRAMITAÇÃO** (a unidade reaparece a cada visita; documentos numerados globalmente sob ela) | 29,30,31 | — | **SIM** | Endpoint + tela |
| 18 | **Folha de Ocorrências** em PDF (Data/Hora · Ocorrência · Usuário/Unidade · Observação) | 35 | `models/audit.py` tem o dado; `pdf_relatorio_tramitacao.py` é relatório, não folha do processo | **SIM** | Gerador |
| 19 | **Arquivos Editáveis separados dos Documentos do processo** | 09,20,25 | anexo é anexo | **SIM** | Coluna |
| 20 | **Cota de anexação POR PROCESSO, com barra, mostrada antes** (`49.5 MB / 800.0 MB`) | 09,28,33 | só limite por arquivo (`config.py:85` = 20 MB) | **SIM** | Soma + campo |
| 21 | **Juntada de documentos com justificativa** | 28 | — | **SIM** | Tela |
| 22 | **Juntada por apensação com justificativa** | 27 | **já exigimos** (`models/apensamento.py:36` `motivo` NOT NULL) | **NÃO** | — |
| 23 | **QR code na capa** | 19,23,29,30 | `pdf_capa.py` + `validacao_publica` — conferir se a capa traz QR | **VERIFICAR** | — |
| 24 | **PDF consolidado servido do S3 por URL pré-assinada** (211 páginas) | 32 | filesystem local (item 3.1 do backlog) | **EVIDÊNCIA** | — |

### 2.4 Configuração e catálogos

| # | Candidato | Captura | AS-IS nosso | Vale? | Custo |
|---|---|---|---|---|---|
| 25 | **Marcadores** — etiquetas coloridas por setor, filtráveis em relatório | 07,40,41,44 | — | **SIM** | 2 tabelas |
| 26 | **Referência Legal** como hipótese de restrição específica ("Lei 12.527/2011 - Art. 7, §3° - Documento preparatório") | 14,19,23 | 5 níveis de sigilo sem fundamento legal | **SIM** | Catálogo + N:N |
| 27 | **Clonar modelo** como botão de primeira classe | 43 | — | **SIM** | Endpoint |
| 28 | **Modelo vinculado ao tipo de documento**; o editor só abre depois de escolher o tipo | 16,42,43 | `models/especie_documental.py` existe; `TemplateDocumento` tem `categoria` livre | **SIM** | FK |
| 29 | **Tags no modelo** (`(NUM-CI)`, `(FROM-CAPACITY)`, `(TO-CAPACITY)`, `(DATE)`) | 43 | `services/placeholders.py:35-51` — 14 tags, sintaxe `{{a.b}}` | **PARCIAL** — faltam destinatário e número do documento | 2 tags |
| 30 | **Numeração do documento no ato da assinatura** (`Nº (GERADO AO ASSINAR O ARQUIVO)`) | 17,43 | — | **SIM** | Sequência |
| 31 | **Preferências de notificação: matriz evento × canal**, com "Não se aplica" como terceiro estado | 39 | `models/notificacao.py:37-42` — **1 linha por usuário**, 3 flags de canal | **SIM** | Tabela |
| 32 | **Mural de mensagens no painel** (orientações da Casa Civil, com data) | 01,02 | — | **TALVEZ** | Tabela |
| 33 | **Toast de job com etapas nomeadas** ("Unificando documentos do processo") | 31,33 | jobs existem; feedback é genérico | **SIM** | Front + status |
| 34 | **Cadeado na lista** para processo restrito | 08 | conferir | **VERIFICAR** | — |
| 35 | **Dar ciência da capa** (ato formal de tomar conhecimento) | 19,23 | — | **DEPENDE DE NEGÓCIO** | — |

### 2.5 Estruturais (§5)

| # | Candidato | Captura | AS-IS nosso |
|---|---|---|---|
| 36 | **Multi-lotação com perfil por lotação** | 38 | `models/usuario.py:20` `id_unidade_trabalho` **singular** |
| 37 | **Assunto hierárquico** (taxonomia de 3 níveis) | 13 | `models/assunto.py:29` `assunto` String(1000) **plano** |
| 38 | **Rascunho = processo sem NUP** ("NUP será gerado após a tramitação") | 04,09 | abertura é atômica e emite NUP |

---

## 3. O que NÃO trazer

| Item | Razão |
|---|---|
| **"Tornar sem efeito"** | A ata registra como defeito ("acúmulo de páginas inutilizadas em auditorias"). Nosso desentranhamento com termo é o comportamento preferido. |
| **Assunto achatado em string** | O SUiTE busca a taxonomia por substring. A taxonomia vale; o achatamento não — ver E2. |
| **Acesso excepcional a processo sigiloso** | Exigência burocrática do órgão, não lacuna de sistema. |
| **Justificativa de apensação** | **Já temos** (`apensamento.motivo` NOT NULL). Não refazer. |
| **Abas fixas substituindo nossos filtros em URL** | Nosso modelo é mais composável. As abas entram como **atalhos para filtros**, preservando a URL como fonte. |
| **Editor próprio** | Google Docs já é a estratégia, e o SUiTE confirma a escolha (usa o mesmo). |
| **Admin substituindo a navegação principal** | Temos launcher e módulos; a navegação lateral que se troca inteira briga com isso. |

---

## 4. Fatias propostas, por (valor ÷ custo)

### F1 — Permanência, tempo total e tempo decorrido `nenhuma migration`

**Se só desse para fazer uma, seria esta.**

Calcular a permanência entre movimentações consecutivas e expor: (a) por nó da
linha do tempo, (b) total ativo e contagem de tramitações no topo, (c) tempo
decorrido ao lado da data em cada linha das listas.

Distinguir os dois tempos que o SUiTE distingue e que nossos campos já separam:
**esperando alguém pegar** (`data_hora_movimentacao` → `data_hora_recebimento`)
e **em análise com alguém** (`data_hora_recebimento` → próxima movimentação).
É a diferença entre gargalo de fila e gargalo de trabalho.

*Custo:* service + schema + front. Zero schema de banco.
*Testes:* permanência de nó intermediário; nó aberto (sem próxima movimentação)
conta até agora; movimentação sem recebimento não vira permanência negativa;
processo com uma só movimentação.

### F2 — Responsável-pessoa, escopo e situação `1 coluna`

`processo.id_usuario_responsavel` nullable — nulo **é** o estado "pendente de
designação", que o SUiTE trata como de primeira classe. Filtro
`escopo=meus|unidade|unidade_e_subordinadas` (a hierarquia já existe em
`id_unidade_pai`). Coluna Situação em texto. Botão "Atribuir para mim", e o
rótulo alternando Atribuir/Alterar. Busca de responsável **restrita a quem é
lotado na unidade**.

*Custo:* 1 coluna nullable + índice `(tenant_id, id_usuario_responsavel)`.
*Testes:* nasce sem responsável; atribuição entra no histórico; `escopo=meus`
não vaza processo alheio; `escopo=unidade` **inclui** os sem responsável;
subordinadas alcança neto e não alcança irmão; **um teste HTTP com usuário
não-SU**.

### F3 — Protocolo central e destinos permitidos `1 coluna`

`unidade_trabalho.recebe_de_outro_orgao` (nome a definir). O endpoint de
destinos devolve só as marcadas quando o envio é para fora do órgão, e o front
mostra o rótulo na opção — o usuário vê **por que** aquela unidade está na
lista. Fecha A3/A4/A5 da spec de 28/08, que hoje são o pior buraco de UX
registrado.

*Custo:* 1 coluna + endpoint + troca de query no front.
*Testes:* unidade não marcada não aparece para envio externo; envio interno não
filtra; `test_guarda_ordem_rotas.py` (declarar a literal antes da paramétrica);
**teste HTTP com usuário não-SU**.

### F4 — `arquivar`: fechar o contrato que mente `sem migration`

`validar_acao_strict` (`workflow_integration.py:148`) aceita `"arquivar"` e não
existe `def arquivar`. Implementar com **motivo de catálogo + observação +
anexo justificativo**, como o SUiTE, ou remover do contrato. Já estava na spec
de 28/08 como P1; as capturas agora dizem qual é o formulário.

*Custo:* service + endpoint + `ARQUIVAMENTO` em `protocolos.acao` via seed —
**e em `ci/seed-e2e.sql`**, porque o `e2e-assinatura.yml` não roda o
`seed_bootstrap`. Nenhuma migration: `protocolos.acao` é tabela legada.

### F5 — Favoritos e marcadores `2 tabelas`

Favorito tem um propósito que só ficou claro na captura 05: **o processo
continua visível depois de sair do meu setor**. É lista de acompanhamento, não
atalho. Marcadores são etiquetas coloridas por unidade, filtráveis.

*Custo:* `favorito(tenant, usuario, processo)` e
`marcador` + `processo_marcador`. RLS pelo boilerplate.
*Testes:* favorito sobrevive à tramitação para outra unidade; marcador não
vaza entre tenants; **usuário não-SU**.

### F6 — Cota de anexação por processo `1 campo derivado`

Somar o que o processo já tem e mostrar `X / limite` com barra em **todo**
diálogo que anexa, antes de tentar. É a resposta direta ao que a ata registra
sobre erro de tamanho de arquivo: mostrar o orçamento em vez de recusar depois.

*Ambiguidade:* no SUiTE a cota aparece como 800 MB numa tela e **1.2 GB** em
outra. Não consegui determinar o que a governa (tipo de processo? nível de
acesso? outra coisa). **Registro como ambíguo** — ver §6, Q4.

### F7 — Folha de ocorrências `gerador`

PDF legível da trilha: Data/Hora · Ocorrência · Usuário/Unidade · Observação.
Temos o dado em `audit_log` e `processo_trail`; falta a saída. Vale porque é o
artefato que se anexa a um procedimento — e a ata cita "folhas de ocorrência
com o histórico completo" como algo que o Ramom demonstrou.

### F8 — Numeração de documento e de página `coluna + contagem`

`Documento Nº` sequencial por processo e `Página do processo` cumulativa (a
captura 20 mostra 2 → 4 → 70, com o anexo de 66 páginas no meio). É o que
permite citar "fls. 70" num despacho sem gerar o PDF antes — a deficiência que
o Ramom apontou na reunião.

*Cuidado:* contar páginas de PDF exige ler o arquivo. Para anexo grande isso é
trabalho de job, não de request.

### F9 — Preferências de notificação por evento `1 tabela`

Matriz evento × canal, com "Não se aplica" como terceiro estado explícito (diz
"este evento não chega por SMS" em vez de mostrar um toggle inútil). Nosso
`notificacao_preferencia` é 1 linha por usuário com 3 flags.

*Migração:* a linha atual vira N linhas (uma por evento) com o mesmo valor de
canal — preserva exatamente o comportamento de quem já configurou.

### F10 — Modelos: clonar, vincular ao tipo, tags que faltam `FK + endpoint`

Clonar como botão de primeira classe; `TemplateDocumento.id_especie_documental`
substituindo a `categoria` livre; e as duas tags que o SUiTE tem e nós não:
**destinatário** (`TO-CAPACITY`) e **número do documento** (`NUM-CI`).

---

## 5. Mudanças estruturais propostas

### E1 — Multi-lotação com perfil por lotação

**(a) O que trava.** `models/usuario.py:20` — `id_unidade_trabalho` é **uma**
coluna nullable. Um usuário existe em exatamente uma unidade. A ata pede troca
de lotação "para comissões específicas" (§41) e a captura 38 mostra o desenho:
uma principal e N secundárias, cada uma com seu conjunto de perfis. Com uma
coluna, participar de comitê exige apagar a lotação de origem.

**(b) Desenho.** `aprimora_py.usuario_lotacao(tenant_id, id_usuario,
id_unidade, principal bool, habilitada bool, cargo, vinculo)`, com índice
parcial único garantindo **uma principal por usuário**. A concessão de
permissão passa a ser por `(usuario, lotação)` — o que casa com nosso
`UsuarioGrupo`, que já é uma tabela de vínculo e hoje só não tem a unidade.

**(c) Migração.** Cada `usuario.id_unidade_trabalho` não-nulo vira uma linha
`usuario_lotacao` com `principal=true`. A coluna **permanece** durante a
transição, mantida em sincronia com a lotação principal por trigger ou pelo
service — ninguém é obrigado a migrar de leitura no mesmo PR.

**(d) O que quebra.** Todo lugar que lê `usuario.id_unidade_trabalho`. Como a
coluna sobrevive espelhando a principal, o comportamento atual não muda até que
cada chamador seja migrado deliberadamente.

**(e) Reversão.** Enquanto a coluna existir e estiver sincronizada, reverter é
parar de escrever em `usuario_lotacao` e apagar a tabela. Depois que algum
caminho passar a depender de lotação secundária, não é mais reversível sem
perda — **e esse é o degrau a declarar no PR que o cruzar**.

> Pré-requisito de negócio: Q1 da §6. Sem saber se permissão é por lotação ou
> global, a tabela nasce com a coluna errada.

### E2 — Assunto hierárquico

**(a) O que trava.** `models/assunto.py:29` — `assunto: String(1000)` plano, com
`tipo_processo` como string livre (`:15`). A Decisão 2 da ata pede catálogo
global de assuntos com customização local, e o SUiTE mostra o formato: três
níveis (`Aquisição - Equipamentos e material permanente - Aeronaves`), o padrão
CONARQ. Com string plana não dá para filtrar por ramo, agregar por nível, nem
distinguir o que é padrão do que é local.

**(b) Desenho.** `id_assunto_pai` auto-referente + `nivel` + `codigo`, e uma
coluna `origem` (`global` | `local`) para separar o herdado do customizado. A
busca continua por caminho concatenado — **derivado**, não armazenado.

**(c) Migração.** Assuntos existentes viram folhas de nível 1 com
`origem='local'` e `id_assunto_pai=NULL`. Nada muda de comportamento: uma
árvore de um nível é uma lista.

**(d) O que quebra.** Nada imediatamente — o campo textual permanece e continua
sendo o que as telas mostram. O que muda é a possibilidade de filtrar por ramo,
que hoje não existe.

**(e) Reversão.** Enquanto ninguém tiver criado hierarquia real, apagar as
colunas devolve ao estado atual. Depois da primeira árvore de verdade, reverter
achata e perde os pais.

> Pré-requisito: Q2 da §6 (herança ou cópia).

### E3 — Rascunho = processo sem NUP

**(a) O que trava.** A abertura é atômica: `services/abertura_processo.py` cria
o processo já numerado, com NUP e ação de ABERTURA. Não há estado anterior.
O SUiTE emite o NUP **na tramitação** ("NUP será gerado após a tramitação",
captura 09) e a aba Rascunhos lista só **Data + Assunto**, sem NUP (captura 04).

**(b) Desenho.** `processo.numero_processo` e `nup` passam a ser nullable, com
`situacao='rascunho'` enquanto não tramitou; a emissão migra para o ato de
tramitar.

**(c) Migração.** Nenhum dado a migrar — todo processo existente já tem NUP e
já tramitou. A mudança é só de caminho novo.

**(d) O que quebra.** Todo lugar que assume `numero_processo` não-nulo —
incluindo PDFs, notificações, `link_url`, busca e a guarda de NUP. É a fatia
com maior superfície das três.

**(e) Reversão.** Reverter exige que não exista nenhum rascunho vivo; com
rascunhos gravados, voltar significa numerá-los ou apagá-los.

> **Recomendo adiar.** A ata (§32) descreve "abas de rascunhos para **edições em
> andamento**", o que pode ser documento em edição e não processo sem número —
> e documento em edição nós **já temos** (`models/minuta.py:103`). Antes de
> mexer na numeração do protocolo, vale confirmar qual das duas coisas o
> usuário quer. Q3 da §6.

---

## 6. Decisões de negócio pendentes

**Q1 — Permissão é por lotação ou por usuário?** No SUiTE, cada lotação carrega
seu conjunto de perfis: o mesmo usuário é "Administrador de Unidade" no comitê
e não na origem. Nosso `UsuarioGrupo` é por usuário. *Pergunta:* o vínculo de
grupo passa a levar a unidade, ou o perfil segue global e só a lotação ativa
muda o que se vê? **Decide a chave de E1 e o desenho de qualquer trabalho no
item 1.0.7.**

**Q2 — Catálogo global de assuntos: herança ou cópia?** Hoje o padrão chega ao
tenant por cópia no provisionamento, e padrão novo não alcança tenant
existente. *Pergunta:* (a) cópia basta, (b) precisa de "aplicar padrão a este
tenant", ou (c) precisa de *fallback* em leitura? Recomendo (b): (c) faz toda
query de catálogo ganhar dois níveis.

**Q3 — "Rascunho" é processo sem número ou documento em edição?** Ver E3. A ata
admite as duas leituras e a diferença de custo é de uma ordem de grandeza.

**Q4 — A cota de anexação é por quê?** As capturas mostram 800 MB e 1.2 GB em
contextos diferentes e **não consegui determinar a regra**. *Pergunta:* o limite
é por processo, por tipo de processo, por nível de acesso, ou por órgão?

**Q5 — "Dar ciência" é ato registrável?** O SUiTE tem o botão e o evento
correspondente nas notificações ("Dado ciência", "Dado ciência ao processo").
*Pergunta:* é ato jurídico com efeito (inicia prazo? vincula?) ou só marca de
leitura? Se tiver efeito, não é UI — é regra.

**Q6 — Referência legal vincula o nível de sigilo?** No SUiTE, "Restrito" vem
com "Lei 12.527/2011 - Art. 7, §3°". *Pergunta:* a hipótese legal é obrigatória
ao restringir, e o catálogo é global ou por tenant?

**Q7 — Marcador é por unidade, por tenant, ou por usuário?** A administração é
setorial na captura 40, mas os marcadores aparecem em processos de outras
unidades na captura 07.

---

## 7. O que NÃO verifiquei

- **Nada rodou.** Docker indisponível nesta máquina; toda afirmação sobre o
  nosso AS-IS vem de leitura de código, não de execução.
- **Não conferi o QR code na capa** (#23) nem o **cadeado de sigilo na lista**
  (#34). Ambos marcados VERIFICAR no inventário.
- **Não sei o que governa a cota** (Q4) — ambíguo nas capturas, não deduzido.
- **Não vi o SUiTE em uso**, só capturas estáticas. Fluxo, latência, mensagens
  de erro e o que acontece quando algo falha ficam fora.
- **Não estimei esforço em horas.** "Custo" aqui é natureza da mudança (cálculo,
  coluna, tabela, tela), que é o que dá para afirmar sem medir.
- **Os 27 novos não foram cruzados com a matriz da spec de 28/08** item a item;
  cruzei o que mudava conclusão. A matriz continua válida no que afirma.
- **`e4a41ee` é o `main` de referência.** O PR #50 (abas ARIA) pode ter entrado
  depois; não conferi.
