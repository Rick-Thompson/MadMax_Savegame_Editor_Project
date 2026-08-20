#!/usr/bin/env python3
"""Mad Max save - the hash-named property store in the tail of section 2.

Record layout, repeating, sorted ascending by hash:

    u32 index      sequential (starts at 1, not 0)
    u32 reclen     = 16 + vallen
    u64 hash       stable name key - high 32 bits always zero
    u64 vallen
    u8  value[vallen]

Key records by HASH. The index shifts whenever a record is inserted, so
index-keyed diffs are worthless; hash-keyed diffs are stable.

  tail.py SAVE.sav            locate + count
  tail.py A.sav B.sav         diff by hash
"""
import os, struct, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _l(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    mod=importlib.util.module_from_spec(s); s.loader.exec_module(mod); return mod
m=_l('madmax_save.py')

def _walk(d,o,hi):
    out={}; li=None; lh=-1
    while o+24<=hi:
        idx,rl=struct.unpack_from('<II',d,o)
        if rl<16 or rl>1<<16 or o+8+rl>hi: break
        hh,vl=struct.unpack_from('<QQ',d,o+8)
        if hh>>32 or vl+16!=rl: break
        if (li is not None and idx!=li+1) or hh<=lh: break
        out[hh]=d[o+24:o+24+vl]; li=idx; lh=hh; o+=8+rl
    return out,o

def streams(path,minrec=30):
    """-> list of (start, end, {hash: value})"""
    d=m.load(path); h=m.header(d); lo=m.PAYLOAD_START; hi=lo+h['block_len']
    res=[]; o=lo
    while o<hi-24:
        rl,=struct.unpack_from('<I',d,o+4)
        if 16<=rl<=1<<16:
            hh,vl=struct.unpack_from('<QQ',d,o+8)
            if not hh>>32 and vl+16==rl:
                r,e=_walk(d,o,hi)
                if len(r)>=minrec:
                    res.append((o,e,r)); o=e; continue
        o+=1
    return res

def props(path):
    """Merge every hash-named stream into one dict."""
    out={}
    for s,e,r in streams(path): out.update(r)
    return out

def fmt(v):
    if v is None: return "-"
    if len(v)==0: return "(empty)"
    if len(v)==1: return "u8 %d"%v[0]
    if len(v)==2: return "u16 %d"%struct.unpack('<H',v)[0]
    if len(v)==4:
        u=struct.unpack('<I',v)[0]; f=struct.unpack('<f',v)[0]
        return "f32 %g"%f if 1e-6<abs(f)<1e9 else "u32 %d"%u
    if len(v)==8:
        a,b=struct.unpack('<II',v); return "2x %d,%d"%(a,b)
    if len(v)<=32: return "%dB %s"%(len(v),v.hex(' '))
    return "%dB %s.."%(len(v),v[:24].hex(' '))

if __name__=='__main__':
    if len(sys.argv)==2:
        for s,e,r in streams(sys.argv[1]):
            print("0x%06X..0x%06X  %d records"%(s,e,len(r)))
    else:
        A=props(sys.argv[1]); B=props(sys.argv[2])
        print("A %d recs   B %d recs"%(len(A),len(B)))
        add=sorted(set(B)-set(A)); rem=sorted(set(A)-set(B))
        mod=sorted(k for k in A if k in B and A[k]!=B[k])
        print("added=%d removed=%d modified=%d"%(len(add),len(rem),len(mod)))
        for t,ks in (('ADD',add),('DEL',rem),('MOD',mod)):
            for k in ks[:80]:
                print("  %-4s %08X  %s -> %s"%(t,k,fmt(A.get(k)),fmt(B.get(k))))
