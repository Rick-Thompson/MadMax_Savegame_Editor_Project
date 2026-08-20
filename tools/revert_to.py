#!/usr/bin/env python3
"""Revert every parsed feature of AFTER.sav back to BEFORE.sav, keeping all
other progress. Used to undo one event exactly, rather than guessing.

  revert_to.py AFTER.sav BEFORE.sav OUT.sav [--slot N] [--deltafrom FILE.sav]

Removing table rows changes the payload length, which invalidates the checksum
delta - so pass --deltafrom a known-good save of the resulting length.
"""
import struct, sys, os, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def load(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    mod=importlib.util.module_from_spec(s); s.loader.exec_module(mod); return mod
m=load('madmax_save.py'); E=load('sec2edit.py')

def main(a):
    after,before,out=a[1],a[2],a[3]
    slot=int(a[a.index('--slot')+1]) if '--slot' in a else None
    dsrc=a[a.index('--deltafrom')+1] if '--deltafrom' in a else after
    d,h,head,s2=E.split(after)
    ts=E.tables(s2); r=E.roles(ts)
    _,_,_,s2b=E.split(before); tb=E.tables(s2b); rb=E.roles(tb)
    for name in ('live','markers','roster'):
        ref={struct.unpack_from('<I',e,0)[0]:e for e in tb[rb[name]]['ents']}
        cur=ts[r[name]]['ents']
        keep=[]; removed=modified=0
        for e in cur:
            k=struct.unpack_from('<I',e,0)[0]
            if k not in ref:
                removed+=1; continue                    # appeared after -> drop
            if ref[k]!=e:
                keep.append(ref[k]); modified+=1        # changed after -> revert
            else:
                keep.append(e)
        addedback=[ref[k] for k in ref
                   if k not in {struct.unpack_from('<I',x,0)[0] for x in cur}]
        keep.extend(addedback)
        ts[r[name]]['ents']=keep
        print("  %-8s removed %d, reverted %d, restored %d"%(name,removed,modified,len(addedback)))
    # reassemble
    new=bytearray(); pos=0
    for t in ts:
        new+=s2[pos:t['off']]
        cnt=len(t['ents']); nb=cnt*t['esz']
        f=list(t['f']); f[0]+= nb-f[6]; f[4]=cnt; f[6]=nb
        new+=struct.pack('<7I',*f)
        for e in t['ents']: new+=e
        pos=t['off']+28+t['count']*t['esz']
    new+=s2[pos:]
    payload=head+bytes(new)
    hdr=bytearray(d[:m.PAYLOAD_START])
    struct.pack_into('<Q',hdr,0x10,m.PAYLOAD_START+len(payload))
    if slot is not None: hdr[0x48]=slot
    body=bytes(hdr)+payload+(payload if m.has_mirror(d) else b'')
    body+=b'\x00'*((-len(body))%512)
    if '--padto' in a:                      # pad with extra zero blocks to reach a
        target=int(a[a.index('--padto')+1]) # length whose checksum delta we know
        if target<len(body): raise SystemExit("--padto %d < natural %d"%(target,len(body)))
        if (target-len(body))%512: raise SystemExit("--padto must be a 512 multiple away")
        print("  padding %d -> %d with %d zero bytes"%(len(body),target,target-len(body)))
        body+=b'\x00'*(target-len(body))
    delta=m.delta_of(m.load(dsrc))
    print("  payload %d -> %d ; file %d -> %d ; delta %08X from %s"%(
        h['block_len'],len(payload),len(d),len(body),delta,os.path.basename(dsrc)))
    if len(body)!=len(m.load(dsrc)):
        raise SystemExit("length %d does not match the delta source (%d)"%(len(body),len(m.load(dsrc))))
    m.save(out, m.reseal(body,delta))
    print("  wrote",out)
main(sys.argv)
