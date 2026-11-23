# Relatórios do Protocolo

> **Status:** vivo · **Autoridade sobre:** o que cada número de `/m/protocolo/relatorios` mede, quem vê, e as limitações conhecidas.
> **Última verificação:** 2026-11-22 (SI-49: relatório salvo abre no resultado).
> Índice: [docs/INDEX.md](INDEX.md) · precedência: código > `CLAUDE.md` > este doc.

Fonte de verdade executável: `backend/app/services/relatorios_comum.py` (as
regras), `relatorios_gerencial.py` (a página), `relatorios_documentacao.py` e
os testes `backend/tests/test_relatorios_protocolo_medidas.py` e
`test_relatorios_protocolo_filtros.py` (o que cada número mede) e
`test_relatorios_protocolo_acesso.py` (quem vê); o relatório montado, em
`relatorios_montado.py` e `test_relatorio_montado.py`. Se este doc divergir deles, o
código vence e este arquivo deve ser corrigido.

## Três telas, três perguntas

| Tela | Pergunta | Onde |
|---|---|---|
| Painel de controle, andar de cima | O que a minha unidade tem para fazer **agora**? | `/m/protocolo/painel` |
| Painel de controle, **Panorama do protocolo** | Como o protocolo andou **no período** (7/30/90 dias), na minha unidade ou em todas? | `/m/protocolo/painel`, abaixo dos quadros |
| **Relatórios** | Qual relatório responde à minha pergunta, e a lista que prova cada número | `/m/protocolo/relatorios` (índice) e as listas |
| Dashboard executivo | (legado) panorama em gráficos | `/dashboard` — **fora do menu** (ver Limitações) |

Desde 2026-11-14 (decisão do time): os números do período saíram da página de
Relatórios e foram para o **Painel de controle**, como segundo andar
(`components/protocolo/PanoramaDoProtocolo.tsx`), no visual do Panorama do
Início: cartões, gráficos com a pergunta no título e cada bloco levando ao
relatório que prova o número. Os filtros do Panorama são simples: período por
botões e **minha unidade (padrão, a regra de negócio de hoje) ou todas**. Os
filtros finos (tipo, assunto, serviço) ficam nos Relatórios. Sem comparação
com o período anterior. O Panorama lê `GET /relatorios/gerencial.json`, o
mesmo endpoint da antiga página — **não** o dashboard executivo.

As tabelas e a lista do Painel saíram (mesmo dia): "Aguardando retorno" e
"Assinaturas" viraram detalhe dos quadros Enviados e Para assinar; "Parados há
mais tempo" é o cartão de Parados do Panorama, que leva à visão Parados do
relatório de Processos — que, nessa visão, ordena do mais parado para o menos
e mostra "parado há N dias".

**Dois prazos no quadro "Os prazos estão sendo cumpridos?", o do serviço como
principal** (decisão de 2026-11-14). O **prazo do serviço** (a promessa ao
cidadão; o mesmo dos Relatórios) é a barra principal. O **prazo do envio** (o
da caixa: o do encaminhamento vigente, ou o do serviço quando o envio não fixou
um — o que pinta a linha na caixa) vem embaixo, menor, só em "Minha unidade",
porque é da mesa da unidade ativa, agora. Por isso os dois "vencidos" podem
diferir. Por que o do serviço é o principal: vale igual para todos (o do envio
depende de alguém preencher), fecha a conta com a lista do relatório, e mede o
que o cidadão sente.

A página de **Relatórios virou um índice**: os quatro relatórios padrão
(Processos, Tramitação, Documentação, Assinaturas), cada um com a pergunta que
responde e quem o usa (a lista do SI-33), mais "Meus relatórios" e o montador
(SI-35). Ela não consulta número nenhum. As listas continuam como eram.

## Os números do período (Panorama) e as listas

Um filtro, o **recorte comum** (período, unidade, tipo, assunto, serviço), vale
igual no Panorama, nas quatro listas, no montador, nos CSVs e nos PDFs — os
campos são um componente só (`CamposDoRecorte`).
**Cada seção conta pela sua própria data** e diz qual é:

| Seção | Conta | Pela data de |
|---|---|---|
| Entrada e saída no tempo (gráfico) | abertos e arquivados por semana (mês, acima de ~6 meses) | abertura / arquivamento; sem período no filtro, as últimas 12 semanas |
| Entrada | processos abertos e por canal | abertura |
| Andamento | em andamento, em trânsito, parados | **hoje** — não usa o período |
| Saída | arquivados e tempo médio até arquivar | arquivamento |
| Prazos | arquivados no prazo ou com atraso; em aberto dentro do prazo, vencendo, vencidos | arquivamento / **hoje** |
| Gargalos | entradas em cada unidade, atrasos, permanência média | entrada na unidade |
| Documentos exigidos | abertos cujo serviço exige documentos: pendentes, parciais, completos | abertura; situação dos documentos **hoje** |
| Complementação | processos com pedido feito / aguardando o cidadão / respondido; tempo médio de resposta | pedido / **hoje** / resposta |
| Assinaturas | pedidas, pendentes, concluídas, canceladas, tempo médio | pedido |

