# The economy table — the 1520-entry roster, decoded

The largest table in the save is not a bespoke save structure. It is a verbatim
copy of a table the game ships.

`global/economyresources.economyresourcesc` (in `patch_win64`, not
`archives_win64`) is an ADF holding 1776 `EconomyResource` rows. The save stores
the first **1520** of them — the value the file itself calls
`SpawnedStartIndex`. Every `ID` and every `ProfileIndex` in a real save matches
the shipped table exactly: **1520 of 1520, zero mismatches.** That is not count
matching. Row *n* of the save is row *n* of the game's table.

```
EconomyResource (24 bytes)          EconomyResourceProfile (36 bytes)
  0  u64 ID                           0  u32   Profile           name hash
  8  u8  ProfileIndex  ────────────►  4  enum  Type
  9  u8  pad[3]                       8  f32   RegenerationRate
 12  f32 LastAmount                  12  f32   StartAmountMin
 16  u32 LastVisited                 16  f32   StartAmountMax
 20  u32 pad                         20  f32   Capacity
                                     24  f32   CoolDownTime
                                     28  u8    Infinite
                                     32  f32   FillChance
```

`EconomyResourceType` is a 9-member enum:

```
0 Water   1 Food   2 Fuel   3 Scrap   4 Threat
5 Ammo_Shotgun   6 Ammo_Sniper   7 Ammo_Thunderstick   8 Shiv
```

## What this corrects

Three columns in [OBJECT-TYPES.md](OBJECT-TYPES.md) were described from
observation alone. They now have names, and one of the descriptions was wrong:

| was called | actually is | note |
|---|---|---|
| `u32 type` | `u8 ProfileIndex` + 3 pad | an index into the 71 profiles, not a class id |
| `f32 state`, "1.0 intact / 0.0 destroyed" | `f32 LastAmount` | **a quantity, not a flag.** A water source reads 465.468; a scrap pile reads 13.254. Threat objects only look boolean because their capacity is 1 |
| `u32 546` | `u32 LastVisited` | a respawn clock. 144 in one save, 23 in another — it is not a constant |

The practical consequence: "restore by setting it back to 1.0" is right only for
capacity-1 threats. For everything else the correct restore value is the
profile's `StartAmountMax`, which `tools/economy.py refill` reads for you.

## The 71 profiles, and what the save holds

```
prof  type               start          cap  fill  rows  class
   5  Fuel                   0-0          40  1.00    17
  10  Water                150-350      1000  1.00     3
  11  Water                250-500      1000  1.00    48
  12  Water                350-1000     1000  1.00    82
  17  Scrap                 50-100       100  1.00     1
  26  Scrap                  5-5           5  1.00     6
  27  Scrap                  3-6           6  1.00   110
  29  Scrap                 10-15         15  1.00   420
  31  Scrap                 15-25         25  1.00   127
  32  Scrap                  1-3           3  1.00   157
  34  Scrap                 15-20         20  1.00   130
  35  Scrap                 20-30         30  1.00     4
  36  Scrap                 40-60         60  1.00    16
  37  Scrap                100-100       100  1.00     1
  40  Food                 500-500       500  1.00   101
  41  Food                1000-1000     1000  1.00    41
  42  Threat                14-14         14  1.00     6  camp
  43  Threat                 6-6           6  1.00    31  camp
  45  Threat                 1-1           1  1.00    34  scarecrow
  46  Threat                 1-1           1  1.00    22  scarecrow
  47  Threat                 1-1           1  1.00    23  scarecrow
  48  Threat                 1-1           1  1.00    18  scarecrow
  49  Threat                 1-1           1  1.00    35  sniper
  52  Threat                 1-1           1  1.00    30  minefield
  53  Threat                 3-3           3  1.00    13  convoy
  69  Scrap                  1-1           1  0.00    44
```

Two thirds of the roster — 1096 of 1520 rows — is Water, Food, Scrap and Fuel.
Those are the scavenging pickups. Only 224 rows are Threat, and those are the
activities.

## Where the class labels come from

`global/regioninfo.regioninfoc` is a second ADF: `ThreatsInRegions`, 32 region
slots, each holding five `EconomyResourceIndices` arrays. Those arrays hold row
indices into the economy table. Grouping them gives the class of every threat
object, with no guessing:

