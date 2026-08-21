# Mad Max (2015) — save file format

**Status: working save editor.** Edited saves load in game, in both save formats,
and destroyed world objects can be restored — verified in game.

This is the format spec. For the convoy investigation and the failures see
`FINDINGS.md`; for how to run your own experiment see `METHODOLOGY.md`.

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

## 7. What can and cannot be restored

**Static world props can be restored. Dynamic encounters cannot — yet.**

| class | example | roster | restorable |
|---|---|---|---|
| static prop | scarecrow (type 45) | authoritative | **yes, verified** |
| dynamic encounter | convoy (type 53) | records the result, does not govern it | **no** |

Convoys: the roster entry holds `3.0` intact and flips to `0.0` **when the leader
dies** - not when the support cars are cleared (confirmed by killing the leader
first, then the escorts, which left the roster alone). Restoring it to `3.0`
sticks - the game keeps the value across later autosaves - but the convoy does
not come back.

Four probes have now failed:

1. roster restored to `3.0` alone - convoy still gone
2. roster + the 9 markers created by the kill removed - still gone
3. roster + all 22 markers from the whole encounter removed - still gone
4. roster + the table-2 position row zeroed - still gone

**Markers are derived state.** After probe 3 the game regenerated 18 of the 22
deleted rows on the next autosave, same keys and same flags, with no roster or
record change. So table 1 is rebuilt from something more authoritative and
editing it achieves nothing. A support car left over from the fight, still
carrying its blown tyre, survived the same edit - live world entities persist in
the unparsed tail of section 2, and that is where the encounter's real state
must live.

### 7.0 What the full-coverage scan of a convoy kill found

With section 3 parsed by hash, the ten-frame snapshot series was re-scanned:
four control frames of ordinary driving, then the four frames spanning the
convoy fight. Control-subtracted, the kill moves exactly **24 features** that
never move during control:

| where | change |
|---|---|
| roster `593B2B20` | `3.0` -> `0.0` |
| table 2 `194895AE` | position frozen at the wreck |
| markers | 9 rows added, all flagged `0003` |
| section 3 | 21 records added, 4 modified |
| section 1 | **nothing** - the record stream does not track convoys at all |

The 21 added section-3 records are all present, with byte-identical values, in
every reference-ladder stage from PT2 (5 convoys dead) through PT6 (all 13 dead), and
absent in PT1 (none dead). They do **not** change between PT3 and PT4 when three
more convoys die. So they are one-time global first-kill flags, not per-convoy
state.

**Conclusion: the only per-convoy persistent state in the whole file is
`roster[key].state` plus the position row in table 2.** There is no hidden
completion record. The markers are derived, section 1 is silent, and the
property store only counts firsts.

That narrowed the open question to one testable thing: whether a stored position
in table 2 is what marks a convoy as already-instantiated. `convoy.py revive`
restores the roster state to `3.0` **and** zeroes the position row - the one
combination none of the three earlier probes had tried.

**Probe 4 result: it does not work.** The edited save loads, the roster reads
alive and the position row reads unspawned, and the convoy is still cleared in
game. Every structure in the file that parses has now been covered. See
`FINDINGS.md` for what that leaves.

Marker flags, for the record: `0003` = tracked/live, `0000` = resolved. A
scarecrow kill adds exactly one marker flagged `0000`; the convoy fight added 22,
all flagged `0003`, never one `0000`. Support cars respawn when they unload from
memory, so the markers are not per-vehicle kill records - they track the leader's
components and damage.

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
