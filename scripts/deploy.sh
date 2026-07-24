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

error() {
  echo "[ERROR] $*" | tee -a deploy.log
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

# Build containers
build_containers() {
  log "Building Docker containers..."
  docker compose build --no-cache
  log "✓ Build complete"
}

# Start services
start_services() {
  log "Starting services..."
  docker compose up -d
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

  BACKEND_READY=0
  for i in {1..30}; do
    if curl -sf http://localhost:8001/api/v2/auth/me >/dev/null 2>&1; then
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
  backup_database
  pull_code
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
  pull_code
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
  echo "  Backend:   http://localhost:8001/api/v2"
  echo "  API Docs:  http://localhost:8001/docs"
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
    deploy_full
    ;;
  quick)
    deploy_quick
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
