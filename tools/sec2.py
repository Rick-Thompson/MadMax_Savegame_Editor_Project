#!/usr/bin/env python3
"""Map and diff the tables in payload section 2.
Each table: u32 size, u32, u32, const 4, u32 count, u32 one, u32 count*entsize
followed by `count` fixed-size entries. Entries are keyed by their first u32."""
import os, struct, sys, importlib.util
spec=importlib.util.spec_from_file_location('m', os.path.join(os.path.dirname(os.path.abspath(__file__)),'madmax_save.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def sec2(p):
    d=m.load(p); h=m.header(d)
    r=m.records(d); rend=max(r[i][1]+len(r[i][0]) for i in r)-m.PAYLOAD_START
    return d[m.PAYLOAD_START+rend:m.PAYLOAD_START+h['block_len']]

def tables(s):
    out=[];end=-1
    for o in range(0,len(s)-28):
        if o<end: continue
        f=struct.unpack_from('<7I',s,o)
        if f[3]!=4 or f[5]!=1: continue
        cnt,nb=f[4],f[6]
        if not cnt or not nb or nb>len(s)-o or nb%cnt or f[0]<nb: continue
        esz=nb//cnt
        if esz not in (4,8,12,16,20,24,28,32,48,64): continue
        ents=[s[o+28+k*esz:o+28+(k+1)*esz] for k in range(cnt)]
        out.append(dict(off=o,size=f[0],count=cnt,esz=esz,ents=ents)); end=o+28+nb
    return out

def keyed(t):
    d={}
    for e in t['ents']:
        d.setdefault(struct.unpack_from('<I',e,0)[0],[]).append(e)
    return d

def diff(pa,pb,label=''):
    A,B=tables(sec2(pa)),tables(sec2(pb))
    print("=== %s ==="%label)
    for i,(a,b) in enumerate(zip(A,B)):
        tag='' if a['count']==b['count'] else '   <<< %+d'%(b['count']-a['count'])
        print("table %d @%-6d entries=%-2dB  count %d -> %d%s"%(i,a['off'],a['esz'],a['count'],b['count'],tag))
        ka,kb=keyed(a),keyed(b)
        new=[k for k in kb if k not in ka]
        gone=[k for k in ka if k not in kb]
        mod=[k for k in ka if k in kb and ka[k]!=kb[k]]
        if new: print("     NEW keys (%d):"%len(new))
        for k in new:
            for e in kb[k]: print("        %08X  %s"%(k,e.hex(' ')))
        if gone: print("     GONE keys (%d):"%len(gone))
        for k in gone:
            for e in ka[k]: print("        %08X  %s"%(k,e.hex(' ')))
        if mod: print("     MODIFIED keys (%d):"%len(mod))
        for k in mod:
            print("        %08X  %s"%(k,ka[k][0].hex(' ')))
            print("        %8s  %s"%('',kb[k][0].hex(' ')))
    print()

if __name__=='__main__':
    diff(sys.argv[1],sys.argv[2],sys.argv[3] if len(sys.argv)>3 else '')
