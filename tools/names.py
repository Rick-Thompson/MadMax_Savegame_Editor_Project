#!/usr/bin/env python3
"""Recover names for the hashes in a save, by hashing strings out of the game binaries.

Mad Max runs on Avalanche's Apex engine, which keys runtime properties by a
32-bit Bob Jenkins lookup3 hash of the property name (the same `u32 nameHash`
used by the RTPC container format) - see jenkins() below for the exact variant. Saves contain no strings at all - every
identifier in them is one of these hashes - but the executable and the gameplay
DLLs are full of the source strings.

So: harvest every identifier-looking string from the binaries, hash them all,
and intersect with the hashes a save actually uses.

  names.py harvest OUT.txt FILE [FILE ...]  extract strings (resumable)
  names.py build   STRINGS.txt OUT.tsv     hash them -> hash<TAB>name
  names.py match   OUT.tsv SAVE.sav        report which save hashes are named
"""
import os, re, struct, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _l(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    mod=importlib.util.module_from_spec(s); s.loader.exec_module(mod); return mod

M32=0xFFFFFFFF
def _rot(x,k): return ((x<<k)|(x>>(32-k)))&M32
def _mix(a,b,c):
    a=(a-c)&M32; a^=_rot(c,4);  c=(c+b)&M32
    b=(b-a)&M32; b^=_rot(a,6);  a=(a+c)&M32
    c=(c-b)&M32; c^=_rot(b,8);  b=(b+a)&M32
    a=(a-c)&M32; a^=_rot(c,16); c=(c+b)&M32
    b=(b-a)&M32; b^=_rot(a,19); a=(a+c)&M32
    c=(c-b)&M32; c^=_rot(b,4);  b=(b+a)&M32
    return a,b,c
def _final(a,b,c):
    c^=b; c=(c-_rot(b,14))&M32
    a^=c; a=(a-_rot(c,11))&M32
    b^=a; b=(b-_rot(a,25))&M32
    c^=b; c=(c-_rot(b,16))&M32
    a^=c; a=(a-_rot(c,4))&M32
    b^=a; b=(b-_rot(a,14))&M32
    c^=b; c=(c-_rot(b,24))&M32
    return a,b,c

def jenkins(data, seed=0):
    """Avalanche's name hash: Bob Jenkins lookup3 hashlittle2, the `c` word.

    Confirmed against Gibbed.JustCause3 (HashJenkins) and kk49/DECA
    (hash32_func). NOT one-at-a-time - an earlier attempt here used OAAT and
    matched nothing, which is the expected result for the wrong function and is
    easy to mistake for the wrong string source."""
    n=len(data); a=b=c=(0xDEADBEEF+n+seed)&M32
    p=0; rem=n
    while rem>12:
        a=(a+int.from_bytes(data[p:p+4],'little'))&M32
        b=(b+int.from_bytes(data[p+4:p+8],'little'))&M32
        c=(c+int.from_bytes(data[p+8:p+12],'little'))&M32
        a,b,c=_mix(a,b,c); p+=12; rem-=12
    if rem==0: return c
    tail=data[p:p+rem]+b'\0'*(12-rem)
    a=(a+int.from_bytes(tail[0:4],'little'))&M32
    b=(b+int.from_bytes(tail[4:8],'little'))&M32
    c=(c+int.from_bytes(tail[8:12],'little'))&M32
    return _final(a,b,c)[2]

# Binaries: any identifier-looking run. Archives: only NUL-delimited runs -
# compressed data produces millions of false identifier matches, and requiring a
# NUL on both sides cuts one 863 MB archive from 2.4 million junk strings to
# 6752 real ones.
IDENT=re.compile(rb'[A-Za-z_][A-Za-z0-9_./\-]{2,63}')
NULSTR=re.compile(rb'\x00([A-Za-z_][A-Za-z0-9_./\\\-]{4,79})\x00')

def harvest(paths,out):
    """Append strings from each file to out. Skips files already recorded, so a
    long archive sweep can be run in batches."""
    seen=set(); done=set()
    if os.path.exists(out):
        for line in open(out,'rb').read().split(b'\n'):
            if line.startswith(b'#done '): done.add(line[6:].decode('latin1'))
            elif line: seen.add(line)
    added=0
    for f in paths:
        key=os.path.basename(f)
        if key in done: continue
        n=0
        with open(f,'rb') as fh:
            arc = f.endswith(('.arc','.tab','.shader_bundle'))
            pat = NULSTR if arc else IDENT
            grp = 1 if arc else 0
            carry=b''
            while True:
                b=fh.read(1<<24)
                if not b: break
                for m in pat.finditer(carry+b):
                    v=m.group(grp)
                    if v not in seen: seen.add(v); n+=1
                carry=b[-96:]
        done.add(key); added+=n
        print("  %-24s +%d" % (key,n))
    with open(out,'wb') as o:
        o.write(b'\n'.join(sorted(seen)))
        o.write(b'\n'+b'\n'.join(b'#done '+d.encode('latin1') for d in sorted(done))+b'\n')
    print("total %d strings, %d files done (+%d new)"%(len(seen),len(done),added))

def build(src,out):
    n=0
    with open(out,'w') as o:
        for line in open(src,'rb').read().split(b'\n'):
            if not line or line.startswith(b'#done '): continue
            for v in {line, line.lower()}:
                o.write("%08X\t%s\n"%(jenkins(v),v.decode('latin1'))); n+=1
    print("%d hashes -> %s"%(n,out))

def load(tsv):
    d={}
    for line in open(tsv):
        h,_,name=line.rstrip('\n').partition('\t')
        d.setdefault(int(h,16),set()).add(name)
    return d

def save_hashes(path):
    m=_l('madmax_save.py'); se=_l('sec2edit.py'); t=_l('tail.py')
    out={}
    _,_,head,s2=se.split(path); ts=se.tables(s2); roles=se.roles(ts)
    inv={v:k for k,v in roles.items()}
    for i,tb in enumerate(ts):
        out['table %d %s'%(i,inv.get(i,'?'))]={struct.unpack_from('<I',e,0)[0] for e in tb['ents']}
    out['property store']={h for h in t.props(path) if h<=M32}
    return out

def match(tsv,path):
    names=load(tsv); groups=save_hashes(path)
    print("dictionary: %d distinct hashes\n"%len(names))
    for g,hs in groups.items():
        hit={h for h in hs if h in names}
        print("%-22s %5d hashes, %4d named (%.1f%%)"%(g,len(hs),len(hit),100*len(hit)/max(1,len(hs))))
        for h in sorted(hit)[:12]:
            print("      %08X  %s"%(h,' | '.join(sorted(names[h]))[:90]))

if __name__=='__main__':
    a=sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0]=='harvest': harvest(a[2:],a[1])
    elif a[0]=='build': build(a[1],a[2])
    elif a[0]=='match': match(a[1],a[2])
    else: sys.exit(__doc__)
