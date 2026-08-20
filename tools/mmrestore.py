#!/usr/bin/env python3
"""Fully restore a destroyed world object.

  mmrestore.py IN.sav OUT.sav --obj T3KEY --marker T1KEY [--slot N]

Restoring needs BOTH halves (verified in game):
  table 3 (24B entries, the 1520-object roster) : f32 state 0.0 -> 1.0
      = the physical object.  Alone: object present, no map marker.
  table 1 (16B entries)                         : tail bytes 00 00 -> 03 00
      = the map / tracking status. Alone: marker present, no object.

Get both keys by diffing a save from before and after destroying the thing:
  sec2.py BEFORE.sav AFTER.sav
"""
import os, struct, sys, subprocess, importlib.util, os
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location('m', os.path.join(os.path.dirname(os.path.abspath(__file__)),'madmax_save.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
ed=importlib.util.spec_from_file_location('e', os.path.join(os.path.dirname(os.path.abspath(__file__)),'sec2edit.py'))
E=importlib.util.module_from_spec(ed); ed.loader.exec_module(E)

def main(a):
    inp,out=a[1],a[2]
    obj=marker=None; slot=None
    i=3
    while i<len(a):
        if a[i]=='--obj': obj=int(a[i+1],16); i+=2
        elif a[i]=='--marker': marker=int(a[i+1],16); i+=2
        elif a[i]=='--slot': slot=int(a[i+1]); i+=2
        else: i+=1
    d,h,head,s2=E.split(inp)
    ts=E.tables(s2)
    sets=[]
    if obj is not None:
        for e in ts[E.roles(ts)['roster']]['ents']:
            if struct.unpack_from('<I',e,0)[0]==obj:
                new=bytearray(e); struct.pack_into('<f',new,12,1.0)
                sets.append(('roster','%08X'%obj,bytes(new).hex()))
                print("  object  %08X : state %.1f -> 1.0"%(obj,struct.unpack_from('<f',e,12)[0]))
                break
        else: raise SystemExit("object key %08X not in table 3"%obj)
    if marker is not None:
        for e in ts[E.roles(ts)['markers']]['ents']:
            if struct.unpack_from('<I',e,0)[0]==marker:
                new=bytearray(e); new[12:14]=b'\x03\x00'
                sets.append(('markers','%08X'%marker,bytes(new).hex()))
                print("  marker  %08X : tail %s -> 03 00"%(marker,e[12:14].hex(' ')))
                break
        else: raise SystemExit("marker key %08X not in table 1"%marker)
    E.rebuild(inp,out,[],[],slot,sets)

if __name__=='__main__': main(sys.argv)
