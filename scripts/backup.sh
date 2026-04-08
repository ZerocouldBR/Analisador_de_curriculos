#!/bin/bash
# ============================================================
# Backup automatizado do Analisador de Curriculos
# Uso: ./scripts/backup.sh
# Cron: 0 3 * * * /opt/analisador-curriculos/scripts/backup.sh >> /opt/backups/postgres/backup.log 2>&1
# ============================================================

set -euo pipefail

# Configuracoes
BACKUP_DIR="${BACKUP_DIR:-/opt/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DATE=$(date +%Y%m%d_%H%M%S)
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.prod.yml"

# Criar diretorio de backup se nao existir
mkdir -p "$BACKUP_DIR"

echo "[$(date)] ============================================"
echo "[$(date)] Iniciando backup..."
echo "[$(date)] Diretorio: $BACKUP_DIR"
echo "[$(date)] Retencao: $RETENTION_DAYS dias"

# 1. Backup do PostgreSQL
echo "[$(date)] Backup do PostgreSQL..."
docker compose -f "$COMPOSE_FILE" exec -T db \
    pg_dump -U analisador -d analisador_curriculos \
    --format=custom --compress=9 \
    > "$BACKUP_DIR/db_backup_$DATE.dump"
echo "[$(date)]   -> $(ls -lh "$BACKUP_DIR/db_backup_$DATE.dump" | awk '{print $5}')"

# 2. Backup dos uploads (curriculos)
echo "[$(date)] Backup dos uploads..."
if docker compose -f "$COMPOSE_FILE" exec -T api ls /app/uploads/ > /dev/null 2>&1; then
    docker compose -f "$COMPOSE_FILE" exec -T api \
        tar -czf - -C /app uploads/ \
        > "$BACKUP_DIR/uploads_backup_$DATE.tar.gz"
    echo "[$(date)]   -> $(ls -lh "$BACKUP_DIR/uploads_backup_$DATE.tar.gz" | awk '{print $5}')"
else
    echo "[$(date)]   -> Diretorio uploads vazio ou inacessivel, pulando..."
fi

# 3. Backup do .env (configuracoes)
echo "[$(date)] Backup das configuracoes..."
if [ -f "${PROJECT_DIR}/backend/.env" ]; then
    cp "${PROJECT_DIR}/backend/.env" "$BACKUP_DIR/env_backup_$DATE.env"
    chmod 600 "$BACKUP_DIR/env_backup_$DATE.env"
    echo "[$(date)]   -> env_backup_$DATE.env"
fi

# 4. Remover backups antigos
echo "[$(date)] Removendo backups com mais de $RETENTION_DAYS dias..."
DELETED=$(find "$BACKUP_DIR" \( -name "*.dump" -o -name "*.tar.gz" -o -name "*.env" \) -mtime +$RETENTION_DAYS -delete -print | wc -l)
echo "[$(date)]   -> $DELETED arquivos removidos"

# 5. Resumo
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
TOTAL_FILES=$(find "$BACKUP_DIR" -type f | wc -l)
echo "[$(date)] ============================================"
echo "[$(date)] Backup concluido com sucesso!"
echo "[$(date)] Total: $TOTAL_FILES arquivos, $TOTAL_SIZE"
echo "[$(date)] ============================================"
