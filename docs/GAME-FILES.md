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

All extract cleanly with `arcx.py`, and `tools/adf.py` now decodes them.

## Reading a graph script

```
adf.py typelib "<gamedir>/MadMax.exe" /tmp/typelib
adf.py dump convoy_wreck_handler.gsrc --names dict.tsv --lib /tmp/typelib/*.adf
```

Output is the real node graph:

```
GraphScript : GSGraph
  Nodes : A[GSNode][16]
    [0] : GSNode
      Class = 2188805253 (=CheckVariable)
      DataSet : GSDataSet
        Data : A[GSData][2]
          [0]: Operator = 16
        DataSets : A[GSDataSet][3]
          [0] Name = 3584055701 (=input_pins)
          [1] Name = 3048499994 (=output_pins)
              [0] Name = 706834940 (=true)
              [1] Name = 3855993015 (=false)
          [2] Name = 2681797045 (=variable_pins)
```

Three things had to be worked out that Gibbed's reader does not cover:

**The type library is inside `MadMax.exe`, not the archives.** A `.gsrc`
declares *zero* types and refers to them by hash. Nothing in the 27,501-path
file list is a type library, and no `.adf` extension exists at all. The
definitions are 40 ADF blobs compiled into the executable - 302 types between
them, including `GSGraph` (`63B4A6F9`), the root type of every graph script.
`adf.py typelib` pulls them out.

**Primitive types are implicit and follow a naming rule.** Gibbed hard-codes
four hashes with the names as comments (`uint8011`, `uint16022`, `uint32044`,
`uint64088`). Those are `lookup3(name + type + size + alignment)`, which
reproduces all four exactly and yields the rest for free - `int8011`,
`float044`, `double088`, `String588`.

**Enum type definitions carry members.** Gibbed's reader throws on anything but
Structure and Array, which is why one blob in the executable fails to load with
it. Enum entries are 12 bytes: `s64 nameIndex, s32 value`.

Also worth knowing: every offset inside an instance - including array offsets -
is relative to the instance start, not to the file.

## Everything in a graph is a hash, and the hashes resolve

Node classes, pin names and value types are all `lookup3` names, and the
dictionary from `names.py` resolves them. So the hash function *is* used
throughout the game data - it is specifically the save's keys that do not
follow it.

`convoy_wreck_handler.gsrc` decodes to 1868 lines and this node inventory:

| count | node class |
|---|---|
| 4 | TransformGetPos, SleepFrame, ExternalGraph, CompareVariable |
| 3 | ObjectGetTransform, ExternalVariableStringHash, ExternalVariableString |
| 2 | TimeLock, SendGlobalEvent, **RelicIsCollected**, ExternalVariableObject, ExternalVariableInt, DistanceBetweenPoints, Debug, DatablockIntArraySize |
| 1 | **GUIXSetConvoyRouteWrecked**, **GUIXSetConvoyRouteRelicCollected**, IsValidObject, GetPlayerCharacter, OrderedExecute, TransformRotateLocal, VariableObject, Return, Main |

`GUIXSetConvoyRouteWrecked` and `RelicIsCollected` are the two states the game
tracks per convoy route, and `DatablockIntArraySize` suggests the per-convoy
data is an int array in a datablock rather than anything we have found in the
save. That is the thread to pull next.

`convoy_spawner_mapicon_handler.gsrc` turns out to be exactly what its name
says - 16 nodes that position the map icon (`ObjectGetTransform`,
`ObjectSetTransform`, `SendGlobalEvent`). The spawn *decision* is not in it, so
the next files to read are `convoy_choreographer.gsrc` and whatever
`graphs/spawning/spawn_ids_update_prio_on_range.gsrc` leads to.
