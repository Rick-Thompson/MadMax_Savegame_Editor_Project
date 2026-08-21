#!/usr/bin/env python3
"""Print the layout of a save's payload and mark everything that does not parse.

Run this before concluding that a diff has covered a whole file. About 30% of a
mid-game payload does not parse as any known structure, split between two
regions, and an incomplete map is how a search ends up chasing the wrong bytes.

  mapsave.py SAVE.sav [SAVE.sav ...]
"""
import os, struct, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _l(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    mod=importlib.util.module_from_spec(s); s.loader.exec_module(mod); return mod
m=_l('madmax_save.py'); se=_l('sec2edit.py'); t=_l('tail.py')

REGION_A_MAGIC=0xF9715A12

def layout(path):
    d=m.load(path); h=m.header(d); lo=m.PAYLOAD_START; hi=lo+h['block_len']
    spans=[]
    r=m.records(d)
    spans.append((lo,max(r[i][1]+len(r[i][0]) for i in r),
                  'section 1 record stream (%d recs)'%len(r)))
    _,_,head,s2=se.split(path); base=lo+len(head)
    ts=se.tables(s2); roles=se.roles(ts); inv={v:k for k,v in roles.items()}
    for i,tb in enumerate(ts):
        a=base+tb['off']
        spans.append((a,a+28+tb['count']*tb['esz'],
                      'table %d %-8s esz=%-3d cnt=%d'%(i,inv.get(i,'?'),tb['esz'],tb['count'])))
    for st,en,rr in t.streams(path):
        spans.append((st-32,en,'section 3 property store (%d recs)'%len(rr)))
    return d,lo,hi,sorted(spans)

def describe_gap(d,a,b):
    if b-a<32: return ''
    magic,=struct.unpack_from('<I',d,a+4)
    if magic==REGION_A_MAGIC:
        n=d.count(bytes.fromhex('efbeadde'),a,b)
        return '  <- REGION A, entity arena, %d DEADBEEF slots'%n
    if b-a>4096:
        for o in range(a,min(a+256,b-8)):
            idx,sz=struct.unpack_from('<II',d,o)
            if idx<8 and 0<sz<=256:
                n=0; q=o; last=-1
                while q+8<=b:
                    i2,s2=struct.unpack_from('<II',d,q)
                    if s2>256 or q+8+s2>b or i2<=last: break
                    n+=1; last=i2; q+=8+s2
                if n>=32:
                    return '  <- REGION B, (id, size, value) streams, first at +0x%X'%(o-a)
    return ''

def main(path):
    d,lo,hi,spans=layout(path)
    print("%s\n  payload 0x%X..0x%X  %d bytes"%(os.path.basename(path),lo,hi,hi-lo))
    cur=lo; unk=0
    for a,b,lab in spans:
        if a>cur:
            print("  ?????? 0x%06X..0x%06X %8d  UNKNOWN%s"%(cur,a,a-cur,describe_gap(d,cur,a)))
            unk+=a-cur
        print("  known  0x%06X..0x%06X %8d  %s"%(a,b,b-a,lab)); cur=max(cur,b)
    if hi>cur:
        print("  ?????? 0x%06X..0x%06X %8d  UNKNOWN%s"%(cur,hi,hi-cur,describe_gap(d,cur,hi)))
        unk+=hi-cur
    print("  unmapped: %d bytes, %.0f%% of payload"%(unk,100*unk/(hi-lo)))

if __name__=='__main__':
    if len(sys.argv)<2: sys.exit(__doc__)
    for p in sys.argv[1:]: main(p)
