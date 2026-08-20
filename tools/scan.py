#!/usr/bin/env python3
"""Iterative value scan across Mad Max saves, like a memory scanner.

Usage:  scan.py SAVE1=VALUE1 SAVE2=VALUE2 [...]

Keeps only file offsets whose decoded value equals the stated number in EVERY
save. Two or three saves with different known values usually pin a field to a
single offset. Needed because the second payload section is rewritten heavily
on every save, so a plain diff of two saves is hopeless there.
"""
import os, struct, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location('m',os.path.join(HERE,'madmax_save.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def offsets_with(d, val, kinds=('u32','u16','f32','u8')):
    out=set()
    n=len(d)
    if 'u8'  in kinds and 0<=val<256:
        out|={(o,'u8') for o in range(n) if d[o]==val}
    if 'u16' in kinds and 0<=val<65536:
        out|={(o,'u16') for o in range(n-1) if struct.unpack_from('<H',d,o)[0]==val}
    if 'u32' in kinds:
        out|={(o,'u32') for o in range(n-3) if struct.unpack_from('<I',d,o)[0]==val}
    if 'f32' in kinds:
        out|={(o,'f32') for o in range(n-3)
              if abs(struct.unpack_from('<f',d,o)[0]-val)<0.01}
    return out

def main(argv):
    pairs=[a.rsplit('=',1) for a in argv[1:]]
    cand=None
    for path,val in pairs:
        d=m.load(path); v=float(val) if '.' in val else int(val)
        s=offsets_with(d,v)
        cand = s if cand is None else (cand & s)
        print(f"{path} = {val}: {len(s)} matches, {len(cand)} surviving")
    lens={len(m.load(p)) for p,_ in pairs}
    if len(lens)>1:
        print("\n!! files differ in length %s - fixed offsets will not align."%sorted(lens))
        print("   Take both saves standing still so the payload size stays put.")
    h=m.header(m.load(pairs[0][0]))
    recs=m.records(m.load(pairs[0][0]))
    rend=max((recs[i][1]+len(recs[i][0]) for i in recs), default=0)
    print(f"\n{len(cand)} candidate offsets:")
    for o,t in sorted(cand):
        where=('header' if o<m.PAYLOAD_START else
               'records' if o<rend else
               'section2' if o<m.PAYLOAD_START+h['block_len'] else 'mirror/pad')
        rid=''
        for i,(v_,off) in recs.items():
            if off<=o<off+len(v_): rid=f' (record id {i})'; break
        print(f"  0x{o:06X}  {t:<4} [{where}]{rid}")
    return cand

if __name__=='__main__':
    main(sys.argv)
