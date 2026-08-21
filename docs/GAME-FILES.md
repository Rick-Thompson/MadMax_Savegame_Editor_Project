# The game's own files

The save is not the only source of truth. Mad Max ships 32 GB of `.tab`/`.arc`
archives, and **[Gibbed.MadMax](https://github.com/gibbed/Gibbed.MadMax)** (Rick
Gibbed, 2017, zlib licence) is a full toolkit for them - published two years
after release and, until now, not connected to any work on the save format.

`data/gibbed/master.dirlist` is Gibbed's file list, 27,501 real paths,
redistributed here with his licence alongside it. It is the single most useful
external artefact for this project: it names things the save only hashes.

## Extracting a file

`tools/arcx.py` reads the archives directly - no .NET needed.

```
arcx.py find archives_win64 convoy_spawner_mapicon_handler.gsrc
  -> C5A20C40  game37.arc off=186791936 csz=1309 usz=6261

arcx.py get archives_win64 /tmp/out convoy_wreck_handler.gsrc
  -> 32101 bytes
```

Format, per Gibbed's `ArchiveTableFile.cs`:

```
.tab:  u32 alignment (0x0800)
       u32 chunkListCount
       chunkListCount x { u32 nameHash, u32 chunkCount,
                          chunkCount x { u32 uncompressedOffset, u32 compressedOffset } }
       entries to EOF:  { u32 nameHash, u32 offset, u32 compressedSize, u32 uncompressedSize }
```

Payloads are raw deflate (no zlib header) when the two sizes differ, stored when
they match, and deflated per chunk for entries that appear in the chunk table.
`nameHash` is `lookup3(basename)` - see [HASHES.md](HASHES.md).

## Counts that confirm the roster types

Cross-referencing per-type counts in the roster against the game's own file
names settles three of the unlabelled types and produces one strong hypothesis.

| roster type | count | file evidence | label |
|---|---|---|---|
| 53 | 13 | `hoodornaments_convoy_01` … `_13`, exactly 13 | **convoy** |
| 52 | 30 | 31 distinct `minefield_*` ids; the wiki says 30 minefields | **minefield** |
| 49 | 35 | 36 distinct `snNNNN` ids | **sniper** (already confirmed in game) |

The convoy count is a clean three-way agreement: 13 hood-ornament files, 13
roster entries of type 53, and 13 rows in the section-2 position table.

**Scarecrows probably span types 45-48.** The dirlist holds 97 distinct `scNNNN`
ids, and the four adjacent fully-cleared types sum to exactly that:

```
45 (34) + 46 (22) + 47 (23) + 48 (18) = 97
```

The game has four scarecrow sizes, and type 45 is the one confirmed in game. A
five-minute test settles it: destroy a scarecrow of a visibly different size and
see which type moves.

## The convoy graph scripts

The behaviour that has resisted six save-edit probes is implemented here:

```
graphs/convoys/convoy_spawner_mapicon_handler.gsrc   <- the spawner
graphs/convoys/convoy_choreographer.gsrc
graphs/convoys/convoy_wreck_handler.gsrc
graphs/convoys/convoy_navigation_handler.gsrc
graphs/convoys/convoy_is_position_near_route.gsrc
graphs/convoys/convoy_notify_gui_of_route.gsrc
graphs/convoys/convoy_update_time_on_route.gsrc
graphs/convoys/convoy_effect_interpolator.gsrc
graphs/convoys/hood_ornament_load.gsrc
graphs/convoys/hood_ornament_ready_to_equip.gsrc
graphs/convoys/hood_ornament_unload_update_map_icon.gsrc
scripts/gameobjects/player_stats_gameplay_loadsave.xvmc
```

All extract cleanly with `arcx.py`. They are ADF-encoded node graphs, so the
strings alone are thin - `convoy_wreck_handler.gsrc` yields `ConvoyData`,
`WRECK`, `STARTED`, `wrecked`, `Desapwned` (their typo) and
`savemanager_autosave`, which is suggestive but not a mechanism. Reading the
graph needs an ADF parser; `Gibbed.MadMax.ConvertAdf` is one, and the format is
documented in `Gibbed.MadMax.FileFormats/AdfFile.cs`.

`convoy_spawner_mapicon_handler.gsrc` is 6261 bytes and is where "already
instantiated" versus "never spawned" gets decided. That makes it the most direct
answer available to the question this project started with, and it needs no more
in-game experiments to read.
