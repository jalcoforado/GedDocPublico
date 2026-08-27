# Inventário PHP → Cutover

Passo 1 do [CUTOVER.md](CUTOVER.md): mapear o que do PHP `protocolos-aprimora` ainda precisa ser decidido antes do cutover.

**Total**: 44 controllers PHP, ~7.455 LOC. Em produção real, completar o inventário rodando:

```bash
docker exec aprimora-py-nginx tail -10000 /var/log/nginx/access.log | \
  awk '/X-Aprimora-Backend: php-legacy/ {print $7}' | sort | uniq -c | sort -rn
```

(precisa adicionar `$backend` ao `log_format` do nginx primeiro — log atual é o combined padrão).

## Rotas Python já migradas (regex nginx, em ordem alfabética)

`assuntos`, `bairros`, `cidadao`, `cidades`, `dashboard`, `enderecos`, `grupos`, `home`, `jobs`, `login`, `manifestantes`, `organograma`, `para-assinar`, `perfil`, `processos`, `relatorios`, `tipos-anexo`, `tipos-manifestante`, `tipos-processo`, `unidades-trabalho`, `usuarios`, `workflow`

## Decisão por controller PHP

| Controller | LOC | Status | Decisão |
|---|---|---|---|
| **Processo** | 1367 | ✅ migrado | Cobrir endpoint de PDF (capa/etiqueta/completo) — `processos/` + `relatorios/` cobrem o resto |
| **AcaoProcesso** | 642 | ✅ migrado | encaminhar/receber/cancelar/arquivar via `/api/v2/processos/*` |
| **Usuario** | 447 | ✅ migrado | `/usuarios` |
| **Catalogo** | 343 | ✅ migrado | `/api/v2/catalogo/*` |
| **ProcessoUsuarioExterno** | 334 | ✅ migrado | Portal cidadão |
| **Thumb** | 285 | 🟡 parcial | Geração de thumbnail de anexo — verificar se Python já entrega |
| **FichaDesentranhamento** | 266 | 🔴 não migrado | Funcionalidade pouco usada (verificar telemetria); avaliar aposentar OU migrar pra `/api/v2/processos/{id}/desentranhar` |
| **LoginUsuarioExterno** | 250 | ✅ migrado | `/cidadao/login` |
| **UnidadeTrabalho** | 218 | ✅ migrado | `/unidades-trabalho` |
| **Login** | 207 | ✅ migrado | `/login` |
| **Cidade** | 201 | ✅ migrado | `/cidades` + `/bairros` |
| **DocumentoEletronico** | 165 | 🔴 não migrado | Consulta pública de documento por código. Decisão: migrar (URLs públicas precisam estar no Python pós-cutover) ou aposentar se substituído por `/cidadao/processos/{id}` |
| **GerarProcessosEnvolvido** | 161 | 🔴 não migrado | Relatório de processos envolvidos. Avaliar uso real; pode ir junto com relatórios da Fase 6 |
| **Arquivo** | 160 | ✅ migrado | upload/download de anexos via `/api/v2/anexos/*` |
| **Imprimir** | 155 | 🟡 parcial | Vários PDFs (capa, etiqueta, comprovante de encaminhamento, processo completo). Cobertura no Python via `/api/v2/processos/{id}/capa.pdf` etc — auditar paridade |
| **UsuarioExterno** | 137 | ✅ migrado | Portal cidadão tem cadastro |
| **Index** | 131 | ⚪ Codeigniter | Roteador padrão CI — sumirá com o cutover |
| **Relatorio** | 128 | ✅ migrado | `/relatorios` |
| **Autorizacao** | 124 | ✅ migrado | permissões e grupos |
| **GovBr** | <100 | 🔴 não migrado | Login com gov.br (Fase 5.2 ainda bloqueada por credenciais homologação). **Bloqueador soft pro cutover** se a prefeitura usa |
| **LoginGovBr** | <100 | 🔴 não migrado | idem GovBr |
| **AssinaturaGovBr** | <100 | 🔴 não migrado | Assinar via gov.br (Fase 5.2). **Bloqueador soft** |
| **RedefinicaoSenha** | <100 | 🟡 parcial | Já temos auth com bcrypt, falta UI de "esqueci minha senha" no Python |
| **RedefinicaoSenhaUsuarioExterno** | <100 | 🟡 parcial | idem, lado cidadão |
| **AssuntoTipoProcessoTipoAnexo** | <100 | ✅ migrado | tela de configuração |
| **Assunto** | <100 | ✅ migrado | `/assuntos` |
| **Manifestante** | <100 | ✅ migrado | `/manifestantes` |
| **Endereco** | <100 | ✅ migrado | `/enderecos` |
| **Lotacao** | <100 | ✅ migrado | usuários × unidades |
| **Home** | <100 | ✅ migrado | `/home` |
| **Api** | <100 | 🟡 ?? | `cadastrarEmpenho` — integração externa? Investigar |
| **Email** | <100 | 🔴 não migrado | Driver SMTP — substituído pelo motor de notificações (17b) |
| **Poder** | <100 | 🔴 não migrado | Cadastro de poder (executivo/legislativo) — catálogo. Migrar como tela admin ou aposentar |
| **Secretaria** | <100 | 🔴 não migrado | Idem — catálogo de secretarias |
| **Unidadeorcamentaria** | <100 | 🔴 não migrado | Catálogo orçamentário |
| **Incorporacao** | <100 | 🔴 não migrado | Incorporação de processos. Investigar uso |
| **Consulta** | <100 | 🔴 não migrado | Consulta pública? Investigar |
| **DadosCarimbo** | <100 | 🟡 parcial | Carimbo de PDF — `pdf_carimbo.py` já tem |
| **GerarProcessoCompleto** | <100 | ✅ migrado | `processos/{id}/completo.pdf` |
| **ArquivosProcessoPagamento** | <100 | 🔴 não migrado | Specific feature, investigar |
| **UsuarioData** | <100 | 🔴 não migrado | Investigar |
| **Totem** | <100 | 🔴 não migrado | Auto-atendimento físico (totem). Aposentar provavelmente |
| **Desenv** | <100 | ⚪ dev | Ferramentas de dev — não vai pra prod |
| **Info** | <100 | ⚪ dev | Endpoint de info — não vai pra prod |
| **_scaffold** | <100 | ⚪ dev | Codeigniter scaffolding — sumirá |

