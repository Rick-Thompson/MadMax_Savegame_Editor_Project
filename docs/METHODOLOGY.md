# How to find a field

Every field in this project was found the same way. The method matters more
than any individual result, because the game generates enough incidental churn
between saves to make a naive diff useless.

---

## 1. The save is autosave-driven

The game writes a save whenever world state changes. You do not need to reach a
save point — interacting with almost anything triggers a write. That makes it
possible to capture a *time series* of a single event.

`watch_saves.py` polls the save directory and snapshots every distinct write:

```
python3 tools/watch_saves.py ~/.steam/debian-installation/userdata/<id>/234140/remote ./snapshots
```

It reads each file twice and compares, to avoid capturing a torn write, and
names each snapshot `NNN_slotSS_ptNNNN.sav`.

Two traps:

- **Switching slots copies the save** and rewrites the playtime field. A file
  whose playtime advanced may be byte-identical in payload. Hash the payload,
  not the header.
- The game **always resumes you at the nearest base**, not where you saved, so
  do not expect the player position to reflect where you were.

---

## 2. Control subtraction

Never diff two saves and read the result. Capture a **control stretch** first —
several frames of doing something deliberately irrelevant, ideally the same
kind of activity as the event you care about — then capture the event.

Any feature that moves during the control is churn. Subtract it. The remainder
is signal.

For the convoy work this took ~2200 changing features down to 28, and 24 of
those survived the subtraction.

A good control for "I killed a convoy" is "I drove around and shot at things
for the same length of time". A bad control is "I stood still", because it does
not exercise the same systems.

---

## 3. Key by identity, never by position

This is the single biggest source of false results in this file format.

| structure | key by | never by |
|---|---|---|
| record stream | record id | byte offset |
| tables | the entry's first u32 | row index |
| property store | the u64 hash | the u32 index |
| tables (selecting which table) | entry size + row count | table position |

The payload grows as you play, so byte offsets shift. Later-game saves grow an
extra table, so table indices shift. The property store renumbers its index
field on every insert, so record indices shift. Each of these produced a
plausible, entirely wrong analysis at some point.

---

## 4. Diff the quietest channel first

Typical churn between two ordinary autosaves:

| structure | churn |
|---|---|
| property store (`tail.py`) | 0-9 modified records, 0 added |
| tables (`sec2.py`) | a handful of rows |
| record stream (`madmax_save.py rdiff`) | 1-2 ids, mostly `id 1848` (a live timer) |
| raw bytes | tens of thousands |

Start with `tail.py`. It has the best signal-to-noise ratio in the file.

---

## 5. Staged experiments

When one action changes several things at once, split it in game. The convoy
work established that the roster flips on the *leader's* death and not the
escorts' by deliberately killing them in the opposite order across two runs.
That single ordering change ruled out an entire hypothesis.

Design the in-game session before you start playing, and write down what you did
— including mistakes. "I also accidentally blew up a scarecrow early in the
session" turned out to matter.

---

## 6. Value scanning

For a field with a known value but no known location — scrap, health, fuel —
capture two saves with different known values and intersect the candidates:

```
python3 tools/scan.py save_a.sav=161 save_b.sav=10000000
```

Scrap was found this way. One practical detail: after editing a resource value
directly, the game may not notice until something forces it to re-read the
total. Collecting one more unit of the resource in game is enough.

---

## 7. Rules for editing

- **Preserve file length.** The integrity value is carried across the edit as a
  delta, and the delta is only valid at constant length. Every tool here
  enforces this and refuses otherwise. The 512-byte padding usually leaves
  enough slack that adding or removing a few table rows still works out.
- **Modify entries in place. Never delete rows.** Deletion shifts positions and
  produces wholesale resets that look exactly like success.
- **Read the intact value from a reference save.** Not everything is `1.0`;
  convoys are `3.0`, and other types store health or timers in the same field.
- **Turn off Steam Cloud** before touching anything.
- Keep the originals. `_original_backup/` exists for a reason.

---

## 8. Confirm in game, or it did not happen

Several results in this project looked correct in the diff and were wrong on
screen, and one looked wrong in the diff and was correct. The save is evidence;
the game is ground truth.
