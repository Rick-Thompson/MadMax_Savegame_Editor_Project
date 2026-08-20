#!/usr/bin/env python3
"""
madmax_save.py - inspect / decode / diff / patch Mad Max (2015, PC) save files.

Mad Max saves (GameSaveNN.sav, Settings.sav) are plain structured binary
XOR'd with a fixed 32-byte repeating key. This tool undoes that, parses the
header, and helps you find which bytes correspond to which bit of progress.

Save locations (PC):
  %USERPROFILE%\\Documents\\WB Games\\Mad Max\\Saves\\         (active)
  %USERPROFILE%\\Documents\\WB Games\\Mad Max\\Backup Saves\\  (backups)
  Steam\\userdata\\<SteamID3>\\234140\\                        (Steam Cloud copy)

File layout (little-endian):
  0x000 u32   CRC-32 of decoded[4:EOF], init BCEAC598, xorout 7B7AD18A
  0x004 u32   magic 0x33116F7F
  0x008 u64   size field A
  0x010 u64   payload end offset  (= PAYLOAD_START + block_len)
  0x018 u32   unix timestamp (playthrough created / older stamp)
  0x020 u32   unix timestamp (this save)
  0x028 u64   play time in seconds
  0x030 f64   unknown double
  0x038 u32   1
  0x03C u32   id / build stamp
  0x048 u8    save slot number (1..10)
  0x049 u8    save format version (2 = current build, 6 = older saves
              which use DIFFERENT crc parameters - do not reseal those)
  0x04C u16   year, u8 month, u8 day, u8 hour, u8 minute (local time)
  0x0F0       payload block, length = (val@0x10 - 0xF0)
  ...         optionally THE SAME PAYLOAD BLOCK AGAIN (mirror copy)
  ...         zero padding to a 512-byte boundary

When a mirror copy is present, every edit must be applied to both copies.
`patch` detects this and does it, then recomputes the checksum.

Usage:
  python3 madmax_save.py info    SAVE.sav
  python3 madmax_save.py decode  SAVE.sav OUT.bin
  python3 madmax_save.py encode  IN.bin  SAVE.sav
  python3 madmax_save.py diff    A.sav B.sav [--max 200] [--bits]
  python3 madmax_save.py patch   IN.sav OUT.sav OFFSET=HEXBYTES [more...]
  python3 madmax_save.py peek    SAVE.sav OFFSET [LENGTH]
  python3 madmax_save.py verify  SAVE.sav [more...]
  python3 madmax_save.py reseal  IN.sav OUT.sav
  python3 madmax_save.py records SAVE.sav [ID]
  python3 madmax_save.py rdiff   A.sav B.sav
  python3 madmax_save.py setrec  IN.sav OUT.sav ID=HEXBYTES [more...]
"""

import struct
import sys
import datetime
import zlib

KEY = bytes.fromhex(
    "ead5bad5eed5abeeba57abaaabbaabee" "ba75aa57aed5abeaba75ae75abab5dd5"
)
MAGIC = 0x33116F7F
PAYLOAD_START = 0xF0

# Integrity value at offset 0x00: CRC-32 (reflected IEEE, poly 0xEDB88320)
# over the DECODED bytes [4:EOF], with a non-standard init and final xor.
# Solved from four fresh saves + two Settings.sav across two machines.
CRC_INIT = 0xBCEAC598
CRC_XOROUT = 0x7B7AD18A
_M32 = 0xFFFFFFFF


def checksum(plain: bytes, delta: int = 0) -> int:
    """The value that belongs at offset 0x00 for this decoded file.

    `delta` handles the older v6 save format, whose CRC parameters are still
    unknown. Empirically its stored value differs from the v2 formula by an
    amount that depends ONLY on the file length - verified on files sharing a
    length but differing in 3064 payload bytes. Since editing bytes in place
    never changes the length, carrying the original file's delta across an edit
    produces a correct checksum without knowing the v6 parameters at all.
    """
    v = (zlib.crc32(plain[4:], CRC_INIT ^ _M32) ^ _M32) ^ CRC_XOROUT
    return (v ^ delta) & _M32


def delta_of(plain: bytes) -> int:
    """Format offset of a KNOWN-GOOD file. 0 for current-format (v2) saves."""
    return (struct.unpack_from("<I", plain, 0)[0] ^ checksum(plain)) & _M32


def reseal(plain: bytes, delta: int = 0) -> bytes:
    """Recompute and store the checksum. Call after ANY edit."""
    b = bytearray(plain)
    struct.pack_into("<I", b, 0, checksum(bytes(b), delta))
    return bytes(b)


