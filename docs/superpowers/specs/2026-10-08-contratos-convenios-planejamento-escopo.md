# Gestão de contratos e convênios — planejamento

> **Status:** proposta. Decisões D1–D4 tomadas em 2026-10-08 (seção 10); **implementação não
> autorizada** — nada aqui foi construído nem está liberado para construir.
> **Autoridade sobre:** as decisões D1–D4 e o roteiro da seção 9, até um spec de fatia substituí-los.
> **Redigido em:** 2026-10-08. **Fontes conferidas nessa data:** Manual do SIM 2026, IN TCE-CE
> 01/2025, Anexo I da Portaria 615/2026 e o texto da Lei 14.133/2021 no Planalto. As demais leis
> foram citadas de memória — a seção 12 separa o que foi lido do que não foi.

## 1. Em uma página

**O problema, visto da cadeira do gestor.** Contrato e convênio são onde o município mais perde
dinheiro e onde o gestor mais responde pessoalmente: vigência que vence sem ninguém perceber,
aditivo acima do limite legal, fiscal que nunca foi designado, convênio cujo prazo de prestação de
contas passa em branco e deixa o município inadimplente para novas transferências. Nenhuma dessas
falhas é de má-fé; todas são de **calendário e de responsável sem nome**.

**O que o TCE-CE cobra.** Todo mês, até o dia 30 do mês seguinte, o município envia pelo SIM cada
contrato firmado, cada aditivo, quem é o fiscal, o processo de contratação que o originou, e os
convênios e parcerias. Uma vez por ano, pelo eContas, presta contas de gestão por unidade — a partir
do exercício de 2026 com dados estruturados em XML. O que o município informa no SIM durante o ano
é o que o Tribunal confronta na prestação de contas.

**O que propomos.** Tratar contrato e convênio como **um ciclo de vida com dono, prazo e
evidência em cada etapa**, e fazer o sistema ser o lugar onde esse ciclo acontece — de modo que a
remessa ao SIM seja consequência do trabalho do dia a dia, e não uma digitação paralela no fim do
mês.

**O que já existe.** O módulo de pagamentos tem um cadastro de contrato enxuto (número, fornecedor,
unidade, objeto, vigência, valor). Ele sustenta o pagamento, mas não a gestão: não tem aditivo,
fiscal, processo de origem, garantia nem identificador do PNCP — que são justamente os campos que o
SIM exige (seção 4).

**O que precisa de decisão antes de qualquer código:** seção 10.

## 2. Marco legal — o que cada norma obriga na prática

| Norma | O que impõe à gestão de contratos e convênios |
|---|---|
| **Constituição Federal**, arts. 37 (XXI), 70, 71, 74 | Licitar como regra; prestar contas de todo recurso público; manter controle interno. |
| **Lei 14.133/2021** (Licitações e Contratos) | O eixo de tudo — os pontos que viram regra de sistema estão detalhados logo abaixo da tabela. Além deles: formalização e cláusulas necessárias (arts. 89–95), garantias (arts. 96–102), extinção (arts. 137–139), recebimento provisório e definitivo (art. 140), sanções e processo de responsabilização (arts. 155–163), segregação de funções e linhas de defesa (arts. 7º e 169). |
| **Lei 14.133, art. 184** | Aplica a lei, no que couber, a convênios e instrumentos congêneres. |
| **Lei 13.019/2014** (MROSC) | Parcerias com organizações da sociedade civil: termo de colaboração, termo de fomento, acordo de cooperação; chamamento público; plano de trabalho; **gestor da parceria** e comissão de monitoramento; prestação de contas pela OSC e análise pelo município em prazo certo. Exige regulamento municipal. |
| **Lei 4.320/1964**, arts. 58–65 | Empenho prévio, liquidação (verificar o direito do credor) e só então pagamento. Contrato sem empenho é despesa irregular. |
| **LC 101/2000** (LRF) | Estimativa de impacto e adequação orçamentária antes de criar despesa (arts. 15–17); condições para **receber** transferência voluntária (art. 25); vedação de assumir obrigação sem caixa nos dois últimos quadrimestres do mandato (art. 42); transparência (art. 48). |
| **Lei 12.527/2011** (LAI) | Publicação ativa de contratos, aditivos e convênios, na íntegra. |
| **Lei 13.709/2018** (LGPD) | CPF de fiscal, sócio e dirigente é dado pessoal: publica-se o necessário, não tudo. |
| **Lei 8.429/1992** e **Lei 12.846/2013** | Improbidade e anticorrupção — o pano de fundo da responsabilização pessoal do gestor e do fiscal. |
| **LINDB**, arts. 20–30 | A decisão do gestor deve ser motivada considerando as consequências práticas; responde por dolo ou erro grosseiro. Na prática: **registre por que decidiu**. |
| **Decreto federal 11.531/2023** e Portaria Conjunta MGI/MF/CGU 33/2023 | Convênios e contratos de repasse com recursos da União, operados no **Transferegov.br**. |
| **LC estadual 119/2012** e Decreto estadual 32.811/2018 | Transferências voluntárias do Estado do Ceará, operadas no **e-Parcerias** (CGE-CE). O município entra como convenente; atraso na prestação de contas gera inadimplência. |
| **Constituição do Ceará**, art. 42; **IN TCE-CE 01/2025**; INs 02/2013 e 03/2013 | Prazo mensal do SIM; regras das prestações de contas de governo (PCG) e de gestão (PCS). |