Por que não um seletor único de data: com o período pela abertura, a Saída
contaria "abertos em outubro que um dia foram arquivados" — número plausível
que responde outra pergunta.

A comparação com o período anterior e os "principais assuntos" saíram da
página em 2026-11-11, para deixá-la mais limpa. Os assuntos
viraram o quadro **"Agrupar por"** da lista de processos.

No Panorama, cada bloco leva à sua lista com o recorte que produziu o número:

| Bloco do Panorama | Leva a |
|---|---|
| Cartões Abertos, Arquivados, Em andamento, Parados, Prazo vencido | lista de processos, na visão do cartão |
| Entrada e saída no tempo; Por onde entram | lista de processos |
| Os prazos estão sendo cumpridos? (cada fatia) | lista de processos, na visão da fatia |
| Onde os processos demoram? | tramitação, pela data de chegada |
| Os documentos estão em dia? (cada fatia) | lista de documentação, na visão da fatia |
| Assinaturas pendentes; Como andam as assinaturas? | assinaturas, pela data do pedido |

Na lista de processos, o seletor **"Mostrar"** escolhe o recorte de cada número
do grupo (abertos, arquivados, em andamento, em trânsito, parados, no prazo, com
atraso, dentro do prazo, vencendo, vencidos). Cada opção é a mesma consulta que
produziu o número: o backend garante que o número é o total dessa lista, e o
frontend garante que cada opção pede esses mesmos parâmetros
(`VISOES_PROCESSOS` em `frontend/lib/relatorios.ts`). Nas opções "de hoje" o
período não entra na consulta, mas fica na URL e volta a valer ao trocar de
opção. **CSV e PDF de lista ficam nas listas**; o Panorama sai inteiro em PDF
("PDF do panorama", o antigo "PDF desta página").

Cada lista tem, além do recorte comum, **os filtros do que ela mostra**:

| Lista | Filtros próprios |
|---|---|
| Processos | Mostrar (a visão); **Sigilo** (só ostensivos / só sigilosos) e **Origem** (internos / externos) — os critérios dos cartões "Sigilosos" e "Externos", que passam a ser o total da lista filtrada; quadro **Agrupar por** tipo, unidade dona, unidade onde está agora (arquivado: onde foi arquivado), assunto ou serviço |
| Tramitação | Período pela abertura ou pela entrada na unidade; **Só processos com atraso** |
| Documentação | Mostrar (a visão: todos que exigem documentos, pendentes, parciais, completos, complementação pedida / aguardando / respondida) |
| Assinaturas | Data do pedido ou da conclusão, solicitante, assinante, status |

"Só com atraso" analisa o recorte inteiro antes de cortar a lista (o atraso sai
das etapas, calculadas por processo); acima de 10 mil processos no recorte, a
tela pede para filtrar mais em vez de responder pela metade.

As opções do filtro de serviço vêm de `GET /relatorios/servicos.json` (basta a
transação `processo`), não de `GET /servicos`, que exige administrar o
catálogo — quem só consulta relatórios veria o filtro vazio. Serviços inativos
entram: processo antigo pode ser de um serviço que saiu do catálogo.

## Definições

- **Período:** dias em **hora de Brasília**, inclusive nas duas pontas. O banco
  grava UTC; "até 10/11" vai até 11/11 03:00 UTC.
- **"Pela data X" só conta quem tem X**, com ou sem período. Sem período, os
  arquivados são os que têm arquivamento, e as assinaturas pela conclusão são
  as concluídas. (Até 2026-11-12, sem período, a Saída contava todos os
  processos, abertos inclusive.) Por isso as contas da página fecham: arquivados
  de Prazos = Saída; em aberto de Prazos = Andamento; sem período, Entrada =
  Andamento + Saída — `test_as_contas_da_pagina_fecham` confere todas.
- **Situação:** *arquivado* = tem movimentação de arquivamento; *em trânsito* =
  envio ainda não recebido nem desfeito; *em andamento* = o resto. São as
  mesmas condições das caixas de trabalho. O campo `processo.ativo` **não é
  usado**: nenhuma parte do sistema o escreve.
