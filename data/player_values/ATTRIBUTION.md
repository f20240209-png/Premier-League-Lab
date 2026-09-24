# Historical EPL player-value extract

Source: [dcaribou/transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets),
built from Transfermarkt. The publisher lists
[CC0-1.0](https://github.com/dcaribou/transfermarkt-datasets/blob/master/LICENSE).
This is an independently prepared educational extract, not an official
Transfermarkt API, live feed or endorsement.

The four public compressed CSVs were retrieved on 22 September 2026 from the
publisher's download host. `provenance.json` records each original SHA-256 hash,
the extract checksum, exact preparation time, eligibility rules and counts.
`epl_values.csv` contains 1,994 player-season records across EPL seasons
2021/22 through 2025/26. It does not contain 2026/27 data.

Values are dated Transfermarkt estimates in EUR, not completed transfer fees.
Scoring/assist definitions belong to that source and may differ from other
providers. All joins within this extract use Transfermarkt player/game IDs;
those IDs must not be treated as football-data.org, API-Football or Big Balls
Data IDs. Position is the downloaded profile position, not a historical field.

Reproduce with `scripts/prepare_value_snapshot.py` using the original source
files. The raw downloads stay in `instance/value-source` and are not bundled.
