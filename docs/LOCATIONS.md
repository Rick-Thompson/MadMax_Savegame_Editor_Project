# Location and activity types

Every open-world thing you can find, clear, or collect in Mad Max, as the game
itself names it — recovered from three independent sources and cross-checked
against the save:

1. **`data/gibbed/master.dirlist`** — 27,501 real game paths. Level objects are
   named `a0N_<code><NNNN>`, so counting distinct ids per code counts instances.
   This list is Gibbed's *known-names* list, not the full archive index, so every
   count here is a **lower bound** unless a second source confirms it.
2. **`MadMax.exe` and the gameplay DLLs** — 398,623 strings. The engine's own
   API names (`ConvoyDataSetWrecked`, `OWInsigniaDestroyed`, `GetCampInfo`) say
   what the game thinks these things are.
3. **`global/tracked_objects.bl`** — the engine's per-class object registry,
   which pins three classes exactly.

Where a count matches the object roster in [OBJECT-TYPES.md](OBJECT-TYPES.md),
that is noted. Where it doesn't, that is noted too.

---

## 1. The world is 16 numbered zones

Every location id in the game carries a zone token. There are exactly sixteen
open-world zones, plus two non-open-world areas:

```
chum00
jeet00     jeet01     jeet02     jeet03     jeet04
gutgash00  gutgash01  gutgash02  gutgash03  gutgash04
pinkeye00  pinkeye01  pinkeye02  pinkeye03  pinkeye04
--- not open world ---
gastown01  (Gastown)
home01     (stronghold interior)
```

The engine works in zones too: `GetRegionThreat`, `GetTerritoryThreat`,
`DepleteAllThreatInRegion`, `GetCampCountForTerritory`, and the save key
`save_data_info_threat` are all per-region. Deathrun records are keyed
identically — `deathrun_gutgash03_time`, `deathrun_pinkeye04_opuswars_time` —
one per zone for the fifteen non-Chum zones.

**Human-readable names.** The map textures give them
(`a00_gui_streamed_locations_<name>_alpha_dif`), and they group exactly the way
Steam guides group them:

| territory | zones |
|---|---|
| Chumbucket's | Chumbucket's Hideout |
| Jeet's | Balefire Flatland, Blackmaws, Colossus, Dry Gustie, Fuel Veins |
| Gutgash's | Cadavanaugh, Chalkies, Grit Canyons, Parch Moon, Reek Hills |
| Pink Eye's | Grandrise, Knit Sack, Rot'n'Rusties, The Heights, Wailing Winds |
| Deep Friah's / endgame | The Dump, The Dunes, Gastown, Underdunes, Deep Friah |

**Open:** which *name* is which *number*. `jeet02` is one of Jeet's five zones,
but nothing yet says which. The map textures are alphabetical, not indexed.

The walkthrough's four camp categories — Oil Pump, Transfer Tank, Stank Gum and
Top Dog — match the game's own marker icons one for one (`pump_camp`,
`transfer_camp`, `stankgum`, `top_dog_camp`), which is independent confirmation
of the icon taxonomy in §3.

**Unconfirmed:** `tracked_objects.bl` list[0] holds **16** object ids that match
no save table — the same 16 as the zone count. That is suggestive and no more.
Hashing 10,044 name variants of every zone token and map name against those ids
produced **zero** matches, so they are editor objectids, not name hashes, and
the identification is still count-matching only — the same weak evidence class
that produced the retracted `CPlayer` claim in [HASHES.md](HASHES.md).

---

## 2. Location types

`a0N_` is the map area: `a01` = Jeet + Gutgash, `a02` = Pink Eye, `a04` =
Gastown, `a00` = global/shared.