**Lei 14.133 — o que foi conferido no texto vigente e vira regra:**

- **Art. 94.** A divulgação no PNCP é **condição de eficácia do contrato e de seus aditamentos**:
  20 dias úteis da assinatura em caso de licitação, 10 dias úteis em contratação direta. Contrato
  de urgência vale desde a assinatura, mas a publicação fora do prazo gera **nulidade**. Em obra,
  há dois prazos a mais em sítio oficial: 25 dias úteis da assinatura (quantitativos e preços
  contratados) e 45 dias úteis da conclusão (quantitativos executados e preços praticados).
  Contratação de artista por inexigibilidade exige detalhar cachê, transporte, hospedagem e
  infraestrutura. **O aditivo também tem prazo de PNCP** — é o ponto mais esquecido.
- **Arts. 106 e 107.** Serviço e fornecimento contínuo: até 5 anos, com atesto de vantagem e de
  crédito orçamentário **no início de cada exercício**; prorrogável até o máximo de 10 anos, se
  previsto em edital e atestada a vantagem.
- **Art. 111.** Contrato de escopo (obra, entrega definida): a vigência prorroga-se
  automaticamente se o objeto não for concluído. O alerta de vencimento desses contratos é
  diferente do alerta dos contínuos.
- **Art. 117.** Um ou mais fiscais **especialmente designados**, ou seus substitutos; o fiscal
  anota as ocorrências em **registro próprio** e leva ao superior o que passa da sua competência.
- **Art. 125.** Acréscimo ou supressão unilateral de até **25% do valor inicial atualizado**; em
  reforma de edifício ou equipamento, até **50% para acréscimo**. O art. 126 veda transfigurar o
  objeto.
- **Art. 136.** Reajuste e repactuação previstos no contrato, mudança de razão social e empenho de
  dotação vão por **apostila**, sem termo aditivo. Apostila e aditivo são registros distintos.
- **Art. 141.** Ordem cronológica **por fonte de recursos**, em quatro categorias: bens, locações,
  serviços, obras. A quebra exige justificativa prévia e **comunicação ao controle interno e ao
  tribunal de contas**.
- **Art. 176.** Só municípios de até 20 mil habitantes têm prazo estendido (seis anos da
  publicação) para os requisitos de agentes, licitação eletrônica e divulgação em sítio oficial.
  Conferir a população do município piloto antes de assumir qualquer folga.
- **Arts. 184 e 184-A.** A lei se aplica a convênios no que couber; convênio com a União de até
  R$ 1,5 milhão tem regime simplificado (Lei 14.770/2023).

O município ainda precisa de **regulamento próprio** da Lei 14.133 e da Lei 13.019. Se Itaitinga e
Sobral já os têm, o sistema deve espelhá-los; se não têm, é pré-requisito do projeto (seção 10).

## 3. O que o TCE-CE exige

Antes: o Tribunal de Contas dos Municípios foi extinto em 2017 e suas atribuições passaram ao
**TCE-CE**. Material antigo que cita "TCM" refere-se ao mesmo conjunto de obrigações.

### 3.1 SIM — Sistema de Informações Municipais

Remessa **mensal**, arquivos texto de layout fixo gerados pelo sistema do município, validados pelo
programa do Tribunal (PGI) e enviados pelo SIMWeb. **Prazo: até o dia 30 do mês subsequente.**
Versão vigente: Manual do SIM 2026, Portaria 1227/2025, atualizado pela Portaria 130/2026.

Correções e acréscimos só são aceitos até **31 de janeiro do ano seguinte** — ou antes, até a data
da prestação de contas de gestão da unidade. Depois disso o que foi informado errado fica errado.

Os arquivos que tocam contratos e convênios:

| Tabela | Arquivo | Conteúdo | Quando enviar |
|---|---|---|---|
| 501 Processos administrativos para contratações | `LI` `.LCO` | Licitação, dispensa, inexigibilidade | Mês da homologação ou ratificação |
| 502–507 | `PE` `CL` `MC` `LT` `TL` `DL` `.LCO` | Publicações, responsáveis pela contratação, licitantes, itens, dotações | Com o processo |
| **511 Contratos** | `CO` `.LCO` | Contrato original **e cada aditivo** | Mês da assinatura |
| **513 Contratados** | `CT` `.LCO` | Cadastro de quem foi contratado | Com o contrato |
| 531–536 Parcerias OSC — processo | `.OSC` | Chamamento, comissões, OSCs, dotações | Com o processo |
| **537 Parcerias OSC** | `PS` `.OSC` | Termo de colaboração, fomento ou acordo de cooperação | Mês da assinatura |
| **538 Aditivos das parcerias** | `PD` `.OSC` | Aditivos | Mês da assinatura |
| 601 Notas de empenho | `NE` `.DCD` | Empenho, **com o contrato e o processo a que se vincula** | Mensal |
| 612 / 602 / 603 / 604 | `.DCD` | Liquidações, notas fiscais e seus itens, pagamentos | Mensal |
| **807 Transferências federais e estaduais** | `TF` `.OUT` | Convênios e contratos de repasse **recebidos** | No primeiro repasse do exercício |
| 901–903 Obras | `.OSE` | Obra, medições, status (inclusive paralisação) | Conforme o fato |

