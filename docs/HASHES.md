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

Documented in three places, one of them Mad Max's own toolkit:

- **[Gibbed.MadMax](https://github.com/gibbed/Gibbed.MadMax)** -
  `Gibbed.MadMax.FileFormats/StringHelpers.cs`. Rick Gibbed's 2017 toolkit for
  this exact game. Its `HashJenkins` is lookup3, despite the bare name.
- [Gibbed.JustCause3](https://github.com/gibbed/Gibbed.JustCause3) - same function
- [kk49/DECA](https://github.com/kk49/deca) - `deca/hashes.py`, `hash32_func`

Two independent check values from DECA reproduce exactly:

```
lookup3("_class")      = 1473B179
lookup3("_class_hash") = D04059E6
```

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

## Where the hash is actually used: the archives

**The `.tab` archive index is keyed by `lookup3(basename)`** - the file's name
only, not its path. This is worth stating precisely because the difference is
stark:

| what is hashed | entries matched, out of 44,149 |
|---|---|
| full path (`graphs/convoys/convoy_choreographer.gsrc`) | 1 |
| path, lowercased | 1 |
| path with backslashes | 1 |
| **basename (`convoy_choreographer.gsrc`)** | **24,732** |

`tools/arcx.py` uses this to pull any file out of the game by name.

## Where it is *not* used: the save

**The save's keys are not lookup3 of any known name.** Tested against 101,426
candidates built from Gibbed's `master.dirlist` (27,501 real game paths, plus
basenames, stems and path tokens) and the class field namelists:

| structure | keys | named |
|---|---|---|
| table 0 live | 25 / 196 | 0 |
| table 1 markers | 14 / 832 | 0 |
| table 2 convoys | 13 | 0 |
| table 3 roster | 1520 | 0 |
| property store | 706 / 10706 | 0 |

Zero, in both the 0% and the 100% reference save. An independent run by another
model reached the same result from a different candidate set (58,995 strings),
and additionally swept Jenkins seeds 0-255 and tried FNV-1a, DJB2, SDBM, CRC-32
and Murmur3. Also zero.

### A retracted result

An earlier version of this file reported one name recovered:

```
E9BB5FD1  CPlayer
```

found by hashing 398,623 strings out of the game binaries. **Treat it as
withdrawn.** With a 583k-entry dictionary against 2178 keys, ~0.3 random
collisions are expected, so a single hit was never evidence - and now that a
much better corpus of 101,426 *real* game names produces exactly zero matches
across every keyed structure, the most likely reading is that the one hit was
the expected coincidence.

The supporting detail was weaker than it looked, too. That record does embed
its own key in its value, but the game wrote both fields, so they agree whether
or not the name is right. The record is still obviously the player object - 576
bytes, changes when you move. Its *name* is unknown.

So **"hash-named property store" is an assumption, not a finding.** The keys may
be a different hash, a hash of some string form not present in the file lists,
or engine-assigned object ids that were never names at all. Settling it probably
needs the disassembler that would also settle the integrity value.

## What the binaries do contain

`names.py harvest` reads the executable and the gameplay DLLs - 398,623 unique
identifier-looking strings - plus whatever sits in plaintext inside the
archives. Useful as a corpus, but it did not crack the save keys.


One harvesting note worth keeping: inside an archive, take only strings with a
NUL on **both** sides. Compressed data throws off enormous numbers of
identifier-shaped byte runs - 863 MB of `game0.arc` gives 2.4 million junk
matches under a plain identifier regex and 6752 real ones under the
NUL-delimited one. In practice this is now moot: `arcx.py` extracts real files,
which beats scraping compressed bytes.

## Next

The save-key scheme is open. Ways in, roughly in order of cost:

1. Extract and read `player_stats_gameplay_loadsave.xvmc` and the other
   `*_loadsave.xvmc` scripts (`arcx.py get` pulls them; they are XVM bytecode
   and `Gibbed.MadMax.XvmDisassemble` reads them). They are literally the game's
   save/load logic.
2. Convert the ADF files with `Gibbed.MadMax.ConvertAdf` - ADF carries a
   string-hash table, which is a naming corpus *and* a second confirmation of
   the hash.
3. Disassemble the executable around the save writer.
