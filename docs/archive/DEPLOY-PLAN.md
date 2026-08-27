# 📋 Plano de Deploy — Aprimora-py

**Data**: 2026-07-24  
**Versão**: dee7a91 (RLS permissões fix)  
**Status**: Pronto para deploy  

---

## 📊 Resumo Executivo

### Mudanças Implementadas
- ✅ **Backend**: Fix de permissões com RLS context (SET LOCAL app.tenant_id)
- ✅ **Config**: Corrigido APP_NAME em docker-compose.yml (sistemas → aprimora)
- ✅ **Frontend**: Schema MeResponse atualizado com permissões
- ✅ **Auth**: Endpoint /auth/me retorna permissões corretamente

### Status de Testes
| Suite | Resultado | Detalhe |
|-------|-----------|---------|
| Permissões | ✅ 10/10 PASSED | Sistema funcionando |
| Crypto | ✅ 3/3 PASSED | Cifra OK |
| Frota | ⚠️ 7/16 (pre-existing DNS issues) | Não regressão |
| Auth | ⚠️ 1/3 (pre-existing fixtures) | Google OAuth fixtures |

### Risco
- 🟢 **BAIXO** — Mudanças isoladas a permissões/config
- 🟢 **REVERSÍVEL** — Simples git revert se necessário
- 🟢 **TESTADO** — Suite de permissões 100% pass

---

## 🚀 Opções de Deploy

### Opção 1: Deploy Manual (via SSH)
```bash
# No VPS
cd /app
git pull origin main
docker compose build backend frontend
docker compose up -d
sleep 10 && docker compose ps
curl http://localhost:8001/api/v2/auth/me
```

**Tempo**: ~5-10 min | **Risco**: Médio | **Facilidade**: Média

---

### Opção 2: Deploy via Script (RECOMENDADO)
```bash
# No VPS
cd /app
bash scripts/deploy.sh start  # Full deploy
# ou
bash scripts/deploy.sh quick  # Quick restart (sem rebuild)
```

**Tempo**: ~5-10 min | **Risco**: Baixo | **Facilidade**: Alta

---

### Opção 3: Deploy via GitHub Actions (AUTOMATIZADO)
1. Configure secrets no GitHub:
   - `VPS_HOST`: 103.230.142.69
   - `VPS_USER`: root
   - `VPS_PASSWORD`: Aprimora2026.
   - `VPS_PORT`: 22

2. Push para main ou dispare manualmente:
   ```bash
   git push origin main
   # GitHub Actions dispara automaticamente
   ```

**Tempo**: ~5-10 min | **Risco**: Muito baixo | **Facilidade**: Muito alta

---

## 📝 Checklist Pré-Deploy

- [ ] Código em main com commits dee7a91 ✓ (já feito)
- [ ] Testes de permissões passando ✓ (já feito)
- [ ] Backup do banco disponível (manual)
- [ ] VPS acesso verificado
- [ ] Docker/docker-compose disponível no VPS

---

## 🔍 Validação Pós-Deploy

```bash
# Health check automático (script faz isso)
curl http://localhost:8001/api/v2/auth/me

# Verificar permissões carregadas
curl http://localhost:8001/api/v2/auth/me | grep is_super_usuario

# Logs
docker compose logs -f backend | grep "permissoes\|auth"

# Testes (opcional)
docker compose exec backend pytest tests/test_permissoes_matriz.py -v
```

---

## 🔄 Plano Rollback

Se der problema:
```bash
cd /app
git revert dee7a91
docker compose build backend
docker compose up -d backend
```

---

## 📚 Próximos Passos

1. **Escolha método de deploy** (recomendo Opção 2 ou 3)
2. **Execute deploy**
3. **Valide /auth/me endpoint**
4. **Monitore logs** por 10-15 min
5. **Teste login** no frontend com admin user

---

## 📞 Suporte

Se houver erro:
1. Verifique `docker compose logs backend | tail -100`
2. Verifique conectividade com banco: `docker compose ps db`
3. Verifique arquivo config.py tem `APP_NAME: aprimora`
4. Reverter último commit se necessário

---

**Preparado por**: Claude Code  
**Risco Geral**: 🟢 BAIXO  
**Pronto para Deploy**: ✅ SIM