**O que a tabela 511 pede de cada contrato** — é a lista mínima do que o cadastro precisa ter:

- CPF do gestor que celebrou, número (até 15 caracteres, **único no exercício**) e data;
- tipo de objeto, em 18 categorias fixas (assessoria, publicidade, coleta de resíduos, obra,
  evento, medicamentos, terceirização, locação de imóvel, transporte escolar, combustível, locação
  de veículos, merenda, TI, material de consumo, gênero alimentício, bem permanente…);
- **modalidade**: original, ou aditivo de acréscimo, de redução, de prazo, de prazo e acréscimo, de
  prazo e redução, ou de renovação;
- vigência (início e fim previsto), objeto, valor;
- se for obra: número, tipo, data de início e término previsto, herdados da tabela de obras;
- processo administrativo de origem (número e data de autuação, como na tabela 501);
- **CPF e nome do fiscal do contrato** — o CPF precisa existir na tabela 951 (agentes públicos);
- **Id do contrato no PNCP**, quando cadastrado.

Três regras do manual que derrubam remessa quando ignoradas:

1. **Aditivo é um registro novo**, que aponta para o contrato original (CPF do gestor, número e
   data do original). Não se altera o registro do contrato.
2. No aditivo, o campo de valor leva **só a diferença**, sempre **positiva** — inclusive em
   redução. Aditivo só de prazo vai com valor zero. A vigência informada é a **nova data final**.
3. O empenho (601) carrega o contrato e o processo. Empenhar sem contrato cadastrado, ou com número
   diferente do enviado na 511, gera inconsistência entre arquivos.

**O processo de contratação (tabela 501) e o Portal de Licitações.** O número do processo
informado no SIM tem de ser **o mesmo** usado no Portal de Licitações do TCE-CE — uma terceira
obrigação, anterior ao contrato. A 501 pede ainda: espécie (licitação, dispensa por valor, demais
dispensas, inexigibilidade, adesão a ata, credenciamento…), valor estimado, fundamentação legal
no formato "lei, artigo, parágrafo, inciso", os Ids do PNCP da contratação e da ata, e o **CPF de
quem deu o parecer jurídico, de quem cotou preços, de quem fez o termo de referência e de quem
homologou** — todos precisam constar no cadastro de agentes públicos (tabela 951).

**Convênio tem dois sentidos, e o SIM os separa:**

- **Município recebe** (convênio ou contrato de repasse federal/estadual) → tabela **807**: código
  da transferência, natureza da receita, função de governo, órgão cedente, objeto, conta bancária
  que recebe, datas de celebração e vigência, valor total e **contrapartida municipal**.
- **Município repassa a OSC** (Lei 13.019) → tabelas **531–538**: instrumento, vigência, objeto,
  justificativa, valor, dirigente da OSC, **agente público responsável pela parceria**, processo e
  modalidade (chamamento, dispensa ou inexigibilidade de chamamento).

### 3.2 eContas — as prestações de contas

Sistema do portal e-TCE por onde o município envia três coisas: **PCG** (contas de governo, do
prefeito), **PCS** (contas de gestão, por unidade) e **tomada de contas especial**.

- Regras gerais: IN 01/2025; PCS pela IN 03/2013; PCG pela IN 02/2013.
- **Prazo da PCS: 180 dias** do encerramento do exercício (anual) ou do término da gestão
  (parcial, quando o responsável é exonerado antes do fim do ano) — IN 01/2025, art. 5º. Quem
  presta contas é o dirigente da Unidade Prestadora de Contas que foi gestor no exercício.
- O Relatório de Desempenho da Gestão (IN 01/2025, art. 17) cobre, entre outros, **parcerias com
  o terceiro setor** e a **ordem cronológica de pagamento, com justificativa de cada
  descumprimento**.
- A **Portaria 51/2026** padroniza a classificação das unidades e a estrutura da PCS, com anexos e
  modelos de relatório por tipo de unidade (secretarias e fundos, autarquias e fundações, estatais,
  câmaras, consórcios).
- A **Portaria 615/2026** fixa o padrão técnico: a partir das contas do **exercício de 2026**,
  documentos gerais em PDF pesquisável e as informações **por unidade orçamentária em XML
  estruturado** (modelos 1 a 20).
- O Manual do SIM 2026 acompanha essa mudança: o eixo passa a ser a **Unidade Prestadora de
  Contas**, com a tabela de Gestores (101) identificando quem presta contas e a de Ordenadores
  (109) registrando todos que executam despesa.

**Os modelos XML que dependem deste módulo** (Anexo I da Portaria 615/2026, um arquivo por unidade
gestora e unidade orçamentária):

