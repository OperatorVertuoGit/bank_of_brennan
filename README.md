# bank_of_brennan

Home lab: an isolated network subnet behind the house internet connection, with a Mac mini
serving personal document storage and public web applications.

## Setup guides

| Guide | Covers |
|---|---|
| [docs/home-subnet-setup.md](docs/home-subnet-setup.md) | Cabling, Cox gateway, Asus router, switch, address plan, verification |
| [docs/mac-mini-server-setup.md](docs/mac-mini-server-setup.md) | macOS as a headless server, Cloudflare Tunnel, Tailscale, keeping documents private, backups |

Do them in that order — the server setup assumes the subnet is working.

## Architecture

```
  Cox Panoramic Gateway   192.168.0.1/24     <- main house network
            |  LAN -> WAN
      Asus Router         192.168.50.1/24    <- isolated lab subnet
            |
        Switch
            |
      Mac mini            192.168.50.10
```

The house network is untouched and cannot reach the lab. The lab reaches the internet
normally.

## Access model

Nothing is exposed by port forwarding. Both access paths dial **outward** from the Mac mini:

- **Public web apps** — Cloudflare Tunnel, TLS terminated at Cloudflare
- **Private apps and documents** — Tailscale, reachable only from your own devices

No open inbound ports, no DDNS, no static IP, and the home IP address never appears in
public DNS.

| Address | Purpose |
|---|---|
| `192.168.0.1` | Cox gateway |
| `192.168.0.50` | Asus WAN (reserved on Cox) |
| `192.168.50.1` | Asus LAN / lab gateway |
| `192.168.50.10` | Mac mini |
| `192.168.50.2` – `.99` | Fixed lab addresses |
| `192.168.50.100` – `.200` | Lab DHCP pool |
