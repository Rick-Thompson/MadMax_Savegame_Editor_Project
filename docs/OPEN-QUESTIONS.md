# Open questions

Ranked by how tractable they look. Each one includes what has already been ruled
out, so nobody repeats the dead ends in [FINDINGS.md](FINDINGS.md).

---

## 1. Can a convoy be made to respawn?

**Status: six probes failed.** See [FINDINGS.md](FINDINGS.md) for the full
record. What follows is the current state of the search, not a conclusion.

Everything tried so far, all length-preserving, all confirmed to load:

| # | edit | result |
|---|---|---|
| 1 | roster state -> `3.0` | convoy still cleared |
| 2 | roster + the 9 kill markers removed | still cleared |
| 3 | roster + all 22 encounter markers removed | still cleared |
| 4 | roster + table-2 position row zeroed | still cleared |
| 5 | roster + position + 13 vehicle records set to `1` | still cleared |
| 6 | roster + position + 13 vehicle records orphaned | still cleared |

### The reason none of that was ever going to be conclusive

**Thirty percent of the payload had never been parsed.** An earlier draft of
this file said the gap after the roster table was "roughly 6 KB". It is
**39,892 bytes**, and there is a second unmapped region of **18,025 bytes**
after the property store. Together that is 58 KB of a 195 KB payload. The claim
that every byte was accounted for was wrong, and it was wrong in the direction
that made the convoy look unsolvable.

### 1a. Region A - the live entity arena

`0x011194`..`0x01AD68` in one sample, between the roster table and the property
store. Structure so far:

- a 32-byte header, magic **`0xF9715A12`**, same shape as the property-store
  header: magic, arena size (30376), reserve, `0`, `8`, size
- **547 slots marked by `0xDEADBEEF`**, at fixed strides (44, 52, 96, 192, 244,
  288, 384 bytes). The count is 547 in every frame examined, so it is a fixed
  pool, not a growing list
- each slot carries a hash, a type word, and a world position as three floats
- at `+0x76B8` a second sub-structure with its own counters, one of which moved
  by exactly `+21` at the convoy kill - matching the 21 property records added
- from `+0x7900`, a sorted ascending hash array where insertions shift every
  later entry. This churns during ordinary driving too (16-22 inserts between
  control saves), so it is a general registry rather than convoy state

This is where the support car with the shot-out tyre lives - the thing that
survived probes 2 and 3 intact.

**Two isolated words changed here at the kill and nowhere else:**

| offset from region start | 033 (alive) | 034 (dead) |
|---|---|---|
| `+0x00` | `0` | `1` |
| `+0x10` | `0` | `F7F4A073` |

`F7F4A073` is not a property-store hash, not a roster key and not a marker key.
It already existed once in region A before the kill, 144 bytes away from the
slot it was written into, so the kill *copied a reference* into a header field
rather than inventing a value. The same pattern shows at `+0x76B8`
(`0` -> `010E69A2`) and `+0x7700` (`9` -> `0404BC01`), each also a duplicate of
a value 144 bytes away.

Something in region A has a 144-byte stride. Working that out is the next
concrete task, and it is pure analysis - no game time needed.

### 1b. Region B

`0x02B4AF`..`0x02FB18`, 18 KB after the property store. This one is not
mysterious: it is ordinary `(u32 id, u32 size, value)` streams with sequential
ids, and `resource.py` already reads one of them (scrap is id 42). It has never
been diffed across the convoy frames.

### 1c. The experiment that would settle it

Every probe so far has guessed at what "not resolved" looks like. There is a way
to *measure* it instead.

From the Steam forums, and consistent with everything here: shoot or harpoon a
wheel off the lead truck to **disable it without destroying it**, then leave.
The whole convoy respawns. Same poster: leave one scrap pile in a camp and the
camp repopulates.

So capture that state.

1. Find a live convoy, save - **A: untouched**
2. Blow a wheel off the lead truck, kill nothing else, save - **B: disabled**
3. Drive away until it despawns, save - **C: disabled, unloaded**
4. Return later once it has respawned, save - **D: respawned**
5. On a different convoy, destroy the leader outright, save - **E: destroyed**

`B`/`C` versus `E` is a controlled A/B on the one variable that matters:
same fight, same damage, one will come back and one will not. Whatever differs
between them is the answer, and `D` confirms the direction. No amount of blind
editing substitutes for this.

### 1d. The executable

If convoy availability is computed at load time from region or territory
progression rather than read from the save, no save edit will ever work. That
would still be an answer. Finding the code that reads the roster's type-53
entries would settle it, but it needs static analysis rather than more diffing.

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

Ten of the roster's type ids have no label: **5, 10, 11, 12, 17, 26, 37, 40, 41,
69**. Types 11, 17, 26, 37 and 69 are never cleared even at 100% completion, so
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
