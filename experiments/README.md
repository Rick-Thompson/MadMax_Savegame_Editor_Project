# Experiment log

Every in-game experiment run against a real save, and what it showed. Kept
because several of these were run twice before anyone realised the first result
was an artefact.

| # | setup | edit | result |
|---|---|---|---|
| 1 | fresh slot | XOR-decode, re-encode unchanged | loads - obfuscation confirmed |
| 2 | fresh slot | change one payload byte, naive checksum | **corrupt** - integrity value is real |
| 3 | fresh slot | delta-carry reseal | **loads** - workaround confirmed |
| 4 | mid-game | destroy 1 scarecrow in game, diff | one type-45 roster entry `1.0`->`0.0`, one tracking row added flagged `0000` |
| 5 | mid-game | destroy sniper tower in game, diff | one type 45 **and** one type 49 flip - 45 is the structure, 49 the sniper |
| 6 | mid-game | roster `1.0`, tracking untouched | object present, **no map marker** |
| 7 | mid-game | tracking flag only | marker present, **no object** |
| 8 | mid-game | both halves | **fully restored** |
| 9 | mid-game | destroy all 34 type-45 in save | all 34 gone in game - table structure confirmed |
| 10 | mid-game | restore all 34 | all 34 back |
| 11 | mid-game | delete an unrelated object's tracking rows | **an unrelated scarecrow also came back** - probes 2, 3 and the early "successes" were artefacts of row deletion |
| 12 | convoy cleared | roster -> `3.0` | value sticks across autosaves; **convoy still gone** |
| 13 | convoy cleared | roster + 9 kill rows deleted | still gone |
| 14 | convoy cleared | roster + all 22 encounter rows deleted | still gone; **game regenerated 18 of 22 rows** on next autosave |
| 15 | staged | kill leader first, then escorts | roster flips on the **leader**, escorts do nothing |
| 16 | staged | drive away and back | support cars respawn on unload - not per-vehicle tracking |
| 17 | scrap known 161 | intersection scan vs 10,000,000 | **scrap = record id 42, f32** |
| 18 | scrap edited | set 42, load, collect 1 scrap | value takes effect - the game re-reads on change |
| 19 | convoy cleared | roster -> `3.0` + table-2 position zeroed | **still gone** - last parseable structure ruled out |

## How to add to this

Include the before and after saves. Half the wrong turns above would have been
caught immediately if someone else had been able to re-run the diff.