def check(plain: bytes):
    """(stored, computed, ok)"""
    stored = struct.unpack_from("<I", plain, 0)[0]
    computed = checksum(plain)
    return stored, computed, stored == computed


# ---------------------------------------------------------------- codec
def xor(data: bytes) -> bytes:
    """Self-inverse: same call decodes and encodes."""
    k = KEY
    return bytes(b ^ k[i % 32] for i, b in enumerate(data))


def load(path: str) -> bytes:
    return xor(open(path, "rb").read())


def save(path: str, plain: bytes) -> None:
    open(path, "wb").write(xor(plain))


# ---------------------------------------------------------------- header
def header(d: bytes) -> dict:
    g = lambda fmt, off: struct.unpack_from(fmt, d, off)[0]
    h = {
        "unknown0": g("<I", 0x00),
        "magic": g("<I", 0x04),
        "size_a": g("<Q", 0x08),
        "payload_end": g("<Q", 0x10),
        "stamp_old": g("<I", 0x18),
        "stamp_save": g("<I", 0x20),
        "playtime_s": g("<Q", 0x28),
        "double30": g("<d", 0x30),
        "id3c": g("<I", 0x3C),
        "slot": d[0x48],
        "version": d[0x49],
        "date": tuple(struct.unpack_from("<HBBBB", d, 0x4C)),
        "file_len": len(d),
    }
    h["block_len"] = h["payload_end"] - PAYLOAD_START
    h["mirror_at"] = PAYLOAD_START + h["block_len"]
    return h


def has_mirror(d: bytes) -> bool:
    """Some saves store the payload block twice, some only once.

    Detect it rather than assume it: the file must be long enough AND the
    second copy must actually equal the first.
    """
    h = header(d)
    n, m = h["block_len"], h["mirror_at"]
    if len(d) < m + n:
        return False
    return d[PAYLOAD_START : PAYLOAD_START + n] == d[m : m + n]


def cmd_info(path):
    d = load(path)
    h = header(d)
    ok = "OK" if h["magic"] == MAGIC else "BAD (not a Mad Max save?)"
    y, mo, da, hh, mm = h["date"]
    print(f"{path}")
    print(f"  magic            0x{h['magic']:08X}  {ok}")
    print(f"  slot             {h['slot']}   format version {h['version']}")
    print(f"  saved            {y:04d}-{mo:02d}-{da:02d} {hh:02d}:{mm:02d} (local)")
    print(
        f"  save timestamp   {h['stamp_save']}  "
        f"{datetime.datetime.utcfromtimestamp(h['stamp_save'])} UTC"
    )
    print(
        f"  older timestamp  {h['stamp_old']}  "
        f"{datetime.datetime.utcfromtimestamp(h['stamp_old'])} UTC"
    )
    print(
        f"  play time        {h['playtime_s']} s "
        f"({h['playtime_s']/3600:.2f} h)"
    )
    print(f"  unknown @0x00    0x{h['unknown0']:08X}")
    print(f"  id @0x3C         0x{h['id3c']:08X}")
    print(f"  file length      {h['file_len']}")
    print(f"  payload block    0x{PAYLOAD_START:X} .. 0x{h['payload_end']:X}"
          f"  ({h['block_len']} bytes)")
    st, cp, ok = check(d)
    dl = delta_of(d)
    print(f"  checksum @0x00   stored {st:08X}  computed {cp:08X}  "
          + ("VALID (v2 format)" if ok
             else f"v{d[0x49]} format, delta {dl:08X}"))
    if has_mirror(d):
        print(f"  mirror copy at   0x{h['mirror_at']:X} (present, identical)")
    else:
        print(f"  mirror copy      none (single payload copy)")
    # player transform sits at the very start of the payload
    m = struct.unpack_from("<16f", d, PAYLOAD_START + 0x28)
    print(f"  likely player pos (x,y,z): {m[12]:.1f}, {m[13]:.1f}, {m[14]:.1f}")



# ---------------------------------------------------------------- records
# The first section of the payload is a flat stream of records:
#     u32 id, u32 size, value[size]
# starting at payload+0x20 and running for the length given at payload+0x18.
# Record ids are stable across saves, so diffing BY ID is immune to the payload
# growing (which shifts every byte offset and breaks a raw byte diff).
RECORDS_START = 0x20


