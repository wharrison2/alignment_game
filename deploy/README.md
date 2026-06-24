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

## Step 8 — DDoS & bot protection (Cloudflare, free) — strongly recommended before sharing the link

A single droplet cannot absorb a volumetric flood on its own — the network pipe
saturates regardless of code. The fix is to put **Cloudflare's free tier** in
front: it soaks up volumetric attacks, filters bots, hides your droplet's real IP,
and gives you per-IP rate limiting — all with no code. The backend already has
matching app-level backstops (a per-game turn cap, a cached post-mortem so it
can't be made to re-simulate on demand, a request-concurrency limit that sheds to
503, and a body-size cap), but those protect the box *after* traffic arrives;
Cloudflare keeps most abusive traffic from arriving at all.

**Do this AFTER Steps 1–7 work over HTTPS** (Caddy needs to get its certificate
first; doing it before Cloudflare proxying avoids a confusing chicken-and-egg with
the certificate challenge).

1. **Add the domain to Cloudflare.** Create a free account at cloudflare.com →
   "Add a site" → enter `yourdomain.com`. Cloudflare scans your existing DNS and
   gives you **two nameservers**.
2. **Point GoDaddy at Cloudflare.** In GoDaddy → your domain → Nameservers →
   "Change" → "I'll use my own nameservers" → paste Cloudflare's two nameservers.
   (This moves DNS hosting to Cloudflare; propagation can take up to a few hours.)
3. **Turn on proxying.** In Cloudflare → DNS, make sure the `@` and `www` **A
   records point to `<droplet-ip>`** with the **orange cloud ON** (Proxied). The
   orange cloud is what routes traffic through Cloudflare and hides your origin IP.
4. **Set TLS mode to Full (strict).** Cloudflare → SSL/TLS → Overview →
   **Full (strict)**. This keeps HTTPS all the way to the droplet and validates
   Caddy's real certificate.
5. **Lock the firewall to Cloudflare** so attackers can't bypass the proxy by
   hitting the droplet IP directly. Either use DigitalOcean's Cloud Firewall to
   allow 80/443 only from Cloudflare's published IP ranges
   (https://www.cloudflare.com/ips/), or keep `ufw` but restrict those ports to
   those ranges. (SSH/22 stays open to you.)
6. **Turn on bot + rate-limit protection** (Cloudflare dashboard):
   - **Security → Bots → Bot Fight Mode: On** (free) — challenges obvious bots.
   - **Security → WAF → Rate limiting rules**: the free plan includes one rule.
     Add: *if URI path starts with `/api/`, more than ~60 requests per minute per
     IP → Block (or Managed Challenge)*. This directly throttles `/api/new` and
     `/api/action` floods.
   - Optionally flip **"Under Attack Mode"** on temporarily if you're ever
     actively targeted — it shows an interstitial challenge to every visitor.

After this, re-verify the site still loads over HTTPS and a game plays end to end
(the cookie and same-origin requests work identically through Cloudflare).

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

The backend is Python's stdlib `http.server` (thread-per-request), but it now
sheds load past a concurrency cap (503) instead of spawning unbounded threads,
times out slow connections, caps body size, bounds per-game length, and caches the
post-mortem — so a single client can't cheaply exhaust it. Behind Caddy and
Cloudflare this is fine for a low-to-moderate-traffic game. If you ever outgrow it,
the handlers are thin wrappers over `Session`, so they port cleanly to
Flask/FastAPI under gunicorn/uvicorn — at which point the in-memory session
registry would move to a shared store (Redis/DB). Out of scope until you actually
have the load.