| code | ids found | what it is | evidence |
|---|---:|---|---|
| `sc` | 97 | **Scarecrow** | exact: `tracked_objects` list[2] = 97 ids → roster types 45–48 |
| `sn` | 38 | **Sniper** | `tracked_objects` list[1] = 35 → roster type 49 (35). 38 ids, 3 presumed unused |
| `minefield_<zone>_NN` | 31 | **Minefield** | `tracked_objects` list[3] = 30 → roster type 52 (30) |
| `sd` | 19 | **Camp** | has intel markers (`intelsd`, 12) → it is a camp |
| `fd` | 6 | **Camp, fuel depot** | profile 42: exactly 6, worth 14 threat each — see [ECONOMY.md](ECONOMY.md) |
| `wc` | 4 | **Camp, warchief (top dog)** | `intelwc` (4); icon `top_dog_camp`; inside the 31 profile-43 camps |
| `vv` | 5 | camp, kind unknown | `a01_vv1050_camp.blo`; no intel markers, no roster match |
| `fo` | 2 | unknown | `a02_fo2020`, `a02_fo2040`; `_gameplay` sub-file like the camps |
| `enc` | 5 | **Stronghold** (encampment) | `CEncampmentInventory`, `GetEncampmentLevel`; `enc1010_level_01..05` |
| `loot_<zone>_NN` | 212 | **Scavenging location** | `ScavengeLocationCleared`, `OWScavengeCampCleared` |
| `buried_carwreck_<zone>_NN` | 22 | **Buried car wreck** | scavenging sub-type |
| `deathrun_<zone>` | 15 | **Death run** | `CompleteDeathrun`, `GetCompletedDeathruns`, `deathrun_<zone>_time` |
| convoys | 14 | **Convoy** | 14 `CConvoyDataContainer`s in `global/convoys.blo`; roster type 53 (13) + 13 table-2 rows |
| `mm`, `sm` | 16, 9 | main / side missions | `a00_gui_streamed_locations_side_mission_smNNNN` |
| `intel`, `intelsd`, `intelwc`, `intelfd` | 21, 12, 4, 4 | **Information encounter** | the camp-hint markers that vanish once you take the camp |

**There are 37 camps.** That is now a hard number, not an inference:
`global/regioninfo.regioninfoc` groups economy-table rows by threat class and
slot 0 holds exactly 37. They split 6 (profile 42, worth 14 threat) + 31
(profile 43, worth 6). The file list has `sd` 19 + `wc` 4 + `vv` 5 + `fo` 2 = 30
camp-shaped ids against that 31, one short — consistent with Gibbed's list being
partial. See [ECONOMY.md](ECONOMY.md).

### Not yet placed

`vv` (5) and `fo` (2) are clearly level geometry of the same shape as the camps
— each has a `_gameplay` companion `.blo`, and `a01_vv1050_camp.blo` is
literally named `_camp` — but neither has intel markers and neither matches a
roster type count. `lto20`/`lto40`/`lto30`/`lto60` each carry `obj01a`–`obj01e`,
five objectives apiece, and are unidentified.

---

## 3. Map marker icons

The full icon set, from `a00_gui_streamed_region_icons_*`. This is the game's
own marker taxonomy, and it is shorter than the location list because several
location types share an icon:

```
vantage          pump_camp        top_dog_camp     transfer_camp
scavenge         vehiclegraveyard debri            generic
buzzards         roadkill         stankgum
chumbucket       gutgash          jeets
```

`buzzards` / `roadkill` / `stankgum` are the three enemy factions — the exe
carries `max_detected_buzzard`, `max_is_roadkill_stealth`, `Scrotus: Stealth`
and so on — so a camp's icon depends on who holds it, not on what it is. That
is why the icon set doesn't map one-to-one onto the `sc`/`sd`/`fd`/`wc` codes.

---

## 4. Engine API names worth knowing

These come straight out of `MadMax.exe` and are the best available statement of
what state the game actually tracks per location.

**Convoys** — confirms the state semantics we reverse-engineered from saves:

