# The game's own save and load code

`tools/xvm.py` disassembles Mad Max's XVM bytecode. A `.xvmc` is an ADF file
holding a `module` instance (`XvmFormatModule`, defined in the executable's
embedded type library) plus optional `debug_info` and `debug_strings`. When the
debug strings are present - and in Mad Max they always are - every global,
attribute and method reference disassembles to its **literal name**, not a hash.

Instructions are `u16`: `opcode = w & 0x1F`, `oparg = w >> 5`.

## What the save/load script actually says

`scripts/gameobjects/player_stats_gameplay_loadsave.xvmc`, in full:

```
function Load  args 2  locals 4  stack 4
    0    ldglob "playerstats"
    1    ldattr "GetPlayerStats"
    2    call 0
    3    stloc 2
    4    ldloc 0
    5    ldloc 1
    6    ldglob "scriptgo"
    7    ldattr "LoadGameObjectData"
    8    call 2
    9    stloc 3
    10   ldloc 3
    11   jz label_18
    12   ldloc 3
    13   ldfloat 0
    14   lditem
    15   ldloc 2
    16   stattr "ComboRecord"
    17   jmp label_18
  label_18:
    18   ret 0

function Save  args 2  locals 3  stack 5
    0    ldglob "playerstats"
    1    ldattr "GetPlayerStats"
    2    call 0
    3    stloc 2
    4    ldloc 0
    5    ldloc 1
    6    ldloc 2
    7    ldattr "ComboRecord"
    8    mklist 1
    9    ldglob "scriptgo"
    10   ldattr "SaveGameObjectData"
    11   call 3
    12   pop
    13   ret 0
```

The convention is plain: **`Save` builds an ordered list and hands it to
`scriptgo.SaveGameObjectData(self, ctx, list)`; `Load` gets the list back from
`LoadGameObjectData(self, ctx)` and assigns the items positionally.** That is
exactly the shape of the per-object records in the save.

## Why this is not the shortcut it looks like

Of 843 `.xvmc` scripts in the game, **two** mention `SaveGameObjectData`: the one
above, and `scriptgo.xvmc` itself. And `scriptgo` is a stub - every one of its 20
functions is a single `ret 0`:

```
function LoadGameObjectData  args 2  locals 2  stack 0
    0    ret 0
function SaveGameObjectData  args 3  locals 3  stack 0
    0    ret 0
```

Those are native bindings. The script layer declares the interface; the
implementation is C++ inside `MadMax.exe`.

So the scripting VM persists exactly one gameplay value - the player's combo
record - and everything else in the save file is written by native code. Reading
the save routines "in one shot" from the scripts is not available; the remaining
path there is disassembling the executable.

What the scripts *do* give, cheaply:

- a confirmed serialisation convention (ordered positional lists per object)
- the names of the native entry points to look for in a disassembler:
  `SaveGameObjectData`, `LoadGameObjectData`
- 843 scripts of readable gameplay logic with literal names throughout, which is
  a large naming corpus for [HASHES.md](HASHES.md)