| Modelo | Conteúdo | O que exige de nós |
|---|---|---|
| **17 — Mapa de licitações** | Licitações, dispensas e inexigibilidades "com seus enquadramentos legais e contratos vinculados" | Modalidade, número do processo, fundamentação, CNPJ e nome do contratado, número e objeto do contrato, vigência inicial e final, função programática, **valor inicial e valor final** |
| **16 — Pagamentos por credor** | Relação de pagamentos por fornecedor | Já é dado do módulo de pagamentos |
| **02 — Relatório de desempenho** | Seções de contratos de prestação de serviço, de parcerias com o terceiro setor e de doações e subvenções | Contratos de terceirização e parcerias, com aditivos e acompanhamento financeiro |

O par "valor inicial / valor final" do modelo 17 é o que amarra tudo: só sai certo se cada aditivo
e cada apostila estiverem registrados. O próprio anexo avisa que divergência entre o mapa e os
registros reais "pode indicar irregularidades graves".

**Não conferido:** os campos dos modelos 16 e 02 (só os títulos das seções) e os anexos da
Portaria 51/2026.

### 3.3 O piloto: o que Itaitinga já tem

Levantado em 2026-10-08, por fontes públicas. Nada aqui foi confirmado com a prefeitura.

- **Sistema contábil: ASPEC** (informado pelo Jorge). A fabricante é de Fortaleza e vende um
  conjunto: Contábil SIAFIC, Orçamento, PPA, **Licitação**, Almoxarifado, Patrimonial, Folha,
  Transparência, Protocolo e outros.
- **O Aspec Licitação já cobre o processo de contratação.** A página do produto descreve:
  cadastro de fornecedores e comissões, processos licitatórios e contratações diretas **com seus
  contratos e aditivos**, registro de preços, publicação no PNCP, processos de parceria com OSC,
  e exportação dos contratos para empenho no Aspec Contábil.
- **O que a página do produto não descreve** é o que vem depois da assinatura: fiscal designado,
  registro de ocorrências, medições, alertas de vigência, garantias, sanções. Também não há
  produto de convênios nem menção a API ou exportação de dados. Ausência em página de divulgação
  não prova ausência no sistema — é o primeiro item a confirmar com a prefeitura.
- **Itaitinga usa da ASPEC só a contabilidade e a execução da despesa** (informado pelo Jorge em
  2026-10-08). O Aspec Licitação **não** está em uso lá: o processo de contratação e a gestão de
  contratos estão fora da ASPEC.
- **Há estoque público de contratos.** O portal do município lista 1.019 contratos e aditivos de
  2013 a 2026, em 14 secretarias, com número, contratado, CNPJ, objeto, valor e vigência. O portal
  é de outro fornecedor (Assesi), não da ASPEC.
- **Regulamento da Lei 14.133: existe pelo menos um.** O **Decreto Municipal nº 010/2023**, de
  14/03/2023, regulamenta o § 3º do art. 8º — justamente a atuação de agente de contratação,
  equipe de apoio, comissão e **fiscais e gestores de contratos**. Está citado na Portaria
  026/2025, que designa os agentes de contratação. **O texto do decreto não foi localizado**; é
  ele que define as atribuições que a G2 precisa espelhar.
- **Regulamento da Lei 13.019: não localizado.** O município celebra termos de fomento citando
  diretamente o art. 16 da lei federal. Pode haver decreto que a busca não alcançou.

**O que isso muda no plano.** A dúvida era se a fatia G3 (processo de contratação completo)
reconstruiria algo que a prefeitura já opera no Aspec Licitação. Não reconstrói: Itaitinga não usa
esse módulo. **A decisão D2 fica como está**, e a fronteira com a ASPEC passa a ser nítida:

| Fica na ASPEC | Fica no módulo `contratos` |
|---|---|
| Orçamento e dotações | Processo de contratação (tabelas 501–507) |
| Empenho, liquidação, pagamento | Contrato, aditivo, apostila (511, 513) |
| Balancetes e demais arquivos contábeis do SIM | Fiscal, gestor, ocorrências, medições, recebimento |
| | Convênios e parcerias (807, 531–538) |

A costura entre os dois lados tem três pontos, e os três passam por **número**:

1. **Dotação.** O processo de contratação precisa indicar a dotação (tabela 507), e o orçamento é
   da ASPEC. Sem importação, a classificação é digitada — com validação de formato, não de saldo.
2. **Empenho.** A nota de empenho sai da ASPEC e carrega o número do contrato e do processo
   (tabela 601, campos 24 a 29). O número que o módulo gera tem de ser **exatamente** o que o
   contador digita no empenho, nos 15 caracteres do SIM.
3. **Saldo do contrato.** Empenhado, liquidado e pago são fatos da ASPEC. Para mostrar saldo por
   contrato (fatia G4) é preciso importar a execução ou digitá-la em dobro.

Ficou uma pergunta nova: **quem gera hoje os arquivos 501–513 do SIM de Itaitinga**, se a ASPEC
não tem o dado de licitação? Ou alguém digita esses dados no contábil só para a remessa, ou há
outro sistema na cadeia. A resposta diz contra o quê a fatia G6 confere — ver D10.

## 4. Diagnóstico — o que o sistema tem e o que falta

Conferido no código em 2026-10-08 (`backend/app/models/pagamentos.py`).

