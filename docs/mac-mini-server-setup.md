# Setting Up the Mac Mini Server

Turning the Mac mini into a server that does two jobs:

1. **Holds your personal documents** — reachable at home and when you're away
2. **Runs public websites** — on the domain you own

Finish [home-subnet-setup.md](home-subnet-setup.md) first. This guide assumes the Mac mini is
plugged into the switch at `192.168.50.10` with working internet.

---

## 1. The idea, in plain English

You want strangers on the internet to reach your **website**, but absolutely nobody to reach
your **documents**. Same machine, opposite rules. Getting that right is most of this guide.

### The obvious approach, and why we're not using it

Normally, hosting a website from home means **port forwarding** — punching a hole through your
router so outside traffic can get in.

Three problems:

1. **You'd need two holes.** You have two receptionists now (Cox, then Asus). Traffic from
   outside has to get past both.
2. **Cox blocks the useful holes.** Websites live on slots 80 and 443. Cox blocks incoming
   traffic on those for home internet accounts. So the standard approach doesn't even work.
3. **A hole stays open.** Anyone on the internet can knock on it forever. That's a permanent
   thing to defend.

### What we do instead

Both access methods work by **calling out** from your Mac mini, rather than letting anything
call in.

Think of a phone call. Instead of publishing your number and waiting for calls, **your Mac mini
phones a big call center downtown and keeps the line open**. Visitors call the call center. The
call center passes them down the line that's already connected. Nobody ever learns your number.

| What you need | What does it | How |
|---|---|---|
| Public website | **Cloudflare Tunnel** | Your Mac phones Cloudflare and holds the line. Visitors reach Cloudflare, which passes them down |
| Your documents and private apps | **Tailscale** | A private hallway only your own devices can walk down |

**What this gets you:** no port forwards. No holes in either router. Your home address never
appears anywhere public. If someone scans your home internet address looking for open doors,
they find nothing — because there is nothing.

That "double NAT" thing people warn about? It only ever caused trouble for connections coming
*in*. You have none. It stops mattering.

---

## 2. More words you'll run into

| Word | What it means |
|---|---|
| **Server** | A computer whose job is answering other computers, not being sat in front of |
| **Headless** | A computer running with no monitor or keyboard attached |
| **SSH** | Controlling a computer by typing commands at it from another computer |
| **SMB** | The standard way to share folders over a network. What Finder uses |
| **TLS / HTTPS** | The padlock in the browser. Scrambles traffic so nobody in between can read it |
| **Docker / container** | A sealed box you run a program inside. It can only see what you hand it |
| **DNS nameservers** | The company that answers "what address is this domain?" |
| **Domain registrar** | Who you bought the domain name from |
| **localhost / `127.0.0.1`** | "This same computer." A program listening here can only be reached from the machine itself |

---

## 3. Getting macOS ready to be a server

A Mac that runs unattended in a corner needs different settings than a Mac you sit at.

### Step 1 — Confirm its address

**Why:** you pinned it to `192.168.50.10` back in the network guide. Confirm it took.

```bash
ipconfig getifaddr en0
```

**Expect:** `192.168.50.10`

**Don't set a static IP in macOS.** The router already decides addresses. Two places deciding is
how you get conflicts.

### Step 2 — Stop it going to sleep

**Why:** a sleeping server can't answer anybody. A laptop should sleep; a server must not.

**System Settings → Energy Saver:**

| Setting | Set to | Why |
|---|---|---|
| Prevent automatic sleeping when the display is off | **ON** | Otherwise it naps and your site goes down |
| Start up automatically after a power failure | **ON** | Comes back by itself after an outage — see the FileVault warning below |
| Wake for network access | **ON** | Lets it respond when something reaches out |

### Step 3 — Turn on remote control

**Why:** you need to run commands on it without sitting in front of it.

**System Settings → General → Sharing**, turn on:
- **Remote Login** — command-line access (SSH)
- **Screen Sharing** — see its desktop from another Mac
- **File Sharing** — how you'll reach documents (set up in section 6)

You'll reach all three through Tailscale, so none of them ever face the internet.

### Step 4 — Firewall and updates

- **System Settings → Network → Firewall:** ON. Under Options, turn on **stealth mode** (don't
  reply to strangers probing the machine)
