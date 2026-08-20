# Mad Max (2015) save file format & editor

Reverse-engineering notes and a working save editor for Avalanche Studios'
*Mad Max* (2015, Steam app id 234140).

**Status: the container format is fully solved.** Saves can be decoded, edited,
re-sealed and loaded by the game. Destroyed static world objects can be put
back — verified in game, both directions, individually and in bulk. Scrap can
be set to any value. Dynamic encounters (convoys) can be *marked* un-cleared but
do not respawn; see [docs/FINDINGS.md](docs/FINDINGS.md) for exactly how far
that has been chased and where it stopped.

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
| restore a destroyed scarecrow, sniper tower, etc. | `mmworld.py --restore-type` | **yes, in game** |
| destroy objects in bulk (for testing) | `mmworld.py --destroy-type` | **yes, in game** |
| set scrap | `resource.py set 42=N` | **yes, in game** |
| inspect the 13 convoys | `convoy.py list` | yes |

## What does not work

Convoys do not come back. The roster value can be set back to "alive" and it
sticks across later autosaves, but the encounter never respawns. Four separate
probes have now failed, including one that covered every byte in the file that
parses. See [docs/FINDINGS.md](docs/FINDINGS.md).

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
  OBJECT-TYPES.md         the 1520-entry object roster, per-type counts
tools/                    the Python utilities (see tools/README.md)
data/
  ladder/                 PT1-PT6, a 0% -> 100% reference ladder
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

1. **A convoy respawn.** Four probes have failed. `docs/OPEN-QUESTIONS.md` lists
   what is left to try, mostly on the executable side rather than the save.
2. **A closed-form solution to the integrity value.** The delta-carry workaround
   means edits must preserve file length. Solving it properly would lift that.
3. **Object type labels.** Types 5, 10, 11, 12, 17, 26, 37, 40, 41, 69 are
   unidentified. Labelling one takes about two minutes: destroy one thing in
   game, save, and diff.
4. **Windows / other-platform confirmation.** Everything here was worked out on
   Linux under Proton plus four older Windows saves.

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
