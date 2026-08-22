# Open questions

Ranked by how tractable they look. Each one includes what has already been ruled
out, so nobody repeats the dead ends in [FINDINGS.md](FINDINGS.md).

---

## 1. Can a convoy be made to respawn?  **SOLVED**

Yes. The record is the 32-byte blob the property store keys by each convoy's
`CConvoyDataContainer` objectid, read out of `global/convoys.blo`. See
[GAME-FILES.md](GAME-FILES.md).

```
state 0   never encountered   -> convoy present, not on the map
state 2   active              -> route marked in red, convoy drivable and complete
state 3   wrecked
```

Verified in game on a live playthrough and on the 100% reference save.
`convoy.py reset --state S` writes it.

Six earlier probes failed against roster state, marker rows and the table-2
position row, all of which move when a convoy dies and none of which govern it.
That history is in [FINDINGS.md](FINDINGS.md).

The open part that remains: whether the same pattern - a `save = 1` entity in a
`.blo` whose objectid keys a property-store record - unlocks the other activity
types the same way. Camps, minefields and sniper towers all have entities in
their own `.blo` files, and nobody has looked yet.

## 2. The integrity value at offset 0

**Status: worked around, not solved.**

The workaround — read the delta off the original file, carry it across the edit
— is reliable but constrains every edit to preserve file length. Solving it
properly would remove that constraint.

What is known: the delta depends **only on file length**, never on content. Five
independent files of length 1020928 share delta `0x0E7EDB6E` despite differing in
thousands of payload bytes.

What has been ruled out, across ten distinct file lengths: CRC-32 over plain
ranges with solved init/xorout, CRC-32C, Koopman, CRC-32Q, FNV, Jenkins, Adler,
byte-sum, per-save seed fields, several byte orderings, and length values
prepended or appended in four encodings. Nothing fits three or more lengths.

The likeliest explanation is that the length dependence comes from something
structural — a count, a padding rule, a second pass — rather than from a
different polynomial. Someone with the binary in a disassembler would find this
in an afternoon.

## 3. Unlabelled object types

Types 49, 52 and 53 are now labelled (sniper, minefield, convoy) from the game's
file list, and scarecrows probably span 45-48 - see
[OBJECT-TYPES.md](OBJECT-TYPES.md).

Ten type ids still have no label: **5, 10, 11, 12, 17, 26, 37, 40, 41, 69**. Types 11, 17, 26, 37 and 69 are never cleared even at 100% completion, so
they are probably scenery or permanent structures. Types 5, 10, 12, 40 and 41
are only partially cleared, which makes them the interesting ones.

Labelling one takes about two minutes: destroy one in game, save, run
`sec2.py before.sav after.sav`, note which type moved. Per-type counts are in
[OBJECT-TYPES.md](OBJECT-TYPES.md).

## 4. The rest of the resource stream

Scrap is record id 42, an f32. Ids **41, 26 and 28** change plausibly with
health, fuel and water but have not been confirmed. Confirming one is a
five-minute experiment: note the value in game, save, change only that resource,
save again, diff.

## 5. The 42 KB blob

Property store record `16336C91` is a 42 KB value rewritten on nearly every
save. It is by far the largest single record in the file and its contents are
completely unexamined. It may be a heightmap-style visited/discovered mask, a
photo-mode buffer, or a serialised entity graph — nobody has looked.

## 6. Are the tracking rows reconstructible?

The game regenerated 18 of 22 deleted tracking rows on the next autosave, with
identical keys and flags. Whatever it rebuilds them from is more authoritative
than the table itself, and finding it would probably answer question 1 as well.
The four rows it did *not* regenerate may be the informative ones — they were
never identified.

## 7. Platform coverage

Everything here was worked out on Linux under Proton, plus four older Windows
saves via OneDrive. The XOR key, header layout and integrity behaviour are
identical across both, and across save format generations 2 and 6. Consoles are
entirely untested.

## 8. Position editing

Record `id 0` in the record stream is a 64-byte 4x4 transform — a
respawn/checkpoint position, not the player's live position. Writing to it has
not been tried. Since the game always resumes at the nearest base, it is not
obvious this would do anything, but it is cheap to test and would be useful for
reaching out-of-bounds areas.