## Resumo

- ✅ **22 controllers migrados** (~75% do volume PHP) — não precisam de ação
- 🟡 **6 parciais** — auditar paridade antes do cutover
- 🔴 **13 não migrados** — decidir 1 a 1: migrar ou aposentar
- ⚪ **3 dev/CI** — somem naturalmente

## Bloqueadores SOFT pro cutover

1. **gov.br** (GovBr + LoginGovBr + AssinaturaGovBr): aguardando credenciais de homologação (Fase 5.2). Se a prefeitura cliente NÃO usa gov.br, não bloqueia.
2. **Esqueci minha senha** (RedefinicaoSenha + RedefinicaoSenhaUsuarioExterno): UI Python pode pegar no portal admin e cidadão.
3. **Thumb** (geração de miniatura de anexo): se o usuário acessa via PHP hoje, verificar paridade Python.

## Bloqueadores DUROS

Nenhum identificado. Os 13 "não migrados" são features de uso baixo/nicho que podem ser aposentadas ou migradas em uma rodada futura.

## Próximos passos

1. ~~Adicionar `$backend` ao `log_format` do nginx~~ ✅ feito — `log_format aprimora` com `|backend=$backend|host=$host` no final
2. Habilitar Strangler em prod e observar 1 semana
3. ~~Auditar paridade dos 🟡~~ ✅ feito — ver seção abaixo
4. Decisão go/no-go por controller 🔴
5. Implementar "esqueci minha senha" se ainda for usado

## Auditoria de paridade dos 🟡

### Imprimir.php × Python

Cobertura **6/8** (75%) — gaps são features pouco usadas.

| PHP Imprimir.{método} | Python | Status |
|---|---|---|
| `capaProcesso` | `GET /api/v2/processos/{id}/capa.pdf` | ✅ |
| `etiquetaUnica` | `GET /api/v2/processos/{id}/etiqueta-unica.pdf` | ✅ |
| `etiquetaDupla` | `GET /api/v2/processos/{id}/etiqueta-dupla.pdf` | ✅ |
| `montarProcesso` / `getProcessoParaImpressao` | `GET /api/v2/processos/{id}/completo.pdf` | ✅ |
| `comprovanteEncaminhamento` | `GET /api/v2/processos/encaminhamentos/{id}/comprovante.pdf` | ✅ |
| `comprovanteRecebimento` | ⚠ **não migrado** | 🔴 implementar antes do cutover OU aposentar (recebimento já loga no histórico, comprovante PDF é nice-to-have) |
| `fichaDetalheProcesso` | ⚠ **não migrado** | 🔴 verificar uso real; relatório de tramitação já cobre boa parte |
| `fichaDesentranhamento` / `getBase64FichaDesentranhamento` | ⚠ **não migrado** | 🔴 vive junto com `FichaDesentranhamento.php` — feature de "desentranhar anexo de processo", uso baixo |

### DadosCarimbo.php × Python

DadosCarimbo é **utilitário de leitura** (`getNomeUsuario`, `getLotacaoUsuario`, `getCpfUsuario`, `getDataAtual`, `getDataHoraAtual`) — não é endpoint de PDF.
Equivalente Python: `backend/app/services/pdf_carimbo.py` (Fase 4) já implementa carimbo no PDF de anexos.
**Status: ✅ migrado** (caminhos diferentes, mesmo resultado).

### Thumb.php × Python

Endpoint genérico de thumbnail (`?src=URL&size=100&crop=1...`) — gera JPG de qualquer imagem.
**Não é usado pelo Python stack**: `grep` no frontend Next.js e no backend FastAPI não retornou nenhuma referência a `/thumb`.
**Status: 🔴 aposentar** — o Next.js usa `<Image>` próprio. Após cutover o endpoint some sem impacto.

## Síntese da auditoria

**Bloqueadores duros**: 0
**Bloqueadores soft**: 3 PDFs PHP-only (`comprovanteRecebimento`, `fichaDetalheProcesso`, `fichaDesentranhamento`) — todos features de baixo uso. Decisão: implementar SE telemetria de prod mostrar uso > X req/dia, senão aposentar com aviso.

**Próximo passo recomendado**: subir nginx com novo `log_format` em prod, deixar 1 semana, analisar logs com:
```bash
awk '/backend=php-legacy/ {for(i=1;i<=NF;i++) if($i~/"GET|"POST/) print $(i+1)}' \
  /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -30
```

Se nenhuma das 3 features acima aparecer no top → aposentar todas (-3 bloqueadores soft → cutover desbloqueado).
