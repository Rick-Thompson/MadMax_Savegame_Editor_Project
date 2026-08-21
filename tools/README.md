# Tools

Python 3, no dependencies. Every script finds `madmax_save.py` relative to its
own location, so keep them in the same directory; run them from anywhere.

`madmax_save.py` is the library the rest import — decode/encode, header parsing,
the record stream, and the integrity reseal.

## Inspecting

```
madmax_save.py info SAVE.sav         header: slot, playtime, timestamps, format gen
madmax_save.py verify SAVE.sav       integrity value: stored, computed, delta
madmax_save.py records SAVE.sav      list section-1 records by id
madmax_save.py rdiff A.sav B.sav     diff section-1 records by id
madmax_save.py peek / decode         raw access to the decoded payload

sec2.py A.sav B.sav                  map and diff the four section-2 tables
tail.py SAVE.sav                     locate the property store, count records
tail.py A.sav B.sav                  diff the property store by hash  <- start here

tailedit.py list IN.sav [PREFIX ...] list property records, with offsets
tailedit.py edit IN.sav OUT.sav --set HASH=HEX --orphan HASH [--slot N]
                                     --set replaces a value of the SAME length.
                                     --orphan is a length-preserving soft
                                     delete: the record's hash is rewritten to
                                     (previous hash + 1) so it stays sorted but
                                     nothing can look it up. Use only on
                                     records the game recreates on demand.
convoy.py list SAVE.sav              the 13 convoys: roster state + position row
mmworld.py SAVE.sav --status         what is destroyed, by object type
resource.py list SAVE.sav            the resource stream (scrap is id 42)
```

## Editing

All editing tools preserve file length and refuse the edit if they cannot.

```
mmworld.py IN OUT --restore-type 45 [--ref REF.sav] [--slot N]
mmworld.py IN OUT --restore-all [--slot N]
mmworld.py IN OUT --destroy-type 45 [--slot N]        for testing

mmrestore.py IN OUT --obj <roster key> --marker <tracking key> [--slot N]
convoy.py revive IN OUT --roster HEX [--misc HEX] [--slot N]
resource.py set IN OUT 42=50000 [--slot N]

sec2edit.py IN OUT [--set T:KEY:HEX] [--add T:HEX] [--del T:KEY] [--slot N]
madmax_save.py setrec IN OUT ID=HEX
madmax_save.py patch IN OUT OFFSET=HEX
```

`--ref` gives `mmworld.py` a reference save to read each type's true intact
value from. Without it, it falls back to the modal value, which is right for
most types and wrong for convoys.

`--slot N` rewrites the slot byte in the header so the file can be dropped into
a different slot.

## Analysis

```
watch_saves.py SAVEDIR OUTDIR       snapshot every distinct autosave
scan.py A.sav=161 B.sav=10000000    intersection value scan
revert_to.py BEFORE AFTER OUT       revert every parsed feature back to BEFORE
```

`watch_saves.py` must be run by hand in a terminal — it is a long-running poll
loop.

## A note on what is not here

Earlier iterations included tools that diffed the property store by its
sequential index rather than by hash. They produced hundreds of spurious
changes and were removed rather than kept as examples. If you write your own
analysis, key by hash. See `../docs/METHODOLOGY.md` section 3.
