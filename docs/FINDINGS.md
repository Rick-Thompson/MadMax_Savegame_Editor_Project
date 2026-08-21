# The convoy investigation

The goal that drove most of this project: make a cleared activity replayable.

**It is solved** - see [GAME-FILES.md](GAME-FILES.md) for the record that does
it. This document is the road there, six failed probes included, because the
failures are the useful part: every one of them was a real edit to a real field
that genuinely tracks convoy state, and none of them worked.

The lesson, stated once: **a field that changes when something happens is not
necessarily the field that causes it.** Roster state, marker rows and the
table-2 position all move when a convoy dies. All three are downstream.

---

## 1. Static props — solved

A scarecrow (object type 45) lives in two places, and **both** must be edited:

| edit | result in game |
|---|---|
| roster `state` -> `1.0` only | object physically present, no map marker |
| tracking flag -> `03 00` only | marker present, no object |
| **both** | **fully restored** |

Verified in both directions: destroying all 34 scarecrows by editing the save
removed all 34 in game; restoring them brought all 34 back. One partially
restored scarecrow was visible from a distance and despawned as the player drove
up to it, which is what a half-edit looks like.

Convoys are object type 53 and sit at `3.0` when intact rather than `1.0`. Always
read the intact value from a reference save rather than assuming.

---

## 2. Convoys — what was measured

A ten-frame snapshot series was captured with `watch_saves.py`: four frames of
ordinary driving as a control, then the frames spanning one convoy fight —
route appears, engagement, leader killed, artifact collected.

Control-subtracted, the leader's death moves exactly **24 features** in the
whole file:

| where | change |
|---|---|
| roster `593B2B20` | `3.0` -> `0.0` |
| table 2 `194895AE` | live position frozen at the wreck |
| tracking table | 9 rows added, all flagged `0003` |
| property store | 21 records added, 4 modified |
| record stream (section 1) | **nothing at all** |

Additional facts established along the way:

- The roster flips **when the leader dies**, not when the escorts are cleared.
  Confirmed by killing the leader first and the escorts afterwards, which left
  the roster untouched.
- Support cars respawn when they unload from memory, so the tracking rows are
  not per-vehicle kill records. They track the leader's components and damage.
- The whole encounter adds 22 tracking rows, every one flagged `0003`
  (tracked/live) and never `0000` (resolved). A scarecrow kill adds exactly one
  row, flagged `0000`. Convoys are a different mechanism.

---

## 3. The failed probes

| # | edit | result |
|---|---|---|
| 1 | roster restored to `3.0` | value sticks across later autosaves; convoy still gone |
| 2 | roster + the 9 rows created by the kill deleted | still gone |
| 3 | roster + all 22 rows from the whole encounter deleted | still gone |
| 4 | roster + the table-2 position row zeroed | still gone |

Probe 4 was the interesting one, and it is the reason this document exists: it
was designed after the property store was finally parsed correctly, and it
covered the last structure in the file that had never been touched. It still
failed.

**Probes 2 and 3 also produced a second finding: the tracking table is derived
state.** After probe 3 the game regenerated 18 of the 22 deleted rows on the
next autosave — same keys, same flags — with no roster or record change. So it
is rebuilt from something more authoritative and editing it achieves nothing.

---

## 4. Ruling out the property store

The 21 property records added by the kill looked like the best remaining
candidate. They are not per-convoy:

- All 21 are present with **byte-identical values** in every reference-ladder stage
  from PT2 (5 convoys dead) through PT6 (all 13 dead).
- All 21 are **absent** in PT1 (no convoys dead).
- None of them change between PT3 and PT4, during which **three more convoys
  die**.

That is the signature of one-time global first-kill flags — "player has now
destroyed a convoy" — not of per-convoy state.

---

## 4a. The vehicle ledger — 13 records that track the convoy itself

Re-reading the property store across the whole session, rather than only across
the kill, turned up a group the kill-only diff could not see because **they were
written when the convoy spawned, not when it died**:

| hash | 023-031 | 032 (spawn) | 033 | 034 (kill) | 036 (drove off) | 037 |
|---|---|---|---|---|---|---|
| `23C77753` and 12 others | absent | `1` | `1` | `1` | `FF01` | `FF01` |

Thirteen records, identical timing, identical values, moving as one block:

- **absent** before the convoy has ever spawned
- **`1`** from the moment the route appears on the map, through the whole fight
- **`0xFF01`** once the wrecks despawn

Thirteen is the size of the convoy - lead truck plus escorts. The read is that
this is a per-vehicle ledger: absent = never instantiated, `1` = live,
`FF01` = gone.

The same thirteen hashes appear in the reference ladder, absent in PT1 and
`FF01` in PT2 through PT6 - and PT2 is the first stage where this same convoy
(`593B2B20`) is dead. So the names are static spawn-point identifiers baked
into the game data, not per-playthrough handles, which is what makes them worth
editing.

