#!/usr/bin/env bash
# Backup do Aprimora — banco + papéis globais + uploads.
#
# Até 2026-08-05 a VPS tinha exatamente UM backup: um dump manual de 24/jul,
# 43 KB, gravado na mesma máquina do banco. Sem cron, sem timer, sem cópia
# fora do host. Ou seja: qualquer perda do disco levava junto o backup.
#
# O `backup_database` do `scripts/deploy.sh` existia, mas estava desligado
# (`BACKUP_DB=1`) e, pior, era escrito assim:
#
#     docker compose exec -T db pg_dump ... > "$BACKUP_FILE" || log "Backup skipped"
#
# O redirecionamento cria o arquivo ANTES de o `pg_dump` rodar. Dump que falha
# deixa no disco um arquivo de zero byte com nome de backup, o script loga
# "Backup skipped" e termina com sucesso. É a mesma família do export vazio que
# `app/cli/backup.py` já aprendeu a barrar: artefato sintaticamente plausível,
# inútil, e que só se revela no dia do restore.
#
# Por isso aqui a ordem é: gerar em área de espera -> VERIFICAR -> só então
# publicar com `mv`. Um arquivo em `$DESTINO` é um arquivo que passou na
# verificação; não existe estado intermediário visível.
#
# O que NÃO está resolvido: a cópia fora da máquina. Enquanto o destino remoto
# não for definido, isto é proteção contra `DROP TABLE` e migration ruim, NÃO
# contra perda do servidor. Ver RUNBOOK, seção "Backup".
#
# Uso:
#     scripts/backup-aprimora.sh                 # backup completo
#     DESTINO=/mnt/x scripts/backup-aprimora.sh  # outro destino
#
# Códigos de saída: 0 sucesso; qualquer outro = NENHUM artefato foi publicado.
set -euo pipefail

CONTAINER_DB="${CONTAINER_DB:-aprimora-py-db}"
CONTAINER_BACKEND="${CONTAINER_BACKEND:-aprimora-py-backend}"
PGUSER_DUMP="${PGUSER_DUMP:-ged_user}"
PGDATABASE_DUMP="${PGDATABASE_DUMP:-ged_saas_db}"
DESTINO="${DESTINO:-/root/backups}"
RETENCAO_DIARIA="${RETENCAO_DIARIA:-14}"
RETENCAO_SEMANAL="${RETENCAO_SEMANAL:-8}"

# Tamanho mínimo do dump. O banco de homologação tem ~23 MB e o dump comprimido
# fica na casa das centenas de KB; 20 KB é folgado o bastante para não acusar
# falso positivo num tenant recém-provisionado e apertado o bastante para pegar
# dump truncado ou vazio.
MIN_BYTES_DUMP="${MIN_BYTES_DUMP:-20480}"

TS="$(date -u +'%Y%m%dT%H%M%SZ')"
DIA_DA_SEMANA="$(date -u +'%u')"   # 7 = domingo

log() { printf '[%s] %s\n' "$(date -u +'%H:%M:%S')" "$*"; }
falhar() { printf '[ERRO] %s\n' "$*" >&2; exit 1; }

ESPERA="$(mktemp -d)"
trap 'rm -rf "$ESPERA"' EXIT

# ---------------------------------------------------------------- pré-checagem
docker inspect "$CONTAINER_DB" >/dev/null 2>&1 \
  || falhar "container '$CONTAINER_DB' não existe. Backup NÃO foi feito."

mkdir -p "$DESTINO/diario" "$DESTINO/semanal"

# --------------------------------------------------------------------- 1. banco
# `pg_dump -Fc` escreve o arquivo ele mesmo, DENTRO do container. Nada de
# redirecionar a saída do `docker exec`: é justamente o redirecionamento que
# fabrica o arquivo vazio quando o comando falha.
log "Gerando dump de $PGDATABASE_DUMP..."
DUMP_NO_CONTAINER="/tmp/aprimora_${TS}.dump"
docker exec "$CONTAINER_DB" pg_dump -U "$PGUSER_DUMP" -d "$PGDATABASE_DUMP" \
  --format=custom --compress=9 --file="$DUMP_NO_CONTAINER" \
  || falhar "pg_dump falhou. Nenhum artefato publicado."

# `pg_restore -l` lê o índice do arquivo: prova que é um dump custom íntegro e
# não um arquivo qualquer com o nome certo. Roda DENTRO do container, onde o
# `pg_restore` da mesma versão já existe — trazer outra imagem só para isto
# introduziria dependência de rede num script cujo trabalho é justamente
# funcionar no dia ruim.
ENTRADAS="$(docker exec "$CONTAINER_DB" pg_restore -l "$DUMP_NO_CONTAINER" \
  | grep -c '^[0-9]' || true)"
[ "${ENTRADAS:-0}" -ge 100 ] \
  || falhar "pg_restore -l listou apenas ${ENTRADAS:-0} entradas no dump. Arquivo corrompido ou banco vazio."

docker cp "$CONTAINER_DB:$DUMP_NO_CONTAINER" "$ESPERA/banco.dump"
docker exec "$CONTAINER_DB" rm -f "$DUMP_NO_CONTAINER"

