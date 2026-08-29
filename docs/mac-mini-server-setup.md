# Mac Mini Server Setup

Setting up a Mac mini on the lab subnet to do two jobs at once:

1. **Personal document storage** — available at home and remotely, never on the internet
2. **Public web applications** — served on a domain you own

Do [home-subnet-setup.md](home-subnet-setup.md) first. This assumes the Mac mini is on the
switch at `192.168.50.10` with working internet.

---

## The approach: nothing is exposed

The instinct for "host a website from home" is port forwarding. Don't. Behind double NAT it
means forwards on *both* routers, Cox blocks inbound 80/443 on residential lines anyway, and
every forward is a permanent hole someone can knock on.

Instead both access paths are **outbound-initiated**:

- **Cloudflare Tunnel** for the public site — `cloudflared` dials *out* to Cloudflare and
  holds the connection open. Visitors reach Cloudflare; Cloudflare pushes traffic down the
  existing tunnel.
- **Tailscale** for private access — same idea, an encrypted mesh between your own devices.

```
                          +---------------------------+
   internet visitors ---> |        Cloudflare         |
                          +-------------+-------------+
                                        ^  outbound only
                                        |
   you, away from home ---> Tailnet ----+
                                        |
                          +-------------+-------------+
                          |         Mac mini          |
                          |  cloudflared              |
                          |  tailscaled               |
                          |  Docker apps -> 127.0.0.1 |
                          |  Documents  -> LAN + Tailnet only
                          +---------------------------+
```

**No port forwards. No DMZ. No DDNS. No static IP from Cox.** Your home IP never appears in
DNS. A port scan of your address finds nothing, because there is nothing.

> The network guide describes an optional port forward for reaching a lab service from the
> house. That one is different in kind: it lives on the **Asus WAN**, which faces the Cox
> LAN, not the internet. The Cox gateway gets no forwards at all, so the internet edge stays
> closed either way.

Double NAT stops mattering entirely — it only ever obstructed inbound connections, and there
are none.

---

## Part 1 — macOS as a headless server

A Mac mini running as a server needs settings a desktop Mac doesn't.

### Network

Don't set a static IP in macOS. The Asus reservation from the network guide already pins it
to `192.168.50.10` — one source of truth. Confirm:

```bash
ipconfig getifaddr en0        # expect 192.168.50.10
```

### Power and sleep

**System Settings -> Energy Saver:**

- **Prevent automatic sleeping when the display is off** — ON. A sleeping server is an
  offline server.
- **Start up automatically after a power failure** — ON. This is what gets you back after an
  outage while you're away.
- **Wake for network access** — ON.

### Remote access

**System Settings -> General -> Sharing:**

- **Remote Login (SSH)** — ON
- **Screen Sharing** — ON
- **File Sharing** — ON (configured in Part 4)

You'll reach all three over Tailscale, so they never need to face the internet.

### Firewall and updates

**System Settings -> Network -> Firewall:** ON, and under Options enable **stealth mode**.

**System Settings -> General -> Software Update -> Automatic Updates:** enable security
responses and system files at minimum.

### FileVault — read this before deciding

FileVault encrypts the disk. On a machine holding personal documents that sounds obviously
correct, and there's a real catch.

**With FileVault on, a reboot leaves the disk locked until someone logs in at the console.**
Nothing auto-starts. No SSH, no Tailscale, no tunnel — the services aren't merely stopped,
they're unreachable inside an encrypted volume. That "Start up automatically after a power
failure" setting above will faithfully power the Mac on and leave it sitting at a login
screen. If you're away from home, the server is down until you get back.

The honest options:

| Option | Tradeoff |
|---|---|
| **FileVault on**, unlock manually after outages | Disk encrypted at rest. Unattended reboots need physical presence |
| **FileVault on**, use authenticated restart for planned reboots | `sudo fdesetup authrestart` unlocks on the *next* boot only — good for updates you initiate, no help for a power cut |
| **FileVault off**, rely on physical security + encrypted backups | Survives reboots unattended. Anyone with physical access to the machine can read the disk |

There's no free answer — it's genuinely encryption-at-rest versus unattended availability.
For a machine at home holding personal documents, **FileVault on** is the defensible choice,
and pair it with a UPS so brief outages don't force a reboot at all. Decide deliberately
rather than discovering it during your first power cut.

```bash
# planned reboot with FileVault on — unlocks automatically on next boot
sudo fdesetup authrestart
```

---

## Part 2 — Private access with Tailscale

Set this up **first**. It's how you'll administer the machine for everything that follows,
and it means you never need the public path for management.

```bash
# on the Mac mini
brew install --cask tailscale
```

Launch it, sign in, then install Tailscale on your laptop and phone under the same account.
Every device gets a stable `100.x.y.z` address that works from anywhere.

```bash
tailscale status        # devices and their tailnet addresses
tailscale ip -4         # this machine's tailnet address
```

