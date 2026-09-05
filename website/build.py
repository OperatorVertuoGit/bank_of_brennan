#!/usr/bin/env python3
"""Static site generator for Pier Point 3D.

  python3 website/build.py            build website/public/
  python3 website/build.py --check    build, then fail on SEO/content problems

Content lives in website/content/*.json (owned by the web-publisher agent).
website/public/ is generated — never hand-edit it.
Standard library only, on purpose: this must build on any machine with Python 3.
"""
import argparse
import html
import json
import pathlib
import re
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
CONTENT = HERE / "content"
THEME = HERE / "theme"
ASSETS = HERE / "assets"
OUT = HERE / "public"


def load(name):
    return json.loads((CONTENT / f"{name}.json").read_text(encoding="utf-8"))


def e(s):
    return html.escape(str(s), quote=True)


def render(template, mapping):
    def sub(m):
        return str(mapping.get(m.group(1), ""))
    return re.sub(r"\{\{(\w+)\}\}", sub, template)


# ---------------------------------------------------------------- page shell

def nav_html(services, root, current):
    links = [("", "Home"), ("services/", "Services")]
    links += [(f"services/{s['slug']}/", s["nav"]) for s in services[:4]]
    links += [("portfolio/", "Work"), ("about/", "About"), ("quote/", "Get a quote")]
    out = []
    for href, label in links:
        cur = ' aria-current="page"' if href == current else ""
        out.append(f'<a href="{root}{href}"{cur}>{e(label)}</a>')
    return "".join(out)


def local_business_jsonld(site, extra=None):
    a = site["address"]
    doc = {
        "@context": "https://schema.org",
        "@type": "ProfessionalService",
        "name": site["brand"],
        "description": site["tagline"],
        "url": site["base_url"],
        "telephone": site["phone"],
        "email": site["email"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": a["street"],
            "addressLocality": a["city"],
            "addressRegion": a["region"],
            "postalCode": a["postal_code"],
            "addressCountry": a["country"],
        },
        "geo": {"@type": "GeoCoordinates", "latitude": site["geo"]["lat"], "longitude": site["geo"]["lng"]},
        "areaServed": [{"@type": "City", "name": c} for c in site["area_served"]],
        "sameAs": [u for u in site.get("sameAs", []) if not u.startswith("TODO")],
    }
    if extra:
        return json.dumps([doc, extra], indent=None)
    return json.dumps(doc, indent=None)


def page(site, services, *, path, title, meta, body, jsonld=None, current=""):
    """path: '' for root, else 'services/3d-scanning'."""
    depth = len([p for p in path.split("/") if p])
    root = "../" * depth if depth else ""
    a = site["address"]
    shell = (THEME / "base.html").read_text(encoding="utf-8")
    canonical = site["base_url"].rstrip("/") + "/" + (path + "/" if path else "")
    doc = render(shell, {
        "title": e(title), "meta": e(meta), "canonical": e(canonical),
        "root": root, "brand": e(site["brand"]), "nav": nav_html(services, root, current),
        "phone": e(site["phone"]), "phone_display": e(site["phone_display"]),
        "email": e(site["email"]), "street": e(a["street"]), "city": e(a["city"]),
        "region": e(a["region"]), "postal": e(a["postal_code"]), "hours": e(site["hours"]),
        "areas": ", ".join(e(x) for x in site["area_served"]),
        "footer_note": e(site["footer_note"]),
        "jsonld": jsonld or local_business_jsonld(site),
        "body": body,
    })
    dest = OUT / path / "index.html" if path else OUT / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(doc, encoding="utf-8")
    return dest


# ---------------------------------------------------------------- components

