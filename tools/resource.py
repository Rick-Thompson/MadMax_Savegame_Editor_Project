#!/usr/bin/env python3
"""Read/write the player resource record stream in payload section 2.

  resource.py list SAVE.sav
  resource.py set  IN.sav OUT.sav ID=VALUE [...] [--slot N]

Section 2's tail contains (u32 id, u32 size, value) streams just like section 1.
One of them holds the player resources; **id 42 is scrap, stored as f32**.

The stream is located by its id/size byte signature rather than a fixed offset,
because the offset moves as the payload grows. Values are written to the mirror
copy too, and sizes are preserved so the checksum delta stays valid.
"""
import os, re, struct, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _load(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    mod=importlib.util.module_from_spec(s); s.loader.exec_module(mod); return mod
m=_load('madmax_save.py')

# id 42 size 4, then 12 bytes later id 43 size 1 - a stable anchor
ANCHOR=re.compile(re.escape(bytes.fromhex('2a00000004000000'))+b'.{4}'+
                  re.escape(bytes.fromhex('2b00000001000000')), re.S)

def streams(d):
    """all offsets where the resource stream anchor appears (payload + mirror)"""
    return [mm.start() for mm in ANCHOR.finditer(d)]

def walk_back(d,anchor,limit=4096):
    """find the stream start: the earliest offset that walks cleanly to anchor"""
    best=anchor
    for s in range(max(0,anchor-limit),anchor,1):
        o=s; ok=False; last=-1; n=0
        while o+8<=anchor+16:
            rid,sz=struct.unpack_from('<II',d,o)
            if sz>2048 or o+8+sz>len(d) or rid<=last: break
            last=rid; n+=1
            if o==anchor: ok=True; break
            o+=8+sz
        if ok and n>=8: return s
    return best

def records(d,start,stop):
    o=start; out={}
    while o+8<=stop:
        rid,sz=struct.unpack_from('<II',d,o)
        if sz>2048 or o+8+sz>stop: break
        out[rid]=(o+8,d[o+8:o+8+sz]); o+=8+sz
    return out

def fmt(v):
    if len(v)==1: return "u8 %d"%v[0]
    if len(v)==2: return "u16 %d"%struct.unpack('<H',v)[0]
    if len(v)==4:
        u=struct.unpack('<I',v)[0]; f=struct.unpack('<f',v)[0]
        return "f32 %.2f"%f if 1e-4<abs(f)<1e9 else "u32 %d"%u
    if len(v)==8: return "u64 %d"%struct.unpack('<Q',v)[0]
    return "%dB"%len(v)

NAMES={42:'SCRAP'}

def main(a):
    if a[1]=='list':
        d=m.load(a[2]); ss=streams(d)
        print("resource stream found at %d offsets (payload + mirror): %s"%(
            len(ss),[hex(x) for x in ss]))
        if not ss: return
        st=walk_back(d,ss[0])
        for rid,(off,v) in sorted(records(d,st,ss[0]+64).items()):
            print("  id %-4d 0x%06X  %-18s %s"%(rid,off,fmt(v),NAMES.get(rid,'')))
        return
    inp,out=a[1+1],a[2+1] if a[1]=='set' else (a[1],a[2])
    inp,out=a[2],a[3]
    slot=int(a[a.index('--slot')+1]) if '--slot' in a else None
    edits=[x for x in a[4:] if '=' in x]
    d=bytearray(m.load(inp)); delta=m.delta_of(bytes(d))
    ss=streams(bytes(d))
    if not ss: raise SystemExit("resource stream not found")
    for anchor in ss:                       # payload AND mirror
        st=walk_back(bytes(d),anchor)
        recs=records(bytes(d),st,anchor+64)
        for e in edits:
            k,val=e.split('='); rid=int(k)
            if rid not in recs: raise SystemExit("no id %d in the stream"%rid)
            off,old=recs[rid]
            if len(old)==4:
                new=struct.pack('<f',float(val))
            elif len(old)==1: new=bytes([int(val)])
            elif len(old)==2: new=struct.pack('<H',int(val))
            else: raise SystemExit("id %d is %dB, not editable here"%(rid,len(old)))
            d[off:off+len(new)]=new
            print("  0x%06X id %-4d %-16s -> %s"%(off,rid,fmt(old),fmt(new)))
    if slot is not None: d[0x48]=slot
    m.save(out, m.reseal(bytes(d),delta))
    print("wrote %s (%d bytes, delta %08X)"%(out,len(d),delta))

main(sys.argv)
