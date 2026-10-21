# Ehitus AI skillid

AI-agendi skillid Eesti ehitusettevõtetele. Töötavad Claude Code'i, Codexi, Cursori ja teiste [Agent Skills](https://skills.sh) toega agentidega.

```bash
npx skills add 005SNN/ehitus-skills
```

## `ehitushanked`: hankeradar ja hankedokumentide kontroll

**Hankeradar.** *„Leia tänased avatud ehitushanked ja hinda, mis meile sobivad.”*
Loeb riigihangete registrist kõik avatud ehitushanked (~170 korraga) ja hindab igaüht firma profiili järgi skaalal 0–100, koos põhjenduse ja punaste lippudega. Tulemuseks on üks HTML-leht.

**Hankekontroll.** *„Kontrolli hanget 315920. Kas peaksime pakkuma?”*
Laeb registrist alla hanke kogu alusdokumentide paketi (sageli üle 1 GB, sadu faile), teisendab need tekstiks ja koostab aruande:

- **vastuolud dokumentide vahel** (tehniline kirjeldus vs leping vs seletuskirjad vs hinnatabel), mõlema poole tsitaadiga;
- **lepingu riskid võrreldes ETÜ 2013-ga** 14 punkti kaupa: leppetrahvid, vastutus, garantii, tagatised, maksetingimused, lisatööd jne;
- kvalifitseerimis- ja vastavustingimuste kontrollnimekiri;
- valmis **selgitustaotlus** hankijale;
- soovitus **PAKKUDA / PAKKUDA TINGIMUSTEL / MITTE PAKKUDA**.

**Konkurendid ja hinnatase.** *„Kes võidab koolihoonete ehitushankeid ja mis hinnaga?”*
Registri lepingu sõlmimise teadetest (viimased 24 kuud, ~5 600 ehituslepingut) saadakse: kes sarnaseid töid võidab, mitu pakkujat tavaliselt tuleb ja kui palju võidupakkumine hankija eelarvest erineb. Sellest tuleb tõenäoline võiduhinna vahemik. Statistikaameti ehitushinnaindeksiga arvutatakse fikseeritud hinna risk lepingu kestuse peale. Hankekontrolli aruandes on see eraldi jaotis, radaris on iga hanke juures pakkujate tavapärane arv.

**Selgitustaotlus Wordis.** Aruande küsimustest tehakse ametlik kiri (.docx), mille saab saata registri kaudu.

**Iga väide on tõendatav.** Igal leiul on sõnasõnaline tsitaat ja allikas (fail, lehekülg). Renderdaja kontrollib iga tsitaadi masinaga dokumentide tekstist üle (✓ / ⚠) ja näitab selle kohta algdokumendi lehel, punase raamiga nagu ülevaataja märge joonisel. AI teeb mustandi, otsuse teeb inimene.

### Kasutamine

1. Ava agent kaustas, kus tahad tööfaile hoida.
2. Soovi korral loo `firma-profiil.md`: tegevusala, piirkonnad, mahud, referentsid, riskitaluvus. Kui seda pole, kasutab skill näidisprofiili.
3. Küsi: „leia hanked” või „kontrolli hanget <viitenumber>”.

Nõuded: Python 3.10+ (ainult standardteek) ja internet. PDF-ide jaoks on soovitatav poppler-utils (`pdftotext`, `pdftoppm`; ka lehepiltide jaoks), DOCX-ide jaoks valikuliselt `pandoc`, Wordi lehepiltide ja vanade Office failide jaoks LibreOffice.

Sobib kokku nende skillidega: [`anthropics/skills`](https://skills.sh/anthropics/skills) **docx** (selgitustaotlus Wordi), **xlsx** (hinnatabeli täitmine) ja **pdf**.

### Andmeallikad

- Riigihangete registri avalik RSS ja avalik API (`riigihanked.riik.ee/rhr/api/public/v1`): hanke üldandmed ja alusdokumentide pakett. Sisselogimist ei nõua.
- Registri avaandmed (eForms XML, kuude kaupa): lepingu sõlmimise teated ja hanketeated.
- Statistikaamet, ehitushinnaindeks IA10 (andmed.stat.ee API).
- ETÜ 2013 (Ehituse töövõtulepingute üldtingimused), kui see on hanke paketis.

### Piirangud

- Joonistelt (DWG, skaneeritud PDF) teksti ei loeta. Need on loetletud failinimede kaupa.
- AI võib eksida. Aruanne on mustand, mitte õigusnõuanne.

---

*English: Agent skills for Estonian construction companies. `ehitushanked` scans all open public construction tenders and scores their fit for your company. It can also download a tender's full document pack and produce a cited report: cross-document contradictions, contract risks vs the ETÜ 2013 general conditions, a clarification request and a bid/no-bid recommendation. Every quote is machine-verified against the source text.*

MIT litsents.
