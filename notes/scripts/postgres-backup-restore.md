# Postgres Backup Restore

Back up and restore a PostgreSQL database. Run the blocks **in order** from Obsidian (the
`execute-code` ▶ button) so the whole team performs the operation the same, vetted way.

Links: [[script-demo]]
Tags: #postgres #script #backup

---

## Table of Contents

<!-- toc -->
<!-- tocstop -->

---

## Prerequisites

- `psql`, `pg_dump`, and `pg_restore` installed (the `postgresql` client tools).
- Credentials for a role that can read/restore the database, provided via **`~/.pgpass`**
  (`host:port:db:user:password`) — so no password is ever written in this note or the config file.

## Setup — write this run's config

Run this **first**. It writes the config to `/tmp/postgres-backup-restore.env`. Every step below sources it,
and the final Cleanup block removes it.

```bash
cat > /tmp/postgres-backup-restore.env << 'EOF'
# execute-code runs with Obsidian's minimal PATH — add common tool dirs so CLIs are found.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export PGHOST="localhost"
export PGPORT="5432"
export PGUSER="app"
export PGDATABASE="app_db"
export BACKUP_DIR="$HOME/backups"
# Password: from ~/.pgpass — do NOT put it here.
EOF
echo "Config written to /tmp/postgres-backup-restore.env"
```

## Back Up

```bash
source /tmp/postgres-backup-restore.env

mkdir -p "$BACKUP_DIR"
OUT="$BACKUP_DIR/$PGDATABASE-$(date +%Y%m%d-%H%M%S).dump"
pg_dump --format=custom --file="$OUT" "$PGDATABASE"
echo "Backup written to: $OUT"
```

## Restore

> [!WARNING]
> This overwrites objects in the target database. Double-check `PGDATABASE` before running.

```bash
source /tmp/postgres-backup-restore.env

LATEST="$(ls -t "$BACKUP_DIR/$PGDATABASE"-*.dump | head -n1)"
echo "Restoring: $LATEST"
pg_restore --clean --if-exists --no-owner --dbname="$PGDATABASE" "$LATEST"
echo "Restore complete."
```

## Verify

```bash
source /tmp/postgres-backup-restore.env

psql --dbname="$PGDATABASE" -c "\dt"
```

## Cleanup

```bash
rm -f /tmp/postgres-backup-restore.env
echo "Removed /tmp/postgres-backup-restore.env"
```

---

## References

- [pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html)
- [pg_restore](https://www.postgresql.org/docs/current/app-pgrestore.html)
- [obsidian-execute-code](https://github.com/twibiral/obsidian-execute-code)

---
