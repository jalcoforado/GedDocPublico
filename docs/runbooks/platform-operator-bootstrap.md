# Runbook — bootstrap e operação do operador de plataforma

**Status:** aprovado em `SEC-00` (2026-08-01), executável a partir de `SEC-01A` · **Data:** 2026-08-01
**Autoridade:** [ADR-016](../architecture/adr/ADR-016-platform-operator-identity.md) — status **Aceito**

> **Nenhum procedimento deste runbook é executável hoje.** `platform_principal`, o validador de token administrativo e a CLI citada nascem em `SEC-01A`. O documento existe para ser revisado junto com o ADR — se um procedimento aqui for impraticável, a decisão arquitetural precisa mudar antes de virar código.

**Regra que atravessa tudo:** nenhum segredo, chave privada, client secret ou lista real de operadores entra no repositório. O que é identificador de ambiente vai para variável de ambiente; o que é segredo vai para o cofre.

---

## 1. Pré-requisitos, uma única vez por ambiente

| # | Item | Responsável | Evidência |
|---|---|---|---|
| 1 | Grupo de operadores criado no Workspace, com 2FA obrigatória e fator forte (chave de segurança ou TOTP; **SMS não**) | Administrador do Workspace | print da política do grupo, arquivado fora do repo |
| 2 | OAuth client **dedicado** ao console, um por ambiente (dev, homologação, produção) | Administrador do Workspace | Client ID por ambiente |
| 3 | Redirect URI do console registrada, por ambiente | Administrador do Workspace | URI registrada |
| 4 | Papel `aprimora_platform` criado no Postgres, `NOBYPASSRLS`, com grants mínimos | Migration de `SEC-01A` | migration aplicada |
| 5 | Variáveis de ambiente publicadas no host | Operação | `printenv` sem valores no log |
| 6 | Client secret no cofre, nunca no repositório nem no compose versionado | Operação | referência do cofre |

### Variáveis por ambiente

```
PLATFORM_OIDC_ISSUER=https://accounts.google.com
PLATFORM_OIDC_AUDIENCE=<client id do ambiente>
PLATFORM_OIDC_JWKS_URL=https://www.googleapis.com/oauth2/v3/certs
PLATFORM_OIDC_HOSTED_DOMAIN=<dominio corporativo — obrigatorio, nunca no codigo>
PLATFORM_CONSOLE_ORIGIN=<origem do console — obrigatorio, define cookie/CORS/CSP>
PLATFORM_DB_URL=postgresql+asyncpg://aprimora_platform:<cofre>@<host>/<db>
```

`PLATFORM_OIDC_HOSTED_DOMAIN` **não tem default** (D-2). Ausente ou vazia em ambiente que não seja de teste, a fronteira de plataforma nega tudo e a inicialização registra erro de configuração. Um default embutido converteria esquecimento em porta aberta — que é exatamente o modo de falha de `PLATFORM_ADMIN_EMAILS`.

`PLATFORM_CONSOLE_ORIGIN` existe porque o console vai para **origem própria** (Q-3). O domínio definitivo é configuração; nada de host fixo no código, no nginx versionado ou no bundle.

Os segredos ficam, por ora, em **variáveis de ambiente protegidas no host** (Q-4). Cofre de segredos é migração futura registrada na seção 10 — não bloqueia `SEC-01A`.

`PLATFORM_ADMIN_EMAILS` é **removida** em `SEC-01A`. Enquanto existir, é caminho de autorização ativo — ver T-1 do threat model.

### 1.1 Verificar `PLATFORM_ADMIN_EMAILS` sem expor os e-mails

O valor em homologação é desconhecido (Q-1) e precisa ser tratado como **potencialmente preenchido**. A verificação diz **se existe** e **quantos** — nunca quais. Colocar a lista num log é criar uma segunda cópia do alvo de F-01:

```bash
docker exec aprimora-py-backend python -c "import os,sys; v=os.getenv('PLATFORM_ADMIN_EMAILS','').strip(); n=len([e for e in v.split(',') if e.strip()]); print(f'PLATFORM_ADMIN_EMAILS: {\"presente\" if n else \"vazia\"} ({n} entradas)'); sys.exit(1 if n else 0)"
```

