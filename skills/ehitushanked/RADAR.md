# Hankeradar

Eesmärk: kõik praegu avatud ehitushanked → iga hanke sobivus firmale 0–100 → üks HTML-leht, mida juht loeb 2 minutiga.

## 1. Lae hanked

```bash
python3 SKILL_DIR/scripts/rh.py radar --out ehitushanked/radar.json
```

~10 s. Kirjutab ka lühivaate `ehitushanked/radar.md` (üks rida hanke kohta). Loe **lühivaadet**, mitte JSON-it. Lisa `--koik-liigid`, kui firma teeb ka projekteerimist või omanikujärelevalvet.

Valmis, kui skript teatas hangete arvu ja `radar.md` on loetud lõpuni.

## 2. Hinda iga hanget

Loe `firma-profiil.md` (vt SKILL.md). Hinda **iga** rida lühivaates, mitte valimit. Skoor 0–100:

| Kaal | Kriteerium |
|---|---|
| 40 | Töö liik ja CPV vastavad firma tegevusalale |
| 25 | Maht sobib firma vahemikku (puudub maksumus → hinda kirjelduse järgi, märgi lipuga) |
| 15 | Asukoht on firma piirkonnas |
| 10 | Aega pakkumuse koostamiseks piisavalt (< 10 päeva → lipp) |
| 10 | Riskitegurid puuduvad: projekteeri-ja-ehita, kontsessioon, raamleping väikeste tellimustega, erihanke nõuded |

Iga hinnangu juurde üks lause põhjendust (konkreetne, nt „Koolihoone peatöövõtt 7 M€, Harjumaa, sobib referentsidega”) ja 0–3 punast lippu. Hanked, mis ilmselgelt ei sobi (vale tegevusala), saavad skoori < 20 ja lühikese põhjenduse. Ka need kirjuta faili.

Valmis, kui hinnangute arv = hangete arv lühivaate pealkirjas.

## 3. Renderda

Kirjuta `ehitushanked/skoorid.json` (skeem: SKEEMID.md → Radari skoorid), siis:

```bash
python3 SKILL_DIR/scripts/render.py radar ehitushanked/radar.json --skoorid ehitushanked/skoorid.json --out ehitushanked/radar.html
```

Ava fail (`xdg-open` / `open`) või anna kasutajale tee.

## 4. Vastus vestlusesse

Lühidalt: mitu hanget avatud, mitu sobivat (≥ 70), top 5 tabelina (skoor, nimi, maksumus, tähtaeg, üks lause). Lõpeta pakkumisega: „Kas kontrollin hanke X dokumendid?”, mis viib [KONTROLL.md](KONTROLL.md) juurde.