- **Parado:** não arquivado e **sem nenhuma movimentação** há N dias — padrão
  15, escolhido na tela. Conta como movimentação o que vira linha na linha do
  tempo: abertura, envio, recebimento e, desde o SI-62 (2026-11-22), o
  **despacho sem encaminhar**. "Analisei, aguardando parecer" tira o processo
  de Parados: é ato registrado. Assinar, anexar e redigir documento **não**
  contam — não criam movimentação.
- **Unidade, em três sentidos:** *envolvida* (dona ou onde está agora —
  padrão), *dona* (a unidade proprietária escolhida na abertura) e *onde está
  agora*. "Por onde passou" saiu do filtro em 2026-11-12. Na **tramitação pela
  data de entrada** (e nos Gargalos), a unidade é **onde o processo deu
  entrada**, qualquer que seja o sentido escolhido: processo que entrou em B e
  já saiu é entrada de B.
- **Entradas na unidade (Gargalos):** a abertura, na unidade dona, ou um
  recebimento. Envio pendente ou recusado não é entrada.
- **Atraso:** a estadia na unidade terminou (ou segue) depois do **fim do dia**
  do prazo do envio que trouxe o processo — a definição das caixas de trabalho.
- **Prazo do serviço:** abertura + N dias **corridos** (o N é congelado na
  abertura). Arquivado até o prazo = no prazo. Em aberto: *vencido* se já
  passou; *vencendo* se faltam 20% do prazo ou menos (mínimo 1 dia). Processo
  sem prazo de serviço (legado, ou serviço sem prazo) **fica fora da conta** e a
  página diz quantos são. A regra é a de `prazos.calcular_prazo` (a do detalhe
  do processo); a versão em SQL, que permite listar e contar, é comparada a ela
  por teste.
- **Assinatura concluída:** realizada **e** com data de fim. Realizada sem data
  de fim conta como pendente.
- **Sigiloso** (lista de processos): qualquer nível acima de ostensivo — sempre
  dentro do que a credencial de quem consulta alcança.
