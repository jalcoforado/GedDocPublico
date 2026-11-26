# Conta Google — login e Google Docs (OAuth)

> **Status:** vivo · **Autoridade sobre:** setup do OAuth do Google — o login do servidor com a conta Google e a conexão do Google Docs para minutas.
> **Última verificação:** 2026-11-18 (SI-32).
> Índice: [docs/INDEX.md](INDEX.md) · precedência: código > `CLAUDE.md` > este doc.

A mesma credencial do Google (um Client ID + secret) liga duas coisas:

1. **Entrar com o Google** — na tela de login, o servidor municipal entra com a
   conta Google em vez de e-mail e senha. O Google só diz *quem é*; entra quem
   já é usuário **ativo desta prefeitura com aquele e-mail** (o Aprimora não
   cria conta a partir do Google). Escopos: `openid email profile`.
2. **Google Docs nas minutas** — o servidor redige uma minuta "em Google Docs".
   Cada usuário conecta a própria conta Google uma vez e, a partir daí, o
   Aprimora cria o documento no Drive dele e traz o texto de volta. Escopo:
   `drive.file`.

Sem a configuração abaixo as duas ficam **desligadas**, sem erro: o botão
"Entrar com o Google" não aparece, e na tela *Redigir documento* a opção Google
Docs aparece desabilitada com o aviso "ainda não foi configurada neste servidor".

## 1. Projeto no Google Cloud (uma vez)