This is the "live world entities persist somewhere" gap from probe 3 - the
support car that kept its shot-out tyre. It was in the property store after
all; the kill-only diff just could not see records that had been written two
frames earlier.

---

## 4b. How convoys respawn naturally

From a player on the Steam forums, and consistent with everything measured
here:

> you can blow a wheel off the big truck with shotgun, or pull it off with
> harpoon [...] to disable the truck **without destroying it**. [...] Then you
> just leave the truck there without blowing it up, and the whole convoy will
> respawn.

Same poster, on camps: leave one scrap pile behind when clearing a camp and the
enemies respawn.

This reframes the problem. The game already has a respawn path; it is gated on
the encounter never having been *resolved*. So the target is not to reconstruct
a convoy from scratch, it is to find every byte that says "resolved" and put it
back to "never happened". The roster flag was one. The vehicle ledger is very
likely another - a restored roster entry sitting next to thirteen records that
say the vehicles are destroyed is a contradictory state, and the ledger is the
half that describes the encounter instance.

---

## 5. Where it stands

Six probes, all length-preserving, all confirmed to load, all failed:

| # | edit | result |
|---|---|---|
| 1 | roster state -> `3.0` | convoy still cleared |
| 2 | roster + the 9 kill markers removed | still cleared |
| 3 | roster + all 22 encounter markers removed | still cleared |
| 4 | roster + table-2 position row zeroed | still cleared |
| 5 | roster + position + 13 vehicle records set to `1` | still cleared |
| 6 | roster + position + 13 vehicle records orphaned | still cleared |

Probes 5 and 6 were built on the vehicle ledger above. Setting the thirteen
records to "alive" and erasing them so the convoy reads as never-spawned both
left the convoy cleared, so the ledger records the encounter without governing
it - the same relationship the roster and the marker table already had.

### The claim that was wrong

An earlier version of this document said "every byte that parses has now been
accounted for". That was false. **Thirty percent of the payload had never been
parsed at all**: 39,892 bytes between the roster table and the property store,
and 18,025 bytes after it. The gap had been described as "roughly 6 KB" from a
guess that was never checked against the actual offsets.

The pattern is worth naming, because it produced probes 4, 5 and 6. Each new
structure found was assumed to be the last one, so a failed probe read as
evidence that the answer was not in the save - when it was really evidence that
the map was incomplete. Six probes is the cost of that assumption.

The larger region is now partly mapped and is described in
[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md#1a-region-a---the-live-entity-arena): a
fixed pool of 547 `0xDEADBEEF`-marked entity slots carrying hashes, types and
world positions, plus a sorted hash registry. Two isolated header words in it
change at the kill and nowhere else.

### What should happen next

Not another probe. The forum account of convoys respawning when the lead truck
is *disabled rather than destroyed* means the "will respawn" state is reachable
in normal play, so it can be captured and diffed instead of guessed at. The
capture protocol is in
[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md#1c-the-experiment-that-would-settle-it).

---

## 6. Wrong turns worth recording

These all looked like results at the time.

**"Verified on six files" that verified nothing.** An early closed-form solution
to the integrity value was declared solved against six saves. Those six had only
**two distinct file lengths**, and two lengths give exactly 64 equations for the
64 unknown bits being solved for. The fit was guaranteed by construction, not
confirmed by evidence. A later save at a third length broke it immediately.

**A scarecrow "restore" that was an artefact.** Deleting rows from the tracking
table appeared to bring a scarecrow back, three times. Then a control probe that
touched only an *unrelated* object's rows brought the same scarecrow back too.
Deleting rows shifts positions and destabilises associations, resetting things
wholesale. **Modify entries in place; never delete them.**

**Bulk restore that clobbered health values.** A `--restore-all` reported
changing 1319 objects when only 53 were actually destroyed — it was overwriting
`500.0`, `1000.0` and `6.0` health-and-timer values with `1.0`. Only flip the
exact intact<->destroyed pair.

**Positional table indices.** Later-game saves grow an extra 24-byte table,
shifting every table after it. Code that addressed tables by index would have
corrupted a 58-hour save. Select tables by role — entry size and row count —
never by position.

**Playtime as a freshness check.** Switching the active slot *copies* the save
and rewrites the playtime field, so playtime can advance on a file whose
contents are identical. Of 25 captured files only 10 had distinct payloads. Hash
the payload instead.

**"header crc mismatch" in the binary.** That string, and a CRC table sitting
near it in `IOFragments_F.dll`, are an embedded copy of zlib — the neighbouring
strings are "incorrect header check" and "invalid window size". Nothing to do
with the save's integrity value.

**Nine record streams that did not exist.** The property store starts each
record with a sequential index, which made a naive `(id, size, value)` walker
lock on and emit convincing garbage, split into what looked like nine separate
streams. Worse, the index shifts by one for every record inserted ahead of it,
so index-keyed diffs showed hundreds of spurious changes and buried the real
ones. Keying by the hash instead dropped a convoy-kill diff from ~2200 noisy
features to 28.