| threat slot | count | class |
|---:|---:|---|
| 0 | **37** | camp |
| 1 | 97 | scarecrow |
| 2 | 35 | sniper |
| 3 | 13 | convoy |
| 4 | 30 | minefield |

97 scarecrows, 35 snipers, 30 minefields and 13 convoys were already known from
`tracked_objects.bl` and from save diffing. **37 camps is new**, and it is the
first hard number for camps from any source.

Three of the 32 region slots — 28, 29 and 30 — are territory-wide aggregates
that repeat rows the individual regions already list. Counting them doubles
everything; `economy.py` skips them.

Nineteen slots carry objects. Slot 0, 1, 8, 9, 16, 17, 18, 24, 25 and 31 are
empty.

## Positions

The same ADF carries a third instance, `positions`: 1776 XYZ triples,
index-aligned with the resource rows. Every roster row can therefore be placed
on the world map, which is what makes `economy.py dump` able to print a
coordinate for any object in the save.

## Camps

The 37 camps split by threat value:

- **profile 42, worth 14 threat, 6 of them.** Six matches the six `fd####`
  (fuel depot) ids in the file list exactly.
- **profile 43, worth 6 threat, 31 of them.** The file list has
  `sd` 19 + `wc` 4 + `vv` 5 + `fo` 2 = 30 camp-shaped ids, one short of 31 —
  consistent with Gibbed's list being partial. See [LOCATIONS.md](LOCATIONS.md).

Note that the four Top Dog camps do **not** get their own profile: they are
inside the 31. Profile 35 (Scrap 20-30, 4 rows) is a coincidence of count, not
the Top Dog camps.

## Worked example

A fresh save and the 100% save, same rows, same ids, same positions:

```
$ economy.py dump "<game>" slot01.sav --class camp
idx   ID           prof type      LastAmount capacity  visit  class            position
11    30265836     42   Threat        14.000       14    144  camp region 4    -5875 441 3600
114   319220857    43   Threat         6.000        6    144  camp region 4    -6868 409 3542
137   397461050    43   Threat         6.000        6    144  camp region 12   -3472 360 5694

$ economy.py dump "<game>" data/ladder/PT6.sav --class camp
11    30265836     42   Threat         0.000       14     23  camp region 4    -5875 441 3600
114   319220857    43   Threat         0.000        6     23  camp region 4    -6868 409 3542
137   397461050    43   Threat         0.000        6     23  camp region 12   -3472 360 5694
```

Clearing a camp drives `LastAmount` to zero. Setting it back to `StartAmountMax`
is what `refill` does.

## What is still unknown

`LastAmount` is the *threat* the camp contributes, not its completion state. A
camp has more state than one float: three map states (undiscovered / discovered
/ objective met) plus a hidden 100%-complete flag, and the exe carries
`IsCampMainMissionCompleted` and `OWScrotusCampObjectiveCompleted` as separate
calls from `EnemyCampCleared`. Refilling threat has **not** been tested in game
and may well produce a camp that reads as hostile on the map but is still
internally cleared — the same trap that cost six probes on convoys, where the
authoritative record turned out to be a property-store entry and everything in
the tables was downstream. See [FINDINGS.md](FINDINGS.md).

Treat `refill --class camp` as an experiment to run, not a feature that works.
`--type Scrap` and `--type Water` are far safer: those rows have no known
downstream record.

## Reproducing

```sh
python3 tools/economy.py tables "<game dir>"
python3 tools/economy.py dump   "<game dir>" save.sav --class camp
python3 tools/economy.py dump   "<game dir>" save.sav --type Water
```

The tool pulls both ADFs out of the archives itself and caches them under
`tools/.economy-cache`.

## A parser bug worth knowing about

Reading these files needed a fix in `tools/adf.py`. An ADF struct member is 32
bytes: `s64 nameIndex, u32 typeHash, u32 size, u32 offset, u32 flags, u32, u32`.
The parser read `offset` as a signed 64-bit value, which swallows `flags` and
produces offsets like `0x100000000`. Files whose members all have `flags == 0`
parse identically either way, which is why every ADF read before this one —
`tracked_objects`, the graph files, the type library — was unaffected and
correct. `economyresources` has members with flags 1 and 2, and it crashed
outright rather than parsing wrongly, so nothing already published needs
retracting.

The same commit added the primitive `String` type (hash `8955583E`), which is
never present in a file's type table and so has to be special-cased.