```
ConvoyDataGetDiscovered / ConvoyDataSetDiscovered
ConvoyDataGetWrecked    / ConvoyDataSetWrecked
ConvoyDataGetMoverData  / ConvoyDataSetMoverData
GUIXAddConvoyRoute      GUIXSetConvoyRouteWrecked
GUIXSetConvoyRouteRelicCollected
```

Two independent booleans, discovered and wrecked, exactly matching the observed
`u32 state` values `0` (neither), `2` (discovered), `3` (wrecked). See
[FINDINGS.md](FINDINGS.md).

**Camps:**

```
GetCampInfo   GetCampCountForTerritory   IsCampMainMissionCompleted
camp_id   camp_type   camp_type_total_count   player_camp_id_hash
GameProgressionEnemyCamps   EnemyCampCleared
OWScrotusCampCleared   OWScrotusCampObjectiveCompleted
OWScavengeCampCleared   OWInsigniaDestroyed
```

`IsCampMainMissionCompleted` and `OWScrotusCampObjectiveCompleted` being
separate from `...CampCleared` matches the three map states a camp shows
(undiscovered / discovered / objective met) plus a hidden fourth (100%
complete), which is not drawn on the map.

**Threat, per region:**

```
GetRegionThreat   GetTerritoryThreat   DepleteAllThreatInRegion
ThreatLevelWeight   ThreatEvent   save_data_info_threat
```

**Vantage points and strongholds — both are savable game objects:**

```
CVantagePoint            CBalloonControllerObject
CEncampmentInventory     CEncampmentInventoryManager
GetEncampmentLevel   IsEncampmentUnlocked   HasEncampmentLevelChanged
```

`CVantagePoint` is a `CGameObjectCreator` class exactly like
`CConvoyDataContainer`, which means the **five-step convoy method should apply
to vantage points unchanged**: find the balloon `.bl`, unpack the SARC, decode
the RTPC, take the objectids of entities with `save = 1`, look them up in the
property store. Untested.

**Collectibles:**

```
HistoryRelic   HoodOrnamentRelic   PostcardRelic   PaintJobRelic
PickupPictureRelic   DecorationRelic   RelicIsCollected   GetNumFoundRelics
RaceTrophy   IsRaceTrophyStandardAwarded   IsRaceTrophyLegendAwarded
GetGriffaTokenCount   player_griffa_tokens   player_scrap
```

`legend/relics.relicsetc` is an ADF that should enumerate every relic; it has
not been extracted yet.

---

## 5. What this does *not* give us

The exe string dictionary does not name anything in the save. Hashing all
398,623 harvested strings with lookup3 and intersecting against a save produced
**one** hit across all four tables and the property store — `CPlayer`, at
1529 × 573,471 / 2³² ≈ 0.2 expected collisions, i.e. noise. The save's keys come
from the `.gsrc` graph scripts in the archives, not from the binary. That is the
same wall described in [HASHES.md](HASHES.md), and it is why the GPU brute force
on graph names is the route being taken instead.

Camps also remain unreachable from the game files alone: their per-instance
`.blo` files are not resolvable by basename hash, so `sd`/`fd`/`wc`/`vv`
objectids cannot be read out the way convoy objectids were. Camps need a staged
save series. See [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md).

---

## Reproducing this

```sh
# zone tokens and per-code instance counts
grep -oE "^a0[0-9]_[a-z]{2,3}[0-9]{4}" data/gibbed/master.dirlist \
  | sed -E 's/^a0[0-9]_//; s/[0-9]{4}$//' | sort | uniq -c | sort -rn

# engine API names
python3 tools/names.py harvest strings.txt "<game>/MadMax.exe" "<game>"/*.dll
grep -iE "camp|convoy|threat|encampment|relic" strings.txt

# the object registry
python3 tools/arcx.py get "<game>/archives_win64" out tracked_objects.bl
python3 tools/sarc.py get out/tracked_objects.bl out
python3 tools/adf.py dump out/tracked_objects.trackedobjectdatac
```