| Exigência | Hoje | Lacuna |
|---|---|---|
| Contrato: número, fornecedor, unidade, objeto, vigência, valor | Existe (`pagamentos.contrato`) | Número aceita 50 caracteres; o SIM aceita 15 e exige unicidade por exercício. |
| Data de celebração, gestor signatário | Não existe | — |
| Tipo de objeto (18 categorias do SIM) | Há `categoria`, mas é a da fila cronológica | São classificações diferentes; uma não substitui a outra. |
| Aditivos, apostilamentos, valor e vigência atualizados | Não existe | Sem isso não há controle do limite de 25% / 50%. |
| Fiscal e gestor do contrato, com portaria de designação | Não existe | — |
| Processo de contratação de origem | Não existe | O protocolo tem processos, mas sem vínculo. |
| Publicação no PNCP (Id, data, prazo) | Não existe | — |
| Garantia contratual | Não existe | — |
| Registro de ocorrências, medição, recebimento | Não existe | O atesto hoje é um booleano no débito (`liquidacao_confirmada`). |
| Sanções ao contratado | Não existe | O fornecedor tem situação cadastral e histórico — é um ponto de apoio. |
| Empenho vinculado ao contrato | Débito guarda `numero_ne` e `id_contrato` | Sem saldo empenhado × executado por contrato. |
| Ordem cronológica de pagamentos (art. 141) | **Existe** (fatia F3 de pagamentos) | — |
| Convênio recebido | Não existe | Há fonte de recursos e conta bancária, que são as pontas do vínculo. |
| Parceria com OSC | Não existe | — |
| Geração de arquivo do SIM | Não existe | — |

O que reaproveitamos: fornecedor, fonte de recursos, conta bancária, a fila cronológica, os
processos do protocolo (o processo administrativo de contratação **é** um processo), a assinatura
eletrônica, o workflow, as notificações, os anexos com sigilo e a trilha de auditoria.

## 5. Modelo de gestão

### 5.1 O ciclo de vida do contrato

| Etapa | O que acontece | Responsável | Evidência que fica | Prazo que o sistema vigia |
|---|---|---|---|---|
| 1. Origem | Processo de contratação concluído (homologado ou ratificado) | Agente de contratação | Processo no protocolo | — |
| 2. Formalização | Minuta, parecer jurídico, empenho, assinatura | Unidade + jurídico + ordenador | Contrato assinado, nota de empenho | — |
| 3. Publicidade | PNCP e portal da transparência | Setor de contratos | Id PNCP, data | **20 / 10 dias úteis** da assinatura |
| 4. Designação | Portaria de gestor e fiscal, com ciência | Autoridade competente | Portaria + termo de ciência | **Antes do início da execução** |
| 5. Garantia | Recebimento e guarda da garantia | Gestor do contrato | Apólice ou comprovante | Vencimento da garantia |
| 6. Execução | Ordens de serviço, ocorrências, medições | Fiscal | Registro de ocorrências | Periodicidade do contrato |
| 7. Recebimento | Provisório e definitivo; atesto | Fiscal / comissão | Termos de recebimento | Prazos do contrato |
| 8. Pagamento | Liquidação e fila cronológica | Financeiro | Já coberto pelo módulo de pagamentos | Vencimento |
| 9. Alteração | Aditivo, apostila, reajuste, reequilíbrio | Gestor + jurídico + ordenador | Termo aditivo, memória de cálculo | Limite legal; antes do fim da vigência |
| 10. Sanção | Notificação, defesa, decisão | Gestor + autoridade | Processo de responsabilização | Prazos de defesa |
| 11. Encerramento | Termo de encerramento, devolução da garantia | Gestor | Termo + avaliação do fornecedor | — |

A etapa 4 é a mais negligenciada e a que mais expõe o gestor: **contrato sem fiscal designado é
achado certo de auditoria**, e o SIM pede o CPF do fiscal no mês da assinatura.

### 5.2 Papéis e segregação de funções

Quem pede não fiscaliza sozinho; quem fiscaliza não paga; quem paga não atesta.

| Papel | Faz | Não pode acumular com |
|---|---|---|
| Requisitante | Define a necessidade | — |
| Agente de contratação | Conduz o processo | Fiscal do mesmo contrato |
| Gestor do contrato | Coordena, propõe aditivo e sanção, controla prazo e saldo | Ordenador da mesma despesa |
| Fiscal técnico / administrativo | Acompanha a execução, registra ocorrências, atesta | Quem paga |
| Ordenador de despesa | Autoriza empenho e pagamento | Fiscal |
| Jurídico | Parecer sobre minuta e aditivo | — |
| Controle interno | Amostra, audita, recomenda | Qualquer papel de execução |

Em município pequeno o acúmulo é às vezes inevitável. A regra então é: **o sistema não bloqueia,
mas exige justificativa registrada** e sinaliza no painel do controle interno.

### 5.3 Convênios — os dois ciclos

**Município como convenente (recebe).** Captação e proposta → celebração → conta específica e
contrapartida → execução (que gera contratos próprios, vinculados ao convênio) → prestação de
contas parcial e final no sistema do concedente (Transferegov ou e-Parcerias) → aprovação. O risco
central é a **inadimplência**: prestação de contas atrasada ou rejeitada bloqueia novas
transferências ao município inteiro.

