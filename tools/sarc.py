#!/usr/bin/env python3
"""Read SARC ('small archive') containers - Mad Max's .bl / .blo bundles.

Layout, from Gibbed.MadMax.FileFormats/SmallArchiveFile.cs:

    u32  headerSize   always 4
    char magic[4]     'SARC'
    u32  version      2
    u32  indexSize
    index, indexSize bytes, entries while more than 15 bytes remain:
         u32 nameLength, char name[nameLength], u32 offset, u32 size
    data

Offsets are absolute within the .bl file.

  sarc.py list  FILE.bl
  sarc.py get   FILE.bl OUTDIR [NAME ...]     all entries if no NAME given
"""
import os, struct, sys

def entries(path):
    d=open(path,'rb').read()
    hs,=struct.unpack_from('<I',d,0)
    if hs!=4 or d[4:8]!=b'SARC': raise ValueError("%s: not a SARC"%path)
    ver,isz=struct.unpack_from('<II',d,8)
    if ver!=2: raise ValueError("SARC version %d"%ver)
    out=[]; o=16; end=16+isz
    while end-o>15:
        n,=struct.unpack_from('<I',d,o); o+=4
        if n>256: break
        name=d[o:o+n].split(b'\0')[0].decode('latin1'); o+=n
        off,size=struct.unpack_from('<II',d,o); o+=8
        out.append((name,off,size))
    return d,out

if __name__=='__main__':
    a=sys.argv[1:]
    if len(a)<2: sys.exit(__doc__)
    d,ents=entries(a[1])
    if a[0]=='list':
        print("%s  %d entries"%(os.path.basename(a[1]),len(ents)))
        for n,o,s in ents: print("  %-64s %9d  %d bytes"%(n,o,s))
    elif a[0]=='get':
        out=a[2]; want=set(a[3:]); os.makedirs(out,exist_ok=True); n_=0
        for n,o,s in ents:
            if want and n not in want and os.path.basename(n) not in want: continue
            p=os.path.join(out,os.path.basename(n))
            open(p,'wb').write(d[o:o+s]); n_+=1
        print("extracted %d entries to %s"%(n_,out))
    else: sys.exit(__doc__)
