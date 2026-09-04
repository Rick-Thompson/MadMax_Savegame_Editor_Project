# Mad Max (2015) save file format & editor

Reverse-engineering notes and a working save editor for Avalanche Studios'
*Mad Max* (2015, Steam app id 234140).

**Status: solved, including convoys.** Saves can be decoded, edited, re-sealed
and loaded by the game. Destroyed static world objects can be put back. Scrap
can be set to any value. And **cleared convoys can be fully restored** - verified
in game, on a live playthrough and on a 100% save: the routes come back marked
in red on the map, and driving to one gives a complete, working convoy.

```
convoy.py reset SAVE.sav OUT.sav --slot N --state 2
```

`--state 0` brings them back undiscovered instead - present in the world, not
yet on the map.

That took a while. Six earlier attempts failed because they edited records that
*describe* a convoy rather than the one that governs it; the history is in
[docs/FINDINGS.md](docs/FINDINGS.md) and the answer is in
[docs/GAME-FILES.md](docs/GAME-FILES.md).

This is published so other people can take it further. Everything here is
reproducible from the sample saves in `data/`.

---

## What works

| capability | tool | verified |
|---|---|---|
| decode / re-encode any save | `madmax_save.py` | yes |
| pass the game's integrity check after an edit | `madmax_save.py reseal` | yes, loads in game |
| read the header (slot, playtime, timestamps, format gen) | `madmax_save.py info` | yes |
| list / diff the record stream | `madmax_save.py records / rdiff` | yes |
| map and diff the section-2 tables | `sec2.py` | yes |
| diff the hash-named property store | `tail.py` | yes |
| edit a property record in place | `tailedit.py` | yes |
| map a payload and show the gaps | `mapsave.py` | yes |
| recover names for the hashes | `names.py` | see HASHES.md |
| extract files from the game archives | `arcx.py` | yes |
| decode ADF files and graph scripts | `adf.py` | yes |
| read SARC bundles (.bl) | `sarc.py` | yes |
| read RTPC entity data (.blo) | `rtpc.py` | yes |
| disassemble XVM gameplay scripts | `xvm.py` | yes |
| restore a destroyed scarecrow, sniper tower, etc. | `mmworld.py --restore-type` | **yes, in game** |
| destroy objects in bulk (for testing) | `mmworld.py --destroy-type` | **yes, in game** |
| set scrap | `resource.py set 42=N` | **yes, in game** |
| inspect the 13 convoys | `convoy.py list` | yes |
| restore cleared convoys | `convoy.py reset --state 2` | **yes, in game** |

## What is still open

The **save's key scheme**. Every key in a save is a hash of *something*, but
nothing in 101,426 real game names matches under `lookup3` or five other
functions, so the keys stay opaque - you can edit a record once you know what it
governs, but you cannot look one up by name. See
[docs/HASHES.md](docs/HASHES.md).

The **integrity value** at offset 0 is not solved in closed form, so every edit
must preserve file length. The delta-carry workaround makes that a non-issue in
practice, and every tool here enforces it.

**Roughly 30% of the payload still does not parse** - `mapsave.py` shows the
gaps. Nothing needed for the edits above lives there, but it is where the next
findings will come from.

---

## Quick start

Requires Python 3, no dependencies.

```
# where the game actually loads from (Linux/Proton)
SAVES=~/.steam/debian-installation/userdata/<SteamID3>/234140/remote

python3 tools/madmax_save.py info    "$SAVES/GameSave01.sav"
python3 tools/madmax_save.py verify  "$SAVES/GameSave01.sav"

# what is destroyed in this save?
python3 tools/mmworld.py "$SAVES/GameSave01.sav" --status

# put every destroyed scarecrow (object type 45) back, writing to slot 7
python3 tools/mmworld.py "$SAVES/GameSave01.sav" /tmp/out.sav \
        --restore-type 45 --ref data/ladder/PT1.sav --slot 7
cp /tmp/out.sav "$SAVES/GameSave07.sav"
```

**Turn Steam Cloud off for this game first.** It will silently restore the old
save over your edited one.

---

## Repository layout

