# The convoy investigation

The goal that drove most of this project: make a cleared activity replayable.
It worked for static props and failed for convoys. This is the complete record,
failures included, so nobody has to repeat it.

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

## 3. The four failed probes

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

## 5. Conclusion

**The only per-convoy persistent state in the entire save file is
`roster[key].state`, plus a live position row that is pure telemetry.**

There is no hidden completion record. The record stream is silent on convoys,
the tracking table is derived, and the property store only counts firsts. Every
byte that parses has now been accounted for.

Two readings are consistent with the evidence, and distinguishing them requires
looking at the executable rather than the save:

1. **Spawn gating is code-side.** Convoy availability may be computed from
   region/territory progression at load time rather than read from the save, in
   which case no save edit can bring one back.
2. **There is a fifth structure.** A support car left over from the fight —
   still carrying the tyre the player had shot off — survived probes 2 and 3
   intact. Live world entities persist somewhere. The property store turned out
   not to be it, but the region between the roster table and the property store
   is a few kilobytes that still do not parse as anything.

Item 2 is the cheapest remaining lead and is written up in
[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md).

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