Saída `presente (N entradas)` significa que o caminho de F-01 está **ativo naquele ambiente**: qualquer tenant capaz de criar usuário com um desses e-mails alcança operação cross-tenant. Registrar a contagem e a data no controle de mudanças, tratar como incidente aberto até `SEC-01A` chegar ao ambiente, e **não** copiar o valor para ticket, chat ou este runbook.

---

## 2. Bootstrap do primeiro operador

O primeiro principal não pode nascer por HTTP: não há ninguém autorizado ainda, e um endpoint que crie o primeiro operador é um endpoint que cria o segundo.

**Pré-condição:** duas pessoas do grupo de operadores presentes. Uma executa, a outra testemunha e assina o registro.

1. A pessoa a ser cadastrada faz login no console. A tentativa **falha com 403** — autenticada no IdP, sem principal. Isso é o esperado.
2. Colher `iss` e `sub` do log estruturado da tentativa negada. **Não** usar o e-mail para identificar o principal; ele serve só de rótulo.
3. No host, com acesso SSH e fora de qualquer API:

   ```bash
   docker exec aprimora-py-backend python -m app.cli.platform_principal criar \
     --issuer "<iss>" --subject "<sub>" \
     --display-label "<e-mail, apenas rótulo>" \
     --reason "bootstrap inicial — <ticket>" \
     --approved-by "<quem testemunhou>"
   ```

4. Repetir o login. Deve funcionar.
5. Registrar no controle de mudanças: quem, quando, motivo, testemunha, `(iss, sub)` — nunca o token.

**Se o passo 3 falhar por o papel `aprimora_platform` não existir:** a migration de `SEC-01A` não foi aplicada. Parar e aplicar; não contornar com `ged_user`.

---

## 3. Conceder acesso a um novo operador

Mesmo fluxo do bootstrap, com duas diferenças: quem aprova é um operador já ativo, e a entrada no grupo do Workspace vem antes.

1. Incluir a pessoa no grupo de operadores do Workspace e confirmar a 2FA ativa.
2. Login → 403 esperado → colher `(iss, sub)` do log.
3. `platform_principal criar` com `--reason` e `--approved-by` preenchidos.
4. Confirmar acesso e registrar.

**Nunca** conceder acesso apenas adicionando ao grupo do Workspace: o grupo autentica, o principal autoriza. Os dois são necessários.

---

## 4. Revogar acesso

**Imediato** — o principal é consultado a cada requisição:

```bash
docker exec aprimora-py-backend python -m app.cli.platform_principal revogar \
  --issuer "<iss>" --subject "<sub>" \
  --reason "<motivo>" --revoked-by "<quem>"
```

Fazer **nesta ordem**:

1. revogar o principal — corta o acesso já emitido;
2. remover do grupo do Workspace — corta a renovação;
3. em desligamento, suspender a conta.

Inverter a ordem deixa uma janela de até 15 minutos com o access token ainda válido.

**Verificação obrigatória:** tentar uma operação com a sessão da pessoa revogada e confirmar 403.

---

## 5. Break-glass

**Quando:** o IdP está indisponível **e** há incidente que exige operação cross-tenant. Indisponibilidade sem incidente não justifica — o console ficar fora do ar é o comportamento projetado.

**Nunca:** por conveniência, pressa ou para contornar 403 que você não entendeu.

### Procedimento

1. **Dupla aprovação.** Duas pessoas distintas do grupo, nominalmente registradas. Quem executa não pode ser a única aprovadora.
2. **Ativação**, no host:

   ```bash
   docker exec aprimora-py-backend python -m app.cli.platform_principal break-glass \
     --principal "<id do principal de emergência>" \
     --minutes 60 \
     --reason "<incidente>" \
     --approved-by "<pessoa 1>" --approved-by "<pessoa 2>"
   ```

3. **Prazo:** 60 minutos, expiração gravada no registro. **Não renovável** — um segundo período exige nova dupla aprovação e novo registro.
4. **Durante:** cada operação gera evento com os dois aprovadores, motivo e correlation ID. Alerta imediato no canal de operação.
5. **Encerramento:** expira sozinho. Encerrar antes com `break-glass encerrar` assim que o incidente permitir.
6. **Pós-uso:** revisão em até 48 h — o que foi feito, se era necessário, se o IdP voltou, o que evita a próxima. Registrar aqui.

### Registro de usos

