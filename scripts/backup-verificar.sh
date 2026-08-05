#!/usr/bin/env bash
# Prova de restore — restaura um backup num banco descartável e compara.
#
# `backup-aprimora.sh` já verifica que o dump ABRE (`pg_restore -l`). Isto é
# outra coisa: prova que ele ENTRA. Um dump pode ter índice íntegro e ainda
# assim falhar no restore por dependência de papel, extensão ausente ou ordem
# de objetos — e essa diferença só aparece tentando.
#
# Backup nunca restaurado não é backup; é um arquivo com nome de backup. Esta é
# a inversão da guarda: enquanto ninguém rodar isto, "temos backup" é uma
# hipótese não testada.
#
# O banco de trabalho é criado e derrubado aqui mesmo, no cluster da VPS. Ele
# não toca `ged_saas_db` em nenhum momento — só lê contagens de lá para
# comparar. Custa ~23 MB de disco durante a execução.
#
# Uso:
#     scripts/backup-verificar.sh                        # o backup mais recente
#     scripts/backup-verificar.sh /root/backups/diario/aprimora_20260805T160000Z
#
# Saída 0 = restaurou e as contagens batem. Qualquer outra = NÃO confie no
# backup verificado.
set -euo pipefail

CONTAINER_DB="${CONTAINER_DB:-aprimora-py-db}"
PGUSER_DUMP="${PGUSER_DUMP:-ged_user}"
PGDATABASE_DUMP="${PGDATABASE_DUMP:-ged_saas_db}"
DESTINO="${DESTINO:-/root/backups}"

# Schemas conferidos linha a linha. `utils` e `protocolos` são o legado
# compartilhado; `aprimora_py` e `frota` são nossos.
SCHEMAS="utils protocolos aprimora_py frota"

log() { printf '[%s] %s\n' "$(date -u +'%H:%M:%S')" "$*"; }
falhar() { printf '[ERRO] %s\n' "$*" >&2; exit 1; }

ORIGEM="${1:-}"
if [ -z "$ORIGEM" ]; then
  ORIGEM="$(ls -1d "$DESTINO"/diario/aprimora_* 2>/dev/null | sort | tail -1 || true)"
  [ -n "$ORIGEM" ] || falhar "nenhum backup em $DESTINO/diario. Rode backup-aprimora.sh antes."
fi
[ -f "$ORIGEM/banco.dump" ] || falhar "'$ORIGEM/banco.dump' não existe."

log "Verificando: $ORIGEM"

# ------------------------------------------------------------ integridade
if [ -f "$ORIGEM/SHA256SUMS" ]; then
  ( cd "$ORIGEM" && sha256sum -c SHA256SUMS >/dev/null ) \
    || falhar "SHA256SUMS não confere — o backup foi corrompido depois de gravado."
  log "  sha256: confere"
fi

ALVO="verificacao_$(date -u +'%Y%m%d%H%M%S')"
DUMP_NO_CONTAINER="/tmp/${ALVO}.dump"

limpar() {
  docker exec "$CONTAINER_DB" rm -f "$DUMP_NO_CONTAINER" >/dev/null 2>&1 || true
  docker exec "$CONTAINER_DB" dropdb -U "$PGUSER_DUMP" --if-exists --force "$ALVO" >/dev/null 2>&1 || true
}
trap limpar EXIT

docker cp "$ORIGEM/banco.dump" "$CONTAINER_DB:$DUMP_NO_CONTAINER"

log "Criando banco descartável '$ALVO'..."
docker exec "$CONTAINER_DB" createdb -U "$PGUSER_DUMP" "$ALVO" \
  || falhar "não consegui criar o banco de verificação."

log "Restaurando..."
# `--exit-on-error` é o ponto: sem ele o `pg_restore` acumula erros, devolve 0 e
# a verificação passa em cima de um restore pela metade.
if ! docker exec "$CONTAINER_DB" pg_restore -U "$PGUSER_DUMP" -d "$ALVO" \
     --exit-on-error --no-owner --no-privileges "$DUMP_NO_CONTAINER" 2>/tmp/pgrestore.err; then
  sed -n '1,20p' /tmp/pgrestore.err >&2 || true
  falhar "pg_restore falhou. Este backup NÃO é restaurável."