- **System Settings → General → Software Update → Automatic Updates:** turn on security updates
  at minimum

### Step 5 — Decide about FileVault. Read this before you choose.

**FileVault** encrypts the disk, so someone who physically steals the Mac can't read your files.
On a machine holding personal documents that sounds like an obvious yes.

**Here's the catch, and it's a real one.**

With FileVault on, when the Mac restarts, **the disk stays locked until someone types the
password on the actual machine**. Nothing starts up. No remote access, no Tailscale, no website
— those programs are sitting inside a locked disk.

That "Start up automatically after a power failure" setting from Step 2 will faithfully power
the Mac on… and leave it sitting at a login screen. **If you're away from home when the power
blips, your server stays down until you physically get back to it.**

Your options, honestly:

| Choice | What you get | What it costs |
|---|---|---|
| **FileVault ON** | Files unreadable if the Mac is stolen | After any unexpected reboot, it's down until you're home |
| **FileVault ON + a UPS** *(recommended)* | Same protection, and a battery rides out short outages so it rarely reboots at all | Cost of a UPS (~$100) |
| **FileVault OFF** | Always comes back on its own | Anyone who physically takes the Mac can read everything |

There's no option that gives you both for free. It's genuinely a trade.

For a planned restart with FileVault on, this unlocks the disk automatically on the way back up:

```bash
sudo fdesetup authrestart
```

That only helps for restarts *you* start. It does nothing for a power cut.

---

## 4. Private access — set up Tailscale first

**Do this before anything else**, because it's how you'll manage the machine for everything
that follows.

**What Tailscale is:** it puts all your own devices on a private network of their own, no matter
where they physically are. Your laptop in a coffee shop acts like it's plugged in at home. It's
a private hallway with a locked door only your devices have a key to.

**Step 1 — install it on the Mac mini:**

```bash
brew install --cask tailscale
```

Open it, sign in.

**Step 2 — install it on your laptop and phone too**, signed into the same account.

**Step 3 — check it worked:**

```bash
tailscale status      # lists your devices
tailscale ip -4       # this machine's private address, starts with 100.
```

**You should see:** every device listed, each with an address starting `100.`

That `100.x` address works from anywhere in the world and never changes.

### Optional: reach your whole lab remotely

This lets remote devices reach *everything* on the lab network, not just the Mac mini —
including the Asus admin page.

```bash
sudo tailscale up --advertise-routes=192.168.50.0/24
```

Then approve it in the Tailscale admin website under **Machines → (your Mac) → Route settings**,
and on your laptop/phone turn on **Use Tailscale subnet routes**.

---

## 5. The public website — Cloudflare Tunnel

You already own a domain. These steps point it at Cloudflare and connect the tunnel.

### Step 1 — Move your domain's DNS to Cloudflare

**What this means:** DNS is the phone book that turns your domain name into an address.
You're changing *which company* runs your phone book entry. **You are not moving the domain
itself** — it stays bought from wherever you bought it.

1. Make a Cloudflare account, click **Add a site**, type your domain
2. Cloudflare copies your existing records — **check them**. If you get email at this domain,
   confirm the mail records (marked `MX`) came across, or your email will break
3. Cloudflare gives you two **nameserver** addresses
4. Go to your registrar (where you bought the domain) and replace its nameservers with those two

**You should see:** Cloudflare marks the domain **Active**, usually within a few hours.

### Step 2 — Install the tunnel program

```bash
brew install cloudflared
cloudflared tunnel login
```

**You should see:** a browser opens asking you to authorize your domain.

### Step 3 — Create the tunnel

```bash
cloudflared tunnel create bank-of-brennan
cloudflared tunnel list
```

**You should see:** a long ID made of letters and numbers. **Write it down** — the next step
needs it.

This also saves a credentials file in `~/.cloudflared/`. **Back that file up somewhere else.**
It's the tunnel's identity; lose it and you rebuild from scratch.

### Step 4 — Point your web addresses at the tunnel

```bash
cloudflared tunnel route dns bank-of-brennan www.example.com
cloudflared tunnel route dns bank-of-brennan app.example.com
```

Use your real domain. Each command tells the phone book to send that name to your tunnel.

### Step 5 — Say which address goes to which program

Create the file `~/.cloudflared/config.yml`:

