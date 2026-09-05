# Mad Max world-object roster (payload section 2, table 3)

1520 entries, fixed across every save examined - the same counts appear in a 2017
playthrough and in this one, so the type map is universal.

**This table is now fully decoded - see [ECONOMY.md](ECONOMY.md).** It is a
verbatim copy of the first 1520 rows of `global/economyresources.economyresourcesc`,
an ADF the game ships. Every ID and ProfileIndex matches, 1520 of 1520.

Entry = `u64 ID, u8 ProfileIndex, u8 pad[3], f32 LastAmount, u32 LastVisited, u32 pad`

The `type` column below is the **ProfileIndex**: an index into the 71
`EconomyResourceProfile` rows in that ADF, each of which carries a resource type
(Water / Food / Fuel / Scrap / Threat / Ammo / Shiv), a start amount and a
capacity.

The old description of the value column - "state, `1.0` = intact, `0.0` =
destroyed, restore by setting it back to 1.0" - was **wrong**. It is
`LastAmount`, a float quantity: a water source reads 465.468, a scrap pile
13.254. Threat objects only look boolean because their capacity is 1. The
correct restore value is the profile's `StartAmountMax`, which
`tools/economy.py refill` reads for you. The trailing `546` is `LastVisited`, a
respawn clock, and it is not a constant - it reads 144 in one save and 23 in
another.

| type | count | dead PT1 | PT2 | PT3 | PT4 | PT5 | PT6 (100%) | yours now | class |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 5 | 17 | 16 | 13 | 9 | 6 | 4 | 4 | 15 |  |
| 10 | 3 | 1 | 1 | 1 | 1 | 2 | 2 | 1 | mostly cleared at 100% |
| 11 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | never cleared - not an activity |
| 12 | 82 | 1 | 3 | 8 | 12 | 12 | 13 | 1 |  |
| 17 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | never cleared - not an activity |
| 26 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | never cleared - not an activity |
| 27 | 110 | 3 | 22 | 40 | 78 | 97 | 103 | 3 | mostly cleared at 100% |
| 29 | 420 | 13 | 150 | 258 | 377 | 402 | 404 | 13 | mostly cleared at 100% |
| 31 | 127 | 3 | 29 | 63 | 107 | 115 | 118 | 4 | mostly cleared at 100% |
| 32 | 157 | 7 | 37 | 75 | 140 | 154 | 154 | 7 | mostly cleared at 100% |
| 34 | 130 | 3 | 14 | 49 | 94 | 123 | 124 | 3 | mostly cleared at 100% |
| 35 | 4 | 0 | 1 | 1 | 1 | 4 | 4 | 0 | Scrap 20-30 - *not* an activity; the count matching 4 warchief camps was a coincidence |
| 36 | 16 | 0 | 3 | 5 | 7 | 13 | 13 | 0 | mostly cleared at 100% |
| 37 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | never cleared - not an activity |
| 40 | 101 | 0 | 8 | 16 | 29 | 32 | 32 | 0 |  |
| 41 | 41 | 0 | 3 | 14 | 19 | 19 | 19 | 0 |  |
| 42 | 6 | 0 | 2 | 4 | 6 | 6 | 6 | 0 | **camp**, worth 14 threat - the six `fd####` fuel depots |
| 43 | 31 | 1 | 11 | 21 | 31 | 31 | 31 | 1 | **camp**, worth 6 threat - the other 31 camps |
| 45 | 34 | 3 | 23 | 34 | 34 | 34 | 34 | 5 | scarecrow, confirmed in game (see 45-48 note below) |
| 46 | 22 | 0 | 9 | 22 | 22 | 22 | 22 | 0 | **scarecrow** |
| 47 | 23 | 0 | 0 | 6 | 23 | 23 | 23 | 0 | **scarecrow** |
| 48 | 18 | 0 | 0 | 0 | 13 | 18 | 18 | 0 | **scarecrow** |
| 49 | 35 | 0 | 10 | 20 | 33 | 35 | 35 | 0 | sniper, confirmed in game (36 `snNNNN` ids) |
| 52 | 30 | 0 | 9 | 19 | 29 | 30 | 30 | 0 | **minefield** (31 `minefield_*` ids in the game file list; wiki says 30) |
| 53 | 13 | 0 | 5 | 10 | 13 | 13 | 13 | 0 | **convoy**, worth 3 threat |
| 69 | 44 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | never cleared - not an activity |


## Labels

All 25 profiles are now named directly from the game's own data - see
[ECONOMY.md](ECONOMY.md). `global/regioninfo.regioninfoc` groups the same row
indices by threat class, giving 37 camps, 97 scarecrows, 35 snipers, 13 convoys
and 30 minefields with no inference at all.

The section below is the earlier, weaker derivation, kept because the method is
worth reading. It reached the right answers; the economy table proves them.

Cross-referencing per-type counts against Gibbed's 27,501-path file list settles
three types and produces one strong hypothesis. Method and evidence in
[GAME-FILES.md](GAME-FILES.md).

| type | count | evidence | label |
|---|---|---|---|
| 53 | 13 | exactly 13 `hoodornaments_convoy_01..13`, and 13 rows in table 2 | **convoy** |
| 52 | 30 | 31 distinct `minefield_*` ids; the wiki says 30 minefields | **minefield** |
| 49 | 35 | 36 distinct `snNNNN` ids | **sniper** (already confirmed in game) |

**Scarecrows span types 45-48 - confirmed.** `global/tracked_objects.bl` holds a
per-class registry whose list of 97 object ids resolves to roster types 45, 46,
47 and 48 together (see [GAME-FILES.md](GAME-FILES.md)). That matches the 97
distinct `scNNNN` ids in the file list and the four scarecrow sizes the game
ships. The registry also confirms sniper (35 x type 49) and minefield
(30 x type 52). No in-game test needed for any of the three.