| Data | Incidente | Aprovador 1 | Aprovador 2 | Duração | Revisado em |
|---|---|---|---|---|---|
| _(vazio)_ | | | | | |

---

## 6. Rotação de chaves e JWKS

As chaves de assinatura são do Google e rotacionam sozinhas — não temos chave privada de plataforma para guardar. Nossa responsabilidade é o cache:

- respeitar o `Cache-Control` do endpoint JWKS, com teto de 24 h;
- `kid` desconhecido dispara **uma** tentativa de refresh, com rate limit para não virar amplificador;
- refresh falhando com cache expirado → **deny `503`**, nunca allow.

**Rotação do client secret** (fluxo de refresh): criar o novo secret no Workspace, publicar no cofre, recarregar o serviço, confirmar login, só então revogar o antigo. Nunca revogar antes de confirmar.

---

## 7. Indisponibilidade do IdP

**Sintoma:** todas as rotas de plataforma respondem `503`; login no console falha.

**Isto é o comportamento correto.** Não existe procedimento para "liberar temporariamente".

1. Confirmar que é o IdP: `curl` no JWKS a partir do host.
2. Confirmar que o app municipal **não** foi afetado — ele usa outro realm. Se caiu junto, o problema é outro e os realms podem não estar tão separados quanto o ADR exige: **isso é um achado de segurança**.
3. Comunicar a indisponibilidade do console.
4. Se houver incidente que exija operação cross-tenant, seguir o break-glass (seção 5).
5. Registrar duração e impacto.

**O que não fazer:** desativar a validação, aceitar HS256, reativar `PLATFORM_ADMIN_EMAILS` ou apontar a rota de plataforma para o pool municipal.

---

## 8. Ambiente local e de teste

Local **não** usa o Google. A suíte gera um par RSA em memória a cada execução e serve um JWKS fictício — `backend/tests/fixtures/platform_operator_tokens.py`.

```
PLATFORM_OIDC_ISSUER=https://operator.test.local
PLATFORM_OIDC_AUDIENCE=aprimora-operator-test
PLATFORM_OIDC_HOSTED_DOMAIN=test.local
```

Duas propriedades travadas por teste: token municipal é rejeitado pelo validador de plataforma, e token de plataforma é rejeitado pelo validador municipal.

**Nunca** apontar o ambiente local para o client de produção, e nunca copiar um token de produção para depurar local.

---

## 9. Revisão trimestral

| # | Item | Ação se divergir |
|---|---|---|
| 1 | Todo principal ativo corresponde a alguém ainda no grupo do Workspace | revogar o órfão |
| 2 | Todo membro do grupo que não opera mais foi removido | remover |
| 3 | 2FA com fator forte ativa em todas as contas do grupo | corrigir ou remover do grupo |
| 4 | Nenhum break-glass usado sem revisão registrada | revisar retroativamente e apurar |
| 5 | Nenhum segredo apareceu no repositório | rotacionar imediatamente e apurar |
| 6 | `PLATFORM_ADMIN_EMAILS` não existe em nenhum ambiente | remover; enquanto existir, é caminho ativo (T-1) |

Registrar data, quem revisou e divergências encontradas.

---

## 10. Pendências deste runbook

- A CLI `app.cli.platform_principal` **não existe**; nasce em `SEC-01A`. Os comandos aqui são o contrato que ela deve cumprir. **Nenhum operador real vai para código ou seed** (Q-2): a lista de principals é construída por esta CLI, ambiente a ambiente, e o grupo autorizado é configuração.
- **Migração para cofre de segredos** (Q-4): decidido usar variável de ambiente protegida no host por ora. Fica registrada como trabalho futuro e **não bloqueia** `SEC-01A`. Ao adotar cofre, o único procedimento que muda é o da seção 6.
- O host definitivo do console (Q-3) ainda não foi escolhido, mas a decisão de **ter origem própria** está tomada: `PLATFORM_CONSOLE_ORIGIN` é o ponto único de configuração de cookie scope, CORS, CSP e nginx. Nada de domínio fixo no código.
- `PLATFORM_ADMIN_EMAILS` em homologação continua **não verificada** (Q-1). Usar a verificação da seção 1.1 — a que conta sem revelar — assim que houver acesso ao host, e registrar apenas a contagem.