```yaml
tunnel: PASTE-YOUR-TUNNEL-ID-HERE
credentials-file: /Users/YOURNAME/.cloudflared/PASTE-YOUR-TUNNEL-ID-HERE.json

ingress:
  # visitors asking for www.example.com get the program on slot 3000
  - hostname: www.example.com
    service: http://localhost:3000

  # visitors asking for app.example.com get the program on slot 3001
  - hostname: app.example.com
    service: http://localhost:3001

  # anything else gets a "not found". This line must be last
  - service: http_status:404
```

One tunnel handles as many sites as you want, split by name.

> **The most important rule in this file:** every line here is a **door to the public
> internet**. Only add one for something you *want* strangers to reach. Never point one at your
> documents, an admin page, or a database. When adding a site later, re-read this file and check
> nothing has crept in.

### Step 6 — Run it, then make it permanent

Test it first, watching for errors:

```bash
cloudflared tunnel run bank-of-brennan
```

**You should see:** connection messages, and your site loads in a browser. Press `Ctrl+C` to stop.

Then install it so it starts by itself:

```bash
sudo cloudflared service install
```

**About HTTPS:** Cloudflare provides the padlock automatically. No certificates to buy, install,
or renew. Just set **SSL/TLS mode** to **Full** in the Cloudflare dashboard.

**Two honest notes:**
- Cloudflare's free plan is for websites. Streaming lots of video through it goes against their
  terms — use proper storage for that
- Cox's home terms discourage running servers. An outgoing tunnel doesn't look like a server
  from the network's side, and you're opening no ports, which avoids the practical problem

---

## 6. Your documents — and keeping them away from the public side

**This is the section that matters most.** A networking mistake is reversible. A leaked document
isn't.

One machine is doing two jobs with opposite risk levels. Keeping them apart on the machine
itself matters as much as anything you did on the routers.

### Sharing the documents folder

**System Settings → General → Sharing → File Sharing → ⓘ**

1. Add your documents folder
2. Set who can access it explicitly — **never** leave "Everyone: Read Only"

**To reach it from another Mac at home or over Tailscale:** Finder → **Go → Connect to Server**

```
smb://100.x.y.z          # the Mac mini's Tailscale address
```

Full access to your documents from anywhere, with **nothing published to the internet**.

### The five rules that keep documents safe

**Rule 1 — run every public web app in a container, listening only to itself.**

This is the single most important technical detail in this project.

```yaml
ports:
  - "127.0.0.1:3000:3000"     # ✅ correct
```

```yaml
ports:
  - "3000:3000"               # ❌ dangerous
```

**What the difference actually does:**

- `"3000:3000"` means **"anyone who can reach this machine on slot 3000, come on in."** Every
  device on your lab network can reach it.
- `"127.0.0.1:3000:3000"` means **"only programs running on this very same computer may
  knock."** Nothing else on the network can reach it at all.

Since `cloudflared` runs on that same machine, **it can still reach the app — and it's the only
thing that can.** Every visitor to your website is funneled through the tunnel, because there is
no other way in.

That one prefix is the difference between exposing one website and exposing the whole machine.

**Rule 2 — never hand your documents folder to a container.** Containers only see what you give
them. If a website ever gets compromised, the attacker is stuck inside that sealed box with
nothing of yours in it. Check every `volumes:` line you write.

**Rule 3 — run the services under a separate Mac user account**, not your personal one. Websites
have no business having access to your home folder.

**Rule 4 — no documents folder ever appears in `config.yml`.** That file lists things the public
can reach.

**Rule 5 — never put file sharing through the tunnel.** If you later want documents in a browser
from anywhere, that's a real project with logins and hardening — not a line in a config file.

### Check the rules are holding

```bash
sudo lsof -iTCP -sTCP:LISTEN -n -P
```

This lists every program waiting for connections, and who's allowed to reach it.

- **Want to see:** `127.0.0.1:3000` — locked to this machine
- **Warning sign:** `*:3000` — the `*` means *anyone on the network*. Fix it before continuing

---

## 7. Backups

**One Mac mini is not a backup.** Drives fail with no warning, and these are documents you can't
just download again.

The standard rule is **3-2-1**: three copies, on two kinds of storage, one of them somewhere
else. Each copy survives a different disaster:

