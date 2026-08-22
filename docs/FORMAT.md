# Mad Max (2015) — save file format

**Status: working save editor.** Edited saves load in game, in both save formats,
and destroyed world objects can be restored — static props and cleared convoys
alike, verified in game.

This is the format spec. The convoy answer and the game-file work that produced
it are in `GAME-FILES.md`; the six failed probes that came first are in
`FINDINGS.md`; how to run your own experiment is in `METHODOLOGY.md`.

Worked out against ~20 real save files: a live playthrough on Linux/Proton, four
older Windows saves via OneDrive, and a six-stage 0→100% playthrough downloaded
from a published Steam Community guide.

---

## 1. Where the files live

**Linux / Proton** (app id 234140) — **this is what the game actually loads**:

```
~/.steam/debian-installation/userdata/<SteamID3>/234140/remote/
```

`Documents\WB Games\Mad Max\Backup Saves\` inside the Proton prefix is a *backup*
copy, not the load path. On Windows the equivalent pair is
`Documents\WB Games\Mad Max\` plus `Steam\userdata\<SteamID3>\234140\remote\`.

Ten slots, `GameSave01.sav` … `GameSave10.sav`, plus `Settings.sav`.
Steam Cloud will silently restore old saves over edited ones — turn sync off.

**Saves are autosave-driven.** Switching the active slot *copies* the current
save rather than serialising fresh state. If `play time` in the header hasn't
advanced, the file is a copy and contains nothing new. Always check it.

---

## 2. Obfuscation — solved

Every byte XOR'd with a fixed repeating 32-byte key:

```
ea d5 ba d5 ee d5 ab ee ba 57 ab aa ab ba ab ee
ba 75 aa 57 ae d5 ab ea ba 75 ae 75 ab ab 5d d5
```

Same key on both platforms, all slots, `Settings.sav` included, applied
continuously across the whole file. XOR is its own inverse.

---

## 3. File layout

| Offset | Type | Meaning |
|---|---|---|
| `0x00` | u32 | integrity value — §4 |
| `0x04` | u32 | magic `0x33116F7F` |
| `0x08` | u64 | size field A |
| `0x10` | u64 | payload end offset |
| `0x18` | u32 | unix timestamp, playthrough creation |
| `0x20` | u32 | unix timestamp of this save |
| `0x28` | u64 | **play time in seconds** (also the freshness check) |
| `0x30` | f64 | unknown |
| `0x38` | u32 | always 1 |
| `0x3C` | u32 | id / build stamp |
| `0x48` | u8 | **slot number** 1–10 |
| `0x49` | u8 | save format generation (2 or 6) — a property of the playthrough, not the build |
| `0x4C` | u16,u8×4 | year, month, day, hour, minute (local) |
| `0xF0` | | payload, length `= value@0x10 − 0xF0` |
| … | | optional identical mirror copy of the payload |
| … | | zero padding to a 512-byte boundary |

The mirror is optional — detect it, don't assume it.

---

## 4. The integrity value at `0x00`

### The method that works

**Read the delta off the original file and carry it across the edit.**

```python
delta   = stored(original) ^ crc_formula(original)
new_val = crc_formula(edited) ^ delta
```

`crc_formula` = CRC-32 (reflected IEEE) over decoded `[4:EOF]`, `init=0xBCEAC598`,
`xorout=0x7B7AD18A`. Valid as long as the edit doesn't change the **file length**.
Every tool here enforces that and refuses otherwise.

Because files are padded to 512 bytes there is usually slack — adding or removing
a few table entries often leaves the file length untouched, so even structural
edits stay valid. Check the reported length; if it changed, the delta is wrong.

### Why it is not solved in closed form

An earlier draft claimed the formula above was the answer, "verified on six
files". That was wrong and is worth recording. Those six files had only **two
distinct lengths**, and two lengths give exactly 64 equations for the 64 unknown
bits of `(init, xorout)` — the fit was guaranteed, not confirmed.

A later save at a third length has a non-zero delta under that formula. Nothing
tested fits three or more lengths: plain ranges, CRC-32C / Koopman / CRC-32Q /
FNV / Jenkins / Adler / byte-sum, per-save seed fields, byte orderings, and
length values prepended or appended in four encodings. Ten distinct v6 lengths
were eventually available and still nothing fit.

What *is* solid: **the delta depends only on file length, never on content.**
Five independent files of length 1020928 share delta `0x0E7EDB6E` despite
differing in thousands of payload bytes. That is what makes the carry valid.

---

## 5. Payload section 1 — record stream

```
u32 id, u32 size, value[size]     starting at payload+0x20
```

~2877 records, ~31 KB, length at `payload+0x18`. Sizes 1, 2, 4, 8, 64.
**Record ids are stable across saves**, so diff by id — the payload grows as you
play, which shifts byte offsets and makes raw diffs useless.

Dominant motif is groups of four: `(u32 hash, u32 value, u8 state, u8 state)`,
about 431 of them. `u8` states are a bitfield: `1` available, `2` in progress,
`4` complete, `8` a fourth bit, `12` = `4|8`.

Story progress is a sliding frontier: a run of ids goes `12 12 12 8 4 0 0`, with
the `8, 4` boundary advancing one slot per step. Perturbing any of it rewinds the
story a step.

`id 0` is a 64-byte 4×4 transform — a respawn/checkpoint position, **not** Max's
live position (the game always resumes you at the nearest base). `id 1848` is a
live float that changes on almost every save; treat it as noise.

---

## 6. Payload section 2 — tables, and where world objects live

Section 2 follows the record stream: four tables, then more `(id, size, value)`
record streams. Each table header is

```
u32 size, u32, u32, const 4, u32 count, u32 one, u32 count*entrysize
```

| table | entry | count | what it is |
|---|---|---|---|
| 0 | 8 B | grows 25→196 | live objects with map presence |
| 1 | 16 B | grows 14→832 | **map / tracking status** |
| 2 | 32 B | 13 | **the 13 convoys' live positions** |
| 3 | 24 B | **1520, fixed** | **the world-object roster** |

### Table 3 — the object roster

```
u32 key, u32 0, u32 type, f32 state, u32 546, u32 0
```

Sorted by key, **1520 entries in every save examined** — same count and same
per-type counts in a 2017 playthrough and in a 2026 one. The type map is
universal. `state` is `1.0` intact, `0.0` destroyed.

Types fully cleared by 100%: 27 (110), 29 (420), 31 (127), 32 (157), 34 (130),
35 (4), 42 (6), 43 (31), 45 (34), 46 (22), 47 (23), 48 (18), 49 (35), 52 (30),
53 (13). Never cleared: 11, 17, 26, 37, 69. Partial: 5, 10, 12, 40, 41.

A scarecrow was type 45; a sniper tower flipped one type 45 and one type 49, so
45 is a destructible structure class and 49 the sniper. To label a class, destroy
one of something and see which type moves.

### Table 2 — convoy positions

Thirteen rows, always, same thirteen keys in every save examined - and there are
exactly thirteen convoys (roster type 53). Layout:

```
u32 key, u32 0, f32 x, f32 y, f32 z, 12 bytes uninitialised
```

All zero until that convoy first spawns; then it tracks the convoy's position
save by save, and freezes at the wreck when the leader dies. Verified over the
snapshot series: zeros through frames 023-031, a position appearing the moment
the route showed on the map, moving across 032/033, frozen from 034 on.

The trailing 12 bytes are stale buffer contents - `3F000000` drifts in and out
of unrelated rows between saves. Do not read meaning into them.

The convoy's key here is **not** its roster key: the convoy at roster
`593B2B20` is `194895AE` in this table. Pair them by watching one live
encounter.

### Table 1 — map/tracking status

16-byte entries, `u32 key, u32 0, u32 ffffffff, u16 flag, u16 1`. The flag reads
`03 00` while tracked and `00 00` once cleared.

---

## 6.2 Payload section 3 — the hash-named property store

After the tables comes the largest structure in the file and the last one to be
worked out. It is a single stream of

```
u32 index      sequential, starts at 1
u32 reclen     = 16 + vallen
u64 hash       stable name key - a full 64-bit value
u64 vallen
u8  value[vallen]
```

**sorted ascending by hash**, 712 records in the 0% reference save and 10738 in
the 100% one. Records are only ever *added*, never removed - it is an
append-only global registry of named properties.

A 32-byte header sits immediately **before** the first record:

| offset from first record | type | meaning |
|---|---|---|
| `-32` | u64 | magic `0x4CF2625A` |
| `-24` | u32 | arena size - a few dozen bytes larger than the records occupy |
| `-20` | u32 | reserve, `0` / `3072` / `6144` |
| `-16` | u32 | `0` |
| `-12` | u32 | `8` |
| `-8` | **u32** | **record count** - exact, use it to validate a parse |
| `-4` | u32 | `0` |

The count field is the parser's ground truth. If a walk does not end on exactly
that many records, the walk is wrong.

Two things had hidden this structure. The index field made a naive
`(id, size, value)` walker lock on and produce plausible-looking garbage split
into "nine streams", and the index shifts by one for every record inserted
ahead of it, so index-keyed diffs showed hundreds of spurious changes. **Key by
the hash.** Doing that drops a convoy-kill diff from ~2200 noisy features to 29.

### A wrong turn worth recording

The first working parser required the top 32 bits of the hash to be zero,
because every record it had seen so far satisfied that. It does not hold: the
last few hundred records in every save have hashes above `2^32`, and the check
silently truncated the stream there. Nothing errored - the parse just stopped
early and looked complete, and PT6 read as 10706 records instead of 10738.

The count field above is what caught it, which is why it is worth checking on
every parse rather than trusting a clean-looking walk. Re-running the convoy
analysis against the full stream added one changed record (a distance counter)
and left every conclusion standing, but that was luck, not method.

Values are small and typed by length: `u8` flags, `u32` counters, `f32`, 12/32/41
byte structs, one 42 KB blob (`16336C91`, rewritten on nearly every save).

Typical churn between two ordinary autosaves is 0-9 modified records and 0
additions, so this store is an excellent signal channel - far quieter than the
record stream in section 1.

---

## 6.3 The unmapped regions

Roughly **30% of the payload does not parse** as any of the structures above.
`tools/mapsave.py` prints the layout of any save and marks the gaps; run it
before assuming a diff has covered everything.

A typical mid-game save:

```
known  0x0000F0..0x007A8B   31131 bytes  section 1 record stream (2877 recs)
known  0x007A98..0x007BFC     356 bytes  table 0 live     esz=8  cnt=41
known  0x007D58..0x008124     972 bytes  table 1 markers  esz=16 cnt=59
known  0x008130..0x0082EC     444 bytes  table 2 convoys  esz=32 cnt=13
known  0x0082F8..0x011194   36508 bytes  table 3 roster   esz=24 cnt=1520
?????? 0x011194..0x01AD68   39892 bytes  REGION A
known  0x01AD68..0x02B4AF   67399 bytes  section 3 property store (2184 recs)
?????? 0x02B4AF..0x02FB18   18025 bytes  REGION B
```

**Region A** is a live world-entity arena. It opens with a 32-byte header,
magic `0xF9715A12`, laid out like the property-store header - magic, arena size,
reserve, `0`, `8`, size. Inside are **547 slots marked by `0xDEADBEEF`** at
strides of 44, 52, 96, 192, 244, 288 and 384 bytes; the count is 547 in every
frame examined, so it is a fixed pool rather than a list. Each slot carries a
hash, a type word and a world position as three floats. Further in, at about
`+0x7700`, sit counters that track the property store, and from `+0x7900` a
sorted ascending hash array that shifts on every insert.

**Region B** is easier: ordinary `(u32 id, u32 size, value)` streams with
sequential ids. `resource.py` reads one of them - scrap is id 42.

Neither region is understood well enough to edit safely. Region A is the more
interesting of the two: it is where a shot-up support car persisted across
edits that wiped every other trace of the fight.

---

## 7. What can be restored

**Both static props and dynamic encounters can be restored.** They are governed
by different records, which is what made convoys hard.

| class | example | governed by | restorable |
|---|---|---|---|
| static prop | scarecrow (type 45) | roster state + marker row (§7.1) | **yes, verified** |
| dynamic encounter | convoy (type 53) | a property-store record keyed by the object's id (§7.2) | **yes, verified** |

### 7.2 Convoys - the container record

A convoy's authoritative state is **not** in the roster, the marker table or the
table-2 position row. All three change when a convoy dies, and none of them
governs it. The record that does is in the property store, keyed by the
convoy's `CConvoyDataContainer` **objectid** - a value that appears nowhere in
the save's own structures and has to be read out of the game data
(`global/convoys.blo`; see [GAME-FILES.md](GAME-FILES.md)).

All fourteen container objectids are keys in the property store of every save
examined. Each keys a 32-byte record:

```
f32 x4    orientation quaternion
f32 x3    position
u32       state
```

| state | in the world | on the map |
|---|---|---|
| **0** | convoy present | not marked - undiscovered |
| **2** | present and complete | **marked in red, fully playable** |
| **3** | wrecked, position frozen at the wreck | cleared |

Verified in game both ways, on a live playthrough save and on the 100% reference
save. `convoy.py reset --state S` writes it. The game re-saves the slot
afterwards and keeps the value, which is what confirms the record is
authoritative rather than reconstructed from something else.

The roster flag, the ~22 marker rows, the table-2 position and the 13-record
per-vehicle ledger are all **downstream** of this field. Editing any of them in
isolation does nothing - six probes proved that the hard way, and the history is
in [FINDINGS.md](FINDINGS.md).

### 7.3 Notes on the derived records

**Markers are derived state.** Delete rows from table 1 and the game regenerates
them on the next autosave - 18 of 22 came back with identical keys and flags,
with no roster or record change. Editing table 1 for a convoy achieves nothing.

Marker flags, for the record: `0003` = tracked/live, `0000` = resolved. A
scarecrow kill adds exactly one marker flagged `0000`; the convoy fight added 22,
all flagged `0003`, never one `0000`. Support cars respawn when they unload from
memory, so the markers are not per-vehicle kill records - they track the leader's
components and damage.

**What a convoy kill writes,** from a control-subtracted ten-frame snapshot
series (four control frames of ordinary driving, four spanning the fight):

| where | change |
|---|---|
| **property store, container objectid** | **state `2` -> `3`, wreck position stored** |
| roster `593B2B20` | `3.0` -> `0.0` |
| table 2 `194895AE` | position frozen at the wreck |
| markers | 9 rows added, all flagged `0003` |
| section 3, elsewhere | 21 records added, 4 modified |
| section 1 | **nothing** - the record stream does not track convoys at all |

The 21 added property records are one-time global first-kill flags, not
per-convoy state: they are byte-identical in every reference-ladder stage from
PT2 (5 convoys dead) through PT6 (all 13 dead), absent in PT1, and unchanged
between PT3 and PT4 when three more convoys die.

## 7.1 Restoring a static object — verified

**Both halves are required**, and they are independent:

| edit | result in game |
|---|---|
| table 3 `state` → `1.0` only | object physically present, **no map marker** |
| table 1 flag → `03 00` only | marker present, **no object** |
| **both** | **fully restored** |

```
sec2.py BEFORE.sav AFTER.sav          # destroy something, diff, note both keys
mmrestore.py IN.sav OUT.sav --obj <table3 key> --marker <table1 key> --slot N
```

The two keys differ — table 1 and table 3 use separate hash spaces — so get both
from the diff. Length is preserved, so the checksum delta stays valid.

### A wrong turn worth recording

An earlier attempt deleted rows from table 1 and re-added a row to table 0. The
scarecrow came back — but so it did in a probe that only touched an *unrelated*
object's rows. Deleting rows shifts positions and destabilises associations,
resetting things wholesale. It looked like success three times and was an
artefact. Modify entries in place; never delete them.

---

## 8. Toolkit

| tool | use |
|---|---|
| `madmax_save.py info / verify` | header, checksum status, delta, freshness |
| `madmax_save.py records / rdiff` | list and diff section-1 records by id |
| `madmax_save.py setrec ID=HEX` | edit a record by id |
| `madmax_save.py patch OFF=HEX` | raw offset edit, resealed |
| `sec2.py A.sav B.sav` | map and diff the section-2 tables |
| `tail.py A.sav B.sav` | diff the section-3 property store, keyed by hash |
| `convoy.py list / revive` | the 13 convoys: roster state + position row |
| `sec2edit.py --set/--add/--del` | edit table entries and rebuild |
| `mmrestore.py --obj --marker` | restore a destroyed object (both halves) |
| `scan.py SAVE=VALUE …` | intersection value scan, for fields with no known offset |

Scrap is record id 42 (f32) in the resource stream - `resource.py list` /
`resource.py set 42=50000`. Found by the intersection scan across two autosaves
with known totals (161 and 10,000,000).

When hunting an unknown field, diff `tail.py` first. It is the quietest channel
in the file.
