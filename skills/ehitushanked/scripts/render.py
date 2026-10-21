#!/usr/bin/env python3
"""JSON → HTML-aruanne ühtses vormis.

  python3 render.py radar radar.json [--skoorid skoorid.json] [--top N] [--inline] --out radar.html
  python3 render.py aruanne aruanne.json [--tekst DIR] [--inline] --out aruanne.html

Kujundus järgib ehitusjoonise loogikat: päises nurgatempel, leiud on märgitud punasega nagu
ülevaataja märkused joonisel. Skeemid: ../SKEEMID.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

CSS = """
:root {
  --paper: #ffffff;
  --ink: #1c2430;
  --pencil: #5d6673;
  --rule: #c9ced6;
  --rule-strong: #1c2430;
  --redline: #c8242f;
  --amber: #a8650a;
  --wash: #f3f4f6;
  --font: "Aptos", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}
* { box-sizing: border-box; }
html { background: var(--paper); }
body {
  margin: 0;
  color: var(--ink);
  font: 15px/1.55 var(--font);
  font-variant-numeric: tabular-nums;
}
.doc { max-width: 920px; margin: 0 auto; padding: 40px 28px 56px; }

/* Nurgatempel */
.tempel { border: 2px solid var(--rule-strong); margin-bottom: 36px; }
.tempel .pea { padding: 16px 18px 14px; border-bottom: 1px solid var(--rule-strong); }
.tempel .liik { font-size: 13px; color: var(--pencil); margin: 0 0 4px; }
.tempel h1 { font-size: 24px; line-height: 1.25; font-weight: 650; margin: 0; letter-spacing: -0.01em; }
.tempel dl { display: grid; grid-template-columns: repeat(3, 1fr); margin: 0; }
.tempel dl div { padding: 8px 18px 10px; border-right: 1px solid var(--rule); border-top: 1px solid var(--rule); }
.tempel dl div:nth-child(-n+3) { border-top: 0; }
.tempel dl div:nth-child(3n) { border-right: 0; }
.tempel dt { font-size: 12px; color: var(--pencil); }
.tempel dd { margin: 0; font-weight: 600; }

/* Jaotised */
h2 { font-size: 18px; font-weight: 650; margin: 40px 0 6px; padding-bottom: 6px; border-bottom: 1px solid var(--rule-strong); }
h2 .nr { display: inline-block; min-width: 1.8em; }
h2 small { font-weight: 400; color: var(--pencil); font-size: 14px; margin-left: 6px; }
.selgitus { color: var(--pencil); margin: 0 0 14px; font-size: 14px; max-width: 70ch; }
p, li { max-width: 74ch; }
a { color: inherit; text-decoration-color: var(--rule); text-underline-offset: 2px; }
a:hover { text-decoration-color: var(--ink); }

/* Otsus */
.otsus { display: grid; grid-template-columns: 220px 1fr; gap: 24px; align-items: start; margin-top: 14px; }
.otsus .tulemus { border: 2px solid currentColor; padding: 12px 14px; font-weight: 700; font-size: 17px; line-height: 1.25; }
.otsus .tulemus.ei { color: var(--redline); }
.otsus .tulemus.tingimus { color: var(--amber); }
.otsus .tulemus.jah { color: #23663a; }
.otsus p { margin: 0 0 10px; }
.otsus ul { margin: 0; padding-left: 18px; }
.otsus li { margin-bottom: 4px; }

/* Tabelid */
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; font-weight: 600; font-size: 13px; color: var(--pencil); padding: 6px 10px 6px 0; border-bottom: 1px solid var(--rule-strong); }
td { padding: 10px 10px 10px 0; border-bottom: 1px solid var(--rule); vertical-align: top; }
td.num, th.num { text-align: right; white-space: nowrap; }
td.id { width: 44px; font-weight: 700; white-space: nowrap; }
.tingimused td:first-child { width: 34%; color: var(--pencil); }
h3.alam { font-size: 15px; font-weight: 650; margin: 22px 0 6px; }

