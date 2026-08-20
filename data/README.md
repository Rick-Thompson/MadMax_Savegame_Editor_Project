# Data

## `ladder/` — PT1 through PT6

**"Mad Max Savegames"** by **Just Chill**, posted as a Steam Community guide on
5 January 2018:
https://steamcommunity.com/sharedfiles/filedetails/?id=1256911456

The guide lists no restriction on rehosting. Included unmodified apart from
being flattened out of the original folder layout — each stage ships as
`Documents/WB Games/Mad Max/Backup Saves/GameSave01.sav`, renamed here to
`PT1.sav` … `PT6.sav` in playthrough order.

This is the reference ladder. It is what makes the object type map trustworthy:
the roster holds exactly 1520 entries with identical per-type counts in this
2017 playthrough and in a 2026 one, so the type ids are universal rather than
per-save.

| file | state |
|---|---|
| PT1 | The Outer Graves - 0%, nothing cleared |
| PT2 | Jeet's territory - 5 of 13 convoys dead |
| PT3 | Gutgash's territory - 10 of 13 |
| PT4 | Pink Eye's territory - 13 of 13 |
| PT5 | Deep Friah's territory |
| PT6 | 100% |

Useful properties: PT1 gives every object type's **intact** value, which is not
always `1.0`. PT6 gives the set of types that can be cleared at all. The
PT3 -> PT4 step kills three convoys and is the cleanest available test of
whether a candidate field is per-convoy or global.

## `samples/` — one convoy fight, frame by frame

Captured with `watch_saves.py` during a deliberately staged session. Frame
numbers are the capture order; `ptNNNN` is the in-game playtime in seconds, which
is what makes the ordering verifiable.

| frame | what had happened |
|---|---|
| `023_slot03_pt5113` | control: driving, interacting with non-mission NPCs |
| `030_slot03_pt5932` | control: end of the control stretch |
| `031_slot04_pt6015` | convoy route has appeared on the map, nothing engaged |
| `032_slot04_pt6112` | engaged, support cars being cleared |
| `033_slot04_pt6123` | leader still alive - **the last frame before the kill** |
| `034_slot04_pt6167` | **leader dead** |
| `036_slot04_pt6262` | artifact collected |

The pair to diff is `033` -> `034`. Frames `023` and `030` are the control
stretch to subtract. Reproducing the headline result:

```
python3 ../../tools/tail.py 033_slot04_pt6123.sav 034_slot04_pt6167.sav
python3 ../../tools/sec2.py 033_slot04_pt6123.sav 034_slot04_pt6167.sav
```

A scarecrow was also destroyed early in the control stretch, by accident. It is
left in deliberately — it is the reason the control subtraction has to happen,
and it makes a useful second signal.

## `field-map.csv`

222 record-stream ids that change somewhere across the PT1 -> PT6 ladder, with
their values at each stage. A starting point for anyone chasing story or mission
state; most of the file is the sliding `12 12 12 8 4 0 0` progress frontier
described in `../docs/FORMAT.md` section 5.
