#!/bin/bash
#
# Deploy script para Aprimora-py
# Uso: ./scripts/deploy.sh [start|restart|logs|status]
#
set -e

DEPLOY_ENV="${DEPLOY_ENV:-production}"
COMPOSE_FILE="docker-compose.yml"
COMPOSE_OVERRIDE="docker-compose.override.yml"

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a deploy.log
}

# Estado dos serviços + logs recentes. Chamado em toda falha: o deploy roda por
# SSH a partir do CI, então sem isso a única evidência é a mensagem do compose
# ("container X is unhealthy"), que não diz o motivo.
dump_diagnostics() {
  echo "--- docker compose ps ---" | tee -a deploy.log
  docker compose ps -a 2>&1 | tee -a deploy.log || true
  echo "--- docker compose logs (tail 80) ---" | tee -a deploy.log
  docker compose logs --tail=80 --no-color 2>&1 | tee -a deploy.log || true
}

error() {
  echo "[ERROR] $*" | tee -a deploy.log
  dump_diagnostics
  exit 1
}

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
check_requirements() {
  log "Checking requirements..."
  command -v docker >/dev/null 2>&1 || error "Docker not installed"
  command -v git >/dev/null 2>&1 || error "Git not installed"
  log "✓ Requirements OK"
}

# Pull latest code
pull_code() {
  log "Pulling latest code from origin/main..."
  git fetch origin main
  git reset --hard origin/main
  GIT_COMMIT=$(git rev-parse --short HEAD)
  log "✓ Code updated to commit: $GIT_COMMIT"
}

# Re-executa o deploy com o script recém-baixado.
#
# `pull_code` faz `git reset --hard` sobre ESTE arquivo enquanto o bash já o
# está executando. As funções foram parseadas na entrada, então todo o resto
# do deploy roda o código do commit ANTERIOR — foi por isso que a correção do
# conflito de nomes de container pareceu não funcionar e só surtiu efeito um
# commit depois, confundindo o diagnóstico. Após o pull, trocamos o processo
# pelo script novo; `DEPLOY_REEXECUTADO` impede laço infinito e faz o segundo
# processo pular backup/pull (já feitos).
reexecutar_com_script_novo() {
  export DEPLOY_REEXECUTADO=1
  log "Re-executando o deploy com o script do commit ${GIT_COMMIT:-novo}..."
  exec bash "$0" "$@"
}

# Build containers
build_containers() {
  log "Building Docker containers..."
  docker compose build --no-cache
  log "✓ Build complete"
}

# Nomes fixos declarados via `container_name:` no docker-compose.yml.
COMPOSE_FIXED_NAMES="aprimora-py-backend aprimora-py-frontend aprimora-py-worker \
aprimora-py-beat aprimora-py-redis aprimora-py-nginx aprimora-py-db"

# Libera os nomes fixos do compose antes do `up`.
#
# O docker-compose.yml usa `container_name:` explícito, que é global no daemon.
# Qualquer container remanescente com esse nome — de um projeto compose com
# outro nome, de um `up` interrompido, ou criado à mão sem as labels do
# compose — faz o `up` abortar com "Conflict. The container name ... is
# already in use" (deploys 2decf1a e 7cee422). `--remove-orphans` não cobre:
# ele só alcança órfãos do MESMO projeto, e o conflito é por nome global.
#
# A remoção é INCONDICIONAL de propósito. A primeira tentativa condicionava ao
# label `com.docker.compose.project` divergir do projeto atual, e não removeu
# nada — o container preso ou tem o mesmo label, ou não tem label nenhum.
# Como `deploy_full` recria todos os containers de qualquer forma, remover é
# inócuo: os dados vivem no volume nomeado `postgres_data`, que `down` sem
# `-v` e `docker rm` não tocam.
remove_conflicting_containers() {
  log "Liberando nomes fixos do compose antes do up..."

  # Diagnóstico: registra o que está ocupando cada nome (dono e estado) antes
  # de remover, para que a próxima investigação tenha evidência no deploy.log.
  for nome in $COMPOSE_FIXED_NAMES; do
    local info
    info=$(docker inspect -f 'projeto={{ index .Config.Labels "com.docker.compose.project" }} servico={{ index .Config.Labels "com.docker.compose.service" }} estado={{ .State.Status }} criado={{ .Created }}' "$nome" 2>/dev/null || true)
    # `if` em vez de `[ ... ] && log`: sob `set -e`, uma lista AND-OR que
    # termina em falso derruba o script.
    if [ -n "$info" ]; then
      log "  ocupado: $nome → $info"
    fi
  done

  # Derruba o projeto atual pelo caminho normal (respeita ordem/rede).
  docker compose down --remove-orphans >/dev/null 2>&1 || true

  # O que sobrou segurando os nomes é resíduo: remove à força.
  for nome in $COMPOSE_FIXED_NAMES; do
    if docker inspect "$nome" >/dev/null 2>&1; then
      log "⚠ Nome '$nome' ainda ocupado após o down — removendo à força"
      docker rm -f "$nome" >/dev/null 2>&1 || true
    fi
  done
}

# Start services
start_services() {
  log "Starting services..."
  remove_conflicting_containers
  # `set -e` abortaria sem diagnóstico; `error` dispara o dump antes de sair.
  docker compose up -d --remove-orphans || error "docker compose up falhou"
  log "✓ Services started"

  log "Waiting for healthchecks..."
  sleep 10
  docker compose ps
}

# Restart services (faster alternative to full deploy)
restart_services() {
  log "Restarting services..."
  docker compose restart
  log "✓ Services restarted"
  sleep 5
  docker compose ps
}

