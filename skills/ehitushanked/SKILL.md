---
name: ehitushanked
description: "Eesti ehitushanked riigihangete registrist (riigihanked.riik.ee). Kasuta, kui kasutaja tahab (1) leida avatud ehitushankeid ja hinnata nende sobivust oma firmale (hankeradar) või (2) kontrollida konkreetse hanke alusdokumente: vastuolud, lepingu riskid vs ETÜ 2013, kvalifikatsioon, selgitustaotlus, pakkuda või mitte (hankekontroll). Päästikud: ehitushange, riigihange, hankedokumendid, viitenumber, riigihanked.riik.ee link. Estonian public construction tenders: tender search and tender-document risk review."
license: MIT
compatibility: "Vajab Python 3.10+, internetti ja failisüsteemi (Claude Code, Cowork). PDF-i tekstiks soovitatav poppler-utils (pdftotext)."
metadata:
  version: "1.0.0"
  author: "005SNN"
---

# Ehitushanked

Kaks töövoogu ühe registri peal. Kõik väljundid on **eesti keeles** ja iga väide kannab **allikat** (fail + lehekülg/punkt), sest otsuse teeb inimene ja ta peab saama väite ühe klikiga üle kontrollida.

Kirjuta nagu kogenud hankejuht kolleegile: lühikesed laused, konkreetsed numbrid ja punktid, tavaline ehitusvaldkonna sõnavara. Ilma emotikonide, hüüumärkide ja turundussõnadeta. Põhjendused ja lipud on lihtlaused, mitte märksõnajadad.

Skriptid (ainult Pythoni standardteek) on selle skilli kaustas: `scripts/rh.py` (andmed) ja `scripts/render.py` (HTML). Edaspidi `SKILL_DIR` = selle faili kaust. Tööfailid lähevad kasutaja töökausta alamkausta `ehitushanked/`.

## Vali haru

- **Hankeradar**: „leia hanked”, „mis hanked on avatud”, „mis meile sobib”, hommikune ülevaade → loe [RADAR.md](RADAR.md) ja järgi seda.
- **Hankekontroll**: kasutaja annab viitenumbri (nt `315920`), registri lingi või ütleb „kontrolli seda hanget”, „kas pakkuda”, „leia vastuolud” → loe [KONTROLL.md](KONTROLL.md) ja järgi seda.

- **Konkurendid ja hinnatase**: „kes võidab koolihoonete hankeid”, „mis hinnaga sarnased tööd lähevad”, „kui palju pakkujaid tuleb” → käivita `python3 SKILL_DIR/scripts/turg.py vordle --cpv <CPV> [--maksumus N] [--piirkond EE001] --out ehitushanked/turg-<CPV>.json` ja vasta JSON-i põhjal. Numbrid tulevad registri lepinguteadetest. Esita need täpselt ja nimeta valim (CPV, periood, lepingute arv). Hinnaindeks: `turg.py indeks --kestus-kuud N --maksumus N`.

Radarilt jõuab kontrolli loomulikult: pärast radarit paku välja kõrgeima skooriga hanke kontroll.

## Firma profiil

Mõlemad harud kasutavad faili `firma-profiil.md` kasutaja töökaustas (töö liigid, piirkonnad, mahu vahemik, käive, referentsid, pädevused). Kui faili pole, kopeeri `SKILL_DIR/firma-profiil.naidis.md` → `./firma-profiil.md`, ütle kasutajale, et see on näidis, ja jätka sellega.

## JSON-skeemid

Aruande ja radari skoorid kirjutatakse JSON-ina ning renderdatakse skriptiga, nii on väljund iga kord ühesugune. Skeemid: [SKEEMID.md](SKEEMID.md).

## Tulemuse näitamine

Lisaks HTML-failile: kui sul on tööriist `html_render` (nt T3 Code), renderda ka vestlusesse põimitav vaade lipuga `--inline` (radaril koos `--top 10`, aruandel koos `--luhike`) ja näita seda `html_render`-iga, sisuks faili HTML. Muidu ava fail (`xdg-open` / `open`) ja anna tee.
