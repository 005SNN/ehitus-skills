#!/usr/bin/env python3
"""Selgitustaotlus hankijale Wordi failina (.docx), aruande JSON-ist. Ainult Pythoni standardteek.

  python3 taotlus.py ehitushanked/315920/aruanne.json --firma "Näidis Ehitus OÜ" --out ehitushanked/315920/selgitustaotlus.docx
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults>
 <w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/><w:sz w:val="22"/><w:lang w:val="et-EE"/></w:rPr></w:rPrDefault>
 <w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>
 <w:pPr><w:spacing w:before="240" w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Small"><w:name w:val="Small"/><w:basedOn w:val="Normal"/>
 <w:pPr><w:spacing w:after="0"/></w:pPr><w:rPr><w:sz w:val="20"/><w:color w:val="555555"/></w:rPr></w:style>
</w:styles>"""

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def run(text: str, *, bold: bool = False, small: bool = False, grey: bool = False) -> str:
    props = ""
    if bold or small or grey:
        props = "<w:rPr>" + ("<w:b/>" if bold else "") + ("<w:color w:val=\"555555\"/>" if grey else "") \
                + ("<w:sz w:val=\"19\"/>" if small else "") + "</w:rPr>"
    return f'<w:r>{props}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def para(*runs: str, style: str | None = None, indent_hanging: bool = False, align: str | None = None) -> str:
    ppr = ""
    if style or indent_hanging or align:
        ppr = "<w:pPr>" + (f'<w:pStyle w:val="{style}"/>' if style else "") \
              + ('<w:ind w:left="425" w:hanging="425"/>' if indent_hanging else "") \
              + (f'<w:jc w:val="{align}"/>' if align else "") + "</w:pPr>"
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def deadline_et(iso: str) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}))?", iso)
    if not m:
        return iso
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" + (f" kell {m.group(4)}" if m.group(4) else "")


def build(d: dict, firma: str, kontakt: str) -> str:
    h = d.get("hange", {})
    qs = d.get("kusimused_hankijale") or []
    today = dt.date.today().strftime("%d.%m.%Y")
    body = [
        para(run(h.get("hankija") or "Hankija"), style="Small"),
        para(run(f"Riigihangete registri kaudu"), style="Small"),
        para(run(today), style="Small", align="right"),
        para(run(f"Selgitustaotlus riigihankes nr {h.get('viitenumber', '')}"), style="Title"),
        para(run("Riigihange: ", bold=True), run(h.get("nimi") or "")),
        para(run("Pakkumuste esitamise tähtaeg: ", bold=True),
             run(deadline_et(h.get("tahtaeg") or ""))),
        para(run("")),
        para(run("Lugupeetud hankija")),
        para(run("Tutvusime riigihanke alusdokumentidega ja palume selgitada järgmisi küsimusi. "
                 "Iga küsimuse juures on viide dokumendile ja kohale, mida see puudutab.")),
    ]
    for i, q in enumerate(qs, 1):
        text = q.get("kusimus") or q.get("küsimus") or ""
        body.append(para(run(f"{i}.\t"), run(text), indent_hanging=True))
        if q.get("viide"):
            body.append(para(run("\t"), run(f"Viide: {q['viide']}", grey=True, small=True), indent_hanging=True))
    body += [
        para(run("")),
        para(run("Palume vastused avaldada riigihangete registris, et need oleksid kättesaadavad kõigile pakkujatele.")),
        para(run("")),
        para(run("Lugupidamisega")),
        para(run(firma), style=None),
    ]
    if kontakt:
        body.append(para(run(kontakt, grey=True)))
    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1418" w:right="1134" w:bottom="1418" w:left="1701" w:header="709" w:footer="709" w:gutter="0"/></w:sectPr>')
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {W}><w:body>'
            + "".join(body) + sect + "</w:body></w:document>")


def core(title: str, author: str) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"<dc:title>{escape(title)}</dc:title><dc:creator>{escape(author)}</dc:creator>"
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created></cp:coreProperties>')


def firma_from_profile() -> str:
    p = Path("firma-profiil.md")
    if p.exists():
        m = re.search(r"\*\*Firma:\*\*\s*(.+)", p.read_text(encoding="utf-8"))
        if m:
            return m.group(1).strip()
    return "[Firma nimi]"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--firma", help="vaikimisi firma-profiil.md failist")
    ap.add_argument("--kontakt", default="", help="kontaktisik, telefon, e-post")
    a = ap.parse_args()
    d = json.loads(Path(a.json).read_text(encoding="utf-8"))
    if not d.get("kusimused_hankijale"):
        sys.exit("Aruandes pole küsimusi hankijale (kusimused_hankijale).")
    firma = a.firma or firma_from_profile()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("word/document.xml", build(d, firma, a.kontakt))
        z.writestr("docProps/core.xml", core(f"Selgitustaotlus {d.get('hange', {}).get('viitenumber', '')}", firma))
    print(f"Word valmis: {out.resolve()} ({len(d['kusimused_hankijale'])} küsimust)", file=sys.stderr)


if __name__ == "__main__":
    main()