**Município como concedente (repassa a OSC).** Chamamento público → plano de trabalho → celebração
→ liberação de parcelas → monitoramento pelo gestor da parceria e pela comissão → prestação de
contas pela OSC → análise e parecer do município → aprovação, ressalva ou rejeição. O risco central
é **liberar parcela nova sem ter analisado as contas da anterior**.

## 6. Calendário de obrigações

| Quando | Obrigação | Base |
|---|---|---|
| Até 10 dias úteis da assinatura | Publicar no PNCP — contratação direta, **contrato e cada aditivo** | Lei 14.133, art. 94 |
| Até 20 dias úteis da assinatura | Publicar no PNCP — licitação, **contrato e cada aditivo** | Lei 14.133, art. 94 |
| Até 25 dias úteis da assinatura (obra) | Divulgar quantitativos e preços contratados | Lei 14.133, art. 94, § 3º |
| Até 45 dias úteis da conclusão (obra) | Divulgar quantitativos executados e preços praticados | Lei 14.133, art. 94, § 3º |
| No início de cada exercício (contínuos) | Atestar crédito orçamentário e vantagem em manter o contrato | Lei 14.133, art. 106 |
| Antes de iniciar a execução | Designar gestor e fiscal | Lei 14.133, art. 117 |
| **Até o dia 30 de cada mês** | Remessa do SIM do mês anterior | Const. CE, art. 42; IN TCE-CE |
| 120, 90, 60 e 30 dias antes do fim da vigência | Decidir: prorrogar, licitar de novo ou encerrar | Boa prática — é o prazo real de uma nova licitação |
| A cada aditivo | Conferir o limite acumulado de 25% / 50% | Lei 14.133, art. 125 |
| No vencimento da garantia | Renovar ou exigir complemento | Lei 14.133, arts. 96–102 |
| Conforme o instrumento | Prestação de contas de convênio recebido | Instrumento + norma do concedente |
| Conforme a Lei 13.019 | Cobrar e analisar contas das OSCs | Lei 13.019 e regulamento municipal |
| **Até 31 de janeiro** | Último dia para corrigir o SIM do exercício anterior | Manual do SIM 2026, §4.6 |
| **Até 180 dias do fim do exercício** | Prestação de contas de gestão (PCS) pelo eContas | IN 01/2025, art. 5º |
| Até 180 dias da exoneração | PCS parcial do gestor que saiu | IN 01/2025, arts. 4º e 5º |
| Últimos 8 meses do mandato | Não contrair obrigação sem disponibilidade de caixa | LRF, art. 42 |

O prazo da prestação de contas de governo (PCG) **não foi conferido**.

## 7. Riscos e como o modelo responde

| Risco | Consequência | Resposta |
|---|---|---|
| Vigência vence sem decisão | Execução sem cobertura contratual; pagamento por indenização | Alertas escalonados ao gestor, com subida para o secretário |
| Aditivo acima do limite | Nulidade; responsabilização | Cálculo automático do acumulado sobre o valor inicial atualizado |
| Fiscal não designado ou sem ciência | Achado de auditoria; SIM incompleto | Contrato não muda para "em execução" sem fiscal com ciência registrada |
| Pagamento sem atesto do fiscal | Liquidação irregular | Liquidação no módulo de pagamentos passa a exigir o recebimento |
| PNCP fora do prazo | Contrato sem eficácia | Contagem em dias úteis desde a assinatura |
| SIM divergente da realidade | Inconsistência na prestação de contas | Arquivo gerado dos mesmos dados que sustentam o dia a dia |
| Convênio com contas em atraso | Município inadimplente | Calendário por convênio, com responsável nomeado |
| Parcela liberada a OSC com contas pendentes | Dano ao erário | Liberação condicionada à situação da parcela anterior |
| Fracionamento de despesa | Fuga de licitação | Painel de contratações diretas por objeto e fornecedor no exercício |
| Troca de gestão | Perda de memória | Tudo no sistema, com trilha de auditoria |

## 8. Indicadores para o gabinete

Poucos, e todos acionáveis:

- contratos vencendo em 30 / 60 / 90 / 120 dias, por secretaria;
- contratos **sem fiscal designado** — a meta é zero;
- percentual aditivado por contrato, com faixa de atenção a partir de 20%;
- contratos assinados e ainda não publicados no PNCP, com dias úteis restantes;
- saldo contratual × empenhado × liquidado × pago;
- convênios por situação: em execução, contas a prestar, contas em análise, inadimplente;
- pendências da remessa do SIM do mês, por unidade;
- concentração: os dez maiores fornecedores e sua fatia no total contratado.

## 9. Roteiro de implantação

Cada fatia entrega algo que um gestor usa sozinho, e nenhuma começa sem autorização.

Revisado em 2026-10-08, depois das decisões D1–D4 (seção 10): o módulo é próprio e o processo de
contratação entra **completo**, o que acrescentou a fatia G3 e a base de agentes públicos na G2.