def records(d: bytes):
    """{id: (value_bytes, absolute_file_offset_of_value)}"""
    h = header(d)
    p = d[PAYLOAD_START : PAYLOAD_START + h["block_len"]]
    out, o = {}, RECORDS_START
    while o + 8 <= len(p):
        rid, sz = struct.unpack_from("<II", p, o)
        if sz > len(p) - o - 8 or sz > 4096:
            break
        out[rid] = (p[o + 8 : o + 8 + sz], PAYLOAD_START + o + 8)
        o += 8 + sz
    return out


def fmt_value(v: bytes) -> str:
    if len(v) == 1:
        return f"u8 {v[0]}"
    if len(v) == 2:
        return f"u16 {struct.unpack('<H', v)[0]}"
    if len(v) == 4:
        u = struct.unpack("<I", v)[0]
        f = struct.unpack("<f", v)[0]
        return f"u32 {u}" + (f" / f32 {f:.4f}" if 1e-6 < abs(f) < 1e9 else "")
    if len(v) == 8:
        return f"u64 {struct.unpack('<Q', v)[0]}"
    return f"{len(v)}B {v[:16].hex(' ')}"


def cmd_records(path, want=None):
    d = load(path)
    r = records(d)
    print(f"{path}: {len(r)} records")
    for rid in sorted(r):
        if want is not None and rid != want:
            continue
        v, off = r[rid]
        print(f"  id {rid:-6d} (0x{rid:04X}) @0x{off:05X}  {fmt_value(v)}")


def cmd_rdiff(pa, pb):
    ra, rb = records(load(pa)), records(load(pb))
    ka, kb = set(ra), set(rb)
    print(f"A {pa}: {len(ra)} records")
    print(f"B {pb}: {len(rb)} records")
    if ka - kb or kb - ka:
        print(f"  ids only in A: {len(ka-kb)}   only in B: {len(kb-ka)}")
    ch = [k for k in sorted(ka & kb) if ra[k][0] != rb[k][0]]
    print(f"\n{len(ch)} changed records\n")
    for k in ch:
        print(f"  id {k:-6d} (0x{k:04X}) @0x{ra[k][1]:05X}  "
              f"{fmt_value(ra[k][0]):<28} -> {fmt_value(rb[k][0])}")


def cmd_setrec(src, dst, edits):
    plain = load(src)
    delta = delta_of(plain)
    d = bytearray(plain)
    h = header(d)
    n, mirror = h["block_len"], has_mirror(plain)
    r = records(plain)
    for e in edits:
        ids, hexv = e.split("=")
        rid = int(ids, 0)
        if rid not in r:
            raise SystemExit(f"no record with id {rid}")
        old, off = r[rid]
        blob = bytes.fromhex(hexv.replace(" ", ""))
        if len(blob) != len(old):
            raise SystemExit(f"id {rid} is {len(old)} bytes, got {len(blob)} "
                             "- record sizes must not change")
        d[off : off + len(blob)] = blob
        msg = f"  id {rid}: {fmt_value(old)} -> {fmt_value(blob)}"
        if mirror:
            d[off + n : off + n + len(blob)] = blob
            msg += "  (+mirror)"
        print(msg)
    save(dst, reseal(bytes(d), delta))
    print(f"wrote {dst}")


# ---------------------------------------------------------------- diff
def cmd_diff(pa, pb, max_runs=200, bits=False):
    a, b = load(pa), load(pb)
    ha, hb = header(a), header(b)
    print(f"A {pa}  block_len={ha['block_len']}  playtime={ha['playtime_s']}s")
    print(f"B {pb}  block_len={hb['block_len']}  playtime={hb['playtime_s']}s")
    if ha["block_len"] != hb["block_len"]:
        print("\n!! payload lengths differ - offsets will not line up.")
        print("   Diffing only works between two saves of the SAME playthrough")
        print("   made close together (the block grows as the world fills in).")
        return
    n = ha["block_len"]
    pa_, pb_ = (
        a[PAYLOAD_START : PAYLOAD_START + n],
        b[PAYLOAD_START : PAYLOAD_START + n],
    )
    runs, i = [], 0
    while i < n:
        if pa_[i] != pb_[i]:
            j = i
            while j < n and (pa_[j] != pb_[j] or any(
                pa_[k] != pb_[k] for k in range(j, min(j + 8, n))
            )):
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    print(f"\n{len(runs)} differing regions in the payload block\n")
    for (s, e) in runs[:max_runs]:
        off = PAYLOAD_START + s
        av, bv = pa_[s:e], pb_[s:e]
        line = f"payload+0x{s:06X}  file@0x{off:06X}  {e-s:4d}B"
        print(line)
        print(f"    A {av[:32].hex(' ')}")
        print(f"    B {bv[:32].hex(' ')}")
        if e - s <= 8:
            for fmt, name in (("<I", "u32"), ("<f", "f32")):
                if e - s >= struct.calcsize(fmt):
                    try:
                        x = struct.unpack_from(fmt, av, 0)[0]
                        y = struct.unpack_from(fmt, bv, 0)[0]
                        print(f"    {name}: {x!r} -> {y!r}")
                    except struct.error:
                        pass
        if bits:
            set_bits = [
                (s + k) * 8 + bit
                for k in range(e - s)
                for bit in range(8)
                if (~av[k] & bv[k]) >> bit & 1
            ]
            clr_bits = [
                (s + k) * 8 + bit
                for k in range(e - s)
                for bit in range(8)
                if (av[k] & ~bv[k]) >> bit & 1
            ]
            if set_bits:
                print(f"    bits 0->1: {set_bits[:24]}")
            if clr_bits:
                print(f"    bits 1->0: {clr_bits[:24]}")
        print()
    if len(runs) > max_runs:
        print(f"... {len(runs)-max_runs} more (raise --max)")