### Reaching the whole lab subnet remotely (optional)

Advertise the lab subnet so remote devices can reach *everything* on it, not just the Mac:

```bash
sudo tailscale up --advertise-routes=192.168.50.0/24
```

Then approve the route in the Tailscale admin console under **Machines -> Mac mini -> Route
settings**, and on client devices enable **Use Tailscale subnet routes**.

Now `192.168.50.x` works from anywhere — including the Asus admin page, which is otherwise
only reachable from inside the lab.

### Lock down management access

With Tailscale working, restrict SSH and Screen Sharing to the tailnet so they're not even
reachable from the lab subnet:

```bash
# check what is currently listening on all interfaces
sudo lsof -iTCP -sTCP:LISTEN -n -P
```

Use Tailscale ACLs in the admin console to limit which of your devices may reach the Mac
mini's management ports.

---

## Part 3 — Public web apps with Cloudflare Tunnel

You already own the domain. This moves its DNS to Cloudflare and serves apps through the
tunnel.

### 1. Move DNS to Cloudflare

Add the domain in the Cloudflare dashboard, let it import existing records, then change the
nameservers **at your current registrar** to the two Cloudflare gives you.

You are not transferring the domain — the registrar stays where it is. Only DNS moves.
Propagation typically takes minutes to a few hours.

> Check the imported records before switching. If the domain currently has live mail (MX
> records), confirm those imported correctly or you'll interrupt email.

### 2. Install and authenticate

```bash
brew install cloudflared
cloudflared tunnel login          # opens a browser, authorize your domain
```

### 3. Create the tunnel

```bash
cloudflared tunnel create bank-of-brennan
cloudflared tunnel list           # note the tunnel UUID
```

This writes a credentials JSON into `~/.cloudflared/`. **Back it up** — it is the tunnel's
identity.

### 4. Route hostnames to it

```bash
cloudflared tunnel route dns bank-of-brennan www.example.com
cloudflared tunnel route dns bank-of-brennan app.example.com
```

Each creates a proxied CNAME in Cloudflare DNS. Substitute your real domain.

### 5. Map hostnames to local ports

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <YOUR-TUNNEL-UUID>
credentials-file: /Users/<you>/.cloudflared/<YOUR-TUNNEL-UUID>.json

ingress:
  - hostname: www.example.com
    service: http://localhost:3000

  - hostname: app.example.com
    service: http://localhost:3001

  # required catch-all — must be last
  - service: http_status:404
```

One tunnel serves as many apps as you like, split by hostname. No reverse proxy needed. If
the service count grows past a handful, Caddy in front is worth adding — but not yet.

> **The security rule for this file:** an ingress entry is a door to the public internet.
> Only add one for something you intend strangers to reach. Never add one pointing at file
> storage, an admin panel, or a database.

### 6. Run it as a service

```bash
cloudflared tunnel run bank-of-brennan          # test in the foreground first
sudo cloudflared service install                # then install as a launchd service
```

The service survives reboots — subject to the FileVault behavior described in Part 1.

### TLS

Cloudflare terminates HTTPS at its edge and issues the certificate. No certbot, no renewals,
no cron job. Set **SSL/TLS mode to Full** in the dashboard.

### Two practical notes

- Cloudflare's free tier is intended for web content. Serving large volumes of video or
  bulk media through it runs against the terms of service — use dedicated storage for that.
- Cox residential terms nominally discourage running servers. An outbound tunnel doesn't
  look like or behave like a hosted server from the network's perspective, and inbound ports
  stay closed, which avoids the practical friction.

---

## Part 4 — Documents, and keeping them away from the public side

This is the part that actually matters. The networking is reversible; a document leak isn't.

One machine is doing two jobs with very different risk profiles: one is deliberately exposed
to strangers, the other holds personal files. Keep them separated **on the host**, not just
at the network edge.

### File sharing over SMB

**System Settings -> General -> Sharing -> File Sharing -> ⓘ**

- Add the documents folder as a shared folder
- Set per-user permissions explicitly — no "Everyone: Read Only"

This is reachable from the lab subnet and, because Tailscale is a normal network interface,
from your tailnet too. From a remote Mac: **Finder -> Go -> Connect to Server**

```
smb://100.x.y.z          # the Mac mini's Tailscale address
```

Full document access from anywhere, with **nothing published to the internet**.

### The separation rules

1. **Every public app runs in Docker, bound to localhost only.**

   ```yaml
   services:
     web:
       image: your-app
       ports:
         - "127.0.0.1:3000:3000"     # NOT "3000:3000"
   ```

   `"3000:3000"` binds to every interface, making the app reachable from anywhere on the lab
   subnet. `"127.0.0.1:3000:3000"` binds to loopback, so **only `cloudflared` can reach it**.
   That one prefix is the difference between one exposed service and one exposed machine.

2. **Documents are never bind-mounted into a container.** A web app compromise then reaches
   only its own container's files. Audit every `volumes:` entry against this.

3. **Run services under a separate macOS account**, not your personal one. Containers and
   the tunnel don't need access to your home directory.

4. **No document path ever appears in `config.yml`.** Worth re-reading that file whenever
   you add an app.

5. **SMB is never exposed through the tunnel.** Ever. If you later want browser-based file
   access from outside, that's a real project — authentication, hardening, its own
   container — not an ingress line.

### Verify the separation

```bash
# what is listening, and on which interface?
sudo lsof -iTCP -sTCP:LISTEN -n -P
```

Public app ports should show `127.0.0.1:3000`, not `*:3000`. Anything bound to `*` is
reachable from the whole lab subnet — fix it before moving on.

---

## Part 5 — Backups

**A single Mac mini is not a backup.** Drives fail, and the documents here are the kind you
can't re-download. Follow 3-2-1: three copies, two media types, one offsite.

### Copy 1 — the working data

The Mac mini itself. Not a backup, just the original.

### Copy 2 — Time Machine, local

Attach an external drive (2x your data size or more) and enable Time Machine. Gives you fast
restores and file-level version history for accidental deletes.

```bash
tmutil destinationinfo      # confirm the destination
tmutil latestbackup         # confirm backups are actually running
```

Encrypt the Time Machine volume — it holds everything the Mac does.

### Copy 3 — offsite, encrypted

Fire, theft, and flood take out the Mac and the drive sitting next to it together. Something
has to leave the building.

```bash
brew install restic
export B2_ACCOUNT_ID="..." B2_ACCOUNT_KEY="..."
restic -r b2:your-bucket:documents init
restic -r b2:your-bucket:documents backup ~/Documents
```

restic encrypts client-side, so the provider stores ciphertext it cannot read. Schedule it
daily with `launchd` or `cron`, then prune:

```bash
restic -r b2:your-bucket:documents forget \
  --keep-daily 7 --keep-weekly 4 --keep-monthly 12 --prune
