#!/usr/bin/env python3
"""Edit records in the section-3 property store, without changing file length.

  tailedit.py list  IN.sav [PREFIXHEX ...]
  tailedit.py edit  IN.sav OUT.sav [--set HASH=HEXVALUE] [--orphan HASH] [--slot N]

--set     replaces a record's value. The new value must be the SAME LENGTH as
          the old one, so the file length and the checksum delta stay valid.

--orphan  a length-preserving soft delete. The store is a flat array sorted by
          hash, so a record cannot be removed without changing the count field
          and the file length. Instead the record's hash is rewritten to
          (previous hash + 1), which keeps the array sorted and the length
          identical but makes the entry unreachable by name - the game will
          behave as if the property was never written.

          Only use this on records you know the game creates on demand.
          Orphaning something it expects to find can crash or reset progress.

Store header sits 32 bytes before the first record:
    u64 magic 0x4CF2625A, u32 arena size, u32 reserve, u32 0, u32 8,
    u32 record count, u32 0
Neither the count nor the arena size changes under --set or --orphan.
"""
import os, struct, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _l(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    mod=importlib.util.module_from_spec(s); s.loader.exec_module(mod); return mod
m=_l('madmax_save.py'); t=_l('tail.py')

MAGIC=0x4CF2625A

def records(path):
    """-> (decoded bytes, [(off, index, reclen, hash, vallen, value)])"""
    d=m.load(path); out=[]
    for st,en,r in t.streams(path):
        o=st
        while o<en:
            idx,rl=struct.unpack_from('<II',d,o)
            h,vl=struct.unpack_from('<QQ',d,o+8)
            out.append((o,idx,rl,h,vl,bytes(d[o+24:o+24+vl])))
            o+=8+rl
    return d,out

def cmd_list(path,prefixes):
    d,recs=records(path)
    hdr=None
    if recs:
        s=recs[0][0]
        f=struct.unpack_from('<8I',d,s-32)
        if f[0]==MAGIC: hdr=f
    print("%d records%s"%(len(recs)," (header count %d)"%hdr[6] if hdr else ""))
    for off,idx,rl,h,vl,v in recs:
        hx="%016X"%h
        if prefixes and not any(hx.lstrip('0').startswith(p.upper().lstrip('0')) for p in prefixes): continue
        print("  0x%06X  #%-6d %s  %s"%(off,idx,hx.lstrip('0').rjust(8,'0'),t.fmt(v)))

def cmd_edit(inp,out,sets,orphans,slot):
    d,recs=records(inp)
    d=bytearray(d); n=len(d)
    by={h:(i,r) for i,r in enumerate(recs) for h in (r[3],)}
    for hs,hexv in sets:
        h=int(hs,16)
        if h not in by: sys.exit("no record %08X"%h)
        i,(off,idx,rl,hh,vl,v)=by[h]; nv=bytes.fromhex(hexv)
        if len(nv)!=vl: sys.exit("record %08X holds %d bytes, got %d - length must match"%(h,vl,len(nv)))
        d[off+24:off+24+vl]=nv
        print("  set    %08X  %s -> %s"%(h,t.fmt(v),t.fmt(nv)))
    for hs in orphans:
        h=int(hs,16)
        if h not in by: sys.exit("no record %08X"%h)
        i,(off,idx,rl,hh,vl,v)=by[h]
        prev=recs[i-1][3] if i>0 else 0
        nxt=recs[i+1][3] if i+1<len(recs) else (1<<64)-1
        new=prev+1
        if not (prev<new<nxt): sys.exit("no free hash slot beside %08X - neighbours are adjacent"%h)
        struct.pack_into('<Q',d,off+8,new)
        print("  orphan %08X -> %016X  (was %s)"%(h,new,t.fmt(v)))
    if slot is not None: d[0x48]=slot
    body=bytes(d)
    if len(body)!=n: sys.exit("internal: length changed")
    m.save(out, m.reseal(body, m.delta_of(m.load(inp))))
    print("  wrote %s (%d bytes, unchanged)"%(out,len(body)))

if __name__=='__main__':
    a=sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0]=='list': cmd_list(a[1],a[2:])
    elif a[0]=='edit':
        sets=[];orph=[];slot=None;i=3
        while i<len(a):
            if a[i]=='--set': k,_,v=a[i+1].partition('='); sets.append((k,v)); i+=2
            elif a[i]=='--orphan': orph.append(a[i+1]); i+=2
            elif a[i]=='--slot': slot=int(a[i+1]); i+=2
            else: sys.exit("unknown arg "+a[i])
        cmd_edit(a[1],a[2],sets,orph,slot)
    else: sys.exit(__doc__)