# ---------------------------------------------------------------- patch
def cmd_patch(src, dst, edits):
    src_plain = load(src)
    delta = delta_of(src_plain)          # 0 for v2; format offset for v6
    d = bytearray(src_plain)
    h = header(d)
    n = h["block_len"]
    mirror = has_mirror(d)
    for e in edits:
        off_s, hexbytes = e.split("=")
        off = int(off_s, 0)
        blob = bytes.fromhex(hexbytes.replace(" ", ""))
        d[off : off + len(blob)] = blob
        if PAYLOAD_START <= off < PAYLOAD_START + n and mirror:
            moff = off + n
            d[moff : moff + len(blob)] = blob
            print(f"  wrote {len(blob)}B at 0x{off:X} and mirror 0x{moff:X}")
        else:
            print(f"  wrote {len(blob)}B at 0x{off:X}")
    if len(d) != len(src_plain):
        raise SystemExit("refusing to write: edit changed the file length, "
                         "which invalidates the v6 delta")
    sealed = reseal(bytes(d), delta)
    save(dst, sealed)
    st = struct.unpack_from("<I", sealed, 0)[0]
    tag = "v2" if delta == 0 else f"v{d[0x49]} via delta {delta:08X}"
    print(f"  resealed: checksum {st:08X} ({tag})")
    print(f"wrote {dst}")


def cmd_peek(path, off, length=64):
    d = load(path)
    off, length = int(off, 0), int(length)
    for i in range(off, min(off + length, len(d)), 16):
        ch = d[i : i + 16]
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in ch)
        print(f"{i:08x}  {ch.hex(' '):<47}  |{txt}|")


# ---------------------------------------------------------------- main
def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "info":
        for p in argv[2:]:
            cmd_info(p)
            print()
    elif cmd == "decode":
        open(argv[3], "wb").write(load(argv[2]))
        print(f"decoded -> {argv[3]}")
    elif cmd == "encode":
        save(argv[3], open(argv[2], "rb").read())
        print(f"encoded -> {argv[3]}")
    elif cmd == "diff":
        rest = argv[4:]
        mx = 200
        if "--max" in rest:
            mx = int(rest[rest.index("--max") + 1])
        cmd_diff(argv[2], argv[3], mx, "--bits" in rest)
    elif cmd == "patch":
        cmd_patch(argv[2], argv[3], argv[4:])
    elif cmd == "records":
        cmd_records(argv[2], int(argv[3], 0) if len(argv) > 3 else None)
    elif cmd == "rdiff":
        cmd_rdiff(argv[2], argv[3])
    elif cmd == "setrec":
        cmd_setrec(argv[2], argv[3], argv[4:])
    elif cmd == "verify":
        for p_ in argv[2:]:
            d = load(p_)
            st, cp, ok = check(d)
            dl = delta_of(d)
            tag = "VALID v2" if ok else f"v{d[0x49]:<7d}"
            print(f"{tag:9s} stored={st:08X} computed={cp:08X} "
                  f"delta={dl:08X}  {p_}")
    elif cmd == "reseal":
        save(argv[3], reseal(load(argv[2])))
        print(f"resealed -> {argv[3]}")
    elif cmd == "peek":
        cmd_peek(argv[2], argv[3], argv[4] if len(argv) > 4 else 64)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
