# Relatórios do Protocolo

> **Status:** vivo · **Autoridade sobre:** o que cada número de `/m/protocolo/relatorios` mede, quem vê, e as limitações conhecidas.
> **Última verificação:** 2026-11-12 (SI-35).
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
| Painel de controle | O que a minha unidade tem para fazer **agora**? | `/m/protocolo/painel` |
| Dashboard executivo | Qual o **panorama**, em gráficos? | `/dashboard` — **fora do menu** (ver Limitações) |
| **Relatórios** | O que aconteceu **no período**, com a lista que prova cada número? | `/m/protocolo/relatorios` |

## A página de relatórios

Uma página, um filtro no topo (período, unidade, tipo, assunto, serviço), um
gráfico de tendência e as seções abaixo. O filtro é o **recorte comum**: vale
igual na página, nas quatro listas, nos CSVs e nos PDFs.
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

As seções ficam em **quatro grupos, um por tela de destino**, com **um botão de
lista por grupo**:

| Grupo | Subgrupos | Botão leva a |
|---|---|---|
| Processos | Entrada e saída no tempo, Entrada, Andamento, Saída, Prazos | lista de processos |
| Tramitação | Gargalos por unidade | tramitação, pela data de chegada |
| Documentação | Documentos exigidos, Complementação | lista de documentação |
| Assinaturas | Pedidos no período | assinaturas, pela data do pedido |

Na lista de processos, o seletor **"Mostrar"** escolhe o recorte de cada número
do grupo (abertos, arquivados, em andamento, em trânsito, parados, no prazo, com
atraso, dentro do prazo, vencendo, vencidos). Cada opção é a mesma consulta que
produziu o número: o backend garante que o número é o total dessa lista, e o
frontend garante que cada opção pede esses mesmos parâmetros
(`VISOES_PROCESSOS` em `frontend/lib/relatorios.ts`). Nas opções "de hoje" o
período não entra na consulta, mas fica na URL e volta a valer ao trocar de
opção. **CSV e PDF de lista ficam nas listas**; a página de relatórios sai
inteira em PDF.

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
- **Parado:** não arquivado e **sem nenhuma movimentação** (envio, recebimento,
  despacho, assinatura…) há N dias — padrão 15, escolhido na tela.
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