fi
log "  restore concluído sem erro"

# --------------------------------------------------------------- contagens
# Comparação genérica: toda tabela dos schemas listados. Um restore vazio ou
# parcial é sintaticamente perfeito — a contagem é o que o desmascara.
#
# `ged_saas_db` continua vivo e pode ter recebido escrita entre o dump e agora,
# então diferença pequena para MAIS no vivo é esperada. O que reprova é tabela
# com linhas no vivo e ZERO no restaurado: é o modo de falha que importa.
contar() {
  local banco="$1"
  local sql=""
  for s in $SCHEMAS; do
    sql="$sql SELECT '$s.'||tablename AS t, '$s' AS s, tablename AS n FROM pg_tables WHERE schemaname='$s' UNION ALL"
  done
  sql="${sql% UNION ALL}"
  docker exec "$CONTAINER_DB" psql -U "$PGUSER_DUMP" -d "$banco" -tAF'|' -c "
    SELECT t, (xpath('/row/c/text()',
      query_to_xml(format('SELECT count(*) AS c FROM %I.%I', s, n), false, true, '')))[1]::text::bigint
    FROM ($sql) x ORDER BY t;"
}

log "Contando linhas nos dois bancos..."
contar "$PGDATABASE_DUMP" > /tmp/contagem_vivo.txt
contar "$ALVO"            > /tmp/contagem_restaurado.txt

AUSENTES=0
VAZIAS=0
DIFERENTES=0
while IFS='|' read -r tabela n_vivo; do
  [ -n "$tabela" ] || continue
  n_rest="$(grep -F "$tabela|" /tmp/contagem_restaurado.txt | head -1 | cut -d'|' -f2 || true)"
  if [ -z "$n_rest" ]; then
    # Tabela que existe no vivo e não no restaurado. Reprova mesmo com zero
    # linhas: o que falta aqui é o SCHEMA, e um restore sem a tabela não
    # aceitaria o primeiro INSERT do sistema de volta no ar.
    printf '  [AUSENTE] %-55s vivo=%s  restaurado=<tabela não existe>\n' "$tabela" "$n_vivo"
    AUSENTES=$((AUSENTES + 1))
  elif [ "$n_vivo" -gt 0 ] && [ "$n_rest" -eq 0 ]; then
    printf '  [VAZIA]   %-55s vivo=%s  restaurado=0\n' "$tabela" "$n_vivo"
    VAZIAS=$((VAZIAS + 1))
  elif [ "$n_vivo" != "$n_rest" ]; then
    printf '  [difere]  %-55s vivo=%s  restaurado=%s\n' "$tabela" "$n_vivo" "$n_rest"
    DIFERENTES=$((DIFERENTES + 1))
  fi
done < /tmp/contagem_vivo.txt

TOTAL="$(wc -l < /tmp/contagem_vivo.txt)"
log "  $TOTAL tabelas conferidas; $DIFERENTES com diferença; $VAZIAS vazias; $AUSENTES ausentes"

[ "$AUSENTES" -eq 0 ] \
  || falhar "$AUSENTES tabela(s) existem no banco vivo e NÃO no restaurado. O schema não veio inteiro; este backup NÃO serve."
[ "$VAZIAS" -eq 0 ] \
  || falhar "$VAZIAS tabela(s) com dado no vivo e nada no restaurado. Este backup NÃO serve."

if [ "$DIFERENTES" -gt 0 ]; then
  log "AVISO: $DIFERENTES tabela(s) com contagem diferente. Esperado se houve escrita"
  log "       entre o dump e esta verificação; investigue se a diferença for grande."
fi

log "OK — restore provado. Backup verificado: $ORIGEM"