def quote_form(site, compact=False):
    ep = site["form_endpoint"]
    action = "" if ep.startswith("TODO") else e(ep)
    warn = ('<p class="draft"><strong>Not wired up.</strong> Set '
            "<code>form_endpoint</code> in website/content/site.json to the form "
            "provider URL whose webhook feeds scripts/intake_from_form.py.</p>"
            if ep.startswith("TODO") else "")
    extra = "" if compact else """
    <div class="row">
      <label>Roughly how big is it?<input name="size" placeholder="e.g. 600 x 300 x 200 mm"></label>
      <label>When do you need it?<input name="deadline" placeholder="date, or 'flexible'"></label>
    </div>
    <label>Where is the object?
      <select name="location">
        <option>I can bring it to San Clemente</option>
        <option>It needs to be scanned on site</option>
        <option>I would ship it</option>
        <option>Not sure yet</option>
      </select>
    </label>"""
    return f"""{warn}
<form class="quote" method="post" action="{action}">
  <div class="row">
    <label>Name<input name="name" required autocomplete="name"></label>
    <label>Company<input name="company" autocomplete="organization"></label>
  </div>
  <div class="row">
    <label>Email<input type="email" name="email" required autocomplete="email"></label>
    <label>Phone<input type="tel" name="phone" autocomplete="tel"></label>
  </div>
  <label>What is the object?<input name="object" required placeholder="e.g. cast bronze thru-hull fitting"></label>
  <label>What do you need it for?
    <select name="purpose">
      <option>Reverse engineering — I need a CAD model to remake it</option>
      <option>Inspection — compare a part to its CAD</option>
      <option>As-built documentation / scan-to-BIM</option>
      <option>Restoration or replication</option>
      <option>3D print preparation</option>
      <option>Visualization or marketing</option>
      <option>Something else</option>
    </select>
  </label>{extra}
  <label>Anything else we should know?<textarea name="message"
    placeholder="Tolerance that matters, surface finish, deadline constraints, photos you can send"></textarea></label>
  <button class="btn" type="submit">Request a quote</button>
  <p class="formnote">We reply within one business day. Photos help a lot — reply to our email with them.</p>
</form>"""


def faq_jsonld(faqs):
    if not faqs:
        return None
    return {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": f["q"],
                        "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faqs],
    }


# ---------------------------------------------------------------- pages

def build_home(site, services, home):
    h = home["hero"]
    proof = "".join(f'<div><div class="stat">{e(p["stat"])}</div>'
                    f'<div class="label">{e(p["label"])}</div></div>' for p in home["proof"])
    cards = "".join(
        f'<a class="card" href="services/{e(s["slug"])}/"><h3>{e(s["title"])}</h3>'
        f'<p>{e(s["lede"])}</p></a>' for s in services)
    probs = "".join(f"<li>{e(x)}</li>" for x in home["problems"]["items"])
    steps = "".join(f'<li><span class="n">{e(s["n"])}</span><div><strong>{e(s["t"])}</strong>'
                    f"<p>{e(s['d'])}</p></div></li>" for s in home["process"]["steps"])
    why = "".join(f'<div class="card"><h3>{e(w["t"])}</h3><p>{e(w["d"])}</p></div>'
                  for w in home["why"]["items"])
    body = f"""
<section class="hero">
  <h1>{e(h['h1'])}</h1>
  <p>{e(h['sub'])}</p>
  <p><a class="btn" href="quote/">{e(h['cta'])}</a></p>
</section>
<section class="proof">{proof}</section>
<section>
  <h2>{e(home['problems']['title'])}</h2>
  <ul class="checks">{probs}</ul>
</section>
<section>
  <h2>Services</h2>
  <div class="grid">{cards}</div>
</section>
<section>
  <h2>{e(home['process']['title'])}</h2>
  <ol class="steps">{steps}</ol>
</section>
<section>
  <h2>{e(home['why']['title'])}</h2>
  <div class="grid">{why}</div>
</section>
<section>
  <h2>Start a project</h2>
  <p class="lede">Tell us what the object is and what you need it for. We reply within one business day.</p>
  {quote_form(site, compact=True)}
</section>"""
    return page(site, services, path="", title=f"{site['brand']} — {site['tagline']}",
                meta=site["tagline"] + ". Reverse engineering, CAD modeling, inspection and scan-to-BIM for Orange County.",
                body=body, current="")


