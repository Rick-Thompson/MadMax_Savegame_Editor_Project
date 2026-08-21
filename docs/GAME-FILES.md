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

## The rest of the convoy set

All eleven graphs decode. Node-class inventories, which is most of the story:

| graph | lines | what it does |
|---|---|---|
| `convoy_choreographer` | 2438 | **the state machine** - `ConvoyDataGetWrecked`, `DatablockIntArrayInit`, `SpawnRequestDespawnOnDestroy`, `SpawnPriorityEnum` x4, `GameStateInRun`, `GetEconomyResourceId`, `FindObjectByAlias` |
| `convoy_wreck_handler` | 1868 | `GUIXSetConvoyRouteWrecked`, `GUIXSetConvoyRouteRelicCollected`, `RelicIsCollected` x2, `DatablockIntArraySize` x2 |
| `convoy_navigation_handler` | 200981 B | route following |
| `convoy_is_position_near_route` | 237 | `RoadGetNearestEdgeId`, `RoadPathCacheContainsEdgeId`, `RoadPathCacheInsideExtents` |
| `convoy_notify_gui_of_route` | 233 | `GUIXAddConvoyRoute`, `RoadBuildPathsForRoute` |
| `convoy_update_time_on_route` | 387 | accumulates a float against player distance |
| `hood_ornament_load` | 223 | `ObjectWithAliasExists`, `ExternalVariableDatablock` |
| `hood_ornament_ready_to_equip` | 140 | `RigidObjectMakeDynamic`, `CharacterDialogueMuteChildren` |
| `hood_ornament_unload_update_map_icon` | 296 | `MapIconSetPosition`, `FindByNameInObjectHierarchy` |
| `spawn_ids_update_prio_on_range` | 303 | `GetSpawnStatus`, `DatablockIntArrayIterate`, `DatablockIntArrayIterateRemove` |
| `convoy_spawner_mapicon_handler` | 381 | just the map icon |

**Spawning is driven by a datablock int array**, not by anything in the save we
have identified. `spawn_ids_update_prio_on_range` iterates an int array of spawn
ids out of a datablock, asks `GetSpawnStatus` for each, and adjusts priority by
range to the player - and `IterateRemove` takes entries *out* of that array. The
choreographer calls `DatablockIntArrayInit` and gates on `ConvoyDataGetWrecked`.

So the shape is: a runtime array of spawnable ids, initialised from convoy data,
with wrecked convoys removed. Whether that array is rebuilt from the save on
load, or persisted, is the question - and it is a question about a datablock, a
structure this project has not looked for at all.

## Pin names follow a convention, and it is recoverable

Graph pin names hash the same way as everything else. A short candidate sweep
resolved 22 of the 559 distinct unresolved hashes across the decoded graphs, and
the recovered names make the convention obvious - lowercase snake_case, `in_` /
`out_` prefixes:

```
C94BA74A x101  in                0A7C4A95  out_transform    05D54FDE  out_pos
75DD9B5C x5    relic_id          9585D45C  out_priority     13E69FE3  wrecked
BAFB74B7       convoy_data       E3E153A7  wreck_transform  8EA1E143  in_map_icon
1E8D41B7       out_size          AEAB5CF7  spawn_id         34076868  road_distance
```

The remaining 537 are a coverage problem over a combinatorial name space, not a
cryptographic one. See [HASHES.md](HASHES.md#brute-force-where-it-helps).

## A correction, and a useful negative

`RelicIsCollected` suggested an obvious hypothesis: the convoy will not come
back because its hood ornament was collected. Checking the save says otherwise.

Picking up an ornament flips exactly two property-store records from `0` to `1`:

```
700ABC4F   u32 0 -> 1
796FABD2   u32 0 -> 1
```

confirmed on two independent before/after pairs. In the snapshot series that
this project's convoy probes were built from, **both flags are `0` in every
frame, 031 through 037.** The ornament was never picked up in that session.

That corrects a note in this repo's earlier write-up, which described the
034 -> 036 transition as "the artifact pickup" - it was not. And it kills the
hypothesis: that convoy was wrecked with its relic still uncollected, and it
still did not respawn after six probes. Relic state is not the gate.

## global/convoys.bl - and the record six probes missed

`global/convoys.bl` is a **SARC** container (`tools/sarc.py`). Inside it, among
the convoy graphs and effects, sits `global/convoys.blo` - an **RTPC** file
(`tools/rtpc.py`), the Runtime Property Container format from the
[apex-resource-index](https://github.com/EonZeNx/apex-resource-index) patterns.

It decodes to 263 entities with literal names, and the class census is:

```
97 SGameObjectOrderedListEntry   28 CGraphScriptGameObject   14 CMapIcon
97 CNamedPoint                   28 CGameObjectOrderedList   14 CConvoyDataContainer
60 SEventTriggerComponent        14 CRoadPathCache           13 CTeleport
56 CTransformObject              14 CRoadMover               10 CScriptGameObject
50 CEventTrigger                 14 CEffectPointEmitter       1 CTimeTrigger
```

Every entity carries a `save` property. **Exactly 28 have `save = 1`**: the 14
`CConvoyDataContainer`s and the 14 `CMapIcon`s. Nothing else about a convoy is
persisted.

Each container also carries an **`objectid`** - and *all fourteen of those
objectids are keys in the save's property store*. Fourteen out of fourteen.
That is the bridge between the game data and the save file.

### The convoy state record

The record each objectid keys is 32 bytes:

```
f32 x4    orientation quaternion
f32 x3    position
u32       state
```

Across the snapshot series, for the convoy the player fought:

| frame | state | position |
|---|---|---|
| 031 before the route appeared | **0** | zero |
| 033 engaged, leader alive | **2** | zero |
| 034 leader killed | **3** | the wreck site |
| 037 later | **3** | the wreck site |

All thirteen other containers sit at state `0` with a zero position throughout.
So the encoding is `0` never encountered, `2` active, `3` wrecked - and
`ConvoyDataGetWrecked` in the choreographer reads exactly this.

**This is the record that governs the convoy, and no probe had touched it.**
It was in the diffs the whole time, keyed `7D6BB232`, and it was dismissed as
churn because it also moves during ordinary play - which of course it does, it
is a live position. Being noisy is not the same as being derived, and this
project treated the two as equivalent for six probes.

Probe 7 restores the roster to `3.0`, zeroes the table-2 position row, and sets
`7D6BB232` back to thirty-two zero bytes - a convoy that has never been met.
