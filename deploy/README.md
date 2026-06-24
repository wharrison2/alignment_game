# Deploying the alignment game (DigitalOcean droplet + GoDaddy domain + Caddy)

This runbook takes the game from "runs on my laptop" to a public HTTPS site, for
someone who has not done this before. The shape:

```
Browser ──HTTPS(443)──> Caddy (on the droplet)        GoDaddy DNS:
                          │  - auto Let's Encrypt cert    A  @   -> droplet IP
                          │  - redirects 80 -> 443        A  www -> droplet IP
                          │  - security headers
                          └──HTTP──> 127.0.0.1:8000  (Python server, never public)
```

Caddy gets and renews the TLS certificate for you — you never touch certificates.
The Python server stays on localhost; only Caddy is exposed. The firewall opens
just SSH (22), HTTP (80), and HTTPS (443); port 8000 is never reachable from
outside.

Everywhere below, replace `yourdomain.com` with your domain and
`<droplet-ip>` with your droplet's public IPv4 address.

---

## Step 1 — Point the domain at the droplet (do this FIRST)

Caddy can only obtain a certificate once the domain already resolves to the
droplet, and DNS can take a while to propagate — so start here.

In GoDaddy's **DNS Management** for your domain, add two **A** records:

| Type | Name  | Value (points to) |
|------|-------|-------------------|
| A    | `@`   | `<droplet-ip>`    |
| A    | `www` | `<droplet-ip>`    |

(If GoDaddy created default parked records for `@`/`www`, edit those instead of
adding duplicates.)

Then, on your laptop, wait until this prints your droplet IP (can take minutes to
an hour):

```bash
dig +short yourdomain.com
dig +short www.yourdomain.com
```

---

## Step 2 — Prepare the droplet

SSH in as root (DigitalOcean → your droplet → Access):

```bash
ssh root@<droplet-ip>
```

Update the system and confirm Python is recent enough (the app is stdlib-only —
no `pip install` needed):

```bash
apt update && apt upgrade -y
python3 --version          # must be 3.10 or newer (Ubuntu 22.04/24.04 are fine)
```

Create an unprivileged account to run the app (matches `alignment.service`):

```bash
adduser --system --group alignment
```

---

## Step 3 — Get the code onto the droplet

Deploy from the `main` branch (merge the `deploy-https` branch into `main` first —
see "Merging this work" at the bottom).

```bash
git clone <your-repo-url> /opt/alignment_game
chown -R alignment:alignment /opt/alignment_game
```

To update later: `cd /opt/alignment_game && git pull && systemctl restart alignment`.

---

## Step 4 — Firewall (open only SSH, HTTP, HTTPS)

```bash
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw enable           # answer "y"; this will NOT drop your SSH session
ufw status
```

Note: port 8000 is intentionally **not** opened — the backend is only reachable
from Caddy on the same machine.

---

## Step 5 — Run the backend as a service

```bash
cp /opt/alignment_game/deploy/alignment.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now alignment
systemctl status alignment          # should say "active (running)"
curl -s localhost:8000/ | head -c 200    # should print the start of the HTML
```

If `status` shows a crash, read the log: `journalctl -u alignment -n 50`.

The unit sets `ALIGNMENT_DEPLOY=production`, which (a) closes the debug
`/api/truth` god-view endpoint and (b) marks the session cookie `Secure`.

---

## Step 6 — Install and configure Caddy (this is your HTTPS)

Install Caddy from its official apt repository (per
https://caddyserver.com/docs/install#debian-ubuntu-raspbian):

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install -y caddy
```

Install the project's Caddyfile and put your real domain in it:

```bash
cp /opt/alignment_game/deploy/Caddyfile /etc/caddy/Caddyfile
nano /etc/caddy/Caddyfile          # replace both yourdomain.com occurrences, save
systemctl reload caddy
```

Within ~30 seconds Caddy obtains the certificate. Watch it happen if you like:
`journalctl -u caddy -f` (Ctrl-C to stop watching).

---

## Step 7 — Verify it's live and secure

From your laptop:

```bash
curl -sI https://yourdomain.com | grep -i strict-transport   # HSTS header present
curl -sI http://yourdomain.com  | grep -i location           # redirects to https://
```

Then open `https://yourdomain.com` in a browser:
- The padlock shows (valid certificate).
- Play a full game, including the post-mortem at the end.
- Open the site in a second browser (or a private window) and start a different
  game — the two games must be independent (this is the multi-session fix).

Confirm the firewall (no TRUE-state leak in production):

```bash
curl -s https://yourdomain.com/api/truth      # must be exactly {"turns": []}
```

---

## Optional but recommended follow-ups

These harden the box further; none block launch.

```bash
apt install -y unattended-upgrades fail2ban   # auto security patches + SSH brute-force protection
dpkg-reconfigure -plow unattended-upgrades
```

Also consider disabling SSH password login in `/etc/ssh/sshd_config`
(`PasswordAuthentication no`) once your SSH key works.

---

## Operating it

| Task                      | Command                                            |
|---------------------------|----------------------------------------------------|
| Restart backend           | `systemctl restart alignment`                      |
| Backend logs              | `journalctl -u alignment -n 100 -f`                |
| Reload Caddy after edit   | `systemctl reload caddy`                           |
| Caddy / cert logs         | `journalctl -u caddy -n 100 -f`                    |
| Deploy new code           | `cd /opt/alignment_game && git pull && systemctl restart alignment` |

---

## Merging this work

The deployment changes live on the `deploy-https` branch (developed in a separate
git worktree so they stayed isolated from in-progress work on `fix-items`). Before
Step 3, merge `deploy-https` into `main`. The only code file it touches is
`backend_v1/server/server.py` (multi-session + hardening); if `fix-items` has also
changed that file, resolve the merge there — both sets of changes are wanted.

## Capacity note

The backend is Python's stdlib `http.server` (thread-per-request). Behind Caddy
this is fine for a low-to-moderate-traffic game. If you ever outgrow it, the
handlers are thin wrappers over `Session`, so they port cleanly to Flask/FastAPI
under gunicorn/uvicorn — at which point the in-memory session registry would move
to a shared store (Redis/DB). Out of scope until you actually have the load.
