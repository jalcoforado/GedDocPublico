# Matriz de claims — token de operador de plataforma

**Status:** normativo, proposto em `SEC-00` · **Data:** 2026-08-01
**Autoridade:** [ADR-016](../adr/ADR-016-platform-operator-identity.md)
**Consumido por:** `SEC-01A` (validador backend) e `SEC-01B` (console de operador)

Esta matriz é o contrato de validação. `SEC-01A` implementa exatamente estas linhas e cada uma vira um teste nomeado.

---

## 1. Claims do token de plataforma

| Claim | Obrigatório | Regra de validação | Ação se violado |
|---|---|---|---|
| `iss` | sim | igualdade exata com o issuer configurado do IdP administrativo | **deny** `401` |
| `aud` | sim | igualdade exata com o client ID **daquele ambiente**; se vier lista, o valor precisa estar contido | **deny** `401` |
| `azp` | quando presente | igual a `aud` | **deny** `401` |
| `exp` | sim | `agora < exp`, com tolerância de relógio de no máximo **60 s** | **deny** `401` |
| `iat` | sim | `iat <= agora + 60 s`; rejeitar token emitido no futuro | **deny** `401` |
| `nbf` | quando presente | `agora >= nbf - 60 s` | **deny** `401` |
| `sub` | sim | string não vazia; usado com `iss` como chave natural do principal | **deny** `401` |
| `hd` | sim | igual ao domínio corporativo aprovado (**D-2**) | **deny** `403` |
| `email_verified` | sim | precisa ser `true` | **deny** `403` |
| `email` | não | aceito **somente** como rótulo de exibição e para auditoria | nunca decide |
| `amr` / `acr` | ver ADR §2.5 | quando o IdP emitir de forma confiável, exigir fator forte | **deny** `403` |
| `alg` (header) | sim | `RS256`. `HS256`, `none` e qualquer simétrico são proibidos | **deny** `401` |
| `kid` (header) | sim | precisa resolver no JWKS em cache ou após um refresh com rate limit | **deny** `401` |

## 2. Claims que **provam** que o token não é de plataforma

A presença de qualquer um destes num token apresentado a uma rota de plataforma é **rejeição imediata**, não "ignorar o campo". Ignorar seria aceitar um token municipal cujo `iss`/`aud` tivessem sido configurados por engano com os valores de plataforma.

| Claim | Origem | Ação |
|---|---|---|
| `usuario_id` | `build_payload` municipal | **deny** `401` + alerta de confusão de token |
| `cidadao_id` | `build_cidadao_payload` | **deny** `401` + alerta |
| `tipo == "cidadao"` | portal do cidadão | **deny** `401` + alerta |
| `tenant_id` | token municipal | **deny** `401` + alerta |
| `conexao` | claim legado PHP | **deny** `401` + alerta |
| `app` | claim legado PHP | **deny** `401` + alerta |

O alerta importa: a presença desses claims aqui significa ou tentativa de ataque, ou erro de configuração que fundiu os realms. As duas merecem investigação.

## 3. Verificações além do token

Passar na matriz acima é **autenticação**. A autorização exige, em toda requisição:

| Verificação | Regra | Falha |
|---|---|---|
| Principal existe | `platform_principal` com `(issuer, subject)` do token | **deny** `403` |
| Principal ativo | `active = true`, não revogado | **deny** `403` |
| Vigência | `valid_from <= agora < valid_until` (quando houver `valid_until`) | **deny** `403` |
| Não vinculado a tenant | o principal **não** referencia `utils.usuario.id` nem e-mail municipal | erro de integridade — **deny** `500` + alerta |
| Tenant alvo explícito | operações cross-tenant recebem o tenant no payload, nunca do middleware/host | **deny** `400` |
| Papel de banco | conexão aberta com `aprimora_platform`, não com o pool municipal | erro de configuração — **deny** `500` |

Consulta ao principal é feita **a cada requisição**, sem cache de sessão. É isso que faz a revogação valer em minutos, e não em oito horas.

## 4. Matriz aceito × negado

Cada linha é um teste em `SEC-01A`.

| # | Cenário | Resultado |
|---|---|---|
| 1 | Token do IdP administrativo, `aud` do ambiente, `hd` correto, principal ativo | **allow** |
| 2 | Tudo correto, mas principal **inativo** | deny `403` |
| 3 | Tudo correto, mas principal **inexistente** | deny `403` |
| 4 | Token municipal válido (`iss`/`aud` de `jwt_iss`/`jwt_aud`) | deny `401` por `iss` |
| 5 | Token de cidadão válido | deny `401` por `iss` |
| 6 | Token administrativo de **outro ambiente** (`aud` de homolog usado em prod) | deny `401` por `aud` |
| 7 | Token com `alg: HS256` assinado com o segredo municipal | deny `401` por algoritmo |
| 8 | Token com `alg: none` | deny `401` |
| 9 | Token expirado por 61 s | deny `401` |
| 10 | Token com `iat` no futuro além da tolerância | deny `401` |
| 11 | `kid` desconhecido, JWKS refresh não resolve | deny `401` |
| 12 | JWKS indisponível e cache expirado | deny `503`, **nunca** allow |
| 13 | `hd` de outro domínio, principal existente | deny `403` |
| 14 | `email_verified: false` | deny `403` |
| 15 | Mesmo `sub`, **issuer diferente** | deny `403` — não é a mesma identidade |
| 16 | Token de plataforma apresentado a uma **rota municipal** | deny `401` pelo validador municipal |
| 17 | Cookie de operador enviado a API municipal | deny e não vaza sessão |
| 18 | Cookie municipal enviado ao console de operador | deny, árvore de operador não monta |
| 19 | Token válido, mas operação sem tenant alvo explícito | deny `400` |
| 20 | Principal em período de break-glass **expirado** | deny `403` |
| 21 | Usuário municipal com e-mail **idêntico** ao do operador, em qualquer tenant | deny — o e-mail não participa da decisão |
| 22 | Principal criado por endpoint municipal | impossível por construção; teste arquitetural falha o PR |

O cenário **21** é a regressão do achado F-01 e é o teste vermelho que abre `SEC-01A`.

## 5. O que a matriz deliberadamente não cobre

- **Autorização fina dentro da plataforma** (quem pode cancelar tenant vs. só listar). Hoje todo principal ativo tem as mesmas onze rotas. Segregar é trabalho posterior e deve virar item próprio.
- **Rate limiting e detecção de anomalia** no console. Recomendado, fora de `SEC-00`.
- **O realm municipal**, que continua com HS256, segredo compartilhado com o PHP e `iss`/`aud` iguais aos do cidadão. Ver Consequências no ADR-016.