Use um projeto **só do Aprimora** — o nome do app aparece na tela de permissão
que o servidor da Prefeitura vê ("**Aprimora** quer acessar sua Conta do
Google"). Não reaproveite projeto de outro produto.

1. [console.cloud.google.com](https://console.cloud.google.com/) → novo projeto `aprimora`.
2. **APIs e serviços → Biblioteca**: ative **Google Drive API** e **Google Docs API** (as minutas chamam as duas; o login não precisa de API nenhuma).
3. **Tela de consentimento OAuth** (no console novo: *Google Auth Platform*):
   - Tipo: **Externo**.
   - Nome do app: **Aprimora**. E-mail de suporte: uma caixa da equipe, não pessoal.
   - Escopos: `openid`, `.../auth/userinfo.email`, `.../auth/userinfo.profile` (login) e `https://www.googleapis.com/auth/drive.file` (minutas — o Aprimora enxerga apenas os arquivos que ele mesmo criar). Todos não sensíveis: não exigem a verificação completa do Google.
   - Status de publicação: **Em produção**. Em "Teste", só os usuários de teste listados conseguem entrar/conectar e a autorização expira em 7 dias — serve para testar em dev, com as contas da equipe listadas em *Público-alvo → Usuários de teste*.
4. **Credenciais → Criar credenciais → ID do cliente OAuth**:
   - Tipo: **Aplicativo da Web**. (Não "Desktop": esse tipo não aceita o endereço de retorno do servidor.)
   - Nome: `Aprimora web`.
   - **URIs de redirecionamento autorizados** — **dois por ambiente** (login e minutas), ver a seção 2.
   - *Origens JavaScript autorizadas*: deixe vazio — os dois fluxos rodam no servidor.
5. Guarde o **Client ID** e o **Client secret**. Eles vão só no `.env` do servidor — nunca no repositório (que é público), em chat aberto ou e-mail.

## 2. Os endereços de retorno (redirect URIs)

É o erro mais comum. Cada valor tem de ser:

- o endereço que o **navegador** usa para abrir o Aprimora (o nginx), **não** o backend direto. Os callbacks respondem com redirecionamentos relativos (`/login`, `/home`, `/minuta-error`, `/m/protocolo/processos/...`) que só existem no frontend; apontado para o `:8000`, o usuário volta do Google para uma página 404;
- **idêntico**, caractere por caractere, no Google Cloud e no `.env` (`http` × `https`, porta, barra no fim).

Cadastre os **dois** no Google Cloud:

| Ambiente | Minutas (`GOOGLE_OAUTH_REDIRECT_URI`) | Login (derivado — ver abaixo) |
|---|---|---|
| Dev (docker compose padrão) | `http://localhost:8090/api/v2/auth/google/callback` | `http://localhost:8090/api/v2/auth/google-login/callback` |
| Dev com outra porta no nginx | `http://localhost:<porta>/api/v2/auth/google/callback` | `http://localhost:<porta>/api/v2/auth/google-login/callback` |
| Servidor | `https://<domínio>/api/v2/auth/google/callback` | `https://<domínio>/api/v2/auth/google-login/callback` |

O do login **não precisa de variável**: o backend o deriva do
`GOOGLE_OAUTH_REDIRECT_URI` trocando `/auth/google/callback` por
`/auth/google-login/callback`. Só declare `GOOGLE_LOGIN_REDIRECT_URI` se ele
tiver de ser outro endereço.

⚠️ **O Google não aceita IP como endereço de retorno** (só `localhost`). O
servidor acessado por `http://103.230.142.69:8090` precisa de um **domínio com
https** antes de o login e a conexão funcionarem lá.

⚠️ **Um domínio por prefeitura = dois endereços por prefeitura.** O tenant vem
do `Host` (subdomínio). Em instalação com várias prefeituras, cada subdomínio
entra na lista de redirecionamentos do Google Cloud.

## 3. Variáveis de ambiente (`.env` do servidor)

```bash
GOOGLE_OAUTH_CLIENT_ID=<client id>.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=<client secret>
GOOGLE_OAUTH_REDIRECT_URI=<minutas, ver seção 2>
# Opcional — só se o retorno do login não for o derivado do de cima:
# GOOGLE_LOGIN_REDIRECT_URI=https://<domínio>/api/v2/auth/google-login/callback
```

As **minutas** também precisam da `DADOS_SENSIVEIS_ENCRYPTION_KEY` (a mesma que
cifra dados bancários) — sem ela o token não teria como ser gravado, e a
integração conta como desligada. O **login** não guarda token nenhum e não
depende dela.

Depois de mudar o `.env`: `docker compose up -d backend` (o `restart` não relê o
`env_file`). Valor vazio, ou o de exemplo (`YOUR_CLIENT_ID…`), deixa as duas
desligadas.

Os tokens das minutas ficam cifrados no banco (`aprimora_py.google_credencial`)
com a `DADOS_SENSIVEIS_ENCRYPTION_KEY` — trocar essa chave invalida as conexões
existentes (cada usuário conecta de novo).

## 4. Conferir

**Login**

1. `GET /api/v2/auth/google-login/disponivel` → `{"disponivel": true}`; a tela `/login` mostra **Entrar com o Google** abaixo dos botões Servidor/Solicitante.
2. Clicar → escolher a conta no Google → volta logado no Início (ou na tela que pedia login).
3. Com uma conta Google que não é de usuário da prefeitura: volta ao login com "Esta conta Google não é de um usuário desta prefeitura".

**Google Docs**

1. `GET /api/v2/auth/google/status` (logado) → `{"configurado": true, "conectado": false, ...}`.
2. Num processo: aba **Documentos** → **Redigir documento** → em *Onde redigir*, **Conectar agora** → **Conectar Conta Google**. A autorização abre numa **janela à parte**; a tela do processo não sai do lugar.
3. Ao autorizar, a janela se fecha sozinha e o diálogo de redigir (com o que já foi digitado) passa a **Google Docs**. `status` agora diz `"conectado": true`. Se o navegador bloquear a janela, a conexão segue na mesma aba, como antes.
4. Criar um documento em Google Docs abre o documento numa aba nova; **Sincronizar do Google Docs** traz o texto de volta.

## Erros e o que significam

### Login (`/login?google=<motivo>`)

A tela de login mostra a mensagem; o motivo exato vai para o log do backend (`google_login`).

| Motivo | Causa provável |
|---|---|
| `indisponivel` | Client ID/secret vazios (ou o valor de exemplo) no servidor. |
| `cancelado` | O usuário clicou em "Cancelar" no Google — ou o app está em "Teste" e ele não é usuário de teste. |
| `sem_conta` | Nenhum usuário **ativo** desta prefeitura com aquele e-mail. O Aprimora não cria conta a partir do Google: cadastre o servidor (com o e-mail da conta Google) em Usuários. |
| `nao_ativada` | O usuário existe mas o convite ainda não foi aceito (mesma regra do login por senha). |
| `email_nao_verificado` | A conta Google tem e-mail não confirmado no próprio Google. |
| `expirou` | Mais de 10 min na tela do Google, ou o cookie do navegador se perdeu (bloqueio de cookies). Tentar de novo. |
| `falhou` | Troca do código recusada. Quase sempre **redirect URI do login não cadastrado** no Google Cloud, ou credencial do tipo "Desktop". O corpo do erro do Google (`redirect_uri_mismatch`, `invalid_client`) vai para o log. |

### Google Docs (`/minuta-error?error=<código>`)

A tela mostra a mensagem e volta para o processo de onde a conexão partiu.

| Código | Causa provável |
|---|---|
| `google_nao_configurado` | Client ID/secret vazios (ou o valor de exemplo), ou sem `DADOS_SENSIVEIS_ENCRYPTION_KEY`, no servidor. |
| `access_denied` | O usuário clicou em "Cancelar" no Google — ou o app está em "Teste" e ele não é usuário de teste. |
| `state_expired` | Mais de 5 min na tela do Google, ou o Redis reiniciou no meio. Conectar de novo. |
| `conta_diferente` | O link de conexão foi aberto numa sessão de outro usuário. Nada é gravado. |
| `google_api_error` | Troca do código recusada. Quase sempre **redirect URI diferente** do cadastrado, ou credencial do tipo "Desktop". O motivo exato vai para o log do backend (`google_oauth`). |

## Limitação conhecida

O login com o Google **não pede o código por e-mail (2FA)**. Hoje não importa —
a conta por e-mail está desligada (`CONTA_POR_EMAIL=false`) —, mas precisa ser
revisto quando ela for ligada.

## Como funciona (referência)

**Login** — `backend/app/services/google_login.py` (regras) e `backend/app/routers/auth_google_login.py` (rotas). Mesmo desenho do login gov.br do cidadão:

- `GET /api/v2/auth/google-login/disponivel` — `{disponivel}`; a tela usa o `login_google` do `/branding/me`.
- `GET /api/v2/auth/google-login/inicio?next=/…` — grava `state` + `nonce` + `code_verifier` (PKCE) num cookie assinado e preso ao navegador, e manda ao Google com `prompt=select_account` (computador compartilhado na repartição).
- `GET /api/v2/auth/google-login/callback` — confere o cookie e o `state`, troca o código, valida o `id_token` (RS256 no JWKS do Google, `iss`/`aud`/`exp`/`nonce`/`at_hash`), exige `email_verified`, acha o usuário ativo do tenant pelo e-mail (sem caixa) e emite a mesma sessão do login por senha. A troca obrigatória de senha tem precedência sobre o `next`.

**Google Docs** — `backend/app/services/google_oauth_flow.py`, rotas em `backend/app/routers/auth.py`, documento em `backend/app/services/google_docs_service.py`:

- `GET /api/v2/auth/google/status` — `{configurado, conectado, conectado_em}` para a tela.
- `GET /api/v2/auth/google?minuta_id=X&processo_id=Y` — gera o `state` (Redis, 5 min, uso único) e manda para o Google. `minuta_id=0` = só conectar a conta. `popup=1` = a conexão foi aberta numa janela à parte: o callback termina em `/google-conectado`, que avisa a aba de origem por `BroadcastChannel` e se fecha (`frontend/lib/google-conexao.ts`).
- `GET /api/v2/auth/google/callback` — confere que o `state` é do mesmo usuário/tenant da sessão, troca o código por tokens (PKCE: o `code_verifier` guardado no `state`), cifra e grava; revoga a conexão anterior do usuário.
