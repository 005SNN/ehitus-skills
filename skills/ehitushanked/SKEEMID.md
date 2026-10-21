# JSON-skeemid

Võtmed on täpselt sellised, nagu siin. `render.py` loeb ainult neid.

## Radari skoorid: `ehitushanked/skoorid.json`

```json
{
  "profiil": "Näidis Ehitus OÜ, üldehitus 0,5–10 M€",
  "hinnangud": [
    {"viitenumber": "315920", "skoor": 86,
     "pohjendus": "Koolihoone peatöövõtt 7 M€ Keilas, sobib kooli-referentsidega.",
     "punased_lipud": ["läbirääkimistega menetlus", "lammutus + ajaloolise hoone sidumine"]}
  ]
}
```

## Hankekontrolli aruanne: `ehitushanked/<nr>/aruanne.json`

```json
{
  "hange": {"viitenumber": "315920", "nimi": "…", "hankija": "…", "maksumus": 7015000,
            "tahtaeg": "2026-12-02T11:00", "lepingu_periood": "28.12.2026 – 31.07.2028", "link": "https://…"},
  "otsus": {"soovitus": "PAKKUDA TINGIMUSTEL", "pohjendus": "…"},
  "kokkuvote": ["…", "…"],
  "votmenaitajad": [{"nimetus": "Leppetrahv", "vaartus": "0,1% päevas, max 10%", "allikas": "Hankelepingu projekt, p 11.2"}],
  "vastuolud": [{
     "teema": "Garantiiaeg", "tõsidus": "kõrge",
     "a": {"tsitaat": "<täpne koopia>", "allikas": "Tehniline kirjeldus, p 5.1"},
     "b": {"tsitaat": "<täpne koopia>", "allikas": "Hankelepingu projekt, p 10.1"},
     "moju": "…", "soovitus": "…"}],
  "riskid": [{"teema": "Vastutuse piirang puudub", "tõsidus": "kõrge", "tsitaat": "<täpne koopia>",
              "allikas": "Hankelepingu projekt, p 14.3", "etu_vordlus": "ETÜ p … näeb ette …",
              "moju": "…", "soovitus": "…"}],
  "kvalifikatsioon": [{"nõue": "3 sarnast objekti viimase 5 a jooksul, igaüks ≥ 3 M€", "allikas": "Hankepass, lk 7"}],
  "puuduv_info": [{"teema": "…", "miks_oluline": "…", "allikas": "…"}],
  "kusimused_hankijale": [{"kusimus": "…", "viide": "Tehniline kirjeldus p 5.1 vs leping p 10.1"}],
  "metoodika": {"kirjeldus": "Loetud kogu alusdokumentide pakett …", "faile": 920, "loetud tekstiga": 497,
                "lehekülgi": 1212, "kestus": "6 min"}
}
```

`tõsidus` ∈ `kõrge` | `keskmine` | `madal`. `soovitus` ∈ `PAKKUDA` | `PAKKUDA TINGIMUSTEL` | `MITTE PAKKUDA`.
