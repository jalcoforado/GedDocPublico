# Cutover — aposentadoria do PHP

Checklist passo a passo para tirar o monolito PHP `aprimora/` do ar e deixar só o stack Python rodando em produção. Cada passo é reversível até o passo de "ponto de não retorno".

> A migração foi feita em modo **Strangler Fig**: o nginx em `:8090` já roteia cada URL para Python ou PHP conforme [nginx/default.conf](nginx/default.conf). O cutover é o último passo dessa migração.

## 0. Pré-requisitos antes de pensar em cutover

- [ ] Equipe de plantão (devs + suporte) reservada na janela
- [ ] Backup completo do PG `ged_saas_db` (`pg_dump -Fc`) **horas antes**
- [ ] Snapshot da pasta `uploads/anexos/` (arquivos físicos)
- [ ] Smoke Playwright passando (`docker compose --profile test run --rm e2e`)
- [ ] Pelo menos 1 semana de tráfego em produção com nginx Strangler ativo
- [ ] Logs do nginx revisados: zero ocorrências de erro 5xx vindas do Python nas últimas 48h
- [ ] Comunicação enviada aos usuários (janela + duração estimada)
- [ ] Plano de rollback escrito e ensaiado

## 1. Inventário das rotas ainda em PHP

```bash
# Em produção, depois de 1 semana de tráfego, ver o que o fallback `/` está servindo:
docker exec aprimora-py-nginx tail -10000 /var/log/nginx/access.log | \
  awk '$11 ~ /php-legacy/ {print $7}' | sort | uniq -c | sort -rn
```

Cada URL que aparecer com alta frequência precisa de uma das duas decisões:

- **Migrar para Python:** acrescentar o nome no token central da regex em [nginx/default.conf](nginx/default.conf) e implementar no Python.
- **Aposentar:** comunicar aos usuários que essa funcionalidade deixará de existir, com data.

Não dá pra fazer cutover enquanto a coluna "ainda em PHP com tráfego real" não estiver vazia (ou só com URLs aposentadas).

## 2. Trocar JWT para RS256 (corta interop com PHP)

Hoje o JWT é HS256, então tokens emitidos pelo Python eram aceitos pelo PHP. Após cutover, isso não é mais necessário — e RS256 é mais seguro.

```yaml
# docker-compose.yml — backend service
environment:
  JWT_ALGORITHM: RS256   # era HS256
```

Pré-requisito: arquivos `keys/jwt_private.pem` e `keys/jwt_public.pem` devem existir (ver [keys/README.md](keys/README.md)).

Validação aceita ambos os algoritmos, então tokens HS256 ainda válidos continuam funcionando até expirarem (3600s).

## 3. Forçar rehash bcrypt nos usuários ainda em MD5

Hoje cada usuário migra "sob demanda" no primeiro login Python. Antes do cutover, garantir que todos têm `senha_bcrypt` populado:

```sql
-- Quem ainda só tem MD5?
SELECT COUNT(*) FROM utils.usuario
 WHERE senha_bcrypt IS NULL AND excluido = false AND ativo = true;

SELECT COUNT(*) FROM utils.usuario_externo
 WHERE senha_bcrypt IS NULL AND excluido = false AND ativo = true;
```

Se sobrar muita gente sem `senha_bcrypt`:
- Esperar mais dias com PHP no ar (deixa o tráfego natural migrar).
- Ou avisar aos usuários "logue uma vez no novo sistema antes da data X".

Após o cutover, esses usuários **não conseguirão logar pelo PHP nem pelo Python** se a `senha` MD5 for invalidada (passo 6 abaixo).

## 4. Snapshot do estado antes de cortar

```bash
# Backup do banco (tag: pre-cutover-YYYYMMDD)
docker exec ged-saas-project-db-1 pg_dump -U ged_user -Fc ged_saas_db > backups/pre-cutover-$(date +%Y%m%d).dump

# Backup dos arquivos
tar czf backups/uploads-pre-cutover-$(date +%Y%m%d).tar.gz uploads/
```

## 5. Migrar fallback do nginx — para 404 em vez de PHP

Editar [nginx/default.conf](nginx/default.conf), trocar o bloco final:

