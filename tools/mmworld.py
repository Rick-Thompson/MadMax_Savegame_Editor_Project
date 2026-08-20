#!/usr/bin/env python3
"""Mad Max world-object editor - restore or clear objects in bulk.

  mmworld.py SAVE.sav --status
  mmworld.py IN.sav OUT.sav --restore-type 45 [--slot N]
  mmworld.py IN.sav OUT.sav --restore-all    [--slot N]
  mmworld.py IN.sav OUT.sav --destroy-type 45 [--slot N]

Restoring sets the roster state (table 3) back to 1.0 AND flips cleared map
markers (table 1, 00 00) back to tracked (03 00). Both halves are required:
roster alone gives an object with no map marker, markers alone gives a marker
with no object.

Flipping every cleared marker is safe when restoring: an object that is still
intact was never flagged cleared, so only the ones being restored are affected.
Restoring a single type can leave a stale marker for other destroyed objects -
use --restore-all if you want the map to match exactly.
"""
import os, struct, sys, os, io, contextlib, importlib.util
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
def load(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    mod=importlib.util.module_from_spec(s); s.loader.exec_module(mod); return mod
m=load('madmax_save.py'); E=load('sec2edit.py')

def parts(p):
    d,h,head,s2=E.split(p); ts=E.tables(s2); r=E.roles(ts)
    return d,ts,r

def status(p):
    d,ts,r=parts(p)
    rows=[struct.unpack('<IIIfII',e) for e in ts[r['roster']]['ents']]
    mk=ts[r['markers']]['ents']
    print("%s\n  roster %d objects, %d destroyed"%(p,len(rows),sum(1 for x in rows if x[3]==0.0)))
    print("  markers %d  (%d tracked, %d cleared)"%(len(mk),
          sum(1 for e in mk if e[12:14]==b'\x03\x00'),sum(1 for e in mk if e[12:14]==b'\x00\x00')))
    print("\n  %-6s %-7s %-9s %s"%("type","total","destroyed",""))
    c=Counter(x[2] for x in rows); dz=Counter(x[2] for x in rows if x[3]==0.0)
    for t in sorted(c):
        bar='#'*int(20*dz[t]/c[t]) if c[t] else ''
        print("  %-6d %-7d %-9d %s"%(t,c[t],dz[t],bar))

def pristine(ref):
    """key -> intact state, taken from a reference save. The 'intact' value is
    NOT always 1.0 - convoys (type 53) sit at 3.0, other types use 6.0 etc.
    Restoring to a flat 1.0 would silently corrupt them."""
    d,ts,r=parts(ref)
    out={}
    for e in ts[r['roster']]['ents']:
        k,_,t,st,_,_=struct.unpack('<IIIfII',e)
        if st!=0.0: out[k]=st
    return out


def edit(inp,out,types,val,slot,do_markers,ref=None):
    d,ts,r=parts(inp)
    pri=pristine(ref) if ref else {}
    # fall back to the most common non-zero state per type within this save
    bytype={}
    for e in ts[r['roster']]['ents']:
        k,_,t,st,_,_=struct.unpack('<IIIfII',e)
        if st!=0.0: bytype.setdefault(t,Counter())[st]+=1
    sets=[];n=0
    for e in ts[r['roster']]['ents']:
        k,_,t,st,_,_=struct.unpack('<IIIfII',e)
        if types is not None and t not in types: continue
        # only flip the exact alive<->destroyed pair. Other types store health or
        # timers here (500.0, 1000.0, 6.0 ...) and must never be clobbered.
        if val==1.0:
            if st!=0.0: continue
            tgt=pri.get(k) or (bytype.get(t) and bytype[t].most_common(1)[0][0]) or 1.0
        else:
            tgt=0.0
            if st==0.0: continue
        nb=bytearray(e); struct.pack_into('<f',nb,12,tgt)
        sets.append(('roster','%08X'%k,bytes(nb).hex())); n+=1
    print("  roster: %d objects -> %s"%(n,'intact' if val else 'destroyed'))
    if val==1.0 and n:
        seen=Counter()
        for _,kk,hx in sets:
            if _=='roster': seen[struct.unpack_from('<f',bytes.fromhex(hx),12)[0]]+=1
        print("    restored states: %s"%dict(seen))
    if do_markers:
        want=b'\x03\x00' if val else b'\x00\x00'
        have=b'\x00\x00' if val else b'\x03\x00'
        mn=0
        for e in ts[r['markers']]['ents']:
            if e[12:14]!=have: continue
            k=struct.unpack_from('<I',e,0)[0]
            nb=bytearray(e); nb[12:14]=want
            sets.append(('markers','%08X'%k,bytes(nb).hex())); mn+=1
        print("  markers: %d -> %s"%(mn,'tracked' if val else 'cleared'))
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf): E.rebuild(inp,out,[],[],slot,sets)
    for line in buf.getvalue().splitlines():
        if 'payload' in line or 'wrote' in line: print(line)

if __name__=='__main__':
    a=sys.argv
    if '--status' in a: status(a[1]); sys.exit()
    inp,out=a[1],a[2]
    slot=int(a[a.index('--slot')+1]) if '--slot' in a else None
    ref=a[a.index('--ref')+1] if '--ref' in a else None
    if '--restore-all' in a: edit(inp,out,None,1.0,slot,True,ref)
    elif '--restore-type' in a: edit(inp,out,{int(a[a.index('--restore-type')+1])},1.0,slot,True,ref)
    elif '--destroy-type' in a: edit(inp,out,{int(a[a.index('--destroy-type')+1])},0.0,slot,False,ref)
    else: print(__doc__)