- **Documentos exigidos:** a situação da tela do processo
  (`checklist_documentos`): sem serviço ou serviço sem documento → fora da
  conta; só itens opcionais → completo; obrigatórios: nenhum enviado →
  pendente, parte → parcial, todos → completo. "Enviado" = anexo ativo, não
  excluído, marcado com aquele documento. A versão em SQL é comparada à da tela
  por teste. O Dashboard executivo diverge num caso (só opcionais lá é "sem
  documento exigido").
- **Complementação:** pedido do servidor ao cidadão para mandar documentos.
  Os números contam **processos**; o tempo médio de resposta é por pedido
  respondido no período. A lista mostra o pedido mais recente de cada processo.
  A **mensagem do pedido não aparece** em tela nem em CSV: é texto livre e pode
  trazer dado pessoal.

## Relatório montado pela própria pessoa (SI-35)

Em `/m/protocolo/relatorios/montar`, com o grupo **Meus relatórios** no topo
da página de relatórios. A pessoa escolhe colunas e filtros, gera o resultado e
salva com um nome para abrir de novo. Código: `relatorios_montado.py` (a
consulta), `relatorios_salvos.py` (os salvos), `schemas/relatorio_montado.py`
(o catálogo); testes em `backend/tests/test_relatorio_montado.py`.

- **Uma linha por processo.** O recorte é o MESMO da lista de processos
  (`relatorios._base`): prefeitura, rascunho, sigilo, unidade nos três
  sentidos, assunto, tipo, serviço, período pela abertura ou pelo
  arquivamento, situação, prazo, parados, sigilo e origem. O montador só
  acrescenta filtros que estreitam esse conjunto: situação dos documentos,
  complementação aguardando o cidadão, etapa atrasada na tramitação e
  assinatura pendente — cada um com a regra da tela de origem (os testes
  comparam com a Documentação, a Tramitação e as Assinaturas).
- **Tramitação e assinaturas são colunas resumidas do processo** (envios,
  unidades por onde passou, etapas atrasadas, último envio, unidade onde ficou
  mais tempo; assinaturas pedidas, concluídas, pendentes, última conclusão),
  não uma fonte própria. As etapas vêm de
  `relatorios_tramitacao.resumir_tramitacao`, a mesma função da tela de
  Tramitação. O filtro "com etapa atrasada" analisa até 10 mil processos, como
  o "só com atraso" de lá.
- **Catálogo fechado.** Coluna, ordem e agrupamento são uma lista no schema; o
  backend recusa (422) coluna ou chave fora dela. **Sem dado pessoal além do
  nome do manifestante:** CPF/CNPJ, telefones e e-mail ficaram fora por
  decisão do PO (2026-11-12), mesmo o CPF aparecendo na tela do processo.
  Observação, corpo e despachos (texto livre) também.
- **Período fixo ou relativo** ("últimos N dias", "este mês", "mês passado",
  "este ano"). O relativo é resolvido no dia em que o relatório abre, em dia
  local, e a descrição do recorte diz isso.
- **Agrupar por** situação, tipo, unidade dona, onde está, assunto ou serviço:
  a contagem aparece acima da lista e soma o total.
- **Salvos são pessoais.** O relatório salvo (`aprimora_py.relatorio_salvo`,
  migration 0138) pertence a `(tenant_id, id_usuario)`; o de outra pessoa ou
  de outra prefeitura responde **404**. Guarda só a **definição**, nunca os
  dados: cada abertura roda de novo com o sigilo de quem abre, naquele momento
  — credencial rebaixada hoje tira o processo do relatório hoje. Nome único
  por pessoa (sem diferença de maiúsculas), até 50 por pessoa. Coluna que
  sair do catálogo depois de salva é tirada ao abrir, com aviso.
- **O salvo abre no resultado (SI-49).** Os parâmetros (período, filtros,
  colunas, agrupamento) ficam atrás do botão **Editar**: "Gerar relatório"
  aplica e fecha, "Cancelar" descarta o que mudou e fecha. O que está
  filtrado continua à vista na descrição do recorte, acima dos totais. O
  relatório novo, ainda sem salvar, mostra os parâmetros sempre; o salvo que
  não consegue gerar (por exemplo, ficou sem coluna válida) também abre com
  eles. "Salvar alterações" só aparece quando há diferença para o salvo.
- **"Alterações não salvas".** Gerar com outra definição sem salvar deixa na
  tela um resultado que não é o salvo, sob o nome do salvo — e o PDF sai com
  esse nome. O cabeçalho mostra o selo enquanto o resultado na tela diferir
  do salvo. A comparação ignora a ordem das chaves dos filtros (a do servidor
  e a da URL podem vir em ordens diferentes), mas não a ordem das colunas.
- **Exportação:** CSV (lista completa, com o mesmo teto de 50 mil) e PDF
  (lista limitada), com a definição aplicada no parâmetro `d`. No CSV do
  montador as datas saem em `dd/mm/aaaa hh:mm`, para abrir direto na planilha.
- **Compartilhar** um relatório salvo com outra pessoa fica para uma próxima
  versão.

## Quem vê o quê

- **Qualquer servidor com a transação `processo`** vê os relatórios de **todas
  as unidades** da prefeitura (decisão de 2026-11-10). Não há recorte por
  lotação.
- **Sigilo vale em tudo** — lista, totais, quebras, CSV, PDF e os números da
  página: só entra processo que a credencial de quem consulta alcança, a mesma
  regra de `GET /processos`. Um total que contasse o reservado revelaria que ele
  existe.
- Rascunho de outra pessoa não entra; dados de outra prefeitura não entram,
  nem pedindo a unidade dela.

## Exportação

- **CSV** traz o recorte descrito nas primeiras linhas e a lista completa. Se o
  recorte passar do teto (50 mil processos; 10 mil na tramitação), o CSV é
  **recusado** com o motivo, em vez de sair cortado.
- **PDF** tem lista limitada e diz quando cortou ("os N mais recentes de M");
  os totais contam tudo.

## Limitações conhecidas

- **Fuso fixo `America/Fortaleza`.** O cadastro da prefeitura não guarda fuso;
  vale para os municípios do Ceará. Município em outro fuso precisa desse campo
  antes.
- **Canal de entrada antigo.** O campo é recente: processos anteriores aparecem
  como "Não informado" na seção Entrada.
- **Horas nas outras telas.** Os relatórios mostram hora de Brasília; o detalhe
  do processo e as caixas ainda mostram a hora UTC como se fosse local (3h a
  mais). Card separado.
- **Dashboard executivo** (`/dashboard`) saiu do menu em 2026-08-07 e só abre
  pela URL, para quem tem a transação `dashboard`. O Ctrl+K "dashboard" leva ao
  Início, não a ele. O quadro "Ativos agora" dele ainda conta `processo.ativo`.
- **PDF da tramitação em segundo plano:** o botão "Gerar em background" saiu da
  tela em 2026-11-12. Gerava o mesmo PDF de 200 processos que o botão PDF,
  deixava o arquivo em Administração → Jobs (outro módulo) e o download
  (`/jobs/{id}/resultado`) não confere quem pediu o arquivo. O endpoint
  `POST /jobs/relatorio-tramitacao` e a task continuam; refazer é card separado.