```nginx
# ANTES (Strangler):
location / {
  set $backend "php-legacy";
  set $upstream_php "http://protocolo:80";
  proxy_pass $upstream_php;
}

# DEPOIS (cutover):
location / {
  set $backend "python-frontend";
  set $upstream_next "http://frontend:3000";
  proxy_pass $upstream_next;
}
```

Recarregar: `docker exec aprimora-py-nginx nginx -s reload`.

A partir daqui, **qualquer URL não capturada pela regex vai pro Next.js**, que retorna 404 se a rota não existe. O PHP `:8081` ainda está vivo (acessível direto), mas o nginx `:8090` não roteia mais nada pra ele.

**Janela de observação: 24-48h.** Se algo quebrou, basta reverter o `location /` ao bloco "php-legacy" e recarregar. Sem perda de dados — só roteamento.

## 6. Ponto de não retorno — invalidar MD5

Quando estiver confortável com a janela de observação:

```sql
-- Limpar a coluna senha (PHP perde capacidade de validar)
-- A partir daqui, ninguém consegue logar pelo PHP, mesmo direto.
UPDATE utils.usuario        SET senha = NULL;
UPDATE utils.usuario_externo SET senha = NULL;
```

**Esse passo é reversível só se você tiver o backup do passo 4.** Sem backup, senhas MD5 vão pro espaço.

## 7. Desligar containers PHP

```bash
# Parar o container Apache+PHP
docker stop aprimora-protocolo
docker rm aprimora-protocolo

# Remover do compose do projeto PHP (em c:\projetos\aprimora\)
# para não subir de novo por acidente.
```

Network `aprimora_default` pode permanecer — o backend Python continua usando ela pra falar com o PG. Mas o alias `protocolo` deixa de resolver, então é seguro remover o upstream `protocolo` do nginx:

```nginx
# default.conf — limpar referências obsoletas
# (remover: upstream php_legacy, resolver $upstream_php, fallback "php-legacy")
```

## 8. Pós-cutover

- [ ] Atualizar DNS / load balancer para apontar `aprimora.dominio` direto pra `:8090`
- [ ] Remover variável `JWT_SECRET_SOURCE=db` se não for mais necessária (era pra ler segredo legado)
- [ ] Apagar coluna `utils.usuario.senha` e `utils.usuario_externo.senha` em uma janela de manutenção futura (não junto com o cutover — espere ~30 dias estável):
  ```sql
  ALTER TABLE utils.usuario        DROP COLUMN senha;
  ALTER TABLE utils.usuario_externo DROP COLUMN senha;
  ```
- [ ] Decidir destino do código PHP: arquivo morto, arquivar repo, ou deletar (com versionamento histórico preservado).
- [ ] Reapontar backups automáticos pro novo padrão de pastas.
- [ ] Migrar `seed-*.sql` (dados de dev) para o que fizer sentido — fixtures pytest ou seed.py via Alembic. Schema já está em [backend/alembic/versions/](backend/alembic/versions/).

## Rollback de emergência

Cenário: aconteceu algo grave após o passo 5 (corte do fallback).

```bash
# 1. Reverter nginx para Strangler
git checkout HEAD~1 -- nginx/default.conf
docker exec aprimora-py-nginx nginx -s reload

# 2. Subir PHP de volta (se foi parado no passo 7)
cd c:/projetos/aprimora
docker compose up -d
```

Se já passou pelo passo 6 (MD5 zerado):

```bash
# 3. Restaurar backup do banco (perde alterações desde o snapshot)
docker exec -i ged-saas-project-db-1 pg_restore -U ged_user -d ged_saas_db -c \
  < backups/pre-cutover-YYYYMMDD.dump
```

## Riscos conhecidos

| Risco | Mitigação |
|---|---|
| Usuário não migrado tenta logar após corte | Forçar rehash via aviso antes do passo 5 (ver passo 3) |
| URL legada não inventariada quebra fluxo crítico | Janela de observação de 24-48h no passo 5; análise do access.log no passo 1 |
| JWT do PHP ainda em circulação após RS256 | Validação aceita ambos algos enquanto tokens não expiram (3600s) |
| Anexo físico apagado do disco antes do soft-delete sincronizar | Backup do `uploads/` no passo 4 |
| Triggers PG de auditoria param de receber `id_usuario` pq PHP setava via `SET LOCAL` | Confirmar que o Python já está propagando `id_usuario` no contexto da sessão antes do cutover (revisar `database.py`) |