| Copy | Where | What it saves you from |
|---|---|---|
| 1 | The Mac mini | Nothing — this is the original |
| 2 | External drive, Time Machine | Drive failure, and deleting something by accident |
| 3 | Online, encrypted | Fire, flood, theft — anything that takes the whole room |

Copy 3 matters more than people expect. A burglar takes the Mac *and* the drive plugged into it.

### Copy 2 — Time Machine

Plug in an external drive (at least twice the size of your data) and turn on Time Machine.
**Encrypt the drive** when it asks — it will hold everything the Mac does.

```bash
tmutil destinationinfo      # where it's backing up to
tmutil latestbackup         # when it last actually ran
```

### Copy 3 — offsite

```bash
brew install restic
export B2_ACCOUNT_ID="..." B2_ACCOUNT_KEY="..."
restic -r b2:your-bucket:documents init
restic -r b2:your-bucket:documents backup ~/Documents
```

`restic` scrambles your files **before** they leave the house, so the storage company holds
data they can't read.

Once it works, schedule it daily, and trim old copies so it doesn't grow forever:

```bash
restic -r b2:your-bucket:documents forget \
  --keep-daily 7 --keep-weekly 4 --keep-monthly 12 --prune
```

*(Backblaze Personal is a simpler alternative if you'd rather not manage this yourself.)*

### Why keep old versions instead of just a copy

If something quietly corrupts or encrypts your files and your backup just *mirrors* whatever's
there, it dutifully copies the damage over your good backup. Now both copies are ruined.

Keeping a week of daily versions means yesterday's good copy is still sitting there.

### Test a restore every few months — put it on the calendar

```bash
restic -r b2:your-bucket:documents restore latest --target /tmp/restore-test
```

Open a few files. Confirm they're really intact.

**A backup you've never restored from isn't a backup, it's a hope.** Backups fail silently far
more often than people expect, and you find out at the worst possible moment.

---

## 8. Check your work

Several of these fail *silently* — everything looks fine until the day you need it.

### The network

```bash
ipconfig getifaddr en0        # 192.168.50.10
ping -c 3 192.168.50.1        # the Asus
ping -c 3 8.8.8.8             # the internet
```

### The public site

**Load it on your phone with WiFi turned OFF, on cellular.**

This matters. Testing from inside your house can succeed for reasons that have nothing to do
with whether the internet can reach you. Cellular is a genuine outside test.

```bash
dig www.example.com +short
```

**Expect:** Cloudflare addresses. **If your home internet address shows up here, stop** —
something is bypassing the tunnel and exposing your house directly.

### Private access

Also on cellular, WiFi off:

```bash
tailscale status
ssh you@100.x.y.z
```

Then connect to `smb://100.x.y.z` in Finder and open a document.

### Prove nothing is exposed

Find your home address (run this at home):

```bash
curl -s ifconfig.me
```

Then from **outside** your network, check that address for open doors. With no port forwards
set up, it should come back with nothing open.

**Check slot 445 specifically.** That's file sharing. If it's open, your documents are facing
the internet and that needs fixing immediately.

### The test everybody skips

**Pull the Mac mini's power cord out. Plug it back in. Walk away for five minutes.**

Then, without touching the machine, check that your website loads and Tailscale reconnects.

This is where the FileVault behavior from section 3 shows up for real. Much better to find out
now, at home, than from a hotel room.

---

## 9. Quick reference

| Thing | Where |
|---|---|
| Mac mini on the lab network | `192.168.50.10` |
| Mac mini from anywhere | `tailscale ip -4` |
| Asus admin | `http://192.168.50.1` |
| Cox admin | `http://192.168.0.1` |
| Tunnel settings | `~/.cloudflared/config.yml` |
| What's listening, and to whom | `sudo lsof -iTCP -sTCP:LISTEN -n -P` |
| Backup history | `restic -r b2:bucket:documents snapshots` |

### Copy these somewhere that isn't the Mac mini

| What | Why it matters |
|---|---|
| The `~/.cloudflared/` folder | Your tunnel's identity. Lose it, rebuild the tunnel |
| Your restic repository password | **Without it your offsite backup can never be read. Not by you, not by anyone** |
| Tailscale account recovery info | How you get back in if you lose your devices |
| Asus settings export | **Administration → Restore/Save/Upload Setting** — saves redoing this guide |
