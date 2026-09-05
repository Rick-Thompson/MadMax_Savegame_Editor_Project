#!/usr/bin/env python3
"""Read/write the player resource stream in payload section 2.

Section 2's tail carries several `(u32 id, u32 size, value)` streams, the same
shape as section 1. One of them holds the player resources, ending in a fixed
four-record signature:

    u32 K          the id of the next record
    f32 1.0        at record id K
    f32 <scrap>    at record id K+1
    u8  1

**Record ids in this stream are positional, not stable.** Scrap is id 42 in one
save, 48 in another and 50 in a third - the stream grows as the playthrough does
and everything after the insertion point shifts. An earlier version of this tool
hard-coded "id 42 is scrap" and located the stream by an `id 42 / id 43` byte
anchor; that anchor simply fails to match on later saves, so it never wrote to
the wrong field, but it also could not edit them at all. Use the structural
locator instead.

  resource.py list  SAVE.sav              every stream found, with ids
  resource.py scrap SAVE.sav              read scrap
  resource.py scrap IN.sav OUT.sav VALUE  write scrap
  resource.py set   IN.sav OUT.sav ID=VALUE [...] [--slot N]
                                          edit by raw id in the resource stream;
                                          run `list` first, ids are per-save

Edits are applied to the mirror copy as well, and sizes are preserved, so the
integrity delta stays valid.
"""
import os, struct, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _load(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    mod=importlib.util.module_from_spec(s); s.loader.exec_module(mod); return mod
m=_load('madmax_save.py')

def find_streams(d,minrec=12):
    """Every `(u32 id, u32 size, value)` run in `d` that starts at id 0.

    Returns [(start_offset, {id: (value_offset, bytes)})]. Scans the raw buffer,
    so it finds the copies in the mirror as well as in the payload."""
    out=[]; o=0; L=len(d)
    while o+8<L:
        rid,sz=struct.unpack_from('<II',d,o)
        if rid==0 and sz in (1,2,4,8):
            p=o; last=-1; recs={}
            while p+8<=L:
                rid,sz=struct.unpack_from('<II',d,p)
                if sz>2048 or p+8+sz>L or rid<=last: break
                recs[rid]=(p+8,d[p+8:p+8+sz]); last=rid; p+=8+sz
            if len(recs)>=minrec: out.append((o,recs)); o=p; continue
        o+=1
    return out

def find_scrap(d):
    """-> [(offset, value, record_id)] for every copy of the scrap field.

    Matched on the raw bytes rather than by parsing the stream, because the
    stream can sit inside the byte range of a longer neighbour and get skipped.
    The tail of the resource stream is a fixed 45-byte shape whose only unknowns
    are the starting id k and the scrap value itself:

        u32 k    u32 4  u32 k+1      a record whose value is the next id
        u32 k+1  u32 4  f32 m        1.0 in most saves, 0.5 in one - a scalar
        u32 k+2  u32 4  f32 scrap
        u32 k+3  u32 1  u8  1
    """
    hits=[]; o=0; L=len(d)
    while o+45<=L:
        k,sz,v=struct.unpack_from('<III',d,o)
        if sz==4 and v==k+1:
            if (struct.unpack_from('<II',d,o+12)==(k+1,4)
                and struct.unpack_from('<II',d,o+24)==(k+2,4)
                and struct.unpack_from('<II',d,o+36)==(k+3,1) and d[o+44]==1):
                mul,=struct.unpack_from('<f',d,o+20)
                val,=struct.unpack_from('<f',d,o+32)
                if 0<mul<=16 and 0<=val<1e8: hits.append((o+32,val,k+2))
        o+=1
    return hits

def fmt(v):
    if len(v)==1: return "u8 %d"%v[0]
    if len(v)==2: return "u16 %d"%struct.unpack('<H',v)[0]
    if len(v)==4:
        u=struct.unpack('<I',v)[0]; f=struct.unpack('<f',v)[0]
        return "f32 %.2f"%f if 1e-4<abs(f)<1e9 else "u32 %d"%u
    if len(v)==8: return "u64 %d"%struct.unpack('<Q',v)[0]
    return "%dB"%len(v)

def cmd_list(path):
    d=m.load(path); ss=find_streams(d)
    sc={o for o,_,_ in find_scrap(d)}
    seen=set()
    for off,recs in ss:
        sig=tuple(sorted(recs))[:6]
        print("stream @0x%06X  %d records%s"%(off,len(recs),
              "   <- resource stream (scrap here)" if any(v[0] in sc for v in recs.values()) else ""))
        if len(recs)>120: print("   (%d records, not listed)"%len(recs)); continue
        for rid in sorted(recs):
            o,v=recs[rid]
            print("   id %-4d 0x%06X  %-18s %s"%(rid,o,fmt(v),"SCRAP" if o in sc else ""))
        print()

def cmd_scrap(a):
    if len(a)==1:
        for o,v,rid in find_scrap(m.load(a[0])):
            print("0x%06X  record id %-3d  scrap = %g"%(o,rid,v))
        return
    inp,out,val=a[0],a[1],float(a[2])
    d=bytearray(m.load(inp)); delta=m.delta_of(bytes(d))
    hits=find_scrap(bytes(d))
    if not hits: raise SystemExit("scrap field not found in %s"%inp)
    for o,v,rid in hits:
        struct.pack_into('<f',d,o,val)
        print("  0x%06X id %-3d  %g -> %g"%(o,rid,v,val))
    m.save(out,m.reseal(bytes(d),delta))
    print("wrote %s (%d bytes, delta %08X)"%(out,len(d),delta))

def cmd_set(a):
    inp,out=a[0],a[1]
    slot=int(a[a.index('--slot')+1]) if '--slot' in a else None
    edits=[x for x in a[2:] if '=' in x]
    d=bytearray(m.load(inp)); delta=m.delta_of(bytes(d))
    ss=find_streams(bytes(d))
    scoff={o for o,_,_ in find_scrap(bytes(d))}
    tgt=[r for _o,r in ss if any(v[0] in scoff for v in r.values())]
    if not tgt: raise SystemExit("resource stream not found in %s"%inp)
    for recs in tgt:                          # payload AND mirror
        for e in edits:
            k,val=e.split('='); rid=int(k)
            if rid not in recs: raise SystemExit("no id %d in the stream - run `list`"%rid)
            off,old=recs[rid]
            if   len(old)==4: new=struct.pack('<f',float(val))
            elif len(old)==1: new=bytes([int(val)])
            elif len(old)==2: new=struct.pack('<H',int(val))
            else: raise SystemExit("id %d is %dB, not editable here"%(rid,len(old)))
            d[off:off+len(new)]=new
            print("  0x%06X id %-4d %-16s -> %s"%(off,rid,fmt(old),fmt(new)))
    if slot is not None: d[0x48]=slot
    m.save(out,m.reseal(bytes(d),delta))
    print("wrote %s (%d bytes, delta %08X)"%(out,len(d),delta))

if __name__=='__main__':
    a=sys.argv[1:]
    if not a: sys.exit(__doc__)
    if   a[0]=='list'  and len(a)==2: cmd_list(a[1])
    elif a[0]=='scrap' and len(a) in (2,4): cmd_scrap(a[1:])
    elif a[0]=='set'   and len(a)>=4: cmd_set(a[1:])
    else: sys.exit(__doc__)
