# Home Lab Subnet Setup

Building an isolated lab subnet behind a Cox Panoramic Wifi Gateway, using an Asus router
and a switch. Written for a first-time setup — every step says *why*, not just *what*.

The host that lives on this subnet is covered separately in
[mac-mini-server-setup.md](mac-mini-server-setup.md). Do the network first; the server
setup assumes it's working.

---

## The one thing people get wrong

The ethernet cable runs from a **LAN port on the Cox gateway** into the **WAN port on the
Asus**.

The Cox gateway's WAN is the coax coming in from the street — it's already occupied. The
Asus's WAN port is what makes it a *router* rather than just another box on the network,
and it's what creates the second subnet.

If you plug LAN → LAN instead, both routers end up on one flat network with two DHCP
servers handing out conflicting addresses. Symptoms: devices randomly get the wrong
gateway, some have internet and some don't, and it changes every time something reconnects.
No subnet is created at all. It's the single most common failure and it looks like a
hardware problem.

---

## Target layout

```
  [ Coax from street ]
          |
  +-----------------------+
  | Cox Panoramic Gateway |  192.168.0.1/24   <- main house network, Cox WiFi
  +-----------+-----------+
              |  LAN port  ->  WAN port
  +-----------+-----------+
  |     Asus Router       |  WAN: 192.168.0.50   LAN: 192.168.50.1/24
  +-----------+-----------+
              |  LAN port  ->  switch uplink
  +-----------+-----------+
  |    Unmanaged Switch   |
  +-----------+-----------+
              |
        +-----+------+
        |  Mac mini  |  192.168.50.10
        +------------+
        (plus any other lab gear)
```

Two separate networks. The house keeps using Cox WiFi exactly as before and nothing about
it changes. The lab lives behind the Asus, invisible from the house side.

---

## What this gets you

