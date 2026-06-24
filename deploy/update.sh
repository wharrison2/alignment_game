#!/usr/bin/env bash
#
# Update the deployed alignment game to the latest origin/main and restart it.
#
# Run on the droplet as root (the GitHub deploy key lives in root's ~/.ssh):
#   /opt/alignment_game/deploy/update.sh
#
# It pulls the latest main into this shallow + sparse checkout (keeping the .md
# exclusion), re-asserts ownership for the service account, and restarts the
# backend. Safe to run repeatedly. If the deploy configs (Caddyfile / systemd
# unit) changed in the update, it tells you — those are applied by hand on
# purpose (see deploy/README.md), since reloading Caddy/systemd is deliberate.

set -euo pipefail

APP_DIR="/opt/alignment_game"
SERVICE="alignment"
RUN_USER="alignment"
BRANCH="main"

cd "$APP_DIR"

# root operating a repo owned by the service account trips git's ownership guard;
# allow this path once (idempotent — don't append a duplicate entry on re-runs).
if ! git config --global --get-all safe.directory 2>/dev/null | grep -qx "$APP_DIR"; then
    git config --global --add safe.directory "$APP_DIR"
fi

echo "==> Fetching latest origin/$BRANCH (shallow)…"
git fetch --depth 1 origin "$BRANCH"
git reset --hard "origin/$BRANCH"

echo "==> Restoring ownership to $RUN_USER…"
chown -R "$RUN_USER:$RUN_USER" "$APP_DIR"

echo "==> Restarting $SERVICE…"
systemctl restart "$SERVICE"

# Warn (don't auto-apply) if the deploy configs drifted from what's installed.
# /etc copies are byte-identical to these templates after a clean install, so a
# difference means this update changed them and you should re-copy + reload.
if ! cmp -s "$APP_DIR/deploy/Caddyfile" /etc/caddy/Caddyfile 2>/dev/null; then
    echo "NOTE: deploy/Caddyfile changed — re-copy to /etc/caddy/Caddyfile and 'systemctl reload caddy'."
fi
if ! cmp -s "$APP_DIR/deploy/alignment.service" /etc/systemd/system/alignment.service 2>/dev/null; then
    echo "NOTE: deploy/alignment.service changed — re-copy to /etc/systemd/system/, 'systemctl daemon-reload', restart."
fi

echo "==> Done. Now on $(git rev-parse --short HEAD): $(git log -1 --format='%s')"
echo "    Verify:  curl -s https://alignmentgame.net/api/truth   # expect {\"turns\": []}"
