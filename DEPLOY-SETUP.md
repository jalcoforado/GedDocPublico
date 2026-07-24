# 🔧 Setup Deploy Automatizado

## Opção 1: Script Manual (Mais Controle)

### No seu computador:
```bash
# Copiar script para servidor via SSH
sshpass -p "Aprimora2026." scp -r scripts/ root@103.230.142.69:/app/

# Executar no servidor (via SSH ou console VPS)
ssh root@103.230.142.69
cd /app
chmod +x scripts/deploy.sh
bash scripts/deploy.sh start
```

### Ou no console da VPS (Virtualizor):
1. Acesse: https://103.230.142.69:4443 (ou seu provider)
2. Vá até Console/Terminal
3. Cole:
```bash
cd /app
git pull origin main
docker compose build backend frontend
docker compose up -d
```

---

## Opção 2: GitHub Actions (Recomendado - Automático)

### Passo 1: Configure Secrets no GitHub

1. Vá para: https://github.com/jalcoforado/GedDocPublico/settings/secrets/actions
2. Clique em "New repository secret"
3. Adicione estes 3 secrets:

**Secret 1:**
- Name: `VPS_HOST`
- Value: `103.230.142.69`

**Secret 2:**
- Name: `VPS_USER`
- Value: `root`

**Secret 3:**
- Name: `VPS_PASSWORD`
- Value: `Aprimora2026.`

**Secret 4 (opcional):**
- Name: `VPS_PORT`
- Value: `22`

### Passo 2: Dispare Deploy

**Automático** (próximo push para main):
```bash
git push origin main
# GitHub Actions dispara automaticamente
```

**Manual** (via UI):
1. Vá para: https://github.com/jalcoforado/GedDocPublico/actions
2. Selecione workflow: "Deploy to VPS"
3. Clique em "Run workflow"
4. Escolha deploy type: `full` ou `quick`
5. Clique em "Run workflow"

**Verificar status:**
- Workflow rodando: https://github.com/jalcoforado/GedDocPublico/actions
- Clique no run mais recente
- Veja logs em tempo real

---

## Monitoramento Pós-Deploy

### Verificar saúde do servidor (via curl):
```bash
# Backend respondendo
curl -s http://103.230.142.69:8001/api/v2/auth/me | python -m json.tool

# Frontend respondendo
curl -s http://103.230.142.69:8090 | head -c 100

# Logs backend
ssh root@103.230.142.69 "docker compose logs -n 50 backend"
```

### Ou via console VPS:
```bash
docker compose ps
docker compose logs --tail=100 backend
curl http://localhost:8001/api/v2/auth/me
```

---

## Troubleshooting

### Erro: "Permission denied (publickey,password)"
→ Senha incorreta ou SSH desabilitado
→ Verifique credenciais no console da VPS

### Erro: "docker: command not found"
→ Docker não instalado no VPS
→ Execute: `apt-get install -y docker.io docker-compose`

### Erro: "git: not a git repository"
→ Clone o repo manualmente: `git clone https://github.com/jalcoforado/GedDocPublico.git /app`

### Erro: "EADDRINUSE: Port 8001 already in use"
→ Outra aplicação usando porta
→ Mude porta em docker-compose.yml ou mate processo: `docker compose down`

### Permissões erradas após deploy
→ Verificar config.py tem `APP_NAME: aprimora` ✓
→ Verificar docker-compose.yml tem `APP_NAME: aprimora` ✓
→ Restart backend: `docker compose restart backend`

---

## Rollback Rápido

Se algo der errado:
```bash
cd /app
git reset --hard HEAD~1  # Volta ao commit anterior
docker compose build backend
docker compose up -d
```

---

## Dicas

✅ **Backup** antes: `BACKUP_DB=1 bash scripts/deploy.sh start`
✅ **Monitorar logs**: `docker compose logs -f backend`
✅ **Quick mode** para mudanças rápidas: `bash scripts/deploy.sh quick` (sem rebuild)
✅ **Status**: `bash scripts/deploy.sh status`

---

**Status**: Pronto para usar  
**Próximo Passo**: Escolha Opção 1 ou 2 acima
