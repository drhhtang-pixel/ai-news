#!/usr/bin/env bash
# Sample crontab entry — run daily at 08:00:
# 0 8 * * * /path/to/run.sh >> /path/to/cron.log 2>&1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/.env"
    set +a
fi

python3 "$SCRIPT_DIR/agent.py" || exit $?

python3 "$SCRIPT_DIR/publish.py" || echo "Warning: publish.py failed" >&2

git -C "$SCRIPT_DIR" add docs/ summaries.md && \
  git -C "$SCRIPT_DIR" commit -m "Daily summary $(date +%Y-%m-%d)" && \
  git -C "$SCRIPT_DIR" push || echo "Warning: git push failed" >&2

exit 0
