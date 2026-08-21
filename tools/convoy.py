#!/usr/bin/env python3
"""Mad Max - convoy inspection / revival.

There are exactly 13 convoys and they appear in THREE places:

  roster (24B table)  key -> state   3.0 alive, 0.0 destroyed
  misc   (32B table)  key -> live world position, 13 fixed rows, one per convoy
                      all-zero until the convoy first spawns, frozen at the
                      wreck once it dies
  markers(16B table)  ~22 rows added over the course of the fight (derived)

The roster key and the misc key are DIFFERENT hashes for the same convoy.
Pair them by watching a live encounter: the misc row that goes from zeros to a
moving position is the convoy whose roster state later drops to 0.0.

  convoy.py list SAVE.sav
  convoy.py revive IN.sav OUT.sav --roster 593B2B20 [--misc 194895AE] [--slot N]
  convoy.py reset  IN.sav OUT.sav [--slot N] [--state S]   set ALL convoys to state S
                                                  (default 0 = unmet)

The authoritative record is none of the above three: it is the 32-byte blob the
property store keys by each convoy's **CConvoyDataContainer objectid**, taken
from global/convoys.blo (see docs/GAME-FILES.md).

    f32 x4  orientation      f32 x3  position      u32 state

    state 0  never encountered
    state 2  active
    state 3  wrecked

Verified two ways: in a snapshot series the fought convoy walks 0 -> 2 -> 3
while the other thirteen stay at 0, and in an unrelated 100% save thirteen of
the fourteen containers read state 3 with a wreck position each.

`reset` puts every convoy back to unmet - roster state to 3.0, the table-2
position row to zero, and the container record to 32 zero bytes.
"""
import os, struct, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _l(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    mod=importlib.util.module_from_spec(s); s.loader.exec_module(mod); return mod
m=_l('madmax_save.py'); se=_l('sec2edit.py')

ALIVE=3.0

# CConvoyDataContainer objectids, read out of global/convoys.blo with rtpc.py.
# Static game data, identical in every playthrough - all fourteen appear as
# property-store keys in every save examined.
CONTAINERS=[0x7E90E3F6,0x38A45D73,0x8F1728CD,0x59501178,0x7D6BB232,0x132E3492,0x42D456AE,
            0x7C5903DF,0x6FDA7EF0,0x337019D7,0x1FA21EA1,0xB6418D01,0x74C87945,0x35762FBA]

def view(path):
    d,h,head,s2=se.split(path); ts=se.tables(s2); r=se.roles(ts)
    ros=[(struct.unpack_from('<I',e,0)[0],struct.unpack_from('<f',e,12)[0])
         for e in ts[r['roster']]['ents'] if struct.unpack_from('<I',e,8)[0]==53]
    misc=[(struct.unpack_from('<I',e,0)[0],struct.unpack_from('<3f',e,8))
          for e in ts[r['misc']]['ents']]
    return ros,misc

def cmd_list(path):
    ros,misc=view(path)
    print("convoys in roster (type 53): %d"%len(ros))
    for k,s in ros: print("   %08X  %s"%(k,"ALIVE" if s==ALIVE else "destroyed (%g)"%s))
    print("misc rows (live positions): %d"%len(misc))
    for k,p in misc:
        print("   %08X  %s"%(k,"unspawned" if p==(0.0,0.0,0.0) else "(%.0f, %.0f, %.0f)"%p))

def cmd_revive(inp,out,rk,mk,slot):
    sets=[]
    d,h,head,s2=se.split(inp); ts=se.tables(s2); r=se.roles(ts)
    t=ts[r['roster']]
    ent=next((e for e in t['ents'] if struct.unpack_from('<I',e,0)[0]==rk),None)
    if ent is None: sys.exit("roster key %08X not found"%rk)
    if struct.unpack_from('<I',ent,8)[0]!=53:
        print("warning: %08X is type %d, not 53"%(rk,struct.unpack_from('<I',ent,8)[0]))
    new=bytearray(ent); struct.pack_into('<f',new,12,ALIVE)
    sets.append(('roster',rk,bytes(new)))
    if mk is not None:
        t=ts[r['misc']]
        ent=next((e for e in t['ents'] if struct.unpack_from('<I',e,0)[0]==mk),None)
        if ent is None: sys.exit("misc key %08X not found"%mk)
        new=bytearray(ent); new[8:32]=b'\0'*24
        sets.append(('misc',mk,bytes(new)))
    se.rebuild(inp,out,[],[],slot=slot,
               sets=[(a,"%08X"%b,c.hex()) for a,b,c in sets])
    for a,b,c in sets: print("set %s %08X -> %s"%(a,b,c.hex(' ')))

def cmd_reset(inp,out,slot,state=0):
    import tempfile
    te=_l('tailedit.py')
    d,h,head,s2=se.split(inp); ts=se.tables(s2); r=se.roles(ts)
    sets=[]
    n53=0
    for e in ts[r['roster']]['ents']:
        if struct.unpack_from('<I',e,8)[0]!=53: continue
        if struct.unpack_from('<f',e,12)[0]==ALIVE: continue
        new=bytearray(e); struct.pack_into('<f',new,12,ALIVE)
        sets.append(('roster',"%08X"%struct.unpack_from('<I',e,0)[0],bytes(new).hex())); n53+=1
    nmisc=0
    for e in ts[r['misc']]['ents']:
        if not any(e[8:32]): continue
        new=bytearray(e); new[8:32]=b'\0'*24
        sets.append(('misc',"%08X"%struct.unpack_from('<I',e,0)[0],bytes(new).hex())); nmisc+=1
    tmp=tempfile.mktemp(suffix='.sav')
    se.rebuild(inp,tmp,[],[],slot=slot,sets=sets)
    print("  roster: %d convoys set to %.1f ; table 2: %d position rows cleared"%(n53,ALIVE,nmisc))
    # now the container records, in place, same length
    orig=m.load(inp)
    d2,recs=te.records(tmp); d2=bytearray(d2)
    by={rr[3]:rr for rr in recs}
    n=0
    for k in CONTAINERS:
        rr=by.get(k)
        if rr is None: continue
        off,idx,rl,hh,vl,v=rr
        if vl!=32: print("  warning: %08X is %d bytes, expected 32 - skipped"%(k,vl)); continue
        new=bytearray(32); struct.pack_into('<I',new,28,state)
        if bytes(v)==bytes(new): continue
        d2[off+24:off+24+32]=bytes(new); n+=1
    print("  property store: %d container records set to state %d, position cleared"%(n,state))
    body=bytes(d2)
    if len(body)!=len(orig): sys.exit("length changed - refusing")
    m.save(out, m.reseal(body, m.delta_of(orig)))
    os.remove(tmp)
    print("  wrote %s (%d bytes)"%(out,len(body)))

if __name__=='__main__':
    a=sys.argv[1:]
    if a[0]=='list': cmd_list(a[1])
    elif a[0]=='reset':
        s=(int(a[a.index('--slot')+1]) if '--slot' in a else None)
        st=(int(a[a.index('--state')+1]) if '--state' in a else 0)
        cmd_reset(a[1],a[2],s,st)
    elif a[0]=='revive':
        inp,out=a[1],a[2]
        g=lambda n:(int(a[a.index(n)+1],16) if n in a else None)
        s=(int(a[a.index('--slot')+1]) if '--slot' in a else None)
        cmd_revive(inp,out,g('--roster'),g('--misc'),s)
    else: sys.exit(__doc__)
