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

## 3. Unlabelled object types — CLOSED

All 25 profile ids that appear in a save are now labelled directly from the
game's own data. `ProfileIndex` indexes `global/economyresources.economyresourcesc`,
and the never-cleared ids that looked like scenery turned out to be ordinary
pickups: 11 and 12 are Water, 26 and 37 Scrap, 40 and 41 Food, 5 Fuel, 69 a
FillChance-0 Scrap row. See [ECONOMY.md](ECONOMY.md).

What replaced this question is narrower and more interesting: **a camp's state
beyond its threat value.** The Threat row is strictly binary — full or zero,
never partial, across 37 camps x 6 ladder saves — so the three map states
(undiscovered / discovered / objective met) and the 100%-complete state the map
never draws are stored somewhere else. The property store is the obvious
candidate, since that is where the convoy answer turned out to be. A staged
capture of one camp cleared step by step would settle it.

## 4. The rest of the resource stream

Scrap is an f32 in the resource stream (its id moves between saves - see
FORMAT.md). Ids **41, 26 and 28** change plausibly with
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

**Windows writes: the core path is confirmed.** A player edited their scrap on
Windows (`resource.py set 42=N`, the old fixed-id form) and the game loaded the result without
complaint. That is the single most important thing to have verified off-Linux,
because it exercises the whole decode -> edit -> reseal chain: the XOR key, the
mirror and padding layout, length preservation, and above all the **delta-carry
integrity value**. If the checksum carry were wrong on Windows the game would
have rejected the save outright, so this rules out the failure mode that would
have broken everything.

Still unverified on Windows, in rough order of risk:

| edit class | example | exercised by the scrap test? |
|---|---|---|
| resource stream record | `resource.py scrap` | **yes** |
| section-2 table entry | `mmworld.py --restore-type`, roster/marker edits | no |
| property store record | `convoy.py reset` | no |
| slot-byte rewrite | `--slot N` | no |

The table edits are the ones worth testing next, because that is where the
positional-index fragility lives (see the `roles()` note in
[FINDINGS.md](FINDINGS.md)) - a later-game save grows an extra 24-byte table and
shifts everything after it. A convoy reset is the single best test available: it
touches a table **and** a property-store record in one operation, and the result
is obvious in game.

## 8. Position editing

Record `id 0` in the record stream is a 64-byte 4x4 transform — a
respawn/checkpoint position, not the player's live position. Writing to it has
not been tried. Since the game always resumes at the nearest base, it is not
obvious this would do anything, but it is cheap to test and would be useful for
reaching out-of-bounds areas.
