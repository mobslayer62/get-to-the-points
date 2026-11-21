#!/usr/bin/env bash
# Update the online server after new code is merged into main.
#
# Run in a PythonAnywhere Bash console:
#   bash ~/get-to-the-points/backend/deploy/update.sh
# then click "Reload" on the Web tab.
set -euo pipefail

REPO="$HOME/get-to-the-points"
PY="$HOME/.virtualenvs/gttp-venv/bin/python"

cd "$REPO"
echo "==> Pulling the latest main"
git pull --ff-only

cd backend

# Back up the database before migrating; keep the 5 newest backups
if [ -f db.sqlite3 ]; then
    echo "==> Backing up the database"
    mkdir -p backups
    cp db.sqlite3 "backups/db-$(date +%Y%m%d-%H%M%S).sqlite3"
    ls -1t backups/db-*.sqlite3 | tail -n +6 | xargs -r rm --
fi

echo "==> Installing packages"
"$PY" -m pip install -q -r requirements.txt

echo "==> Updating the database"
"$PY" manage.py migrate --noinput

echo "==> Collecting static files (admin CSS)"
"$PY" manage.py collectstatic --noinput

echo
echo "Done. Now open the Web tab on PythonAnywhere and click Reload."