| Fatia | Entrega | Depende de |
|---|---|---|
| **G0 — Escopo** | Decisões D5–D7; regulamentos municipais levantados; amostra real de contratos e de um processo licitatório de uma secretaria | Seção 10 |
| **G1 — Módulo e contrato** | Módulo `contratos` contratável; contrato com todos os campos da tabela 511; aditivos e apostilas como registros próprios; valor e vigência atualizados calculados; `pagamentos.contrato` passa a apontar para cá | G0 |
| **G2 — Pessoas e prazos** | Cadastro de agentes públicos (o subconjunto da tabela 951 que o SIM referencia por CPF); gestor e fiscal com portaria e ciência; alertas de vigência, garantia e PNCP — contrato **e** aditivo; painel do gabinete | G1 |
| **G3 — Contratações** | O processo completo das tabelas 501–507: espécie e modalidade, publicações, agente ou comissão de contratação e seus membros, licitantes, itens com valor estimado e proposto, dotações, homologação ou ratificação; contrato nasce do processo | G2 |
| **G4 — Execução** | Registro de ocorrências, medições, recebimento provisório e definitivo; liquidação do módulo de pagamentos exigindo o atesto; saldo por contrato | G2 |
| **G5 — Convênios** | Convênios recebidos (tabela 807) com calendário de prestação de contas; parcerias com OSC (tabelas 531–538) com liberação condicionada | G1 |
| **G6 — Tribunal (conferência)** | Relatórios no layout do SIM e do Mapa de Licitações (modelo 17) para a contabilidade conferir — **sem envio** | G1–G5 |
| **G7 — Sanções e desempenho** | Processo de responsabilização; avaliação do fornecedor; reflexo na situação cadastral | G4 |

Observações de ordem:

- **O contrato vem antes da licitação, e é de propósito.** A dor diária do gestor é vigência,
  aditivo e fiscal; e há estoque de contratos em vigor que precisa entrar sem processo de origem
  cadastrado. Por isso, na G1 o vínculo com o processo é opcional, e a G3 o torna obrigatório
  apenas para contrato novo.
- **G3 é a maior fatia do roteiro** — sozinha, do tamanho de um módulo de compras. Vale quebrá-la:
  primeiro contratação direta (dispensa e inexigibilidade, que são a maioria dos processos e as
  que mais geram achado por fracionamento), depois licitação com licitantes e itens.
- **Dotação é o ponto fraco da G3.** A tabela 507 pede a classificação orçamentária completa
  (órgão, unidade, função, subfunção, programa, projeto ou atividade, elemento, fonte), e o
  orçamento mora no sistema contábil do município, não aqui. Ou digitamos a classificação como
  texto validado por formato, ou importamos o orçamento. Não decidir isso às cegas: depende de
  D11.
- **G6 é conferência, não remessa** (decisão D3). O sistema contábil continua enviando; nós
  entregamos o que ele deveria estar enviando, para comparar. Gerar arquivo de envio só entra em
  pauta depois de sabermos qual é esse sistema e de um ciclo de conferência sem divergência.

## 10. Decisões que são do Jorge

**Decididas em 2026-10-08:**

| # | Decisão | Resposta |
|---|---|---|
| **D1** | Módulo novo ou extensão de `pagamentos`? | **Módulo novo contratável**, `contratos`. `pagamentos.contrato` evolui para ele. |
| **D2** | Quanto do processo de contratação entra? | **Processo completo** — tabelas 501–507. A recomendação era só o mínimo; a escolha amplia o escopo e criou a fatia G3. |
| **D3** | O que entregar em relação ao SIM? | **Conferência primeiro**: relatório no layout, sem envio. |
| **D4** | PNCP automático ou registro? | **Registro do Id e contagem de prazo**, para contrato e aditivo. |

Consequência de D1 que não é opcional: módulo novo significa transações novas declaradas em
`MODULO_TRANSACOES`, contratação inicial no `seed_bootstrap` e no `ci/seed-e2e.sql`, menu em
`frontend/lib/menus/`, telas sob `app/(app)/m/contratos/` e entrada em `ROTA_MODULO`. E há uma
dependência a desenhar com cuidado: `pagamentos` hoje é dono de `contrato` e de `fornecedor`. Um
município com `contratos` e sem `pagamentos` precisa de fornecedor — logo, fornecedor tende a
subir para o módulo novo ou para `comum`.

**Respondidas em 2026-10-08 (segunda rodada):**

| # | Decisão | Resposta |
|---|---|---|
| **D3-b** | Qual o sistema contábil? | **ASPEC.** Ver seção 3.3 — o que isso implica não é pequeno. |
| **D5** | Piloto? | **Itaitinga, o município inteiro** — todas as secretarias, não uma só. |
| **D6** | Há regulamento municipal? | Da 14.133, **sim em parte**: Decreto 010/2023, texto não localizado. Da 13.019, **não localizado**. |
| **D7** | Fiscal e gestor são usuários? | **Sim.** Cada um entra com o próprio login e registra as próprias ocorrências. |
| **D8** | Quais módulos ASPEC Itaitinga usa? | **Só contabilidade e execução da despesa.** Sem Aspec Licitação. |
| **D2-b** | Manter o processo de contratação completo? | **Sim, D2 mantida.** A dúvida era duplicar o Aspec Licitação; ele não está em uso. |