def build_services_index(site, services):
    cards = "".join(f'<a class="card" href="{e(s["slug"])}/"><h3>{e(s["title"])}</h3>'
                    f'<p>{e(s["lede"])}</p></a>' for s in services)
    body = f"""
<section>
  <h1>Services</h1>
  <p class="lede">Measurement, modeling and verification. Every project quotes a contracted tolerance before work begins.</p>
  <div class="grid">{cards}</div>
</section>"""
    return page(site, services, path="services", title=f"Services — {site['brand']}",
                meta=f"3D scanning, reverse engineering, CAD modeling, inspection and scan-to-BIM services in {site['address']['city']}, CA.",
                body=body, current="services/")


def build_service(site, services, s):
    paras = "".join(f"<p>{e(p)}</p>" for p in s["body"])
    bullets = "".join(f"<li>{e(b)}</li>" for b in s["bullets"])
    faq = ""
    if s.get("faq"):
        faq = "<section><h2>Questions we get</h2>" + "".join(
            f'<details class="faq"><summary>{e(f["q"])}</summary><p>{e(f["a"])}</p></details>'
            for f in s["faq"]) + "</section>"
    service_ld = {
        "@context": "https://schema.org", "@type": "Service",
        "name": s["title"], "description": s["meta"],
        "areaServed": [{"@type": "City", "name": c} for c in site["area_served"]],
        "provider": {"@type": "ProfessionalService", "name": site["brand"], "url": site["base_url"]},
    }
    extra = faq_jsonld(s.get("faq")) or service_ld
    ld = json.dumps([json.loads(local_business_jsonld(site)), service_ld]
                    + ([extra] if extra is not service_ld else []))
    body = f"""
<section>
  <h1>{e(s['title'])}</h1>
  <p class="lede">{e(s['lede'])}</p>
  {paras}
  <ul class="checks">{bullets}</ul>
  <p><a class="btn" href="../../quote/">Get a quote</a></p>
</section>
{faq}
<section>
  <h2>Tell us about the part</h2>
  {quote_form(site, compact=True)}
</section>"""
    return page(site, services, path=f"services/{s['slug']}",
                title=f"{s['title']} — {site['address']['city']}, CA | {site['brand']}",
                meta=s["meta"], body=body, jsonld=ld, current=f"services/{s['slug']}/")


def build_portfolio(site, services, portfolio):
    items = []
    for p in portfolio["projects"]:
        flag = '<p class="draft"><strong>Draft — not for publication.</strong> Replace with a real case study before deploying.</p>' if p.get("draft") else ""
        items.append(f"""<article class="card">
  <h3>{e(p['title'])}</h3>{flag}
  <p><strong>Problem.</strong> {e(p['problem'])}</p>
  <p><strong>Approach.</strong> {e(p['approach'])}</p>
  <p><strong>Result.</strong> {e(p['result'])}</p>
  <p><strong>Constraint.</strong> {e(p['constraint'])}</p>
</article>""")
    body = f"""
<section>
  <h1>Selected work</h1>
  <p class="lede">Published only with written client permission. Confidential projects never appear here.</p>
  <div class="grid">{''.join(items)}</div>
</section>"""
    return page(site, services, path="portfolio", title=f"Work — {site['brand']}",
                meta=f"3D scanning and CAD modeling case studies from {site['brand']} in {site['address']['city']}, CA.",
                body=body, current="portfolio/")


def build_about(site, services, about):
    paras = "".join(f"<p>{e(p)}</p>" for p in about["body"])
    commits = "".join(f"<li>{e(c)}</li>" for c in about["commitments"])
    body = f"""
<section>
  <h1>{e(about['title'])}</h1>
  {paras}
  <h2>What we commit to on every job</h2>
  <ul class="checks">{commits}</ul>
</section>"""
    return page(site, services, path="about", title=f"About — {site['brand']}",
                meta=about["meta"], body=body, current="about/")