# --------------------------------------------------------- 2. papéis globais
# Sem os papéis o restore num cluster novo morre nos GRANTs: `aprimora_app`,
# `aprimora_worker`, `aprimora_migrator` e `aprimora_platform` são referenciados
# por policy e por grant em quase toda migration da família SEC.
log "Gerando dump dos papéis globais..."
GLOBAIS_NO_CONTAINER="/tmp/aprimora_globais_${TS}.sql"
docker exec "$CONTAINER_DB" pg_dumpall -U "$PGUSER_DUMP" --globals-only \
  --file="$GLOBAIS_NO_CONTAINER" \
  || falhar "pg_dumpall --globals-only falhou. Nenhum artefato publicado."
docker cp "$CONTAINER_DB:$GLOBAIS_NO_CONTAINER" "$ESPERA/globais.sql"
docker exec "$CONTAINER_DB" rm -f "$GLOBAIS_NO_CONTAINER"

# ------------------------------------------------------------------ 3. uploads
# Anexo não vive no banco: o caminho é registro, o arquivo é disco. Backup só do
# Postgres restaura processos que apontam para arquivos que não existem mais.
if docker inspect "$CONTAINER_BACKEND" >/dev/null 2>&1; then
  log "Gerando tar dos uploads..."
  UPLOADS_NO_CONTAINER="/tmp/aprimora_uploads_${TS}.tgz"
  docker exec "$CONTAINER_BACKEND" tar czf "$UPLOADS_NO_CONTAINER" -C /app uploads \
    || falhar "tar dos uploads falhou. Nenhum artefato publicado."
  docker cp "$CONTAINER_BACKEND:$UPLOADS_NO_CONTAINER" "$ESPERA/uploads.tgz"
  docker exec "$CONTAINER_BACKEND" rm -f "$UPLOADS_NO_CONTAINER"
else
  falhar "container '$CONTAINER_BACKEND' não existe — os uploads ficariam de fora e o backup seria parcial sem avisar."
fi

# ------------------------------------------------------------- 4. verificação
# Tudo abaixo roda ANTES de qualquer arquivo aparecer em $DESTINO.
log "Verificando artefatos..."

tamanho() { stat -c%s "$1"; }

[ -s "$ESPERA/banco.dump" ] || falhar "dump do banco veio vazio."
BYTES="$(tamanho "$ESPERA/banco.dump")"
[ "$BYTES" -ge "$MIN_BYTES_DUMP" ] \
  || falhar "dump do banco tem $BYTES bytes, abaixo do mínimo de $MIN_BYTES_DUMP. Suspeite de dump truncado."

log "  dump: $BYTES bytes, $ENTRADAS entradas no índice"

# Os quatro papéis da família SEC. Se o `--globals-only` rodar contra um cluster
# onde eles não existem, o arquivo sai sintaticamente válido e sem eles — e o
# restore só falha lá na frente.
for papel in aprimora_app aprimora_worker aprimora_migrator aprimora_platform; do
  grep -q "CREATE ROLE $papel" "$ESPERA/globais.sql" \
    || falhar "papel '$papel' ausente do dump de globais. Restore em cluster novo falharia nos GRANTs."
done
log "  globais: 4 papéis da família SEC presentes"

tar tzf "$ESPERA/uploads.tgz" >/dev/null \
  || falhar "tar dos uploads não abre — arquivo corrompido."
log "  uploads: $(tamanho "$ESPERA/uploads.tgz") bytes"

# --------------------------------------------------------------- 5. publicação
ALVO="$DESTINO/diario/aprimora_${TS}"
mkdir -p "$ALVO.parcial"
mv "$ESPERA/banco.dump" "$ESPERA/globais.sql" "$ESPERA/uploads.tgz" "$ALVO.parcial/"
( cd "$ALVO.parcial" && sha256sum banco.dump globais.sql uploads.tgz > SHA256SUMS )
# O `mv` do diretório é a publicação atômica: até esta linha nada em $DESTINO
# tem nome de backup pronto.
mv "$ALVO.parcial" "$ALVO"
log "Publicado: $ALVO"

if [ "$DIA_DA_SEMANA" = "7" ]; then
  cp -al "$ALVO" "$DESTINO/semanal/aprimora_${TS}" 2>/dev/null \
    || cp -a "$ALVO" "$DESTINO/semanal/aprimora_${TS}"
  log "Cópia semanal: $DESTINO/semanal/aprimora_${TS}"
fi

# ----------------------------------------------------------------- 6. retenção
# Poda DEPOIS de publicar. Podar antes deixaria a janela em que o backup mais
# velho já foi apagado e o novo ainda não existe.
#
# Nada de `ls "$dir"/aprimora_* | ...`: em diretório vazio o glob não expande,
# o `ls` sai com status 2 e, sob `pipefail` + `set -e`, o script inteiro morre
# — DEPOIS de já ter publicado o backup. Aconteceu na primeira execução real:
# artefato correto no disco e exit 2, o que deixaria a unidade systemd vermelha
# todo dia e a poda sem nunca rodar.
podar() {
  local dir="$1" manter="$2"
  local todos=()
  shopt -s nullglob
  todos=( "$dir"/aprimora_* )
  shopt -u nullglob
  local n=${#todos[@]}
  [ "$n" -gt "$manter" ] || return 0
  # O nome carrega timestamp ISO em UTC, então ordem lexicográfica é ordem
  # cronológica.
  mapfile -t todos < <(printf '%s\n' "${todos[@]}" | sort)
  local i
  for (( i = 0; i < n - manter; i++ )); do
    rm -rf "${todos[$i]}"
    log "Removido por retenção: ${todos[$i]}"
  done
}
podar "$DESTINO/diario" "$RETENCAO_DIARIA"
podar "$DESTINO/semanal" "$RETENCAO_SEMANAL"

log "OK — backup completo e verificado."
