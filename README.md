# bank_of_brennan

A home lab: a private network behind the house internet connection, with a Mac mini that
stores personal documents and hosts public websites.

Written for someone doing this for the first time. Every step says what to do, why it exists,
and what you should see when it worked.

## The guides

| Guide | What it covers |
|---|---|
| **1.** [docs/home-subnet-setup.md](docs/home-subnet-setup.md) | Plugging things in, setting up the router, checking it works |
| **2.** [docs/mac-mini-server-setup.md](docs/mac-mini-server-setup.md) | The Mac mini: websites, documents, keeping them apart, backups |

Do them in that order — the second assumes the first is finished.

## What gets built

```
  Cox Panoramic Gateway   192.168.0.1      <- the house network, unchanged
            |  a cable from a LAN port to the WAN port
      ASUS RT-AC68P       192.168.50.1     <- the private lab network
            |
        Switch
            |
      Mac mini            192.168.50.10
```

The house network carries on exactly as before and **cannot reach into the lab**. The lab
reaches the internet normally.

## How things get reached from outside

Nothing is exposed by opening holes in the routers. Instead the Mac mini **calls out** and
keeps the line open:

- **Public websites** — Cloudflare Tunnel, with HTTPS handled for you
- **Documents and private apps** — Tailscale, reachable only by your own devices

So: no open ports, no dynamic DNS, no static IP needed, and your home internet address never
appears in public.

## Addresses

| Address | What it is |
|---|---|
| `192.168.0.1` | Cox gateway |
| `192.168.0.50` | The Asus, as seen by the house network |
| `192.168.50.1` | The Asus, as seen by the lab — its admin page |
| `192.168.50.10` | Mac mini |
| `192.168.50.2` – `.99` | Free for devices you pin by hand |
| `192.168.50.100` – `.200` | Handed out automatically |

## Hardware

- **ASUS RT-AC68P** — dual-band gigabit router (setup page: `router.asus.com`)
- **Cox Panoramic Wifi Gateway** — modem and house router, rented
- Unmanaged gigabit switch
- Mac mini
