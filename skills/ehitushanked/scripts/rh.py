#!/usr/bin/env python3
"""Riigihangete registri tööriist: avatud ehitushanked (radar) ja hankedokumentide allalaadimine (fetch).

Ainult Pythoni standardteek. Valikuliselt kasutab: pdftotext (poppler), pandoc.

  python3 rh.py radar --out radar.json [--koik-liigid]
  python3 rh.py fetch 315920 --dir hanked/315920
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import email.utils
import io
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

BASE = "https://riigihanked.riik.ee"
API = BASE + "/rhr/api/public/v1"
WEB = BASE + "/rhr-web/#/procurement/{id}/general-info"
UA = {"User-Agent": "ehitushanked-skill/1.0 (+https://skills.sh)", "Accept": "application/json"}

TEXT_EXT = {".pdf", ".docx", ".xlsx", ".txt", ".csv", ".xml", ".rtf", ".md"}
# Teenuste hulgast võtame radarisse ehitusega seotud tööd (projekteerimine, järelevalve jne)
SERVICE_KEYWORDS = re.compile(
    r"projekteeri|ehitus|omanikujärelevalv|järelevalv|renoveeri|rekonstrueeri|remont|lammut|"
    r"tehnosüsteem|ehitis|hoone|taristu|teede|sild|võrgu", re.I)


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def http_get(url: str, *, timeout: int = 30, retries: int = 3, accept_json: bool = True) -> bytes:
    headers = dict(UA)
    if not accept_json:
        headers["Accept"] = "*/*"
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Päring ebaõnnestus: {url}: {last}")


def get_json(path: str) -> dict:
    return json.loads(http_get(API + path))


# ---------------------------------------------------------------- radar

def parse_rss() -> list[dict]:
    root = ET.fromstring(http_get(API + "/rss", accept_json=False))
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        desc = (it.findtext("description") or "").strip()
        link = it.findtext("link") or ""
        m_id = re.search(r"/procurement/(\d+)", link)
        m_ref = re.match(r"(\d+)\s*-\s*(.*)", title, re.S)
        parts = desc.split(";", 2)
        m_dead = re.search(r"Tähtaeg:\s*(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})", desc)
        pub = it.findtext("pubDate")
        out.append({
            "id": int(m_id.group(1)) if m_id else None,
            "viitenumber": m_ref.group(1) if m_ref else None,
            "nimi": (m_ref.group(2) if m_ref else title).strip(),
            "liik": parts[0].strip() if parts else "",
            "menetlus": parts[1].strip() if len(parts) > 1 else "",
            "rss_kirjeldus": re.sub(r";\s*Tähtaeg:.*$", "", parts[2] if len(parts) > 2 else "", flags=re.S).strip(),
            "tahtaeg": (f"{m_dead.group(3)}-{m_dead.group(2)}-{m_dead.group(1)}T{m_dead.group(4)}:{m_dead.group(5)}"
                        if m_dead else None),
            "avaldatud": email.utils.parsedate_to_datetime(pub).date().isoformat() if pub else None,
            "link": WEB.format(id=m_id.group(1)) if m_id else link,
        })
    return out


def enrich(t: dict) -> dict:
    try:
        h = get_json(f"/procurement/{t['id']}/header-info")
        t["hankija"] = h.get("contractingAuthorityName")
        t["hankija_kood"] = h.get("contractingAuthorityCode")
        t["roheline"] = h.get("isGreen")
        t["dokumendid_olemas"] = h.get("hasSourceDocuments")
        if h.get("submissionDate"):
            t["tahtaeg"] = h["submissionDate"][:16]
        ver = get_json(f"/procurement/{t['id']}/latest-version").get("value")
        g = get_json(f"/proc-vers/{ver}/general-info")
        t["eeldatav_maksumus"] = g.get("cost")
        t["cpv"] = [f"{c.get('code')} {c.get('name')}" for c in g.get("procurementCpvDtos") or []]
        t["kirjeldus"] = (g.get("shortDescription") or "").strip()
        t["lepingu_algus"] = (g.get("startDate") or "")[:10] or None
        t["lepingu_lopp"] = (g.get("endDate") or "")[:10] or None
        t["osadeks_jaotatud"] = g.get("isDividedIntoParts")
        t["raamleping"] = bool(g.get("isSingleTendererFrameworkAgr") or g.get("isMultipleTendererFrameworkAgr"))
    except Exception as e:  # üksiku hanke viga ei tohi radarit peatada
        t["rikastamise_viga"] = str(e)
    return t


def cmd_radar(a: argparse.Namespace) -> None:
    log("Loen riigihangete registri RSS voogu…")
    items = parse_rss()
    now = dt.datetime.now().strftime("%Y-%m-%dT%H:%M")

    def wanted(t: dict) -> bool:
        if t["liik"] == "Ehitustööd":
            return True
        if a.koik_liigid and t["liik"] == "Teenused":
            return bool(SERVICE_KEYWORDS.search(t["nimi"] + " " + t["rss_kirjeldus"]))
        return False

    # Sama hange võib voos olla mitu korda (muutmisteated, lisateated). Jäta alles uusim.
    uniq: dict[int, dict] = {}
    for t in items:
        if t["id"] and (t["id"] not in uniq or (t["avaldatud"] or "") > (uniq[t["id"]]["avaldatud"] or "")):
            uniq[t["id"]] = t
    sel = [t for t in uniq.values() if wanted(t) and (t["tahtaeg"] is None or t["tahtaeg"] >= now)]
    log(f"RSS-is {len(items)} teadet, neist avatud ehitushankeid {len(sel)}. Laen detailid…")
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        sel = list(ex.map(enrich, sel))
    sel = [t for t in sel if (t.get("tahtaeg") or "9999") >= now]
    sel.sort(key=lambda t: t.get("avaldatud") or "", reverse=True)
    data = {"allikas": API + "/rss", "genereeritud": dt.datetime.now().isoformat(timespec="seconds"),
            "arv": len(sel), "hanked": sel}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    md = Path(a.out).with_suffix(".md")
    lines = [f"# Avatud ehitushanked ({len(sel)}), {data['genereeritud'][:16]}", "",
             "viitenumber | nimi | hankija | eeldatav maksumus € | tähtaeg | menetlus | CPV | kirjeldus"]
    for t in sel:
        desc = re.sub(r"\s+", " ", t.get("kirjeldus") or t.get("rss_kirjeldus") or "")[:350]
        cpv = ", ".join(c.split(" ")[0] for c in t.get("cpv") or [])
        val = f"{t['eeldatav_maksumus']:.0f}" if t.get("eeldatav_maksumus") else "?"
        lines.append(f"{t['viitenumber']} | {t['nimi']} | {t.get('hankija')} | {val} | {(t.get('tahtaeg') or '')[:10]} | "
                     f"{t['menetlus']}{' (raamleping)' if t.get('raamleping') else ''} | {cpv} | {desc}")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    vals = [t["eeldatav_maksumus"] for t in sel if t.get("eeldatav_maksumus")]
    log(f"Valmis: {len(sel)} hanget → {a.out} (lühivaade: {md}). Avalikustatud maksumusega {len(vals)}, kokku {sum(vals)/1e6:.1f} M€.")


# ---------------------------------------------------------------- fetch

def resolve_id(ref: str) -> int:
    m = re.search(r"/procurement/(\d+)", ref)
    if m:
        return int(m.group(1))
    if ref.isdigit() and len(ref) >= 7:
        return int(ref)
    if ref.isdigit():
        for t in parse_rss():
            if t["viitenumber"] == ref:
                return t["id"]
        raise SystemExit(f"Viitenumbrit {ref} ei leitud RSS voost. Kasuta registri linki või sisemist ID-d "
                         f"(nt https://riigihanked.riik.ee/rhr-web/#/procurement/10854744/...).")
    raise SystemExit(f"Ei saa aru hanke tunnusest: {ref}")


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={**UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got, last = 0, 0.0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            got += len(chunk)
            if time.time() - last > 3:
                last = time.time()
                log(f"  laen alla… {got/1e6:,.0f} MB" + (f" / {total/1e6:,.0f} MB" if total else ""))
    log(f"  allalaaditud {got/1e6:,.0f} MB")


def pdf_text(data: bytes) -> tuple[str, int]:
    if shutil.which("pdftotext"):
        p = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", "-", "-"], input=data,
                           capture_output=True, timeout=180)
        pages = p.stdout.decode("utf-8", "replace").split("\f")
    else:
        try:
            from pypdf import PdfReader  # type: ignore
            pages = [pg.extract_text() or "" for pg in PdfReader(io.BytesIO(data)).pages]
        except Exception:
            return "[PDF teksti ei saanud eraldada: paigalda poppler-utils (pdftotext) või pypdf]", 0
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return "".join(f"\n=== lk {i} ===\n{t}" for i, t in enumerate(pages, 1)), len(pages)


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_text(data: bytes, name: str) -> str:
    if shutil.which("pandoc"):
        p = subprocess.run(["pandoc", "-f", "docx", "-t", "gfm", "--wrap=none"], input=data,
                           capture_output=True, timeout=180)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.decode("utf-8", "replace")
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml"))
    lines = []
    for el in root.iter():
        if el.tag == W + "p":
            lines.append("".join(t.text or "" for t in el.iter(W + "t")))
        elif el.tag == W + "tr":
            lines.append(" | ".join("".join(t.text or "" for t in c.iter(W + "t")) for c in el.iter(W + "tc")))
    return "\n".join(lines)


S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def xlsx_text(data: bytes) -> str:
    z = zipfile.ZipFile(io.BytesIO(data))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(S + "si"):
            shared.append("".join(t.text or "" for t in si.iter(S + "t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels}
    out = []
    for sh in wb.iter(S + "sheet"):
        path = target.get(sh.get(R + "id"), "")
        path = path.lstrip("/") if path.startswith("/") else "xl/" + path
        if path not in z.namelist():
            continue
        out.append(f"\n=== leht: {sh.get('name')} ===")
        for row in ET.fromstring(z.read(path)).iter(S + "row"):
            cells = []
            for c in row.iter(S + "c"):
                v = c.find(S + "v")
                if c.get("t") == "s" and v is not None:
                    val = shared[int(v.text)]
                elif c.get("t") == "inlineStr":
                    val = "".join(t.text or "" for t in c.iter(S + "t"))
                else:
                    val = v.text if v is not None else ""
                cells.append(f"{c.get('r')}={val}" if val else "")
            line = "\t".join(x for x in cells if x)
            if line:
                out.append(f"r{row.get('r')}\t{line}")
    return "\n".join(out)


def to_text(name: str, data: bytes) -> tuple[str | None, int]:
    ext = Path(name).suffix.lower()
    try:
        if ext == ".pdf":
            return pdf_text(data)
        if ext == ".docx":
            return docx_text(data, name), 0
        if ext == ".xlsx":
            return xlsx_text(data), 0
        if ext in {".txt", ".csv", ".md", ".xml", ".rtf"}:
            return data.decode("utf-8", "replace"), 0
    except Exception as e:
        return f"[Teksti eraldamine ebaõnnestus: {e}]", 0
    return None, 0


def safe(name: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", name, flags=re.U).strip("_")[:150]


CORE = re.compile(r"hankepass|vastavus|hindamis|leping|tehniline_?\s?kirjeldus|hinnapakkumis|pakkumus|alltöövõt|"
                  r"etü|üldtingimus|ühispakkum|volikiri|kvalifitseeri|selgitus|lisa[ _-]?\d", re.I)
PROJECT = re.compile(r"seletus|kirjeldus|spets|nimekiri|mahu|maht|koond|arvutus|energiam|tuleohutus|graafik|"
                     r"üldosa|lähteülesanne|ekspertiis|uuring", re.I)
GROUP_TITLES = {
    "A": "A. Hankedokumendid: loe täielikult",
    "B": "B. Projekti seletuskirjad ja spetsifikatsioonid: loe sihitult, osade kaupa",
    "C": "C. Muu tekstiga materjal (tootelehed, hooldusjuhendid, tekstiga joonised): ainult vajadusel",
    "D": "D. Joonised ja failid ilma tekstita",
}


def classify(index: list[dict]) -> None:
    seen: dict[str, str] = {}
    for r in sorted(index, key=lambda r: (Path(r["fail"]).suffix.lower() != ".docx", r["fail"])):
        name = Path(r["fail"]).name
        top_level = "/" not in r["fail"]
        if r["olek"] != "tekst":
            r["grupp"] = "D"
        elif name.lower().endswith(".xml") and "espd" in name.lower():
            r["grupp"] = "C"  # ESPD XML kordab hankepassi masinloetaval kujul
        elif CORE.search(name) and (top_level or r["fail"].lower().startswith("lisa")):
            r["grupp"] = "A"
        elif top_level:
            r["grupp"] = "A"
        elif PROJECT.search(name):
            r["grupp"] = "B"
        else:
            r["grupp"] = "C"
        if r["grupp"] in "BC":
            key = re.sub(r"[^a-z0-9]", "", Path(name).stem.lower())
            if key in seen:
                r["duplikaat"] = seen[key]
            else:
                seen[key] = r["fail"]


def render_index(index: list[dict], h: dict, g: dict, pid: int) -> str:
    cost = g.get("cost")
    lines = [f"# {h.get('referenceNumber')} {h.get('procurementName')}",
             f"Hankija: {h.get('contractingAuthorityName')} · Pakkumuste tähtaeg: {(h.get('submissionDate') or '')[:16]}"
             f" · Eeldatav maksumus: {f'{cost:,.0f} €'.replace(',', ' ') if cost else 'avalikustamata'}"
             f" · Leping: {(g.get('startDate') or '')[:10]} – {(g.get('endDate') or '')[:10]}",
             f"Register: {WEB.format(id=pid)}", "",
             f"Faile kokku {len(index)}, loetava tekstiga {sum(r['olek'] == 'tekst' for r in index)}, "
             f"lehekülgi {sum(r.get('lk') or 0 for r in index)}. Tekstifaili nimi = algne tee paketis (`/` → `__`). "
             f"Sama dokumendi PDF/DOCX duplikaadid on peidetud.", ""]
    for grp in "ABC":
        rows = [r for r in index if r["grupp"] == grp and not r.get("duplikaat")]
        if not rows:
            continue
        rows = sorted(rows, key=lambda r: r["fail"])
        if grp == "C" and len(rows) > 40:
            hidden = len(rows) - 40
            rows = sorted(rows, key=lambda r: -(r.get("tähemärke") or 0))[:40]
        else:
            hidden = 0
        lines += [f"## {GROUP_TITLES[grp]}", "", "| tekstifail (tekst/…) | lk | tähemärke |", "|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['tekst'][6:]} | {r.get('lk') or ''} | {r.get('tähemärke')} |")
        if hidden:
            lines.append(f"\n…ja veel {hidden} väiksemat faili (täielik loetelu: index.json).")
        lines.append("")
    dup = sum(1 for r in index if r.get("duplikaat"))
    d_rows = [r for r in index if r["grupp"] == "D"]
    per_top: dict[str, int] = {}
    for r in d_rows:
        per_top[r["fail"].split("/")[0]] = per_top.get(r["fail"].split("/")[0], 0) + 1
    lines += [f"## {GROUP_TITLES['D']}", "", f"{len(d_rows)} faili (täielik loetelu: index.json). Paketiti:"]
    lines += [f"- {k}: {v}" for k, v in sorted(per_top.items())]
    lines += ["", f"Duplikaate (sama dokument teises vormingus) peidetud: {dup}. Vaata index.json välja `duplikaat`."]
    return "\n".join(lines) + "\n"


def cmd_fetch(a: argparse.Namespace) -> None:
    pid = resolve_id(a.hange)
    d = Path(a.dir)
    (d / "tekst").mkdir(parents=True, exist_ok=True)
    log(f"Hanke ID {pid}: laen üldandmed…")
    h = get_json(f"/procurement/{pid}/header-info")
    ver = get_json(f"/procurement/{pid}/latest-version").get("value")
    g = get_json(f"/proc-vers/{ver}/general-info")
    g.pop("procedureTypes", None)
    meta = {"id": pid, "link": WEB.format(id=pid), "header": h, "general": g}
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"  {h.get('referenceNumber')} {h.get('procurementName')} — {h.get('contractingAuthorityName')}")

    pkg = d / "_pakett.zip"
    if pkg.exists() and zipfile.is_zipfile(pkg) and not a.uuesti:
        log("  pakett juba olemas, kasutan seda (--uuesti laeb uuesti)")
    else:
        url = get_json(f"/procurement/{pid}/documents-temp-url").get("value")
        if not url:
            raise SystemExit("Registris pole avalikke hankedokumente.")
        download(BASE + url, pkg)

    max_bytes = int(a.max_mb * 1e6)
    index = []

    def handle(display: str, data: bytes, depth: int) -> None:
        ext = Path(display).suffix.lower()
        if ext == ".zip" and depth < 2:
            try:
                inner = zipfile.ZipFile(io.BytesIO(data))
            except zipfile.BadZipFile:
                index.append({"fail": display, "mb": len(data) / 1e6, "olek": "vigane zip"})
                return
            for zi in inner.infolist():
                if zi.is_dir():
                    continue
                sub = f"{display}/{zi.filename}"
                if Path(zi.filename).suffix.lower() in TEXT_EXT | {".zip"} and zi.file_size <= max_bytes:
                    handle(sub, inner.read(zi), depth + 1)
                else:
                    index.append({"fail": sub, "mb": zi.file_size / 1e6, "olek": "ainult nimi"})
            return
        txt, pages = to_text(display, data)
        if txt is None:
            index.append({"fail": display, "mb": len(data) / 1e6, "olek": "ainult nimi"})
            return
        out = d / "tekst" / (safe(display.replace("/", "__")) + ".txt")
        out.write_text(f"# ALLIKAS: {display}\n{txt}", encoding="utf-8")
        chars = len(re.sub(r"\s+", "", txt))
        index.append({"fail": display, "mb": len(data) / 1e6, "lk": pages, "tähemärke": chars,
                      "tekst": str(out.relative_to(d)), "olek": "tekst" if chars > 200 else "vähe teksti (joonis?)"})

    log("Pakin lahti ja eraldan teksti…")
    with zipfile.ZipFile(pkg) as z:
        for zi in z.infolist():
            if zi.is_dir():
                continue
            ext = Path(zi.filename).suffix.lower()
            if ext in TEXT_EXT | {".zip"}:
                log(f"  {zi.filename} ({zi.file_size/1e6:.1f} MB)")
                handle(zi.filename, z.read(zi), 0)
            else:
                index.append({"fail": zi.filename, "mb": zi.file_size / 1e6, "olek": "ainult nimi"})

    classify(index)
    (d / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "INDEX.md").write_text(render_index(index, h, g, pid), encoding="utf-8")
    n_txt = sum(1 for r in index if r["olek"] == "tekst")
    log(f"Valmis: {len(index)} faili, neist {n_txt} loetava tekstiga → {d}/INDEX.md")
    if not a.hoia_zip:
        pkg.unlink(missing_ok=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("radar", help="avatud ehitushanked registrist → JSON")
    r.add_argument("--out", default="ehitushanked/radar.json")
    r.add_argument("--koik-liigid", action="store_true", help="lisa ehitusega seotud teenused (projekteerimine, järelevalve)")
    r.set_defaults(fn=cmd_radar)
    f = sp.add_parser("fetch", help="lae hanke alusdokumendid alla ja eralda tekst")
    f.add_argument("hange", help="viitenumber (315920), registri link või sisemine ID")
    f.add_argument("--dir", required=True)
    f.add_argument("--max-mb", type=float, default=25, help="suurim üksikfail, millest teksti eraldada")
    f.add_argument("--hoia-zip", action="store_true", help="ära kustuta allalaaditud paketti")
    f.add_argument("--uuesti", action="store_true", help="lae pakett uuesti alla")
    f.set_defaults(fn=cmd_fetch)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