| Direction | Works? | Why |
|---|---|---|
| Lab -> internet | Yes | Traffic NATs out through the Asus, then through Cox |
| Lab -> main house network | **Yes** | Lab traffic NATs onto the Cox subnet; house devices just see the Asus |
| Main house network -> lab | **No** | The Asus firewall drops unsolicited inbound. This *is* the isolation |
| Main network -> one specific lab service | Yes, with a port forward | See [Reaching a lab service from the house](#reaching-a-lab-service-from-the-house) |

That third row is the security boundary. A compromised device on the house network — a
smart TV, a guest's laptop — cannot see or reach anything in the lab.

The asymmetry in rows 2 and 3 surprises people, so it's worth stating plainly: **the lab
can reach the house, but the house cannot reach the lab.** That's normal NAT behavior, and
it's the direction you want.

---

## Before you start

**You'll need:** two ethernet cables (Cox->Asus, Asus->switch) plus one per device, the
Asus admin password (on the label underneath), and access to your Cox gateway admin.

### Step 0: find out what subnet Cox is using — do this first

From any device currently on your home WiFi:

```bash
# macOS / Linux
ip route | grep default        # Linux
route -n get default           # macOS

# Windows
ipconfig
```

Look for the default gateway. It's almost always `192.168.0.1`, sometimes `10.0.0.1`.

**Write it down.** Everything below assumes `192.168.0.1`; substitute yours if different.

> **Collision check:** if Cox is using `192.168.50.x`, that collides with the Asus default
> and nothing will work. Use `192.168.60.1` for the Asus LAN instead of `192.168.50.1`
> everywhere in this document. Two routers cannot use the same subnet — traffic has no way
> to know which side an address is on.

### Step 1: update the Asus firmware first

Power on the Asus by itself, connect a laptop to one of its LAN ports, go to
`http://192.168.50.1`, and run **Administration -> Firmware Upgrade**.

Do this *before* configuring anything. Firmware updates occasionally reset settings, and
you'd rather lose five minutes of work than an hour of it.

---

## Cabling

1. **Cox LAN port -> Asus WAN port.** The Asus WAN port is usually blue, physically
   separated from the LAN ports, and labeled WAN or Internet.
2. **Asus LAN port -> switch.** Any LAN port on the Asus, any port on the switch.
   **Exactly one cable.** Two cables between the same two devices creates a switching loop
   that will flood the network and take it down.
3. **Everything else -> switch.** Mac mini, any other lab gear.

Do not:
- run Cox LAN -> Asus **LAN** (see the top of this document)
- run a second cable between the Asus and the switch
- daisy-chain the switch back to the Cox gateway

---

## Cox gateway configuration

Deliberately minimal. The less you change here, the less there is to break — and rented
Panoramic gateways expose limited settings anyway.

### Reserve the Asus a fixed address

In the Cox admin (either `http://192.168.0.1` or the **Cox Panoramic Wifi app** — the app
has more capability on newer gateways), find the connected-devices list, locate the Asus
router, and set a **DHCP reservation** to `192.168.0.50`.

Why: the Asus's WAN address needs to stay put. If it changes on a lease renewal, any port
forward pointing at it silently breaks and you'll be debugging the wrong layer.

### Leave everything else alone

- **Keep Cox WiFi enabled.** It remains the main house network.
- You do **not** need bridge mode, DMZ, or any port forwarding on the Cox gateway.
- The Cox app may list the Asus as an unknown or unmanaged device, and may report devices
  behind it as "offline". That's expected — it genuinely cannot see into the lab subnet.

---

## Asus router configuration

Connect a laptop to an Asus LAN port and go to `http://192.168.50.1`.

### 1. Operation mode — the setting that matters most

**Administration -> Operation Mode -> Wireless router mode**

> **Do not choose Access Point (AP) mode.** AP mode turns off routing and NAT and makes the
> Asus a dumb extension of the Cox network. Everything will appear to work — internet, WiFi,
> devices connect fine — but there will be no second subnet and no isolation whatsoever. If
> you finish this whole guide and find every device sitting on `192.168.0.x`, this setting
> is why.

### 2. WAN

**WAN -> Internet Connection**

- WAN Connection Type: **Automatic IP (DHCP)**
- Enable UPnP: **No**

UPnP lets any application on the subnet open its own inbound holes without asking. For a
server network you want forwards to be deliberate and few. Nothing in this setup needs it.

### 3. LAN and DHCP

**LAN -> LAN IP**

- IP Address: `192.168.50.1`
- Subnet Mask: `255.255.255.0`

**LAN -> DHCP Server**

- Enable DHCP Server: **Yes**
- IP Pool Starting Address: `192.168.50.100`
- IP Pool Ending Address: `192.168.50.200`

This leaves `.2` through `.99` free for servers with fixed addresses, so automatic
assignments can never collide with something you pinned by hand.

**Manually Assigned IP around the DHCP list** — add a reservation:

- Mac mini -> `192.168.50.10`

Reserve it here rather than setting a static IP on the Mac itself. One source of truth, no
risk of configuring an address the router later hands to something else. The Mac still
"does DHCP" and just always gets the same answer.

### 4. Lock down admin access

**Administration -> System**

- Change the router login password from the default
- **Enable Web Access from WAN: No**

The second one matters. Left on, your router's admin page is reachable from the internet,
and routers are scanned constantly.

### 5. WiFi (optional)

**Wireless -> General** — give the Asus its own SSID, distinct from the Cox one, for
wireless lab gear. Anything joining it lands on the lab subnet.

---

## Address plan

Keep this filled in — you'll refer back to it.

| Role | Address |
|---|---|
| Cox gateway / main house LAN | `192.168.0.1` — `192.168.0.0/24` |
| Asus WAN | `192.168.0.50` (reserved on Cox) |
| Asus LAN / lab gateway | `192.168.50.1` — `192.168.50.0/24` |
| **Mac mini** | `192.168.50.10` (reserved on Asus) |
| Other fixed lab hosts | `192.168.50.2` – `192.168.50.99` |
| Lab DHCP pool | `192.168.50.100` – `192.168.50.200` |

---

## Reaching a lab service from the house

Say the Mac mini serves something on port 5000 and you want it reachable from a laptop on
the house WiFi.

**Asus -> WAN -> Virtual Server / Port Forwarding:**

| Field | Value |
|---|---|
| Service Name | `mac-mini-5000` |
| External Port | `5000` |
| Internal IP | `192.168.50.10` |
| Internal Port | `5000` |
| Protocol | TCP |

Now from any house device: `http://192.168.0.50:5000`

**No Cox configuration is needed.** The Asus's WAN address sits on the Cox subnet, so house
devices can already reach it directly — you're just telling the Asus what to do with that
knock. This is why rented gateways not supporting static routes doesn't matter here.

### What won't work across the boundary

**mDNS and broadcast discovery do not cross subnets.** AirPlay, Chromecast, AirPrint,
"nearby device" pairing, and most printer auto-setup rely on broadcast traffic that stops
at the router. Devices that need to *discover* each other must live on the same side.

This is worth deciding before you move anything: a printer used by the whole house belongs
on the Cox side. Reaching it by IP from the lab still works fine (lab -> house is allowed);
it just won't appear in a "nearby printers" list.

---

## Verification

Run these **in order** from a device plugged into the switch. Each step tests exactly one
layer, so the first failure tells you precisely where the problem is.

```bash
# 1. Did I get a lab address?
ip a            # Linux        -> expect 192.168.50.x
ipconfig        # Windows
ifconfig en0    # macOS

# 2. Can I reach my own gateway (the Asus)?
ping 192.168.50.1

# 3. Can I reach the Cox gateway through the Asus?
ping 192.168.0.1

# 4. Can I reach the internet?
ping 8.8.8.8

# 5. Does DNS work?
nslookup google.com

# 6. Is the path actually two hops?
traceroute 8.8.8.8      # macOS/Linux
tracert 8.8.8.8         # Windows
```

Reading the results:

| First failure | What it means |
|---|---|
| Step 1 — no `192.168.50.x` | Asus DHCP off, or you're plugged into the wrong network |
| Step 1 — got `192.168.0.x` | **AP mode is on**, or the cable is LAN->LAN |
| Step 2 | Cable or switch problem between you and the Asus |
| Step 3 | Asus WAN isn't connected — check the Cox->Asus cable, and the Asus WAN status page |
| Step 4 | Routing or upstream issue; check whether the house network itself is up |
| Step 5 | Connectivity is fine, DNS isn't — set the Asus WAN DNS to `1.1.1.1` and retest |
| Step 6 | Should show `192.168.50.1`, then `192.168.0.1`, then Cox infrastructure. Two private hops = the subnet is real |

Then confirm the isolation actually holds. **From a device on the main Cox WiFi:**

```bash
ping 192.168.50.10
```

**This should fail.** A timeout here is the whole point — it means the house cannot reach
the lab. If it succeeds, you do not have an isolated subnet; re-check operation mode and
cabling.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| No internet on lab devices | Cable in an Asus **LAN** port instead of WAN |
| Everything landed on `192.168.0.x` | Asus is in **AP mode** — switch to Wireless router mode |
| Works, then drops randomly, addresses change | Subnet collision — Cox and Asus on the same range |
| Asus WAN shows `0.0.0.0` or "Disconnected" | Cox gateway needs a reboot to issue a lease. Power-cycle Cox, wait for it to fully come up, then reboot the Asus |
| Port forward works from outside, not from inside the lab | NAT loopback (hairpinning). Use the internal address `192.168.50.10:5000` from within the lab instead |
| Some lab devices fast, others slow | Bad cable or a 100 Mbps port. Check switch link lights — gigabit usually shows a different color |
| Can't reach the Asus admin page | You're on the house side. Admin is only reachable from the lab side by design |

---

## Alternatives not chosen

**Cox gateway in bridge mode.** Turns the Cox box into a plain modem, making the Asus the
only router. This eliminates double NAT and is cleaner networking. Not chosen because it
moves the *entire house* onto the Asus and removes Cox WiFi — the goal here was to leave
the house network untouched. Worth revisiting if you ever want the Asus running everything.

**VLANs on a managed switch.** The textbook segmentation answer, and more flexible than a
second router. Needs a managed switch and better VLAN support than stock Asus firmware
provides. A reasonable future upgrade; unnecessary complexity for a single lab subnet.

**Double NAT** — traffic passing through two NAT layers — is a non-issue for this setup.
It only causes trouble for inbound connections, and the server setup uses outbound-only
tunnels that never need one. See [mac-mini-server-setup.md](mac-mini-server-setup.md).