```
README.md                 this file
docs/
  FORMAT.md               the file format spec - start here
  FINDINGS.md             the convoy investigation, including the failures
  METHODOLOGY.md          how to run a save-diff experiment without fooling yourself
  OPEN-QUESTIONS.md       what is still unsolved, and what to try next
  GAME-FILES.md           the game's own archives - where the convoy answer came from
  OBJECT-TYPES.md         the 1520-entry object roster, per-type counts
  LOCATIONS.md            every location/activity type, with counts and evidence
  HASHES.md               the name hash - where it applies, and where it does not
  SCRIPTS.md              the game's save/load script, disassembled
tools/                    the Python utilities (see tools/README.md)
data/
  ladder/                 PT1-PT6, a 0% -> 100% reference ladder
  gibbed/                 Gibbed.MadMax's file list, 27501 game paths
  samples/                a snapshot series spanning one convoy fight
  field-map.csv           222 record ids that move across the ladder
experiments/              log of every in-game experiment and its result
```

---

## The one-paragraph summary of the format

Every byte is XOR'd with a fixed repeating 32-byte key. Under that is a 0xF0
header (slot, playtime, timestamps, payload length) followed by the payload,
usually an identical mirror copy of the payload, and zero padding to a 512-byte
boundary. The payload has three parts: a `(u32 id, u32 size, value)` record
stream holding story and mission state; four tables, of which the 1520-entry
24-byte one is the world-object roster and the 13-entry 32-byte one is the
convoys; and a large hash-named property store sorted by key. A u32 at offset 0
is an integrity value that the game checks — it is not solved in closed form,
but it depends only on file length, so it can be carried across any
length-preserving edit. Full detail in [docs/FORMAT.md](docs/FORMAT.md).

---

## Contributing

The most useful things anyone could add:

1. **Follow the convoy graph scripts.** `arcx.py` extracts them and `adf.py`
   decodes them into named node graphs - see
   [docs/GAME-FILES.md](docs/GAME-FILES.md). The spawner turned out to be just
   the map icon; `convoy_choreographer.gsrc` and the spawning graphs are next.
2. **The save's key scheme.** Every key in a save is a hash of *something*, and
   nothing in 101,426 real game names matches under `lookup3` or five other
   functions. See [docs/HASHES.md](docs/HASHES.md).
3. **The other activity types.** Convoys are solved, and the method that solved
   them is five repeatable steps (see
   [docs/GAME-FILES.md](docs/GAME-FILES.md)): find the activity's `.bl` bundle,
   unpack the SARC, decode the RTPC, take the `objectid`s of entities with
   `save = 1`, look those up in the property store. Camps, minefields and sniper
   towers have their own bundles and nobody has looked yet.
4. **A closed-form solution to the integrity value.** The delta-carry workaround
   means edits must preserve file length. Solving it properly would lift that.
5. **Object type labels.** Types 52 and 53 are now settled from the game's file
   list, and scarecrows probably span 45-48 (see GAME-FILES.md). Types 5, 10,
   11, 12, 17, 26, 37, 40, 41, 69 are still unidentified. Labelling one takes about two minutes: destroy one thing in
   game, save, and diff.
6. **Windows / other-platform confirmation.** Everything here was worked out on
   Linux under Proton. A player has confirmed a **scrap edit loads correctly on
   Windows**, which validates the decode/reseal chain including the integrity
   value - the failure mode that would have broken everything. Table edits and
   convoy resets are still unverified there; a convoy reset is the best single
   test, since it touches both. See
   [docs/OPEN-QUESTIONS.md](docs/OPEN-QUESTIONS.md).

Please include the before/after saves with any finding. Half the wrong turns
recorded in these docs would have been caught by someone else re-running the
diff.

## Credits

The `data/ladder/` saves are **"Mad Max Savegames"** by **Just Chill**, posted
as a Steam Community guide on 5 January 2018:

> https://steamcommunity.com/sharedfiles/filedetails/?id=1256911456

The guide lists no restriction on rehosting. They are included unmodified apart
from being flattened out of their original folder layout, and are used here only
as analysis input. The type map and the convoy analysis both depend on having a
clean 0%→100% reference ladder, and this one is the reason the object roster
could be shown to be universal rather than per-save. Thanks to the author.

If you would rather fetch them yourself, download from the link above and drop
the six `GameSave01.sav` files into `data/ladder/` as `PT1.sav` … `PT6.sav`, in
playthrough order. Nothing else needs to change.