# Health checks
health_check() {
  log "Running health checks..."

  # Porta 8000 (o compose publica 8000:8000; 8001 nunca existiu) e endpoint
  # /health, que é público. A sonda anterior batia em /auth/me, que exige
  # autenticação: mesmo com o backend sadio, o 401 fazia `curl -sf` falhar e
  # derrubava o deploy no fim. Só chegamos a exercitá-la quando o resto parou
  # de quebrar antes.
  BACKEND_READY=0
  for i in {1..30}; do
    if curl -sf http://localhost:8000/api/v2/health >/dev/null 2>&1; then
      BACKEND_READY=1
      break
    fi
    echo -n "."
    sleep 1
  done

  if [ $BACKEND_READY -eq 1 ]; then
    log "✓ Backend healthy"
  else
    error "Backend not responding after 30s"
  fi

  FRONTEND_READY=0
  for i in {1..30}; do
    if curl -sf http://localhost:8090 >/dev/null 2>&1; then
      FRONTEND_READY=1
      break
    fi
    echo -n "."
    sleep 1
  done

  if [ $FRONTEND_READY -eq 1 ]; then
    log "✓ Frontend healthy"
  else
    error "Frontend not responding after 30s"
  fi
}

# Run migrations if needed
run_migrations() {
  log "Checking database migrations..."
  docker compose exec -T backend alembic upgrade head || log "Migrations skipped (DB may be initializing)"

  # Seed idempotente: garante os pré-requisitos globais (utils.sistema com o
  # app corrente, utils.nivel valor=0, KEY_LOGIN_GLOBAL_JWT) e o vínculo do
  # admin ao grupo SU. Necessário desde a padronização de APP_NAME='sistemas':
  # admin ligado ao sistema antigo deixa de ser reconhecido como super-usuário
  # e passa a receber 403. Não remove nem sobrescreve nada existente.
  log "Aplicando seed_bootstrap (idempotente)..."
  docker compose exec -T backend python -m app.cli.seed_bootstrap || log "seed_bootstrap falhou — verificar manualmente"
}

# Backup database (optional)
backup_database() {
  if [ "$BACKUP_DB" = "1" ]; then
    log "Backing up database..."
    BACKUP_FILE="backups/db_backup_$(date +'%Y%m%d_%H%M%S').sql"
    mkdir -p backups
    docker compose exec -T db pg_dump -U ged_user ged_saas_db > "$BACKUP_FILE" || log "Backup skipped"
    log "✓ Backup saved to $BACKUP_FILE"
  fi
}

# Full deploy (pull + build + start + healthcheck)
deploy_full() {
  log "=========================================="
  log "Starting FULL DEPLOY"
  log "=========================================="

  check_requirements
  if [ -z "${DEPLOY_REEXECUTADO:-}" ]; then
    backup_database
    pull_code
    reexecutar_com_script_novo "$@"   # não retorna: troca o processo
  fi
  build_containers
  start_services
  run_migrations
  health_check

  log "=========================================="
  log "✓ DEPLOY COMPLETE"
  log "=========================================="
  show_urls
}

# Quick restart (for code changes only)
deploy_quick() {
  log "=========================================="
  log "Starting QUICK RESTART (no rebuild)"
  log "=========================================="

  check_requirements
  if [ -z "${DEPLOY_REEXECUTADO:-}" ]; then
    pull_code
    reexecutar_com_script_novo "$@"   # não retorna: troca o processo
  fi
  restart_services
  health_check

  log "=========================================="
  log "✓ RESTART COMPLETE"
  log "=========================================="
  show_urls
}

# Show service URLs
show_urls() {
  echo ""
  echo -e "${GREEN}Service URLs:${NC}"
  echo "  Frontend:  http://localhost:8090"
  echo "  Backend:   http://localhost:8000/api/v2"
  echo "  API Docs:  http://localhost:8000/docs"
  echo ""
}

# Show logs
show_logs() {
  SERVICE="${1:-all}"
  log "Showing logs for: $SERVICE"
  docker compose logs -f --tail=50 $SERVICE
}

# Show status
show_status() {
  log "Service Status:"
  docker compose ps
  echo ""
  log "Recent logs:"
  docker compose logs --tail=20
}

# Cleanup (remove containers/volumes)
cleanup() {
  log "WARNING: This will remove all containers and volumes!"
  read -p "Continue? (y/n) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "Stopping and removing services..."
    docker compose down -v
    log "✓ Cleanup complete"
  fi
}

# Main logic
case "${1:-start}" in
  start)
    deploy_full "$@"
    ;;
  quick)
    deploy_quick "$@"
    ;;
  restart)
    restart_services
    show_urls
    ;;
  logs)
    show_logs "${2:-}"
    ;;
  status)
    show_status
    ;;
  health)
    health_check
    ;;
  cleanup)
    cleanup
    ;;
  *)
    echo "Usage: $0 [start|quick|restart|logs|status|health|cleanup]"
    echo ""
    echo "Commands:"
    echo "  start      - Full deploy (pull + build + start)"
    echo "  quick      - Quick restart without rebuild"
    echo "  restart    - Restart running services"
    echo "  logs [SVC] - Show service logs (default: all)"
    echo "  status     - Show service status"
    echo "  health     - Run health checks"
    echo "  cleanup    - Remove containers and volumes"
    echo ""
    echo "Environment variables:"
    echo "  BACKUP_DB=1 - Backup database before deploy"
    echo "  DEPLOY_ENV  - Deployment environment (production/staging)"
    exit 1
    ;;
esac