def build_quote(site, services):
    body = f"""
<section>
  <h1>Get a quote</h1>
  <p class="lede">The more you can tell us about the object and what you need it for, the tighter the number. We reply within one business day.</p>
  {quote_form(site)}
</section>"""
    return page(site, services, path="quote", title=f"Get a quote — {site['brand']}",
                meta=f"Request a quote for 3D scanning, reverse engineering or CAD modeling in {site['address']['city']}, CA.",
                body=body, current="quote/")


def build_extras(site, pages):
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {site['base_url'].rstrip('/')}/sitemap.xml\n", encoding="utf-8")
    urls = "".join(
        f"  <url><loc>{html.escape(site['base_url'].rstrip('/') + '/' + p)}</loc></url>\n"
        for p in pages)
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n",
        encoding="utf-8")


# ---------------------------------------------------------------- checks

def check(site, home, services, portfolio):
    problems = []
    titles, metas = {}, {}
    for f in OUT.rglob("index.html"):
        doc = f.read_text(encoding="utf-8")
        t = re.search(r"<title>(.*?)</title>", doc, re.S)
        m = re.search(r'<meta name="description" content="(.*?)">', doc, re.S)
        rel = str(f.relative_to(OUT))
        if not t or not t.group(1).strip():
            problems.append(f"{rel}: missing <title>")
        else:
            titles.setdefault(t.group(1), []).append(rel)
        if not m or not m.group(1).strip():
            problems.append(f"{rel}: missing meta description")
        else:
            metas.setdefault(m.group(1), []).append(rel)
            if len(m.group(1)) > 165:
                problems.append(f"{rel}: meta description is {len(m.group(1))} chars (>165)")
        if len(re.findall(r"<h1[ >]", doc)) != 1:
            problems.append(f"{rel}: needs exactly one <h1>")
        for ld in re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S):
            try:
                json.loads(ld)
            except json.JSONDecodeError as ex:
                problems.append(f"{rel}: JSON-LD does not parse: {ex}")
    for value, where in list(titles.items()) + list(metas.items()):
        if len(where) > 1:
            problems.append(f"duplicate title/description across {where}")

    # placeholder content that must not reach production
    blob = json.dumps([site, home, services, portfolio])
    for token in ("TODO", "PLACEHOLDER", "lorem ipsum", "555-0100", "example.com"):
        if token.lower() in blob.lower():
            problems.append(f"placeholder content still present in content JSON: {token!r}")
    if any(p.get("draft") for p in portfolio["projects"]):
        problems.append("portfolio contains draft entries — remove before deploying")
    return problems


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail the build on SEO/placeholder problems")
    args = ap.parse_args()

    site = load("site")
    home = load("home")
    services = load("services")["services"]
    portfolio = load("portfolio")
    about = load("about")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(ASSETS, OUT / "assets")

    built = [build_home(site, services, home),
             build_services_index(site, services)]
    built += [build_service(site, services, s) for s in services]
    built += [build_portfolio(site, services, portfolio),
              build_about(site, services, about),
              build_quote(site, services)]

    paths = [""] + ["services/"] + [f"services/{s['slug']}/" for s in services] \
        + ["portfolio/", "about/", "quote/"]
    build_extras(site, paths)

    for b in built:
        print(f"  {b.relative_to(HERE)}")
    print(f"{len(built)} pages -> {OUT.relative_to(HERE.parent)}")

    problems = check(site, home, services, portfolio)
    if problems:
        print("\nchecks:")
        for p in problems:
            print(f"  - {p}")
        if args.check:
            sys.exit(1)
        print("\n(informational — run with --check to make these fail the build)")


if __name__ == "__main__":
    main()
