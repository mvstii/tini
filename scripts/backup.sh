#!/bin/sh
# Günlük yedek: ./scripts/backup.sh  (docs/DAGITIM.md). Son 14 yedek tutulur.
set -eu
cd "$(dirname "$0")/.."
mkdir -p backups
f="backups/tini-$(date +%Y%m%d-%H%M%S).sql.gz"
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db pg_dump -U tini tini | gzip > "$f"
ls -1t backups/tini-*.sql.gz | tail -n +15 | xargs -r rm --
echo "$f"
