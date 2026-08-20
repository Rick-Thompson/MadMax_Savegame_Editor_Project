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
"""
import os, struct, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _l(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    mod=importlib.util.module_from_spec(s); s.loader.exec_module(mod); return mod
m=_l('madmax_save.py'); se=_l('sec2edit.py')

ALIVE=3.0

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

if __name__=='__main__':
    a=sys.argv[1:]
    if a[0]=='list': cmd_list(a[1])
    elif a[0]=='revive':
        inp,out=a[1],a[2]
        g=lambda n:(int(a[a.index(n)+1],16) if n in a else None)
        s=(int(a[a.index('--slot')+1]) if '--slot' in a else None)
        cmd_revive(inp,out,g('--roster'),g('--misc'),s)
    else: sys.exit(__doc__)
