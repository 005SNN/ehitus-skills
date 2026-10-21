#!/usr/bin/env python3
"""Ehitusturu ajalugu riigihangete registrist: kes võitis, mitme pakkujaga, mis hinnaga.

  python3 turg.py lae [--kuud 24]                           # lepingute ajalugu vahemällu (~1 min esimesel korral)
  python3 turg.py vordle --cpv 45214220 [--maksumus 7015000] [--piirkond EE001] [--hankija "Keila"]
                         [--kestus-kuud 19] --out ehitushanked/315920/turg.json
  python3 turg.py indeks                                    # ehitushinnaindeks (Statistikaamet)

Allikad: riigihanked.riik.ee avaandmed (eForms XML: notice_award ja notice) ning andmed.stat.ee IA10.
Ainult Pythoni standardteek.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import statistics
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

OPEN = "https://riigihanked.riik.ee/rhr/api/public/v1/opendata/{kind}/{y}/month/{m}/xml"
STAT = "https://andmed.stat.ee/api/v1/et/stat/majandus/hinnad/IA10.PX"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ehitushanked"
UA = {"User-Agent": "ehitushanked-skill/1.0"}

CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
EFAC = "http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1"
EFBC = "http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1"
NS = {"cbc": CBC, "cac": CAC, "efac": EFAC, "efbc": EFBC}

REGIONS = {"EE001": "Põhja-Eesti", "EE004": "Lääne-Eesti", "EE008": "Lõuna-Eesti", "EE009": "Kesk-Eesti",
           "EE00A": "Kirde-Eesti"}


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def fetch(url: str, timeout: int = 120) -> bytes:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                raise RuntimeError(f"{url}: {e}") from e
            time.sleep(2 * (attempt + 1))
    return b""


def num(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- parsimine

LEGAL = [(re.compile(r"^(aktsiaselts|as)\s+|\s+(aktsiaselts|as)$", re.I), "AS"),
         (re.compile(r"^(osaühing|oü)\s+|\s+(osaühing|oü)$", re.I), "OÜ")]


def firma(name: str) -> str:
    """Ühtne kuju: „aktsiaselts TARTU EHITUS” → „Tartu Ehitus AS”, „OÜ Nordlin Ehitus” → „Nordlin Ehitus OÜ”."""
    n = " ".join((name or "").split())
    form = ""
    for rx, short in LEGAL:
        if rx.search(n):
            n, form = rx.sub("", n).strip(), short
            break
    if n.isupper() and len(n) > 5:
        n = " ".join(w if len(w) <= 3 else w.capitalize() for w in n.split())
    return f"{n} {form}".strip()


def parse_awards(xml: bytes) -> list[dict]:
    """Ehitustööde (CPV 45*) võitnud osad lepingu sõlmimise teadetest."""
    out = []
    root = ET.fromstring(xml)
    for n in root:
        cpvs = [x.text or "" for x in n.iter(f"{{{CBC}}}ItemClassificationCode")]
        if not any(c.startswith("45") for c in cpvs):
            continue
        orgs = {}
        for o in n.iter(f"{{{EFAC}}}Organization"):
            c = o.find("efac:Company", NS)
            if c is None:
                continue
            orgs[c.findtext("cac:PartyIdentification/cbc:ID", namespaces=NS)] = {
                "nimi": (c.findtext("cac:PartyName/cbc:Name", namespaces=NS) or "").strip(),
                "kood": c.findtext("cac:PartyLegalEntity/cbc:CompanyID", namespaces=NS),
                "piirkond": c.findtext("cac:PostalAddress/cbc:CountrySubentityCode", namespaces=NS),
                "linn": c.findtext("cac:PostalAddress/cbc:CityName", namespaces=NS),
            }
        parties = {tp.findtext("cbc:ID", namespaces=NS): [firma(orgs.get(t.findtext("cbc:ID", namespaces=NS), {}).get("nimi", "?"))
                                                          for t in tp.findall("efac:Tenderer", NS)]
                   for tp in n.iter(f"{{{EFAC}}}TenderingParty")}
        tenders = {}
        for lt in n.iter(f"{{{EFAC}}}LotTender"):
            # LotResult sees on ka viide LotTender-ile ilma summata: jäta need vahele
            if lt.find("cac:LegalMonetaryTotal", NS) is None:
                continue
            tenders[lt.findtext("cbc:ID", namespaces=NS)] = (
                lt.findtext("cac:LegalMonetaryTotal/cbc:PayableAmount", namespaces=NS),
                lt.findtext("efac:TenderingParty/cbc:ID", namespaces=NS))
        lots = {}
        for pl in n.findall(".//cac:ProcurementProjectLot", NS):
            pp = pl.find("cac:ProcurementProject", NS)
            if pp is None:
                continue
            fa = pl.find(".//cac:ContractingSystem/cbc:ContractingSystemTypeCode", NS)
            lots[pl.findtext("cbc:ID", namespaces=NS)] = {
                "nimi": (pp.findtext("cbc:Name", namespaces=NS) or "").strip(),
                "cpv": pp.findtext("cac:MainCommodityClassification/cbc:ItemClassificationCode", namespaces=NS),
                "koht": pp.findtext("cac:RealizedLocation/cac:Address/cbc:CountrySubentityCode", namespaces=NS),
                "linn": pp.findtext("cac:RealizedLocation/cac:Address/cbc:CityName", namespaces=NS),
                "raamleping": bool(fa is not None and (fa.text or "").startswith("fa")),
            }
        buyer = orgs.get(n.findtext("cac:ContractingParty/cac:Party/cac:PartyIdentification/cbc:ID", namespaces=NS), {})
        folder = n.findtext("cbc:ContractFolderID", namespaces=NS)
        date = (n.findtext(".//efbc:TransmissionDate", namespaces=NS) or n.findtext("cbc:IssueDate", namespaces=NS) or "")[:10]
        for lr in n.iter(f"{{{EFAC}}}LotResult"):
            if lr.findtext("cbc:TenderResultCode", namespaces=NS) != "selec-w":
                continue
            lot_id = lr.findtext("efac:TenderLot/cbc:ID", namespaces=NS)
            bids, counts = None, []
            for st in lr.findall("efac:ReceivedSubmissionsStatistics", NS):
                v = num(st.findtext("efbc:StatisticsNumeric", namespaces=NS))
                if st.findtext("efbc:StatisticsCode", namespaces=NS) == "tenders":
                    bids = v
                elif v is not None:
                    counts.append(v)
            if bids is None and counts:
                # alates 02.2026 jätab register StatisticsCode välja; pakkumuste koguarv on alamliikidest suurim
                bids = max(counts)
            amt, tp = tenders.get(lr.findtext("efac:LotTender/cbc:ID", namespaces=NS), (None, None))
            lot = lots.get(lot_id, {})
            if lot.get("cpv") and not lot["cpv"].startswith("45"):
                continue
            out.append({
                "kaust": folder, "osa": lot_id, "kuupaev": date,
                "nimi": lot.get("nimi"), "cpv": lot.get("cpv") or next((c for c in cpvs if c.startswith("45")), None),
                "piirkond": lot.get("koht") or buyer.get("piirkond"), "linn": lot.get("linn") or buyer.get("linn"),
                "hankija": buyer.get("nimi"), "voitja": parties.get(tp) or [],
                "summa": num(amt), "pakkumusi": int(bids) if bids is not None else None,
                "raamleping": lot.get("raamleping", False),
            })
    return out


def parse_estimates(xml: bytes) -> dict[str, float]:
    """Hankija eeldatav maksumus hanketeadetest: {kaust|osa: summa}."""
    est = {}
    root = ET.fromstring(xml)
    for n in root:
        folder = n.findtext("cbc:ContractFolderID", namespaces=NS)
        if not folder:
            continue
        total = n.findtext("cac:ProcurementProject/cac:RequestedTenderTotal/cbc:EstimatedOverallContractAmount", namespaces=NS)
        if num(total):
            est[f"{folder}|*"] = num(total)
        for pl in n.findall(".//cac:ProcurementProjectLot", NS):
            v = pl.findtext("cac:ProcurementProject/cac:RequestedTenderTotal/cbc:EstimatedOverallContractAmount", namespaces=NS)
            if num(v):
                est[f"{folder}|{pl.findtext('cbc:ID', namespaces=NS)}"] = num(v)
    return est


def month_list(months: int) -> list[tuple[int, int]]:
    today = dt.date.today()
    y, m = today.year, today.month
    out = []
    for _ in range(months):
        out.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def load_month(kind: str, y: int, m: int) -> tuple[str, object]:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (f"{kind}-{y}-{m:02d}.v2.json" if kind == "notice_award" else f"{kind}-{y}-{m:02d}.json")
    current = (y, m) == (dt.date.today().year, dt.date.today().month)
    if f.exists() and not (current and time.time() - f.stat().st_mtime > 6 * 3600):
        return kind, json.loads(f.read_text(encoding="utf-8"))
    xml = fetch(OPEN.format(kind=kind, y=y, m=m))
    data = parse_awards(xml) if kind == "notice_award" else parse_estimates(xml)
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return kind, data


def load_history(months: int) -> list[dict]:
    jobs = [(k, y, m) for (y, m) in month_list(months) for k in ("notice_award", "notice")]
    # hanketeated algavad varem kui lepingud: lisa 12 kuud eelarvete jaoks
    jobs += [("notice", y, m) for (y, m) in month_list(months + 12)[months:]]
    awards, est = [], {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for i, (kind, data) in enumerate(ex.map(lambda j: load_month(*j), jobs), 1):
            if kind == "notice_award":
                awards += data
            else:
                est.update(data)
            if i % 12 == 0:
                log(f"  {i}/{len(jobs)} kuufaili…")
    for a in awards:
        e = est.get(f"{a['kaust']}|{a['osa']}") or est.get(f"{a['kaust']}|*")
        a["eelarve"] = e
    log(f"Lepinguid {len(awards)}, neist hankija eelarvega {sum(1 for a in awards if a['eelarve'])} ({time.time()-t0:.0f} s).")
    return awards


# ---------------------------------------------------------------- võrdlus

def q(vals: list[float], p: float) -> float | None:
    vals = sorted(vals)
    if not vals:
        return None
    k = (len(vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def comparables(awards: list[dict], cpv: str, value: float | None, region: str | None) -> tuple[list[dict], str]:
    pool = [a for a in awards if a["cpv"] and a["summa"] and not a["raamleping"]]
    for digits in (5, 4, 3):
        sel = [a for a in pool if a["cpv"][:digits] == cpv[:digits]]
        if value:
            sel = [a for a in sel if value / 3 <= a["summa"] <= value * 3]
        if len(sel) >= 15:
            break
    basis = f"CPV {cpv[:digits]}*" + (f", maksumus {value/3/1e6:.1f}–{value*3/1e6:.1f} M€".replace(".", ",") if value else "")
    if region:
        local = [a for a in sel if a["piirkond"] == region]
        if len(local) >= 20:
            sel, basis = local, basis + f", {REGIONS.get(region, region)}"
    return sorted(sel, key=lambda a: a["kuupaev"], reverse=True), basis


def cpv_stats(awards: list[dict]) -> dict[str, dict]:
    """Pakkujate arvu mediaan CPV 5 esimese numbri kaupa (radari jaoks)."""
    groups: dict[str, list[int]] = defaultdict(list)
    for x in awards:
        if x["cpv"] and x["pakkumusi"] and not x["raamleping"]:
            groups[x["cpv"][:5]].append(x["pakkumusi"])
    return {k: {"n": len(v), "pakkujaid": statistics.median(v)} for k, v in groups.items() if len(v) >= 5}


def cmd_vordle(a: argparse.Namespace) -> None:
    awards = load_history(a.kuud)
    sel, basis = comparables(awards, a.cpv.replace("-", ""), a.maksumus, a.piirkond)
    bids = [x["pakkumusi"] for x in sel if x["pakkumusi"]]
    # Võidusumma ja hankija eelarve suhe: eelarve on teadetes harvem, seega laiem valim (sama CPV 3 kohta, sama mahuvahemik)
    cpv = a.cpv.replace("-", "")
    ratio_pool = [x for x in awards if x["eelarve"] and x["summa"] and not x["raamleping"] and (x["cpv"] or "")[:3] == cpv[:3]
                  and (not a.maksumus or a.maksumus / 3 <= x["eelarve"] <= a.maksumus * 3)]
    ratios = [x["summa"] / x["eelarve"] for x in ratio_pool if 0.3 < x["summa"] / x["eelarve"] < 2]
    ratio_basis = f"CPV {cpv[:3]}*" + (f", eelarve {a.maksumus/3/1e6:.1f}–{a.maksumus*3/1e6:.1f} M€".replace(".", ",") if a.maksumus else "")
    winners: dict[str, dict] = defaultdict(lambda: {"voite": 0, "summa": 0.0, "pakkujaid": []})
    for x in sel:
        w = " + ".join(sorted(firma(n) for n in x["voitja"])) or "?"  # ühispakkujad ühe reana
        winners[w]["voite"] += 1
        winners[w]["summa"] += x["summa"] or 0
        if x["pakkumusi"]:
            winners[w]["pakkujaid"].append(x["pakkumusi"])
    top = sorted(winners.items(), key=lambda kv: (-kv[1]["voite"], -kv[1]["summa"]))[:10]
    res = {
        "alus": basis, "periood_kuud": a.kuud, "allikas": "riigihangete register, lepingu sõlmimise teated (avaandmed)",
        "vordluslepinguid": len(sel),
        "pakkujaid": {"mediaan": statistics.median(bids) if bids else None,
                      "uks_pakkuja_osakaal": round(sum(1 for b in bids if b == 1) / len(bids), 2) if bids else None,
                      "jaotus": {k: sum(1 for b in bids if (b >= 5 if k == "5+" else b == int(k))) for k in ("1", "2", "3", "4", "5+")}},
        "voit_vs_eelarve": {"alus": ratio_basis, "n": len(ratios),
                            "alla_eelarve_osakaal": round(sum(1 for r in ratios if r < 1) / len(ratios), 2) if ratios else None, "mediaan": round(statistics.median(ratios), 3) if ratios else None,
                            "p25": round(q(ratios, .25), 3) if ratios else None, "p75": round(q(ratios, .75), 3) if ratios else None},
        "voidusumma": {"p25": q([x["summa"] for x in sel], .25), "mediaan": q([x["summa"] for x in sel], .5),
                       "p75": q([x["summa"] for x in sel], .75)},
        "sagedasemad_voitjad": [{"nimi": k, "voite": v["voite"], "summa": round(v["summa"]),
                                 "keskmiselt_pakkujaid": round(statistics.mean(v["pakkujaid"]), 1) if v["pakkujaid"] else None}
                                for k, v in top],
        "viimased": [{k: x[k] for k in ("kuupaev", "nimi", "hankija", "voitja", "summa", "eelarve", "pakkumusi", "linn")}
                     for x in sel[:12]],
    }
    if a.maksumus and ratios:
        res["hinnavahemik"] = {"eelarve": a.maksumus, "p25": round(a.maksumus * q(ratios, .25)),
                               "mediaan": round(a.maksumus * statistics.median(ratios)), "p75": round(a.maksumus * q(ratios, .75))}
    if a.hankija:
        own = [x for x in awards if x["hankija"] and a.hankija.lower() in x["hankija"].lower()]
        res["hankija_ajalugu"] = [{k: x[k] for k in ("kuupaev", "nimi", "voitja", "summa", "pakkumusi")} for x in own[:10]]
    if a.kestus_kuud:
        try:
            res["hinnarisk"] = price_risk(a.kestus_kuud, a.maksumus)
        except Exception as e:  # noqa: BLE001
            res["hinnarisk"] = {"viga": str(e)}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    p = res["pakkujaid"]
    log(f"Võrdlus: {len(sel)} lepingut ({basis}). Pakkujaid mediaanis {p['mediaan']}, "
        f"ühe pakkujaga {int((p['uks_pakkuja_osakaal'] or 0)*100)}%. "
        + (f"Võit/eelarve mediaan {res['voit_vs_eelarve']['mediaan']:.0%}. " if ratios else "")
        + f"→ {a.out}")


# ---------------------------------------------------------------- hinnaindeks

def price_index() -> dict:
    years = [str(y) for y in range(dt.date.today().year - 2, dt.date.today().year + 1)]
    body = {"query": [
        {"code": "Aasta", "selection": {"filter": "item", "values": years}},
        {"code": "Ressursigrupp", "selection": {"filter": "item", "values": ["1", "2", "3", "4"]}},
        {"code": "Ehituse liik", "selection": {"filter": "item", "values": ["1"]}},
        {"code": "Kvartal", "selection": {"filter": "all", "values": ["*"]}}],
        "response": {"format": "json-stat2"}}
    req = urllib.request.Request(STAT, data=json.dumps(body).encode(), headers={**UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        js = json.loads(r.read())
    dims = js["id"]
    sizes = js["size"]
    cats = [list(js["dimension"][d]["category"]["index"].keys()) for d in dims]
    labels = {d: js["dimension"][d]["category"].get("label", {}) for d in dims}
    series: dict[str, dict[str, float]] = defaultdict(dict)
    for flat, v in enumerate(js["value"]):
        if v is None:
            continue
        idx, rem = [], flat
        for s in reversed(sizes):
            idx.append(rem % s)
            rem //= s
        idx.reverse()
        key = {d: cats[i][idx[i]] for i, d in enumerate(dims)}
        group = labels["Ressursigrupp"].get(key["Ressursigrupp"], key["Ressursigrupp"])
        series[group][f"{key['Aasta']}-{labels['Kvartal'].get(key['Kvartal'], key['Kvartal'])}"] = v
    out = {}
    for group, pts in series.items():
        ks = sorted(pts)
        last, prev = ks[-1], ks[-5] if len(ks) >= 5 else None
        out[group] = {"viimane": last, "indeks": pts[last],
                      "muutus_aastaga": round(pts[last] / pts[prev] - 1, 4) if prev else None}
    return out


def price_risk(months: int, value: float | None) -> dict:
    idx = price_index()
    total = next((v for k, v in idx.items() if "kokku" in k.lower() or k == "1"), next(iter(idx.values())))
    yoy = total["muutus_aastaga"] or 0
    # fikseeritud hinnaga töö: kulud kasvavad keskmiselt poole perioodi jooksul
    drift = (1 + yoy) ** (months / 12 / 2) - 1
    res = {"allikas": "Statistikaamet IA10, ehitushinnaindeks", "kvartal": total["viimane"],
           "aastamuutus": yoy, "kestus_kuud": months, "eeldatav_kallinemine": round(drift, 4),
           "grupid": {k: v["muutus_aastaga"] for k, v in idx.items()}}
    if value:
        res["summa_eur"] = round(value * drift)
    return res


def cmd_indeks(a: argparse.Namespace) -> None:
    print(json.dumps(price_risk(a.kestus_kuud, a.maksumus), ensure_ascii=False, indent=1))


def cmd_lae(a: argparse.Namespace) -> None:
    load_history(a.kuud)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    l_ = sp.add_parser("lae")
    l_.add_argument("--kuud", type=int, default=24)
    l_.set_defaults(fn=cmd_lae)
    v = sp.add_parser("vordle")
    v.add_argument("--cpv", required=True)
    v.add_argument("--maksumus", type=float)
    v.add_argument("--piirkond", help="NUTS3: EE001 Põhja-Eesti, EE004 Lääne-, EE008 Lõuna-, EE009 Kesk-, EE00A Kirde-Eesti")
    v.add_argument("--hankija")
    v.add_argument("--kestus-kuud", type=int, help="lepingu kestus hinnariski arvutuseks")
    v.add_argument("--kuud", type=int, default=24)
    v.add_argument("--out", required=True)
    v.set_defaults(fn=cmd_vordle)
    i = sp.add_parser("indeks")
    i.add_argument("--kestus-kuud", type=int, default=24)
    i.add_argument("--maksumus", type=float)
    i.set_defaults(fn=cmd_indeks)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
