# Hankekontroll

Eesmärk: **üks link sisse, kõik vajalik välja.** Kasutaja kleebib registri lingi (nt `https://riigihanked.riik.ee/rhr-web/#/procurement/10854744/general-info`), viitenumbri või ID ja ei pea midagi muud ütlema. Kui sõnum on ainult link, tee täiskontroll ja kõik väljundid allpool.

Väljund on kolm faili kaustas `ehitushanked/<viitenumber>/`: `aruanne.html` (aruanne koos konkurentide ja hinnatasemega), `selgitustaotlus.docx` (kiri hankijale) ja `aruanne.json`. Hanke kogu alusdokumentide pakett muutub üheks aruandeks. Aruandes on **vastuolud dokumentide vahel**, **lepingu riskid võrreldes ETÜ 2013-ga**, kvalifitseerimistingimused, puuduv info, valmis selgitustaotlus ja soovitus PAKKUDA / PAKKUDA TINGIMUSTEL / MITTE PAKKUDA.

Iga leid on **tõendatav**: sõnasõnaline tsitaat (kuni ~30 sõna, kopeeritud `tekst/` failist täpselt nii, nagu seal on) ja allikas kujul `Fail.pdf, lk 12` või `Hankelepingu projekt, p 9.3`. Renderdaja kontrollib iga tsitaadi masinaga üle. Kokkuvõte või ümbersõnastus tsitaadi väljal kukub kontrollis läbi.

## Olemasolev aruanne

Kui `ehitushanked/<viitenumber>/aruanne.json` on juba olemas ja kasutaja ei palu uut kontrolli, ära kontrolli uuesti. Renderda olemasolev (samm 6) ja näita seda.

## Kiirkontroll

Kui kasutaja palub kiiret kontrolli või aega on vähe, tee sammud 1–6 nii: loe ainult A-rühm ja energia (EE), tuleohutuse (TO) ja konstruktsiooni (EK) seletuskirjad; alamagente kuni 4. Märgi metoodikasse „kiirkontroll” ja millised osad jäid lugemata. Kestus ~15 min täiskontrolli ~30 min asemel.

## 1. Lae dokumendid

```bash
python3 SKILL_DIR/scripts/rh.py fetch <viitenumber|link>
```

Pakett võib olla üle 1 GB: allalaadimine ja tekstiks teisendamine võtab 1–5 min. Käivita taustal ja ütle kasutajale, mis toimub. Skript kirjutab kõik kausta `ehitushanked/<viitenumber>/` (viitenumber on registri 6-kohaline number, mitte lingis olev sisemine ID) ja trükib selle tee viimase reana. Kui `ehitushanked/<viitenumber>/INDEX.md` on juba olemas, kasuta seda ja jäta allalaadimine vahele.

Valmis, kui `INDEX.md` on olemas. Loe see läbi: failid on rühmitatud **A** (hankedokumendid), **B** (projekti seletuskirjad ja spetsifikatsioonid), **C** (muu tekst) ja **D** (joonised).

## 1b. Turuandmed (käivita taustal kohe pärast sammu 1)

```bash
python3 SKILL_DIR/scripts/turg.py vordle --cpv <põhi-CPV meta.json-ist> --maksumus <cost> --kestus-kuud <lepingu kuud> \
  --hankija "<hankija nimi>" --piirkond <NUTS3> --out ehitushanked/<nr>/turg.json
```

CPV, maksumuse ja lepingu kuupäevad leiad failist `meta.json` (`general.procurementCpvDtos`, `general.cost`, `general.startDate`/`endDate`). Piirkond: EE001 Põhja-Eesti (Harju), EE004 Lääne-, EE008 Lõuna-, EE009 Kesk-, EE00A Kirde-Eesti. Kui maksumus puudub, jäta `--maksumus` ära. Esimene käivitus laeb 24 kuu lepingud (~1 min), edasi vahemälust. `render.py` lisab `turg.json` aruandesse ise. Sinu ülesanne on viidata sellele otsuses: hinnavahemik, pakkujate arv ja hinnarisk.

## 2. Kogu faktid

Faktid kogutakse **faktiperekondade** kaupa, et neid saaks hiljem mehaaniliselt võrrelda. Kasuta täpselt neid `teema` võtmeid:

`TÄHTAJAD` (algus, lõpp, vahetähtajad) · `MAHT` (neto- ja brutopind, korrused, ruumid) · `ENERGIA` (energiaklass, ETA, q50, U-väärtused) · `TULEOHUTUS` (klass, kasutusviis, süsteemid) · `KONSTRUKTSIOON` (betooniklassid, kandesüsteem, vundament) · `GARANTII` · `TAGATISED` · `KINDLUSTUS` · `LEPPETRAHV` · `MAKSMINE` (ettemaks, kinnipidamine, tähtaeg) · `PROJEKTEERIMINE` (kes teeb tööprojekti, vastutus) · `ULATUS` (mis kuulub või ei kuulu töövõtu hulka) · `HINNATABEL` (read ja nende vastavus ulatusele) · `NORMID` · `MUU`.

Üks fakt on `{teema, väide, väärtus, tsitaat, allikas}`.

**Jaota töö alamagentideks**, kui sul on Agent/Task tööriist. Käivita kõik korraga ühes sõnumis:

| Agent | Loeb | Tagastab |
|---|---|---|
| Hanketingimused | A: hankepass, vastavustingimused, hindamiskriteeriumid, alltöövõtjate tingimused | faktid + kvalifitseerimistingimused + hindamiskriteeriumid |
| Leping vs ETÜ | A: hankelepingu projekt (täielikult) + ETÜ_2013 vastavad punktid | lepingu faktid + riskiread (vt 4) |
| Ulatus | A: tehniline kirjeldus + hinnapakkumise tabel | faktid; `ULATUS`/`HINNATABEL` erinevused |
| Üks agent iga B-rühma eriala kohta (AR+SA, EK, KVJ, VK+VKV, EL+ELV+EN, TO+EAT, TL+AS, EE, …) | selle eriala seletuskiri + spetsifikatsioonid | faktid |

Alamagendi ülesandesse kirjuta: töökausta tee, failide nimekiri, faktiperekondade võtmed, tsitaadireegel (täpne koopia `tekst/` failist, lk-number `=== lk N ===` markerist) ja tagastusvorm (JSON-massiiv). Ilma alamagentideta loe ise samas järjekorras: A täielikult, B sihitult (`grep -n -i` märksõnadega: garantii, tähtaeg, m², klass, q50, U=, betoon, C30, tulepüsivus, kWh).

Valmis, kui iga A-faili ja iga B-eriala kohta on faktid käes (või kinnitus, et seal neid polnud).

## 3. Leia vastuolud

Rühmita faktid `teema` järgi. Vastuolu kandidaat tekib siis, kui kaks allikat annavad samale asjale erineva väärtuse (tähtaeg, pind, klass, garantiiaeg, summa), või kui `ULATUS` ja `HINNATABEL` ei kata üksteist (töö on kirjelduses, aga hinnatabelis pole rida). Iga kandidaadi puhul ava mõlemad allikakohad (`grep -n`) ja kinnita. Kinnitamata kandidaat läheb `puuduv_info` alla, mitte vastuoludesse.

Tõsidus: **kõrge** = mõjutab hinda või tähtaega oluliselt või loob vaidlusriski; **keskmine** = vajab selgitust enne pakkumist; **madal** = vormiline.

## 4. Lepingu riskid vs ETÜ 2013

Võrdle hankelepingu projekti ETÜ 2013-ga **iga** alloleva rea kaupa. Iga rea kohta kas riskirida või kinnitus „vastab ETÜ-le”:

leppetrahvid ja viivised (määr, ülempiir) · vastutuse piirang · garantiiaeg ja garantiitagatis · täitmistagatis · ettemaks ja kinnipidamine · maksetähtaeg · hinna muutmine/indekseerimine · lisa- ja muudatustööd · tähtaja pikendamise alused · tellija ühepoolne lõpetamine · projekteerimisvastutus · kindlustus · alltöövõtjad · vaidluste lahendamine.

Ole konkreetne: „ETÜ p 9.3 näeb ette X; leping p 12.4 nõuab Y; mõju: Z”. ETÜ punkti leiad `grep -n` abil failist `tekst/ETÜ_2013.pdf.txt`. Kui paketis ETÜ-d pole, kasuta oma teadmist ETÜ 2013-st ja märgi allikaks „ETÜ 2013 (paketis puudub)”.

Valmis, kui kõik 14 rida on käsitletud.

## 5. Otsus ja küsimused

- **Küsimused hankijale**: iga vastuolu ja olulise puuduva info kohta üks konkreetne küsimus koos viitega. Need moodustavad selgitustaotluse.
- **Otsus**: kaalu riske ja `firma-profiil.md`-d (kvalifikatsioon, maht, riskitaluvus). Põhjendus kuni 3 lauset ja kuni 60 sõna: mis on otsustav ja mis peab muutuma. Detailid jäävad leidudesse.
- **Kokkuvõte**: 3–5 punkti, igaüks üks lause kuni 25 sõna, olulisim enne. Viita leiu tunnusele (V1, R2), kui see on olemas: vastuolud ja riskid nummerdatakse aruandes tõsiduse järjekorras.

## 6. Renderda ja kontrolli

Kirjuta `ehitushanked/<viitenumber>/aruanne.json` (skeem: SKEEMID.md → Hankekontrolli aruanne), siis:

```bash
python3 SKILL_DIR/scripts/render.py aruanne ehitushanked/<nr>/aruanne.json --tekst ehitushanked/<nr>/tekst --out ehitushanked/<nr>/aruanne.html
```

Skript teatab, mitu tsitaati leiti sõna-sõnalt ja mitmele lisati lehepilt: lõige algdokumendi lehest, tsitaat punase raamiga (vajab `originaalid/` kausta, mille `rh.py fetch` alles hoiab). Tsitaat, mis on kopeeritud allikast täpselt, saab lehepildi; parafraas ei saa. Iga „⚠ kontrolli” tsitaadi puhul ava allikas, paranda tsitaat täpseks koopiaks ja renderda uuesti. Valmis, kui kõik tsitaadid on ✓ või leid on eemaldatud.

Tee alati ka selgitustaotlus Wordi failina:

```bash
python3 SKILL_DIR/scripts/taotlus.py ehitushanked/<nr>/aruanne.json --out ehitushanked/<nr>/selgitustaotlus.docx
```

Firma nimi tuleb `firma-profiil.md`-st, kontaktisiku saab lisada `--kontakt "Nimi, tel, e-post"`.

Vestlusesse lühidalt:
1. otsus ühe lausega;
2. 3 olulisemat leidu;
3. tõenäoline võiduhind ja pakkujate arv `turg.json`-ist;
4. teed kolme failini.

Valmis, kui kõik kolm faili on olemas.
