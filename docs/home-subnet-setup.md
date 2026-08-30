# Setting Up Your Home Lab Network

A step-by-step guide, assuming you've never done this before. Every step says what to do,
why it exists, and what you should see when it worked.

Do this guide first. The Mac mini guide, [mac-mini-server-setup.md](mac-mini-server-setup.md),
assumes the network here is finished and working.

---

## 1. What you're building, in plain English

Right now you have one network. Everything in your house — phones, TVs, laptops — sits on it
together, handed out by the white Cox box.

You're adding a **second network behind the first one**. Your Mac mini and lab gear live on the
second one. The rest of the house keeps using the first one and never notices anything changed.

**Why bother?** Two reasons:

1. **Safety.** Your Mac mini will hold personal documents *and* serve a public website. If
   something on the house network gets compromised — a smart TV, a guest's laptop — it can't
   even see your lab, let alone reach it.
2. **Control.** Cox's box gives you very few settings. Your own router gives you all of them.

### The office building picture

This metaphor is used all the way through this guide, so it's worth two minutes now.

Imagine an office building:

- A **router** is a **receptionist**. Mail and visitors pass through them to get in or out.
- The Cox box is the **building's** receptionist. Everyone in the house goes through them.
- Your Asus router is a **second receptionist**, for a **private suite** inside the building.
- Your **subnet** is that private suite. It has its own rooms and its own room numbers.

Everything below is just: hiring the second receptionist, and telling them the rules.

---

## 2. Words you'll run into

You don't need to memorize these. Skim now, come back when a step uses one.

| Word | What it actually means |
|---|---|
| **IP address** | A room number, like `192.168.0.1`. Every device on a network gets one |
| **Subnet** | One group of room numbers that belong together — your private suite |
| **Router** | The receptionist. Passes traffic between two networks |
| **Switch** | A power strip, but for network cables. No brains, just more sockets |
| **WAN port** | The router's **door to the street**. Where the outside world connects |
| **LAN ports** | The router's **doors to rooms inside**. Where your own devices connect |
| **DHCP** | The receptionist handing out room numbers automatically as devices arrive |
| **NAT** | The receptionist putting *their own* return address on all outgoing mail |
| **Firewall** | The receptionist turning away visitors nobody invited |
| **Port** | A numbered mail slot on a device. Websites use slot 80 and 443; your apps pick their own |
| **Port forward** | A standing instruction: "anyone asking for slot 5000, send them to the Mac mini" |
| **DNS** | The phone book. Turns `google.com` into an address a computer can dial |

**NAT is the one worth actually understanding**, because it explains something confusing later.
When your Mac mini sends mail out, the Asus receptionist replaces the return address with their
own. So replies come back to the receptionist, who forwards them in. The outside world never
learns your Mac mini's room number — which is *why* the house can't reach into your lab.

---

## 3. Your equipment and what each piece does

| Device | Job |
|---|---|
| **Cox Panoramic Gateway** (white box) | Building receptionist. Talks to Cox over the coax cable. Runs the house WiFi |
| **ASUS RT-AC68P** (black box with antennas) | Your private suite's receptionist. Creates the second network |
| **Network switch** | Extra sockets. Splits one cable from the Asus into many |
| **Mac mini** | Your server. Holds documents, runs your websites |

Your Asus is an **RT-AC68P**. Its own label tells you two useful things:

- Setup address: **`http://router.asus.com`**
- Factory login: username `admin`, password `admin` — you'll change this

> **Note about the address.** Some guides say to visit `192.168.50.1` to set up an ASUS router.
> **That is not this model.** This one starts at `192.168.1.1`, or just use
> `router.asus.com`, which works either way. Later in Step 8 you'll deliberately change the
> address to `192.168.50.1` — after that, `192.168.50.1` becomes correct. Don't be thrown when
> the address changes partway through; that's you doing it on purpose.

---

## 4. The one mistake to avoid

The cable between the Cox box and the Asus has a right way and a wrong way round.

**Correct:** a **LAN port on the Cox box** → the **WAN port on the Asus**.

In the building picture: you're running a wire from a door *inside* the building to the private
suite's *street door*. The suite's street door is how the suite reaches the rest of the world.

**If you get it backwards** (Cox LAN → Asus **LAN**), you've connected two rooms to each other
with no receptionist in between. Both receptionists start handing out room numbers at once, and
they don't coordinate. Devices get conflicting numbers, some have internet and some don't, and
it changes every time something reconnects. No second network is created at all.

It looks exactly like broken hardware. It isn't. It's this.

---

## 5. Figure out what's already plugged in

Your Asus already has cables in it, so before changing anything, work out which ports they're
in. On the RT-AC68P, the back panel goes, in order:

```
[ 4 ] [ 3 ] [ 2 ] [ 1 ]     [ WAN ]   [ USB 3.0 ]   [ USB 2.0 ]
 <---- yellow ---->          blue        blue
                            globe icon
```

- Four **yellow** sockets, numbered **4, 3, 2, 1**. These are LAN — doors to rooms inside.
- Then one **blue** socket with a small **globe** icon. **This is WAN** — the street door.
- Then a **second blue socket** just past it. **This is USB 3.0, not a network port.** It's a
  different shape and this is the easiest thing to mix up.

**The reliable way to check** — much better than squinting at the back of the router:

1. Connect a laptop to any **yellow** port on the Asus with a cable
2. Open a browser and go to **`http://router.asus.com`**
3. Log in (`admin` / `admin` if it's never been set up)
4. Look at **Network Map**, then **Internet status**

| What you see | What it means |
|---|---|
| An address like `192.168.0.x` | The cable is in the WAN port. Correct |
| `0.0.0.0`, blank, or "Disconnected" | It is **not** in the WAN port (or the Cox end is unplugged) |

---

## 6. Step-by-step

### Step 1 — Find out what address the Cox box uses

**Why:** two networks can't use the same range of room numbers. You need to know Cox's range so
you can pick a different one.

**Do this** from any device already on your home WiFi:

```bash
route -n get default        # Mac
ip route | grep default     # Linux
ipconfig                    # Windows
```

**You should see:** a "gateway" address. Almost always `192.168.0.1`, sometimes `10.0.0.1`.

**Write it down.** This guide assumes `192.168.0.1` — if yours differs, substitute it everywhere.

> **If it says `192.168.50.x`:** that collides with the address you're about to give the Asus.
> Use `192.168.60.1` instead of `192.168.50.1` everywhere below.

---

### Step 2 — Clean the dust out

**Why:** the RT-AC68P runs hot, and an overheating router drops connections at random. That
symptom is maddening to diagnose because everything *looks* configured correctly. Yours has
visible dust in the cooling fins.

**Do this:** unplug it, blow compressed air through the fins, make sure nothing blocks the vents
where it sits.

---

### Step 3 — Factory reset the Asus

**Why:** this router has been used before. If a previous setup left a changed password, you'll
be locked out three steps from now with no way forward.

**Do this:**
1. With the router powered on, press and hold the **Reset** button (small recessed hole on the
   back — use a paperclip) for about **10 seconds**
2. Release when the power light starts flashing
3. Wait about 2 minutes for it to come back up

**You should see:** the power light goes solid again, and `admin`/`admin` works at
`http://router.asus.com`.

---

### Step 4 — Update the router's firmware

**Why:** firmware is the router's own software. Updates fix security holes. Do it **now**,
because updates sometimes wipe settings — better to lose nothing than an hour of work.

**Do this:**
1. Connect a laptop to a **yellow** port on the Asus
2. Go to **`http://router.asus.com`**, log in
3. Go to **Administration → Firmware Upgrade**
4. Click **Check** and install anything offered

**You should see:** the router reboots and reports the new version. Takes about 5 minutes.
**Don't unplug it while this runs.**

---

### Step 5 — Plug in the cables

**Why:** this is the physical shape of the whole setup.

**Do this, in this order:**

1. **Cox box LAN port → Asus WAN port** (the blue one with the globe icon, *not* the blue USB
   one next to it)
2. **Asus yellow port → switch.** Any yellow port, any socket on the switch. **Exactly one
   cable** between them — two cables between the same pair of devices creates a loop that floods
   the network and takes it down
3. **Mac mini and other lab gear → switch**

**You should see:** link lights come on at both ends of each cable within about 10 seconds.

**Do not:**
- Run Cox LAN → Asus **LAN** (see section 4)
- Run a second cable between the Asus and the switch
- Run a cable from the switch back to the Cox box

> Also: there's a plant sitting in the Cox box's port bank. Move it. Water and live network
> gear don't mix, and leaves block the vents.

---

### Step 6 — Give the Asus a permanent address on the Cox network

**Why:** the Cox box hands out addresses that can change over time. If the Asus's address moves,
anything pointing at it silently breaks and you'll waste an evening debugging the wrong thing.
Pinning it means it never moves.

**Do this:**
1. Open the Cox admin — either `http://192.168.0.1` in a browser, or the **Cox Panoramic Wifi
   app** (the app can do more on newer boxes)
2. Find the list of connected devices
3. Find the Asus router in the list
4. Set a **DHCP reservation** (sometimes called "reserved IP" or "static lease") to
   **`192.168.0.50`**

**Finding the Asus in that list:** the label underneath it reads
**MAC: `1C:B7:2C:92:CD:B8`**. A MAC address is a permanent serial number for a network port.

> **Small catch:** the MAC on the label is the *LAN* one, and the WAN MAC is often one digit
> different. So match against whatever Cox actually shows for the router rather than assuming
> the label number appears exactly. If you're unsure, the Asus shows its WAN MAC under
> **Network Map → Internet status**.

**You should see:** the Cox device list shows the Asus pinned to `192.168.0.50`.

**Leave everything else on the Cox box alone.** Keep Cox WiFi on — it stays the house network.
You don't need bridge mode, DMZ, or port forwarding here.

> **Expected weirdness:** the Cox app may show the Asus as an unknown device, and show lab
> devices as offline. That's correct — it genuinely can't see inside your suite.

---

### Step 7 — Make sure the Asus is actually being a router

**Why:** this is the single most important setting in this guide. Routers can run in a mode
where they stop being a receptionist and become just a hallway. In that mode everything
*appears* to work — internet fine, WiFi fine — but there's no second network and no protection
at all.

**Do this:**
1. **Administration → Operation Mode**
2. Choose **Wireless router mode**
3. Save

> **Do not choose Access Point (AP) mode.** That's the "just a hallway" mode. If you finish this
> entire guide and find every device has an address starting `192.168.0.`, this setting is why.

**You should see:** the router reboots and reports Wireless router mode.

---

### Step 8 — Set up the private suite's room numbers

**Why:** you're choosing the address range for your lab, and telling the Asus how to hand out
numbers. Splitting the range matters: some devices should always get the same number, others can
take whatever's free.

**Do this — part A, the router's own address:**

1. Go to **LAN → LAN IP**
2. IP Address: **`192.168.50.1`**
3. Subnet Mask: **`255.255.255.0`**
4. Save

> **The router's address just changed.** Your browser will lose the page — that's expected, not
> a failure. From now on the Asus lives at **`http://192.168.50.1`**. You may need to unplug and
> replug your laptop's cable to pick up a new address.

**Do this — part B, automatic numbers:**

1. Go to **LAN → DHCP Server**
2. Enable DHCP Server: **Yes**
3. IP Pool Starting Address: **`192.168.50.100`**
4. IP Pool Ending Address: **`192.168.50.200`**
5. Save

This means automatic numbers come from `.100`–`.200`, leaving `.2`–`.99` free for devices you
pin by hand. That way an automatic assignment can never collide with a pinned one.

**Do this — part C, pin the Mac mini:**

1. Same page, find **Manually Assigned IP around the DHCP list**
2. Enable it
3. Add the Mac mini's MAC address → **`192.168.50.10`**
4. Save

> **Pin it here, not on the Mac.** One place decides addresses, so nothing can conflict. The Mac
> still asks for an address normally — it just always gets the same answer.

**You should see:** a device plugged into the switch gets an address starting `192.168.50.`

---

### Step 9 — Lock the router down

**Why:** two settings that are dangerous if left at defaults.

**Do this:**
1. **Administration → System** → change the router login password from `admin` to something real
2. On the same page, set **Enable Web Access from WAN** to **No**
3. **WAN → Internet Connection** → set **Enable UPnP** to **No**

**Why each one:**
- The default password is printed on the label and known to everyone
- "Web access from WAN" means your router's admin page is reachable *from the internet*. Routers
  get scanned constantly
- UPnP lets any program on your network punch its own hole through the firewall without asking.
  For a server network you want holes to be deliberate and few. Nothing here needs it

---

### Step 10 — Optional: a WiFi name for the lab

**Wireless → General.** Give the Asus its own network name, different from the Cox one. Anything
that joins it lands in your lab suite.

---

## 7. Your addresses

Worth a screenshot.

| What | Address |
|---|---|
| Cox box (house network) | `192.168.0.1` |
| Asus street door (WAN) | `192.168.0.50` — pinned in Step 6 |
| Asus suite door (LAN) — its admin page | `192.168.50.1` |
| **Mac mini** | `192.168.50.10` — pinned in Step 8 |
| Free for pinning by hand | `192.168.50.2` – `192.168.50.99` |
| Handed out automatically | `192.168.50.100` – `192.168.50.200` |

---

## 8. Check your work

Run these **in order**, from a device plugged into the switch. Each one tests one thing, so the
**first** failure tells you exactly what's wrong. Don't skip ahead — a later test failing means
nothing if an earlier one already failed.

### Test 1 — Did I get a lab address?

```bash
ifconfig en0    # Mac
ip a            # Linux
ipconfig        # Windows
```

- **Expect:** an address starting `192.168.50.`
- **Got `192.168.0.` instead?** You're on the house network. Either the Asus is in AP mode
  (Step 7), or the cable is LAN→LAN (section 4)
- **Got nothing / `169.254.x.x`?** Nothing is handing out addresses. Check Step 8 part B

### Test 2 — Can I reach my own receptionist?

```bash
ping 192.168.50.1
```

- **Proves:** the Asus is reachable through the switch
- **Fails?** Cable or switch problem between you and the router

### Test 3 — Can I reach the building receptionist?

```bash
ping 192.168.0.1
```

- **Proves:** the Asus can pass traffic out to the Cox box
- **Fails?** The Asus's street door isn't connected. Recheck Step 5, and look at **Network Map →
  Internet status**

### Test 4 — Can I reach the internet?

```bash
ping 8.8.8.8
```

- **Proves:** traffic gets all the way out
- **Fails?** Check whether the house network itself is working

### Test 5 — Does the phone book work?

```bash
nslookup google.com
```

- **Proves:** names turn into addresses
- **Fails but Test 4 passed?** Only DNS is broken. Set the Asus's WAN DNS to `1.1.1.1`

### Test 6 — Are there really two networks?

```bash
traceroute 8.8.8.8      # Mac/Linux
tracert 8.8.8.8         # Windows
```

- **Expect:** `192.168.50.1` first, then `192.168.0.1`, then Cox equipment
- **Those two private hops are the proof.** Two receptionists, in order. That's your subnet

### Test 7 — The important one: does the wall hold?

Now go to a device on the **main Cox WiFi** — a phone works — and run:

```bash
ping 192.168.50.10
```

**This must FAIL.** A timeout is a pass.

That's the whole point of the exercise: the house cannot reach into your lab. If it *succeeds*,
your networks aren't separated. Go back to Step 7 and section 4.

---

## 9. Reaching one lab thing from the house

Sometimes you'll want a laptop on house WiFi to reach something in the lab. Say the Mac mini
serves something on port 5000.

**Do this:** on the Asus, go to **WAN → Virtual Server / Port Forwarding** and add:

| Field | Value |
|---|---|
| Service Name | `mac-mini-5000` |
| External Port | `5000` |
| Internal IP | `192.168.50.10` |
| Internal Port | `5000` |
| Protocol | TCP |

**Then from any house device:** `http://192.168.0.50:5000`

You're telling the suite receptionist: "if a visitor asks for slot 5000, walk them to the Mac
mini." **Nothing needs configuring on the Cox box** — the Asus's street door is already on the
house network, so house devices can knock on it directly.

### What won't work across the wall

**Devices can't automatically *find* each other across the two networks.** AirPlay, Chromecast,
AirPrint, and printer auto-setup all work by shouting "anyone there?" to everyone nearby — and
that shout stops at the router.

Reaching something by typing its address still works fine. It just won't show up in a "nearby
devices" list.

**Decide before you move hardware:** a printer the whole house uses should stay on the Cox side.

---

## 10. When something's wrong

| What you see | What's probably going on |
|---|---|
| No internet in the lab | Cable is in a yellow (LAN) port instead of the blue WAN port |
| Everything has a `192.168.0.` address | Asus is in AP mode — Step 7 |
| Works, then randomly drops | Two networks using the same range (Step 1), **or the router is overheating** (Step 2) |
| Asus shows `0.0.0.0` for its street door | Power-cycle the Cox box, let it fully come up, then reboot the Asus |
| Port forward works from outside but not inside the lab | Normal quirk. From inside the lab use `192.168.50.10:5000` directly |
| Some devices much slower than others | Bad cable, or a 100 Mbps port. Switch link lights are usually a different color for gigabit |
| Can't reach the Asus admin page | You're on the house side. It's only reachable from the lab side — that's deliberate |

---

## 11. Things you're not doing, and why

**Putting the Cox box in bridge mode.** This turns the Cox box into a dumb modem and makes the
Asus the only router. Cleaner in theory. Not chosen because it moves *the whole house* onto the
Asus and turns off Cox WiFi — and the goal was to leave the house alone. You have no Cox phone
service, so this stays available later if you ever want the Asus running everything.

**VLANs on a managed switch.** The more flexible way to split networks, using one smarter switch
instead of a second router. Needs hardware you don't have and more VLAN support than this
router's stock firmware offers. Fine as a someday upgrade.

**Worrying about "double NAT".** Your traffic passes two receptionists instead of one. This only
causes problems for connections coming *in* from the internet, and the Mac mini setup uses an
approach that never needs those. See [mac-mini-server-setup.md](mac-mini-server-setup.md).

**About this router.** The RT-AC68P is from 2014 and ASUS has wound down updates for it. It
works fine and it's what you have. But it's the wall standing between the internet and your
personal documents, so treat replacing it as a known future task — not something to do today.