```

Backblaze Personal is a fine simpler alternative if you'd rather not manage this.

### Retention protects you from more than disk failure

Keep versioned history, not just a mirror. A sync that faithfully replicates a ransomware
encryption or an accidental `rm -rf` has destroyed both copies. The `--keep-*` flags above
mean yesterday's good version survives today's mistake.

### Test a restore quarterly

Put it on the calendar.

```bash
restic -r b2:your-bucket:documents restore latest --target /tmp/restore-test
```

Open a few files and confirm they're intact. An untested backup is a hypothesis, not a
backup — and silent failures are the norm, not the exception.

---

## Verification

Work through all of these. Several test things that fail *silently* until you need them.

### Network

```bash
ipconfig getifaddr en0        # 192.168.50.10
ping -c 3 192.168.50.1        # Asus
ping -c 3 8.8.8.8             # internet
```

### Public site

Load it from your **phone on cellular, with WiFi turned off**. Testing from inside the
house can succeed for the wrong reasons and tells you nothing.

```bash
dig www.example.com +short    # Cloudflare addresses, never your home IP
```

If your home IP appears in DNS output, something is bypassing the tunnel.

### Private access

Also from cellular with WiFi off:

```bash
tailscale status
ping 100.x.y.z
ssh you@100.x.y.z
```

Then mount `smb://100.x.y.z` and open a document.

### Confirm nothing is exposed

The critical check. From **outside** your network, scan your home IP:

```bash
curl -s ifconfig.me           # run at home to learn your public IP
```

Then from an external scanner, confirm no open ports. With no forwards on the Cox gateway,
this should come back clean regardless of any Asus-side forward. **Specifically confirm port 445 (SMB) is closed** — that would mean
your documents are internet-facing.

### Unattended recovery — the one people skip

Pull the Mac mini's power cord. Plug it back in. Walk away for five minutes.

Then, without touching the machine, check that the public site loads and Tailscale
reconnects. **This is where FileVault behavior shows up in practice.** Far better to learn
it now than from a hotel room.

---

## Quick reference

| Thing | Where |
|---|---|
| Mac mini, lab subnet | `192.168.50.10` |
| Mac mini, tailnet | `tailscale ip -4` |
| Asus admin | `http://192.168.50.1` |
| Cox admin | `http://192.168.0.1` |
| Tunnel config | `~/.cloudflared/config.yml` |
| Tunnel logs | `sudo launchctl list \| grep cloudflared` |
| Listening ports | `sudo lsof -iTCP -sTCP:LISTEN -n -P` |
| Backup status | `restic -r b2:bucket:documents snapshots` |

### Back these up somewhere other than the Mac mini

- `~/.cloudflared/` — tunnel credentials; losing them means rebuilding the tunnel
- Tailscale account recovery details
- Asus configuration backup (**Administration -> Restore/Save/Upload Setting**)
- restic repository password — **without it the offsite backup is permanently unreadable**
