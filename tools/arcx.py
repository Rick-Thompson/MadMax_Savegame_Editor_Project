#!/usr/bin/env python3
"""Extract files from Mad Max's .tab/.arc archives by name.

The archive index is keyed by **jenkins(basename)** - the lookup3 hash of the
file's name only, not its path. That was worth pinning down: hashing the full
path matches 1 entry out of 44,149, hashing the basename matches 24,732.

.tab layout (Gibbed.MadMax, ArchiveTableFile.cs):
    u32 alignment (0x0800)
    u32 chunkListCount
    chunkListCount x { u32 nameHash, u32 chunkCount, chunkCount x {u32 uncompressedOffset, u32 compressedOffset} }
    entries until EOF: { u32 nameHash, u32 offset, u32 compressedSize, u32 uncompressedSize }

Payloads are raw deflate (no zlib header) when compressedSize != uncompressedSize,
stored otherwise. Entries listed in the chunk table are deflated per chunk.

  arcx.py find  ARCHIVEDIR NAME [NAME ...]      locate by name
  arcx.py get   ARCHIVEDIR OUTDIR NAME [...]    extract by name
"""
import os, struct, sys, zlib, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _l(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
N=_l('names.py')

def read_tab(path):
    d=open(path,'rb').read()
    align,ncl=struct.unpack_from('<II',d,0); o=8
    chunks={}
    for _ in range(ncl):
        nh,cc=struct.unpack_from('<II',d,o); o+=8
        chunks[nh]=[struct.unpack_from('<II',d,o+8*j) for j in range(cc)]
        o+=8*cc
    ents={}
    while o+16<=len(d):
        nh,off,cs,us=struct.unpack_from('<IIII',d,o); ents[nh]=(off,cs,us); o+=16
    return ents,chunks

def index(archdir):
    idx={}
    for f in sorted(os.listdir(archdir)):
        if not f.endswith('.tab'): continue
        arc=os.path.join(archdir,f[:-4]+'.arc')
        if not os.path.exists(arc): continue
        ents,chunks=read_tab(os.path.join(archdir,f))
        for nh,v in ents.items(): idx[nh]=(arc,v,chunks.get(nh))
    return idx

def extract(arc,info,chunk):
    off,cs,us=info
    with open(arc,'rb') as f:
        f.seek(off); raw=f.read(cs)
    if cs==us and not chunk: return raw
    if not chunk:
        return zlib.decompressobj(-15).decompress(raw,us)
    out=b''
    for i,(uoff,coff) in enumerate(chunk):
        nxt=chunk[i+1][0] if i+1<len(chunk) else us
        out+=zlib.decompressobj(-15).decompress(raw[coff:],nxt-uoff)
    return out

if __name__=='__main__':
    a=sys.argv[1:]
    if len(a)<3: sys.exit(__doc__)
    cmd=a[0]
    if cmd=='find':
        idx=index(a[1])
        for name in a[2:]:
            h=N.jenkins(name.encode())
            v=idx.get(h)
            print("%-50s %08X  %s"%(name,h,"%s off=%d csz=%d usz=%d%s"%(os.path.basename(v[0]),v[1][0],v[1][1],v[1][2]," chunked" if v[2] else "") if v else "NOT FOUND"))
    elif cmd=='get':
        idx=index(a[1]); os.makedirs(a[2],exist_ok=True)
        for name in a[3:]:
            h=N.jenkins(name.encode()); v=idx.get(h)
            if not v: print("%-50s NOT FOUND"%name); continue
            data=extract(v[0],v[1],v[2])
            p=os.path.join(a[2],name)
            open(p,'wb').write(data)
            print("%-50s %d bytes -> %s"%(name,len(data),p))
    else: sys.exit(__doc__)