Consequência de D7: fiscal é usuário comum, não super-usuário. O módulo será o primeiro a
depender de verdade de grupo não-SU — o gate de permissão que hoje está inerte passa a valer, e a
leitura precisa ser concedida junto (`CLAUDE.md`, §Modularização). E o fiscal só deve ver os
contratos que fiscaliza: é um quinto eixo de acesso, além de tenant, módulo, permissão e sigilo.

**Em aberto:**

| # | Decisão | Por que importa |
|---|---|---|
| **D10** | Quem gera hoje os arquivos 501–513 do SIM de Itaitinga? | A ASPEC em uso lá não tem o dado de licitação. Saber quem digita, e onde, define contra o quê a G6 confere — e mostra o retrabalho que o módulo elimina. |
| **D11** | A ASPEC exporta orçamento e execução da despesa? | Sem exportação, dotação e saldo de contrato são digitados em dobro (seção 3.3). Com exportação, viram importação periódica. |
| **D9** | Carga inicial: os 1.019 contratos do portal entram? | Com o município inteiro como piloto, cadastrar o estoque à mão é inviável. Só os vigentes já reduz muito. |

## 11. O que este documento não é

Não é parecer jurídico. O enquadramento legal precisa passar pela procuradoria do município antes
de virar regra de sistema — em especial os limites de aditivo, as hipóteses de prorrogação e o
regulamento municipal, que variam com o caso concreto.

## 12. Fontes e limites

**Lido em 2026-10-08:**

- Manual do SIM 2026 — Municípios (TCE-CE), versão de março, 17,7 mil linhas de texto extraído:
  apresentação, §4.1–4.6, índice de arquivos (§5.2) e os layouts das tabelas 501, 511, 513, 537,
  538, 601 (grupos de campos) e 807.
  <https://www.tce.ce.gov.br/downloads/municipios/sim-documentacao-e-programas/Manual_SIM_2026_-_Municpios_vMAR-1.pdf>
- Lei 14.133/2021, texto compilado do Planalto — arts. 94, 106, 107, 111, 117, 125, 126, 136, 141,
  176, 184 e 184-A. <https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/L14133.htm>
- IN TCE-CE 01/2025 (versão atualizada pela Portaria 51/2026) — arts. 3º a 6º e 17.
  <https://www.tce.ce.gov.br/exercicios-anteriores/instrucoes-normativas>
- Anexo I da Portaria 615/2026 — sumário dos modelos e o quadro de campos do modelo 17.
  <https://www.tce.ce.gov.br/downloads/ANEXO_I_-_PORTARIA_615_2026_-_TEMPLATES_DE_XML_-_Modelos_1_a_20.pdf>
- eContas municipal: <https://www.tce.ce.gov.br/municipios/econtas>
- Portaria 51/2026 (notícia do TCE-CE):
  <https://www.tce.ce.gov.br/comunicacao/noticias/6879-portaria-do-tce-ceara-padroniza-informacoes-para-prestacao-de-contas-de-gestao-municipal>
- Portaria 615/2026 (notícia do TCE-CE):
  <https://www.tce.ce.gov.br/comunicacao/noticias/7158-tce-ceara-regulamenta-envio-de-dados-para-prestacao-de-contas-de-gestao-municipais-exercicio-2026>
- LC estadual 119/2012 e e-Parcerias (CGE-CE), por resultado de busca.
- Aspec Licitação e catálogo de produtos da ASPEC — páginas de divulgação, não manual.
  <https://aspec.com.br/produtos/aspec-licitacao/> · <https://aspec.com.br/produtos/>
- Diário Oficial de Itaitinga nº 1231/2025 (Portaria 026/2025, que cita o Decreto 010/2023).
  <https://itaitinga.ce.gov.br/diariooficial.php?id=1269>
- Portal de contratos de Itaitinga. <https://www.itaitinga.ce.gov.br/contratos.php?secr=13&pagina=2>

**Não lido, e por isso não afirmado:**

- o restante da IN 01/2025, as INs 02 e 03/2013, a Portaria 51/2026 e seus anexos, o texto da
  Portaria 615/2026 (o PDF é imagem, sem texto extraível) e o prazo da PCG;
- os campos dos modelos XML 16 e 02;
- das tabelas 502–507 do SIM, só a lista de campos — as regras e observações de cada uma ficam
  para o spec da G3; das 531–536, 901–903 e 951, só os nomes e a posição no índice;
- as **demais leis** da seção 2 (13.019, 4.320, LRF, LAI, LGPD, improbidade, anticorrupção, LINDB,
  decreto federal de convênios, legislação estadual): citadas de memória, a reconferir antes de
  virarem regra. Da Lei 14.133, os artigos **não** listados acima também vêm de memória;
- o **texto do Decreto Municipal 010/2023** de Itaitinga, e qualquer regulamento municipal da Lei
  13.019; os regulamentos de Sobral não foram pesquisados;
- o que o Aspec Licitação faz de fato, além do que a página de divulgação diz.

Uma ressalva sobre o índice de arquivos do manual: na extração de texto a coluna de nome de arquivo
saiu desalinhada das linhas. As siglas `CO` (511), `CT` (513), `PS` (537), `PD` (538), `LI` (501) e
`TF` (807) foram confirmadas no cabeçalho de cada layout; as demais foram inferidas pela sequência.
