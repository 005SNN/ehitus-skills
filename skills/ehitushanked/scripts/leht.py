#!/usr/bin/env python3
"""Tsitaadi koht algdokumendis: lõige lehest ja tsitaadi read, mille aruanne märgib punasega.

Vajab poppler-utils (pdftotext, pdftoppm). Wordi failid teisendatakse PDF-iks LibreOffice'iga,
kui see on paigaldatud. Kui midagi puudub, tagastab None ja aruanne jääb ilma lehepildita.

  python3 leht.py ehitushanked/315920 "ETA = 99 kWh/(m²a), mis vastab A-energiaklassi nõuetele"
"""
from __future__ import annotations

import base64
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DPI = 120          # lehepildi resolutsioon
MARGIN_X = 28      # punktides tsitaadi ümber
MARGIN_Y = 55
MIN_W, MAX_W = 430, 640
WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')
PAGE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.S)


def tokens(t: str) -> list[str]:
    return re.findall(r"\w+", (t or "").lower())


class Lehed:
    def __init__(self, hanke_dir: str | Path):
        self.d = Path(hanke_dir)
        self.orig: dict[str, Path] = {}
        self.names: dict[str, str] = {}
        ix = self.d / "index.json"
        if ix.exists() and shutil.which("pdftotext") and shutil.which("pdftoppm"):
            for r in json.loads(ix.read_text(encoding="utf-8")):
                if r.get("originaal") and (self.d / r["originaal"]).exists():
                    self.orig[Path(r["tekst"]).name] = self.d / r["originaal"]
                    self.names[Path(r["tekst"]).name] = Path(r["fail"]).name
        self._pages: dict[Path, list] = {}

    def pdf(self, tekst_name: str) -> Path | None:
        src = self.orig.get(tekst_name)
        if not src:
            return None
        if src.suffix.lower() == ".pdf":
            return src
        office = shutil.which("soffice") or shutil.which("libreoffice")
        if not office:
            return None
        out_dir = self.d / "originaalid" / "_pdf"
        out = out_dir / (src.stem + ".pdf")
        if not out.exists():
            out_dir.mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td) / ("in" + src.suffix)
                tmp.write_bytes(src.read_bytes())
                subprocess.run([office, "--headless", "--convert-to", "pdf", "--outdir", td, str(tmp)],
                               capture_output=True, timeout=180)
                made = Path(td) / "in.pdf"
                if not made.exists():
                    return None
                shutil.move(str(made), out)
        return out

    def pages(self, pdf: Path) -> list:
        if pdf not in self._pages:
            p = subprocess.run(["pdftotext", "-bbox", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, timeout=180)
            res = []
            for w, h, body in PAGE.findall(p.stdout.decode("utf-8", "replace")):
                words = [(float(a), float(b), float(c), float(dd), html.unescape(t)) for a, b, c, dd, t in WORD.findall(body)]
                res.append((float(w), float(h), words))
            self._pages[pdf] = res
        return self._pages[pdf]

    def find(self, pdf: Path, quote: str):
        """Leiab tsitaadi sõnade järjestuse lehel. Tagastab (lk, laius, kõrgus, sõnakastid) või None."""
        q = tokens(quote)
        if not q:
            return None
        for n, (pw, ph, words) in enumerate(self.pages(pdf), 1):
            flat = [(tok, i) for i, w in enumerate(words) for tok in tokens(w[4])]
            seq = [t for t, _ in flat]
            for need in (len(q), min(len(q), 8)):  # täpne vaste, siis tsitaadi algus
                hit = next((s for s in range(len(seq) - need + 1) if seq[s:s + need] == q[:need]), None)
                if hit is not None:
                    idx = sorted({flat[k][1] for k in range(hit, hit + need)})
                    return n, pw, ph, [words[i][:4] for i in idx]
        return None

    def snippet(self, tekst_name: str, quote: str) -> dict | None:
        try:
            pdf = self.pdf(tekst_name)
            hit = pdf and self.find(pdf, quote)
        except (subprocess.TimeoutExpired, OSError):
            return None
        if not hit:
            return None
        n, pw, ph, boxes = hit
        lines: list[list[float]] = []  # sõnad ridadeks
        for x0, y0, x1, y1 in sorted(boxes, key=lambda b: (round(b[1]), b[0])):
            if lines and abs(lines[-1][1] - y0) < 3:
                ln = lines[-1]
                ln[0], ln[2], ln[3] = min(ln[0], x0), max(ln[2], x1), max(ln[3], y1)
            else:
                lines.append([x0, y0, x1, y1])
        qx0, qx1 = min(b[0] for b in lines), max(b[2] for b in lines)
        qy0, qy1 = min(b[1] for b in lines), max(b[3] for b in lines)
        words = self.pages(pdf)[n - 1][2]
        # lõige täisridadega: ülemine ja alumine piir sõnade servast, mitte poolest reast
        above = [w for w in words if w[1] >= qy0 - MARGIN_Y and w[3] <= qy1 + MARGIN_Y]
        y0 = min([w[1] for w in above] + [qy0 - 4]) - 3
        y1 = max([w[3] for w in above] + [qy1 + 4]) + 3
        # laius: tekstiveeru servad, kui veerg on tavalise lehe laiune; joonistel aken tsitaadi ümber
        band = [w for w in words if w[3] >= y0 and w[1] <= y1]
        x0 = min([w[0] for w in band] + [qx0]) - 12
        x1 = max([w[2] for w in band] + [qx1]) + 12
        if x1 - x0 > MAX_W:
            x0 = max(x0, min(qx0 - MARGIN_X, (qx0 + qx1) / 2 - MAX_W / 2))
            x1 = x0 + MAX_W
        if x1 - x0 < MIN_W:
            pad = (MIN_W - (x1 - x0)) / 2
            x0, x1 = x0 - pad, x1 + pad
        x0, x1 = max(0, x0), min(pw, x1)
        y0, y1 = max(0, y0), min(ph, y1)
        s = DPI / 72
        X, Y, W, H = (round(v * s) for v in (x0, y0, x1 - x0, y1 - y0))
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "lk"
            subprocess.run(["pdftoppm", "-r", str(DPI), "-f", str(n), "-l", str(n), "-x", str(X), "-y", str(Y),
                            "-W", str(W), "-H", str(H), "-gray", "-jpeg", "-jpegopt", "quality=70", "-singlefile",
                            str(pdf), str(out)], capture_output=True, timeout=120)
            jpg = out.with_suffix(".jpg")
            if not jpg.exists():
                return None
            b64 = base64.b64encode(jpg.read_bytes()).decode()
        py = 4 if len(lines) == 1 else 1  # mitmerealisel tsitaadil raamid ei kattu
        rects = [(round(a * s) - X - 5, round(b * s) - Y - py, round((c - a) * s) + 10, round((dd - b) * s) + 2 * py)
                 for a, b, c, dd in lines]
        return {"jpeg": b64, "w": W, "h": H, "lk": n, "read": rects, "fail": self.names[tekst_name]}


if __name__ == "__main__":
    r = Lehed(sys.argv[1])
    from render import norm  # type: ignore  # samast kaustast
    q = sys.argv[2]
    for f in sorted((Path(sys.argv[1]) / "tekst").glob("*.txt")):
        if norm(q) in norm(f.read_text(encoding="utf-8", errors="ignore")):
            sn = r.snippet(f.name, q)
            print(f.name, "→", {k: v for k, v in sn.items() if k != "jpeg"} if sn else "lehte ei leitud")
