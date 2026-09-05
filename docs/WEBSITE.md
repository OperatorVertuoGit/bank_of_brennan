# Website

Static, dependency-free, no runtime. `web-publisher` owns it.

```
website/
  content/          # JSON — the only thing you edit
    site.json       # brand + NAP + form endpoint. Must match Google Business Profile exactly.
    home.json
    services.json   # one generated page per entry
    portfolio.json  # case studies (approved jobs only)
    about.json
  theme/base.html   # page shell with {{token}} slots
  assets/css/styles.css
  build.py          # ~450 lines, standard library only
  public/           # GENERATED — never hand-edit, gitignored
```

## Build

```bash
python3 website/build.py           # build, print advisory checks
python3 website/build.py --check   # build and FAIL on problems (use in CI / pre-deploy)
```

`--check` fails on: missing/duplicate `<title>` or meta description, meta over 165 chars,
a page without exactly one `<h1>`, JSON-LD that does not parse, leftover
`TODO`/`PLACEHOLDER`/example phone/example.com, and draft portfolio entries.
It will fail on a fresh clone — that is the point. It goes green when the owner has
filled in the real brand, address, phone, form endpoint, and at least one real case study.

## Generated pages

`/`, `/services/`, `/services/<slug>/` (one per entry in services.json),
`/portfolio/`, `/about/`, `/quote/`, plus `robots.txt` and `sitemap.xml`.

Every page carries `ProfessionalService` JSON-LD; service pages add `Service` and, where
FAQs exist, `FAQPage`.

## Deploy

Point Cloudflare Pages or Netlify at `website/public/`.

Build command: `python3 website/build.py --check`
Output directory: `website/public`

`public/` is gitignored — it is generated from content on every deploy. If your host
cannot run Python, build locally and deploy the directory.

## The form seam — how a visitor becomes a lead

```
visitor fills /quote/ form
   │  POST to site.json:form_endpoint  (Formspree, Netlify Forms, Basin, a Worker…)
   ▼
form provider webhook / scheduled export
   │  JSON body piped to:
   ▼
python3 scripts/intake_from_form.py
   ├─ writes data/leads/_raw/<stamp>.json      (untouched submission, kept forever)
   └─ writes data/bus/intake-coordinator/inbox/<msg>.json   topic: lead.received
   ▼
intake-coordinator agent creates the lead record
```

`intake_from_form.py` deliberately does **not** create a lead record. Qualification is
judgment work and belongs to the agent.

Verify the provider's webhook signature before piping (`FORM_WEBHOOK_SECRET` in
`ops/.env`). The script accepts a single object or an array of them, so a scheduled
"export everything since X" poll works as well as a live webhook.

## Local SEO checklist (owner, once)

- [ ] Claim and fully complete the Google Business Profile. It outranks the website for
      local-pack queries.
- [ ] NAP identical byte-for-byte in `site.json`, the GBP listing, and every directory.
- [ ] Real photos of real work, descriptive filenames and alt text.
- [ ] Add the GBP and LinkedIn URLs to `site.json:sameAs`.
- [ ] Submit `sitemap.xml` in Google Search Console.
- [ ] Do **not** create thin city pages. Add a service-area page only when there is
      genuinely distinct content for that city.
