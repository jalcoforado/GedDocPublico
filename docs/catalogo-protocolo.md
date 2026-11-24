# Catálogo do Protocolo — tipos de processo e assuntos

> **Status:** vivo · **Autoridade sobre:** como tipo de processo e assunto se relacionam, o catálogo sugerido para demonstração e o que ele NÃO faz.
> **Última verificação:** 2026-11-21 (SI-54).
> Índice: [docs/INDEX.md](INDEX.md) · precedência: código > `CLAUDE.md` > este doc.

Fonte de verdade executável: `backend/app/cli/seed_catalogo_protocolo.py` e
`backend/tests/test_seed_catalogo_protocolo.py` (o seed),
`frontend/lib/catalogo-ativo.ts` e `frontend/__tests__/abertura-catalogo-ativo.test.tsx`
(o que a abertura oferece). Os dados estão em
`backend/app/cli/dados/catalogo_protocolo.json`.

## O modelo

- **Tipo de processo** (`protocolos.tipo_processo`) agrupa assuntos. Na
  abertura ele é opcional e **só filtra** a lista de assuntos.
- **Assunto** (`protocolos.assunto`) pertence a um tipo e pode ter assunto
  pai (hierarquia por tenant). **O processo guarda só o assunto**; o tipo de
  um processo é o tipo do assunto dele. Por isso mover um assunto de tipo
  muda o tipo de todos os processos já abertos com ele.
- Os dois são **por prefeitura** (tenant) e têm `ativo`: desativar tira da
  abertura sem apagar histórico.

Comparando com o SEI: o grupo do tipo de processo do SEI ("Pessoal",
"Licitação") corresponde ao nosso **tipo**; a especificação ("Férias",
"Pregão") corresponde ao nosso **assunto**.

## O catálogo sugerido (SI-54)

Pedido de 2026-11-17: enquanto a prefeitura não traz o levantamento dela,
cadastrar uma lista **sugerida por IA** de tipos e assuntos comuns em
prefeituras de pequeno e médio porte. São 19 tipos e 112 assuntos. **Não é
levantamento de prefeitura nenhuma** e não copia lista de órgão algum. O
campo `revisao_po` do JSON diz se o PO já revisou.

```bash
docker exec aprimora-py-backend python -m app.cli.seed_catalogo_protocolo apply --tenant sobral --allow-non-demo
```

O que o seed garante:

- **Só cria o que falta**, procurando pelo nome no tenant. Rodar de novo não
  duplica.
- **Não altera o que existe.** Não reativa, não renomeia e não move de tipo.
  O que o admin desativou continua desativado.
- **Assunto de mesmo nome sob outro tipo é conflito**: fica onde está e
  aparece no resumo do comando.
- O par "Solicitação" → "Demanda Cidadã", criado pelo `seed_demo`, fica
  intacto: processos e serviços da demonstração apontam para ele. A decisão
  é desativá-lo quando os assuntos novos cobrirem o uso.

## Limitações conhecidas

- **Teto de 200 assuntos na abertura.** O Novo processo e o Balcão carregam
  no máximo 200 (`frontend/lib/assuntos.ts`, teto do `GET /assuntos`), em
  ordem alfabética, e cortam o resto **sem aviso**. O seed avisa quando o
  tenant passa disso; o teste reprova o arquivo se ele passar de 180.
- **Tipo e assunto não carregam sigilo.** No SEI o nível de acesso é
  configurado no tipo de processo; aqui, não. Um PAD aberto com pressa nasce
  ostensivo. O JSON marca com `acesso_restrito_sugerido` o que o SEI costuma
  tratar como restrito, mas **nada lê essa marca**: ela é insumo para o card
  de sigilo por tipo e assunto.
- **Inativo sai da tela, não da API.** A abertura não oferece tipo nem
  assunto inativo (o já escolhido num rascunho continua aparecendo), mas o
  backend ainda aceita abrir processo com assunto inativo
  (`abertura_processo.conferir_referencias_do_tenant` confere só tenant e
  exclusão). Os filtros de Processos e dos Relatórios continuam listando os
  inativos, porque processo antigo tem aquele assunto.
- **"Documento obrigatório" não obriga.** O vínculo assunto ↔ tipo de anexo
  (`obrigatorio`/`opcional`) existe no cadastro, mas nem a abertura nem o
  backend o conferem. Por isso o catálogo sugerido não cadastra documentos.
- **A combinação assunto ativo + tipo inativo não tem regra.** O assunto
  continua sendo oferecido; nada decide ainda se desativar o tipo deveria
  esconder os assuntos dele.
- **Classificação arquivística (CCD) é outro cadastro.** O SEI pede a
  classificação por assunto do plano de classificação; aqui isso é o CCD
  (`protocolos.ccd_classe`), sugerido no Balcão a partir do assunto. O
  catálogo sugerido não o preenche.
