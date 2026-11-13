# Google Docs — configurar a conexão (OAuth)

> **Status:** vivo · **Autoridade sobre:** setup do OAuth do Google Docs para minutas.
> **Última verificação:** 2026-11-13 (SI-32).
> Índice: [docs/INDEX.md](INDEX.md) · precedência: código > `CLAUDE.md` > este doc.

Para que serve: o servidor redige uma minuta "em Google Docs". Cada usuário
conecta a própria conta Google uma vez (tela de consentimento do Google) e, a
partir daí, o Aprimora cria o documento no Drive dele e traz o texto de volta.

Sem a configuração abaixo a integração fica **desligada**: na tela *Redigir
documento* a opção Google Docs aparece desabilitada com o aviso "ainda não foi
configurada neste servidor" — não há botão que leve a erro.

## 1. Projeto no Google Cloud (uma vez)

Use um projeto **só do Aprimora** — o nome do app aparece na tela de permissão
que o servidor da Prefeitura vê ("**Aprimora** quer acessar sua Conta do
Google"). Não reaproveite projeto de outro produto.

1. [console.cloud.google.com](https://console.cloud.google.com/) → novo projeto `aprimora`.
2. **APIs e serviços → Biblioteca**: ative **Google Drive API** e **Google Docs API** (o código chama as duas).
3. **Tela de consentimento OAuth**:
   - Tipo: **Externo**.
   - Nome do app: **Aprimora**. E-mail de suporte: uma caixa da equipe, não pessoal.
   - Escopo: só `https://www.googleapis.com/auth/drive.file` — o Aprimora enxerga apenas os arquivos que ele mesmo criar. É escopo não sensível: não exige a verificação completa do Google.
   - Status de publicação: **Em produção**. Em "Teste", só os usuários de teste listados conseguem conectar e a autorização expira em 7 dias.
4. **Credenciais → Criar credenciais → ID do cliente OAuth**:
   - Tipo: **Aplicativo da Web**. (Não "Desktop": esse tipo não aceita o endereço de retorno do servidor.)
   - Nome: `Aprimora web`.
   - **URIs de redirecionamento autorizados** — um por ambiente, ver a seção 2.
5. Guarde o **Client ID** e o **Client secret**. Eles vão só no `.env` do servidor — nunca em chat aberto, e-mail ou git.

## 2. O endereço de retorno (redirect URI)

É o erro mais comum. O valor tem de ser:

- o endereço que o **navegador** usa para abrir o Aprimora (o nginx), **não** o backend direto. O callback responde com redirecionamentos relativos (`/minuta-error`, `/m/protocolo/processos/...`) que só existem no frontend; apontado para o `:8000`, o usuário volta do Google para uma página 404;
- **idêntico**, caractere por caractere, no Google Cloud e no `.env` (`http` × `https`, porta, barra no fim).

| Ambiente | `GOOGLE_OAUTH_REDIRECT_URI` |
|---|---|
| Dev (docker compose padrão) | `http://localhost:8090/api/v2/auth/google/callback` |
| Dev com outra porta no nginx | `http://localhost:<porta>/api/v2/auth/google/callback` |
| Servidor | `https://<domínio do Aprimora>/api/v2/auth/google/callback` |

⚠️ **O Google não aceita IP como endereço de retorno** (só `localhost`). O
servidor acessado por `http://103.230.142.69:8090` precisa de um **domínio com
https** antes de a conexão funcionar lá.

## 3. Variáveis de ambiente (`backend/.env`)

```bash
GOOGLE_OAUTH_CLIENT_ID=<client id>.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=<client secret>
GOOGLE_OAUTH_REDIRECT_URI=<ver seção 2>
```

A conexão também precisa da `DADOS_SENSIVEIS_ENCRYPTION_KEY` (a mesma que cifra
dados bancários) — sem ela, o token não teria como ser gravado, e a integração
conta como desligada.

Depois de mudar o `.env`: `docker compose up -d backend` (o `restart` não relê o
`env_file`). Valor vazio, ou o de exemplo (`YOUR_CLIENT_ID…`), deixa a
integração desligada.

Os tokens de cada usuário ficam cifrados no banco (`aprimora_py.google_credencial`)
com a `DADOS_SENSIVEIS_ENCRYPTION_KEY` — trocar essa chave invalida as conexões existentes
(cada usuário conecta de novo).

## 4. Conferir

1. `GET /api/v2/auth/google/status` (logado) → `{"configurado": true, "conectado": false, ...}`.
2. Num processo: aba **Documentos** → **Redigir documento** → em *Plataforma de redação*, **Conectar agora** → autorizar no Google.
3. Volta para o mesmo processo; reabrindo *Redigir documento*, a opção **Google Docs** está habilitada. `status` agora diz `"conectado": true`.
4. Criar um documento em Google Docs abre o documento numa aba nova; **Sincronizar do Google Docs** traz o texto de volta.

## Erros e o que significam

A tela `/minuta-error` mostra a mensagem e volta para o processo de onde a conexão partiu.

| Código | Causa provável |
|---|---|
| `google_nao_configurado` | Client ID/secret vazios (ou o valor de exemplo), ou sem `DADOS_SENSIVEIS_ENCRYPTION_KEY`, no servidor. |
| `access_denied` | O usuário clicou em "Cancelar" no Google — ou o app está em "Teste" e ele não é usuário de teste. |
| `state_expired` | Mais de 5 min na tela do Google, ou o Redis reiniciou no meio. Conectar de novo. |
| `conta_diferente` | O link de conexão foi aberto numa sessão de outro usuário. Nada é gravado. |
| `google_api_error` | Troca do código recusada. Quase sempre **redirect URI diferente** do cadastrado, ou credencial do tipo "Desktop". O motivo exato vai para o log do backend (`google_oauth`). |

## Como funciona (referência)

- `GET /api/v2/auth/google/status` — `{configurado, conectado, conectado_em}` para a tela.
- `GET /api/v2/auth/google?minuta_id=X&processo_id=Y` — gera o `state` (Redis, 5 min, uso único) e manda para o Google. `minuta_id=0` = só conectar a conta.
- `GET /api/v2/auth/google/callback` — confere que o `state` é do mesmo usuário/tenant da sessão, troca o código por tokens (PKCE: o `code_verifier` guardado no `state`), cifra e grava; revoga a conexão anterior do usuário.
- Código: `backend/app/services/google_oauth_flow.py`, rotas em `backend/app/routers/auth.py`, documento em `backend/app/services/google_docs_service.py`.