/* Leiud */
.leid { border-left: 3px solid var(--rule); padding: 2px 0 2px 16px; margin: 22px 0; }
.leid.kõrge { border-left-color: var(--redline); }
.leid.keskmine { border-left-color: var(--amber); }
.leid h3 { font-size: 16px; font-weight: 650; margin: 0 0 8px; }
.leid h3 .id { margin-right: 8px; }
.tase { font-size: 13px; font-weight: 600; margin-left: 8px; }
.tase.kõrge { color: var(--redline); }
.tase.keskmine { color: var(--amber); }
.tase.madal { color: var(--pencil); }
.võrdlus { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.tsitaat { margin: 0; }
.tsitaat q { display: block; quotes: none; background: var(--wash); padding: 8px 11px; font-size: 14px; }
.tsitaat figcaption { font-size: 12.5px; color: var(--pencil); margin-top: 4px; }
.kontroll { font-size: 12px; color: var(--pencil); }
.leht { margin-top: 8px; border: 1px solid var(--rule); background: #fff; line-height: 0; padding: 6px 4px; }
.leht-allkiri { font-size: 12px; color: var(--pencil); margin-top: 3px; overflow-wrap: anywhere; }
.võrdlus > * { min-width: 0; }
.leht svg { width: 100%; height: auto; display: block; overflow: visible; }
.leht rect { fill: rgba(200, 36, 47, 0.07); stroke: #c8242f; stroke-width: 2.5; }
.kontroll.ei { color: var(--amber); font-weight: 600; }
.allikas-puudub { color: var(--redline); }
.leid .järeldus { margin: 10px 0 0; font-size: 14.5px; }
.leid .järeldus b { font-weight: 600; }

/* Radar */
.skoor { width: 58px; font-weight: 700; font-size: 16px; }
.skoor .riba { height: 3px; background: var(--rule); margin-top: 3px; }
.skoor .riba i { display: block; height: 100%; background: var(--ink); }
.skoor.madal { color: var(--pencil); }
.skoor.madal .riba i { background: var(--pencil); }
.hange-nimi { font-weight: 600; }
.lisainfo { font-size: 12.5px; color: var(--pencil); margin-top: 2px; }
.põhjendus { font-size: 13.5px; margin-top: 4px; }
.lipud { font-size: 12.5px; color: var(--redline); margin-top: 3px; }
.otsing { width: 100%; max-width: 420px; font: inherit; padding: 8px 10px; border: 1px solid var(--rule); margin: 6px 0 14px; color: var(--ink); background: var(--paper); }
.otsing:focus, button:focus-visible, a:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }

/* Selgitustaotlus */
.kiri { border: 1px solid var(--rule); padding: 18px 22px; }
.kiri ol { padding-left: 20px; margin: 10px 0 0; }
.kiri li { margin-bottom: 9px; }
.kiri .viide { color: var(--pencil); font-size: 13px; }
button.kopeeri { font: inherit; font-size: 14px; border: 1px solid var(--ink); background: var(--paper); color: var(--ink); padding: 6px 14px; cursor: pointer; margin-top: 12px; }
button.kopeeri:hover { background: var(--ink); color: var(--paper); }

.hoiatus { border: 1px solid var(--amber); color: var(--amber); padding: 10px 14px; margin: -18px 0 26px; font-size: 14px; }
.metoodika dl { display: grid; grid-template-columns: max-content 1fr; gap: 4px 18px; margin: 10px 0 0; font-size: 14px; }
.metoodika dt { color: var(--pencil); }
.metoodika dd { margin: 0; }
footer { margin-top: 44px; padding-top: 10px; border-top: 1px solid var(--rule); font-size: 12.5px; color: var(--pencil); }

@media (max-width: 720px) {
  .doc { padding: 20px 16px 40px; }
  .tempel dl { grid-template-columns: 1fr 1fr; }
  .tempel dl div, .tempel dl div:nth-child(-n+3), .tempel dl div:nth-child(3n) { border-right: 1px solid var(--rule); border-top: 1px solid var(--rule); }
  .tempel dl div:nth-child(2n) { border-right: 0; }
  .tempel dl div:nth-child(-n+2) { border-top: 0; }
  .otsus, .võrdlus { grid-template-columns: 1fr; gap: 12px; }
  .peida-kitsal { display: none; }
}
@media print {
  .doc { padding: 0; max-width: none; }
  .otsing, button.kopeeri { display: none; }
  .leid, tr { break-inside: avoid; }
}
"""

# Vestlusesse põimitud vaade (nt T3 Code html_render): taust ja värvid tulevad keskkonna teemast.
INLINE_CSS = """
:root {
  --paper: transparent;
  --ink: var(--foreground);
  --pencil: var(--muted-foreground);
  --rule: var(--border);
  --rule-strong: var(--foreground);
  --redline: var(--destructive, #c8242f);
  --amber: var(--warning, #a8650a);
  --wash: var(--secondary);
  --font: var(--font-sans);
}
html { background: transparent; }
body { font-size: 14px; }
.doc { max-width: none; padding: 0; }
.tempel { margin-bottom: 24px; }
.tempel h1 { font-size: 20px; }
h2 { margin-top: 28px; }
.otsus { grid-template-columns: 1fr; gap: 12px; }
.võrdlus { grid-template-columns: 1fr; gap: 10px; }
button.kopeeri:hover { background: var(--foreground); color: var(--background); }
"""

INLINE = False

SEV_ALIASES = {"kõrge": "kõrge", "korge": "kõrge", "high": "kõrge", "keskmine": "keskmine",
               "medium": "keskmine", "madal": "madal", "low": "madal"}
SEV_ORDER = ["kõrge", "keskmine", "madal"]


def e(x) -> str:
    return html.escape("" if x is None else str(x))


def eur(v) -> str:
    try:
        return f"{float(v):,.0f} €".replace(",", " ")
    except (TypeError, ValueError):
        return "avalikustamata"


def date_et(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        d = dt.datetime.fromisoformat(iso[:16]) if "T" in iso else dt.datetime.fromisoformat(iso[:10])
    except ValueError:
        return iso
    return d.strftime("%d.%m.%Y %H:%M") if "T" in iso and d.hour + d.minute else d.strftime("%d.%m.%Y")


def days_left(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        n = (dt.date.fromisoformat(iso[:10]) - dt.date.today()).days
    except ValueError:
        return ""
    if n < 0:
        return "tähtaeg möödas"
    return "täna" if n == 0 else "homme" if n == 1 else f"{n} päeva"


def sev(x) -> str:
    return SEV_ALIASES.get(str(x or "").strip().lower(), "keskmine")


def pick(d: dict, *keys):
    for k in keys:
        if d.get(k):
            return d[k]
    return None


def tempel(kind: str, title: str, cells: list[tuple[str, str]]) -> str:
    cells = cells + [("", "")] * (-len(cells) % 3)
    items = "".join(f"<div><dt>{e(k)}</dt><dd>{v}</dd></div>" for k, v in cells)
    return (f'<header class="tempel"><div class="pea"><p class="liik">{e(kind)}</p><h1>{e(title)}</h1></div>'
            f"<dl>{items}</dl></header>")


def page(title: str, body: str, footer: str) -> str:
    css = CSS + (INLINE_CSS if INLINE else "")
    script = """
document.querySelectorAll("button.kopeeri").forEach(function (b) {
  b.addEventListener("click", function () {
    navigator.clipboard.writeText(document.getElementById(b.dataset.siht).innerText);
    b.textContent = "Kopeeritud";
  });
});
var otsing = document.querySelector(".otsing");
if (otsing) {
  otsing.addEventListener("input", function () {
    var q = otsing.value.toLowerCase();
    document.querySelectorAll("tbody tr").forEach(function (r) {
      r.style.display = r.innerText.toLowerCase().indexOf(q) > -1 ? "" : "none";
    });
  });
}
"""
    return (f'<!doctype html>\n<html lang="et">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>{e(title)}</title>\n'
            f"<style>{css}</style>\n</head>\n<body>\n<main class=\"doc\">\n{body}\n"
            f"<footer>{footer}</footer>\n</main>\n<script>{script}</script>\n</body>\n</html>\n")


# ---------------------------------------------------------------- radar

def render_radar(data: dict, scores: dict | None, top: int | None = None, market: dict | None = None) -> str:
    rows = data.get("hanked", [])
    by_ref = {}
    profile = ""
    if scores:
        profile = scores.get("profiil", "")
        by_ref = {str(s.get("viitenumber")): s for s in scores.get("hinnangud", [])}
    for r in rows:
        r["_s"] = by_ref.get(str(r.get("viitenumber")))
    if by_ref:
        rows = [r for r in rows if r["_s"]]
        rows.sort(key=lambda r: -(r["_s"].get("skoor") or 0))

    total = sum(r.get("eeldatav_maksumus") or 0 for r in rows)
    soon = sum(1 for r in rows if r.get("tahtaeg") and 0 <= (dt.date.fromisoformat(r["tahtaeg"][:10]) - dt.date.today()).days <= 14)
    good = sum(1 for r in rows if r["_s"] and (r["_s"].get("skoor") or 0) >= 70)
    generated = date_et(data.get("genereeritud", "")[:16])

    cells = [("Seisuga", e(generated)), ("Avatud ehitushankeid", str(len(rows))),
             ("Avalikustatud maksumus kokku", e(eur(total)))]
    if by_ref:
        cells += [("Firma", e(profile) or "profiil puudub"), ("Sobivaid (skoor 70+)", str(good)),
                  ("Tähtaeg 14 päeva jooksul", str(soon))]
    else:
        cells += [("Tähtaeg 14 päeva jooksul", str(soon)), ("Hankijaid", str(len({r.get('hankija') for r in rows}))),
                  ("Allikas", "riigihanked.riik.ee")]
    body = tempel("Hankeradar", "Sobivad ehitushanked" if by_ref else "Avatud ehitushanked", cells)

    shown = rows[:top] if top else rows
    heading = f"{len(shown)} parimat sobivuse järgi" if top else "Kõik hanked sobivuse järgi" if by_ref else "Kõik avatud hanked"
    body += f"<h2>{e(heading)}</h2>"
    if by_ref:
        body += ('<p class="selgitus">Skoor 0–100 arvestab töö liiki, mahtu, asukohta, pakkumuse koostamise aega ja '
                 "riskitegureid firma profiili suhtes.</p>")
    if not top:
        body += '<input class="otsing" type="search" placeholder="Otsi hankija, koha või töö järgi" aria-label="Otsi hankeid">'
    body += "<table><thead><tr>"
    if by_ref:
        body += "<th>Skoor</th>"
    body += '<th>Hange</th><th class="num peida-kitsal">Maksumus</th><th class="num">Tähtaeg</th></tr></thead><tbody>'
    for r in shown:
        s = r["_s"]
        body += "<tr>"
        if s:
            v = max(0, min(100, int(s.get("skoor") or 0)))
            body += (f'<td class="skoor{" madal" if v < 50 else ""}">{v}'
                     f'<div class="riba"><i style="width:{v}%"></i></div></td>')
        meta = [r.get("hankija"), r.get("viitenumber"), r.get("menetlus")]
        if r.get("raamleping"):
            meta.append("raamleping")
        cpv5 = next((c[:5] for c in r.get("cpv") or [] if c.startswith("45")), None)
        mk = (market or {}).get(cpv5)
        body += (f'<td><a class="hange-nimi" href="{e(r.get("link"))}" target="_blank" rel="noopener">{e(r.get("nimi"))}</a>'
                 f'<div class="lisainfo">{e(", ".join(str(m) for m in meta if m))}</div>')
        if s:
            if pick(s, "pohjendus", "põhjendus"):
                body += f'<div class="põhjendus">{e(pick(s, "pohjendus", "põhjendus"))}</div>'
            if s.get("punased_lipud"):
                body += f'<div class="lipud">{e("; ".join(s["punased_lipud"]))}</div>'
        if mk:
            body += (f'<div class="lisainfo">Sarnased hanked 24 kuu jooksul (CPV {cpv5}*): {mk["n"]} lepingut, '
                     f'mediaan {n_et(mk["pakkujaid"])} pakkujat</div>')
        body += (f'</td><td class="num peida-kitsal">{e(eur(r.get("eeldatav_maksumus")))}</td>'
                 f'<td class="num">{e(date_et((r.get("tahtaeg") or "")[:10]))}'
                 f'<div class="lisainfo">{e(days_left(r.get("tahtaeg")))}</div></td></tr>')
    body += "</tbody></table>"
    footer = ("Andmed riigihangete registrist. Sobivuse hinnang on koostatud automaatselt firma profiili põhjal "
              "ja on mõeldud eelvalikuks.")
    return page("Hankeradar", body, footer)


# ---------------------------------------------------------------- aruanne

def norm(t: str) -> str:
    return " ".join(re.findall(r"\w+", (t or "").lower()))


class Verifier:
    """Kontrollib, et tsitaat leidub hankedokumentide tekstis sõna-sõnalt (tühikud ja kirjavahemärgid ei loe).
    Kui hanke kaustas on algdokumendid (rh.py fetch hoiab need alles), lõikab välja ka lehe, kus tsitaat asub."""

    def __init__(self, tekst_dir: str | None, pages: bool = True):
        self.files: list[tuple[str, str]] | None = None
        self.lehed = None
        if tekst_dir and Path(tekst_dir).is_dir():
            self.files = [(f.name, norm(f.read_text(encoding="utf-8", errors="ignore")))
                          for f in sorted(Path(tekst_dir).glob("*.txt"))]
            if pages:
                try:
                    sys.path.insert(0, str(Path(__file__).parent))
                    from leht import Lehed
                    self.lehed = Lehed(Path(tekst_dir).parent)
                except Exception as ex:  # lehepildid on lisainfo
                    print(f"Lehepilte ei saa teha: {ex}", file=sys.stderr)
        self.ok = self.bad = self.shown = 0

    @property
    def corpus(self):
        return self.files

    def where(self, quote: str) -> str | None:
        nq = norm(quote)
        return next((name for name, t in self.files or [] if nq and nq in t), None)

    def mark(self, quote) -> tuple[str, str]:
        """(märge, lehepildi HTML)"""
        if self.files is None or not quote:
            return "", ""
        name = self.where(quote)
        if not name:
            self.bad += 1
            return '<span class="kontroll ei">Tsitaati ei leitud sõna-sõnalt, kontrolli allikast.</span>', ""
        self.ok += 1
        sn = self.lehed.snippet(name, quote) if self.lehed else None
        if not sn:
            return '<span class="kontroll">Tsitaat leitud dokumendist.</span>', ""
        self.shown += 1
        rects = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5"/>' for x, y, w, h in sn["read"])
        img = (f'<svg viewBox="0 0 {sn["w"]} {sn["h"]}" role="img" aria-label="Lõige dokumendist, tsitaat märgitud punasega">'
               f'<image href="data:image/jpeg;base64,{sn["jpeg"]}" width="{sn["w"]}" height="{sn["h"]}"/>{rects}</svg>')
        return ('<span class="kontroll">Tsitaat leitud dokumendist.</span>',
                f'<div class="leht">{img}</div><div class="leht-allkiri">{e(sn["fail"])}, lk {sn["lk"]}</div>')


def quote(q: str | None, source: str | None, ver: Verifier, page: bool = True) -> str:
    src = e(source) if source else '<span class="allikas-puudub">allikas puudub</span>'
    mark, leht = ver.mark(q)
    return (f'<figure class="tsitaat"><q>{e(q)}</q><figcaption>{src}'
            f'{" " + mark if mark else ""}</figcaption>{leht if page else ""}</figure>')


def pct(x) -> str:
    if x is None:
        return "–"
    v = x * 100
    return (f"{v:.1f}%" if abs(v) < 10 else f"{v:.0f}%").replace(".", ",")


def n_et(x) -> str:
    if x is None:
        return "–"
    return (f"{x:g}" if float(x) != int(x) else str(int(x))).replace(".", ",")


def meur(v) -> str:
    return f"{v / 1e6:.2f} M€".replace(".", ",") if v else "–"


def market_section(t: dict, short: bool) -> str:
    """Konkurents ja hinnatase turg.py väljundist. Kõik numbrid on registri andmetest, mitte mudeli hinnang."""
    p = t.get("pakkujaid", {})
    r = t.get("voit_vs_eelarve", {})
    band = t.get("hinnavahemik")
    risk = t.get("hinnarisk") or {}
    rows = [("Võrreldavaid lepinguid", f'{t.get("vordluslepinguid")} viimase {t.get("periood_kuud")} kuu jooksul ({e(t.get("alus"))})'),
            ("Pakkujaid hankes", f'mediaan {n_et(p.get("mediaan"))}' + (f', ühe pakkujaga hankeid {pct(p.get("uks_pakkuja_osakaal"))}' if p.get("uks_pakkuja_osakaal") else ""))]
    if r.get("n"):
        rows.append(("Võidupakkumine hankija eelarvest",
                     f'mediaan {pct(r.get("mediaan"))}, vahemik {pct(r.get("p25"))}–{pct(r.get("p75"))}; '
                     f'alla eelarve jäi {pct(r.get("alla_eelarve_osakaal"))} ({r["n"]} lepingut, {e(r.get("alus"))})'))
    if band:
        rows.append(("Tõenäoline võiduhind selles hankes",
                     f'<b>{meur(band["p25"])} – {meur(band["p75"])}</b>, mediaan {meur(band["mediaan"])} '
                     f'(eelarve {meur(band["eelarve"])})'))
    if risk.get("summa_eur"):
        g = risk.get("grupid", {})
        rows.append(("Hinnarisk fikseeritud hinnaga",
                     f'+{pct(risk.get("eeldatav_kallinemine"))} ehk ~{eur(round(risk["summa_eur"], -3))} {risk.get("kestus_kuud")} kuu jooksul. '
                     f'Ehitushinnaindeks {e(risk.get("kvartal"))}: +{pct(risk.get("aastamuutus"))} aastaga'
                     + (f', materjalid +{pct(g.get("Ehitusmaterjal"))}' if g.get("Ehitusmaterjal") else "")))
    html_ = '<table class="tingimused"><tbody>' + "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows) + "</tbody></table>"
    winners = t.get("sagedasemad_voitjad") or []
    if winners:
        html_ += ('<h3 class="alam">Kes võidab sarnaseid hankeid</h3><table><thead><tr><th>Ettevõte</th><th class="num">Võite</th>'
                  '<th class="num">Summa kokku</th><th class="num peida-kitsal">Pakkujaid keskmiselt</th></tr></thead><tbody>')
        for w in winners[: 5 if short else 10]:
            html_ += (f'<tr><td>{e(w["nimi"])}</td><td class="num">{w["voite"]}</td><td class="num">{e(eur(w["summa"]))}</td>'
                      f'<td class="num peida-kitsal">{n_et(w.get("keskmiselt_pakkujaid"))}</td></tr>')
        html_ += "</tbody></table>"
    recent = t.get("viimased") or []
    if recent and not short:
        html_ += ('<h3 class="alam">Viimased võrreldavad lepingud</h3><table><thead><tr><th>Kuupäev</th><th>Hange ja võitja</th>'
                  '<th class="num">Summa</th><th class="num">Pakkujaid</th></tr></thead><tbody>')
        for x in recent[:10]:
            html_ += (f'<tr><td class="num" style="text-align:left">{e(date_et(x["kuupaev"]))}</td><td>{e(x["nimi"])}'
                      f'<div class="lisainfo">{e(x.get("hankija"))}; võitja {e(", ".join(x.get("voitja") or []))}</div></td>'
                      f'<td class="num">{e(eur(x["summa"]))}</td><td class="num">{e(x.get("pakkumusi") or "–")}</td></tr>')
        html_ += "</tbody></table>"
    own = t.get("hankija_ajalugu") or []
    if own and not short:
        html_ += '<h3 class="alam">Sama hankija varasemad ehituslepingud</h3><ul>'
        for x in own[:5]:
            html_ += (f'<li>{e(date_et(x["kuupaev"]))} {e(x["nimi"])}: {e(", ".join(x.get("voitja") or []))}, '
                      f'{e(eur(x["summa"]))}, {e(x.get("pakkumusi") or "?")} pakkujat</li>')
        html_ += "</ul>"
    return html_


def render_report(d: dict, ver: Verifier, short: bool = False, turg: dict | None = None) -> str:
    h = d.get("hange", {})
    o = d.get("otsus", {})
    m = dict(d.get("metoodika", {}))
    rec = str(o.get("soovitus", "")).strip()
    rec_cls = "ei" if "MITTE" in rec.upper() else "tingimus" if "TINGIMUS" in rec.upper() else "jah"

    vastuolud = sorted(d.get("vastuolud", []), key=lambda x: SEV_ORDER.index(sev(x.get("tõsidus"))))
    riskid = sorted(d.get("riskid", []), key=lambda x: SEV_ORDER.index(sev(x.get("tõsidus"))))
    n_v, n_r = len(vastuolud), len(riskid)
    if short:
        vastuolud, riskid = vastuolud[:3], riskid[:3]
        d = {k: v for k, v in d.items() if k not in ("votmenaitajad", "kvalifikatsioon", "puuduv_info",
                                                       "kusimused_hankijale", "metoodika")}
        m = {}

    deadline = date_et(h.get("tahtaeg"))
    left = days_left(h.get("tahtaeg"))
    cells = [("Hankija", e(h.get("hankija"))), ("Viitenumber", e(h.get("viitenumber"))),
             ("Eeldatav maksumus", e(eur(h.get("maksumus")))),
             ("Pakkumuse tähtaeg", e(deadline) + (f' <span style="font-weight:400">({e(left)})</span>' if left else "")),
             ("Lepingu periood", e(h.get("lepingu_periood")) or "märkimata"),
             ("Register", f'<a href="{e(h.get("link"))}" target="_blank" rel="noopener">ava hange</a>' if h.get("link") else "")]
    body = tempel("Hankedokumentide kontroll", h.get("nimi") or "", cells)

    missing = sum(1 for x in vastuolud if not (x.get("a") or {}).get("allikas") or not (x.get("b") or {}).get("allikas"))
    missing += sum(1 for x in riskid if not x.get("allikas"))
    if missing:
        body += f'<p class="hoiatus">{missing} leiul puudub allikaviide. Need tuleb enne kasutamist üle kontrollida.</p>'

    sec = 0

    def section(title: str, count: int | None = None, intro: str = "") -> str:
        nonlocal sec
        sec += 1
        c = f"<small>{count}</small>" if count is not None else ""
        return f'<h2><span class="nr">{sec}.</span>{e(title)}{c}</h2>' + (f'<p class="selgitus">{e(intro)}</p>' if intro else "")

    body += section("Otsus")
    body += f'<div class="otsus"><div class="tulemus {rec_cls}">{e(rec.capitalize() if rec.isupper() else rec)}</div><div>'
    if pick(o, "pohjendus", "põhjendus"):
        body += f'<p>{e(pick(o, "pohjendus", "põhjendus"))}</p>'
    if d.get("kokkuvote"):
        body += "<ul>" + "".join(f"<li>{e(x)}</li>" for x in d["kokkuvote"]) + "</ul>"
    body += "</div></div>"

    if turg:
        body += section("Konkurents ja hinnatase", None,
                        "Riigihangete registri lepingute andmetest: kes sarnaseid töid võidab, mitme pakkujaga ja mis hinnaga.")
        body += market_section(turg, short)

    if d.get("votmenaitajad"):
        body += section("Põhitingimused")
        body += '<table class="tingimused"><tbody>'
        for k in d["votmenaitajad"]:
            body += (f'<tr><td>{e(k.get("nimetus"))}</td><td>{e(k.get("vaartus"))}'
                     f'<div class="lisainfo">{e(k.get("allikas"))}</div></td></tr>')
        body += "</tbody></table>"

    if vastuolud:
        body += section("Vastuolud dokumentide vahel", n_v,
                        f"Kolm olulisemat {n_v}-st. Kohad, kus kaks hanke dokumenti ütlevad sama asja kohta erinevat."
                        if short and n_v > 3 else "Kohad, kus kaks hanke dokumenti ütlevad sama asja kohta erinevat.")
        for i, v in enumerate(vastuolud, 1):
            s = sev(v.get("tõsidus"))
            a, b = v.get("a") or {}, v.get("b") or {}
            body += (f'<article class="leid {s}"><h3><span class="id">V{i}</span>{e(v.get("teema"))}'
                     f'<span class="tase {s}">{s}</span></h3>'
                     f'<div class="võrdlus">{quote(a.get("tsitaat"), a.get("allikas"), ver)}'
                     f'{quote(b.get("tsitaat"), b.get("allikas"), ver)}</div>')
            if pick(v, "moju", "mõju"):
                body += f'<p class="järeldus"><b>Mõju.</b> {e(pick(v, "moju", "mõju"))}</p>'
            if v.get("soovitus"):
                body += f'<p class="järeldus"><b>Mida teha.</b> {e(v["soovitus"])}</p>'
            body += "</article>"

    if riskid:
        body += section("Lepingu riskid võrreldes ETÜ 2013-ga", n_r,
                        f"Kolm olulisemat {n_r}-st. Tingimused, mis nihutavad riski tavapärasest rohkem töövõtja kanda."
                        if short and n_r > 3 else "Tingimused, mis nihutavad riski tavapärasest rohkem töövõtja kanda.")
        for i, r in enumerate(riskid, 1):
            s = sev(r.get("tõsidus"))
            body += (f'<article class="leid {s}"><h3><span class="id">R{i}</span>{e(r.get("teema"))}'
                     f'<span class="tase {s}">{s}</span></h3>{quote(r.get("tsitaat"), r.get("allikas"), ver)}')
            if pick(r, "etu_vordlus", "etü_võrdlus"):
                body += f'<p class="järeldus"><b>ETÜ 2013.</b> {e(pick(r, "etu_vordlus", "etü_võrdlus"))}</p>'
            if pick(r, "moju", "mõju"):
                body += f'<p class="järeldus"><b>Mõju.</b> {e(pick(r, "moju", "mõju"))}</p>'
            if r.get("soovitus"):
                body += f'<p class="järeldus"><b>Mida teha.</b> {e(r["soovitus"])}</p>'
            body += "</article>"

    if d.get("kvalifikatsioon"):
        body += section("Kvalifitseerimis- ja vastavustingimused", len(d["kvalifikatsioon"]))
        body += "<table><thead><tr><th>Nõue</th><th>Allikas</th></tr></thead><tbody>"
        for q in d["kvalifikatsioon"]:
            body += f'<tr><td>{e(pick(q, "nõue", "noue"))}</td><td class="lisainfo">{e(q.get("allikas"))}</td></tr>'
        body += "</tbody></table>"

    if d.get("puuduv_info"):
        body += section("Puuduv või ebaselge info", len(d["puuduv_info"]))
        body += "<table><tbody>"
        for p in d["puuduv_info"]:
            body += (f'<tr><td style="width:34%;font-weight:600">{e(p.get("teema"))}</td><td>{e(p.get("miks_oluline"))}'
                     f'{"<div class=lisainfo>" + e(p.get("allikas")) + "</div>" if p.get("allikas") else ""}</td></tr>')
        body += "</tbody></table>"

    if d.get("kusimused_hankijale"):
        body += section("Selgitustaotlus", len(d["kusimused_hankijale"]),
                        "Valmis tekst hankijale saatmiseks riigihangete registri kaudu.")
        body += (f'<div class="kiri" id="selgitustaotlus"><p>Lugupeetud hankija</p>'
                 f'<p>Palume selgitada riigihanke „{e(h.get("nimi"))}” (viitenumber {e(h.get("viitenumber"))}) '
                 f"alusdokumente järgmistes küsimustes.</p><ol>")
        for q in d["kusimused_hankijale"]:
            body += f'<li>{e(pick(q, "kusimus", "küsimus"))} <span class="viide">({e(q.get("viide"))})</span></li>'
        body += "</ol></div>"
        body += '<button class="kopeeri" type="button" data-siht="selgitustaotlus">Kopeeri tekst</button>'

    if ver.corpus is not None:
        m["Tsitaate kontrollitud"] = f"{ver.ok} / {ver.ok + ver.bad} leitud dokumentidest sõna-sõnalt"
    if m:
        body += section("Kuidas kontroll tehti")
        body += '<div class="metoodika">'
        if m.get("kirjeldus"):
            body += f'<p class="selgitus">{e(m.pop("kirjeldus"))}</p>'
        body += "<dl>" + "".join(f"<dt>{e(k.replace('_', ' ').capitalize())}</dt><dd>{e(v)}</dd>" for k, v in m.items()) + "</dl></div>"

    footer = ("Koostatud automaatselt hanke alusdokumentide põhjal. Enne otsust kontrolli viidatud kohad üle. "
              "Aruanne ei ole õigusnõuanne.")
    return page(f'{h.get("viitenumber", "")} {h.get("nimi", "")}', body, footer)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("radar")
    r.add_argument("json")
    r.add_argument("--skoorid")
    r.add_argument("--top", type=int, help="näita ainult N parimat (vestlusesse põimimiseks)")
    r.add_argument("--turg", action="store_true", help="lisa iga hanke juurde sarnaste lepingute pakkujate arv (turg.py)")
    r.add_argument("--out", required=True)
    a_ = sp.add_parser("aruanne")
    a_.add_argument("json")
    a_.add_argument("--tekst", help="hanke tekst/ kaust tsitaatide kontrolliks")
    a_.add_argument("--ilma-lehtedeta", action="store_true", help="ära lisa tsitaatide juurde lehepilte")
    a_.add_argument("--luhike", action="store_true", help="ainult otsus ja 3+3 olulisemat leidu (vestlusesse põimimiseks)")
    a_.add_argument("--out", required=True)
    for sub in (r, a_):
        sub.add_argument("--inline", action="store_true", help="vestlusesse põimitav vaade (T3 Code html_render)")
    a = p.parse_args()
    global INLINE
    INLINE = a.inline
    data = json.loads(Path(a.json).read_text(encoding="utf-8"))
    if a.cmd == "radar":
        scores = json.loads(Path(a.skoorid).read_text(encoding="utf-8")) if a.skoorid else None
        market = None
        if a.turg:
            try:
                sys.path.insert(0, str(Path(__file__).parent))
                import turg as turg_mod
                market = turg_mod.cpv_stats(turg_mod.load_history(24))
            except Exception as ex:  # turuandmed on lisainfo, radar töötab ka ilma
                print(f"Turuandmeid ei saanud: {ex}", file=sys.stderr)
        out = render_radar(data, scores, a.top, market)
    else:
        ver = Verifier(a.tekst, pages=not a.ilma_lehtedeta)
        turg_path = Path(a.json).with_name("turg.json")
        turg = json.loads(turg_path.read_text(encoding="utf-8")) if turg_path.exists() else None
        out = render_report(data, ver, a.luhike, turg)
        if ver.corpus is not None:
            print(f"Tsitaadid: {ver.ok} leitud sõna-sõnalt, {ver.bad} vajavad käsitsi kontrolli, "
                  f"{ver.shown} lehepildiga.", file=sys.stderr)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(out, encoding="utf-8")
    print(f"HTML valmis: {Path(a.out).resolve()}", file=sys.stderr)


if __name__ == "__main__":
    main()
