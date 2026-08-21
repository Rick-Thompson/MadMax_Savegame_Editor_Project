# The hashes

Every identifier in a save is a hash. A decoded payload contains **no strings at
all** - a scan of the 100% reference save turns up 61 printable runs of five or
more characters, all of them accidental. Object keys, marker keys, convoy keys
and property-store keys are all opaque numbers.

They are not opaque forever. Mad Max is an Avalanche Studios game, and Avalanche
key their runtime properties by a hash of the property name.

## The function

**Bob Jenkins `lookup3` / `hashlittle2`, taking the `c` word, seed 0.**

Not one-at-a-time. An earlier attempt here used Jenkins OAAT, matched nothing,
and that null result was nearly misread as "the strings must be somewhere else"
- the wrong function and the wrong corpus produce the same symptom, so pin the
function first.

Documented in two independent places:

- [Gibbed.JustCause3](https://github.com/gibbed/Gibbed.JustCause3) -
  `StringHelpers.HashJenkins`
- [kk49/DECA](https://github.com/kk49/deca) - `deca/hashes.py`, `hash32_func`

`tools/names.py` implements it and is checked against the canonical `lookup3.c`
test vectors:

```
hashlittle("", 0)                              = DEADBEEF
hashlittle("Four score and seven years ago", 0) = 17770551
hashlittle("Four score and seven years ago", 1) = CD628161
```

All three match, so the implementation is definitely `lookup3`. Whether *Mad
Max* uses it for save keys is a separate question - see below.

Avalanche also use 48- and 64-bit hashes (murmur3-128, upper or lower slice) for
other purposes. The property store holds a few keys above `2^32` which may be
those, or may be object ids rather than name hashes.

## What is named so far

One record, out of 3811 hashes across every keyed structure in a mid-game save:

```
E9BB5FD1  CPlayer
```

Corroborating detail: that record is 576 bytes, its value starts
`04 00 00 00 | 40 02 00 00 | 3a 00 00 00 | 3a 00 00 00 | d1 5f bb e9`, where
`0x240` is 576 - the record's own length - and the fifth word is the record's
own key. It is the only record in the store that embeds its key in its value.
It changes whenever the player moves. A 576-byte per-player blob called
`CPlayer` is exactly what it looks like.

**Treat it as strongly indicated rather than proven.** With a 583k-entry
dictionary against 2178 store keys, roughly 0.3 random collisions are expected,
so a single hit is not by itself evidence. The embedded key does not settle it
either - the game wrote both the key and the tag, so they would agree whether or
not the name is right. What makes it convincing is that the name, the size, the
contents and the change pattern all describe the same object.

## Why only one

The dictionary is built from the wrong corpus. `names.py harvest` reads the
executable and the gameplay DLLs - 398,623 unique identifier-looking strings -
plus whatever sits in plaintext inside the archives. That yields C++ symbol
names and debug strings, but the gameplay identifiers live in the archives, and
those are compressed.

Sampled 100 MB from the head of six `game*.arc` files:

| archive | NUL-delimited identifier strings |
|---|---|
| game0 | 13289 |
| game2, game6, game10 | 0 |
| game4 | 1 |
| game8 | 2 |

`game0.arc` is the audio archive and its event names are plaintext
(`camp_1410_sca6_max_escaping_camp_03`, `sm1030_conv02_10_chum`). Everything
else is opaque. Roughly 34 GB of archives would yield almost nothing more
without decompressing them.

One harvesting note worth keeping: inside an archive, only take strings with a
NUL on **both** sides. Compressed data throws off enormous numbers of
identifier-shaped byte runs - 863 MB of `game0.arc` gives 2.4 million junk
matches under a plain identifier regex and 6752 real ones under the
NUL-delimited one.

## The next step

Decompress the archives and harvest from the real game data. The `.tab`/`.arc`
pair is a standard Avalanche archive and the entries are AAF-compressed;
[DECA](https://github.com/kk49/deca) and the
[apex-resource-index](https://github.com/EonZeNx/apex-resource-index) tooling
handle this for Just Cause 3/4, and Mad Max is close enough in vintage to be
worth trying. RTPC blobs inside those archives carry `u32 nameHash` keys and
string values, so they are both a naming corpus and a second confirmation of the
hash function.

If that works, the whole project changes character. Naming the roster's 1520
keys turns the object type map from "type 45 is something destructible" into
labels, and naming the property store makes the convoy search a matter of
reading field names instead of diffing.
