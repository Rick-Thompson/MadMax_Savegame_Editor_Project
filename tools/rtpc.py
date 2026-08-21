#!/usr/bin/env python3
"""Read RTPC (Runtime Property Container) files - Mad Max's .blo data.

Layout follows the RTPCv01 pattern from EonZeNx/apex-resource-index:

    header     char magic[4] = 'RTPC', u32 version = 1
    container  u32 nameHash, u32 offset, u16 propertyCount, u16 containerCount  (12 bytes)
               properties[propertyCount] @ offset
               containers[containerCount] @ align4(offset + 9 * propertyCount)
    property   u32 nameHash, u32 data, u8 variantType     (9 bytes)

`data` holds the value inline for u32/f32/bool, and is a file offset for
everything else. Arrays and strings are stored out of line; arrays are prefixed
by a u32 count.

Names are lookup3 hashes - pass `--names` from `names.py build` to resolve them.

  rtpc.py dump FILE.blo [--names D.tsv] [--depth N] [--grep TEXT]
"""
import os, struct, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _l(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
N=_l('names.py')

UNASSIGNED,U32,F32,STRING,VEC2,VEC3,VEC4,MAT3,MAT4,U32ARR,F32ARR,BYTES,DEPRECATED,OBJID,EVENTS=range(15)
VNAME={0:'none',1:'u32',2:'f32',3:'str',4:'vec2',5:'vec3',6:'vec4',7:'mat3x3',8:'mat4x4',
       9:'u32[]',10:'f32[]',11:'bytes',12:'deprecated',13:'objectid',14:'events'}
NAMES={}
def rn(h):
    v=NAMES.get(h)
    return sorted(v)[0] if v else "%08X"%h

class Rtpc:
    def __init__(self,path):
        d=open(path,'rb').read(); self.d=d
        if d[:4]!=b'RTPC': raise ValueError("%s: not RTPC"%path)
        self.version,=struct.unpack_from('<I',d,4)
        self.root=self._container(8)
    def _container(self,o):
        nh,off,npr,nco=struct.unpack_from('<IIHH',self.d,o)
        return dict(hash=nh,off=off,nprop=npr,ncont=nco)
    def props(self,c):
        out=[]
        for i in range(c['nprop']):
            o=c['off']+9*i
            nh,raw=struct.unpack_from('<II',self.d,o)
            vt=self.d[o+8]
            out.append((nh,vt,self.value(vt,raw)))
        return out
    def children(self,c):
        base=c['off']+9*c['nprop']
        base=(base+3)&~3
        return [self._container(base+12*i) for i in range(c["ncont"])]
    def value(self,vt,raw):
        d=self.d
        if vt==U32: return raw
        if vt==F32: return struct.unpack('<f',struct.pack('<I',raw))[0]
        if vt==STRING:
            e=d.index(b'\0',raw); return d[raw:e].decode('latin1')
        if vt in (VEC2,VEC3,VEC4):
            n={VEC2:2,VEC3:3,VEC4:4}[vt]
            return tuple(struct.unpack_from('<%df'%n,d,raw))
        if vt in (MAT3,MAT4):
            n=9 if vt==MAT3 else 16
            return tuple(struct.unpack_from('<%df'%n,d,raw))
        if vt in (U32ARR,F32ARR,BYTES):
            cnt,=struct.unpack_from('<I',d,raw)
            if vt==BYTES: return bytes(d[raw+4:raw+4+cnt])
            f='<%d%s'%(cnt,'I' if vt==U32ARR else 'f')
            return list(struct.unpack_from(f,d,raw+4))
        if vt==OBJID: return struct.unpack_from('<Q',d,raw)[0]
        if vt==EVENTS:
            cnt,=struct.unpack_from('<I',d,raw)
            return [struct.unpack_from('<II',d,raw+4+8*i) for i in range(cnt)]
        return raw

def fmt(v,vt):
    if isinstance(v,float): return "%g"%v
    if isinstance(v,bytes): return v[:24].hex(' ')+("..." if len(v)>24 else "")
    if isinstance(v,tuple): return "("+", ".join("%g"%x for x in v)+")"
    if isinstance(v,list):
        s=", ".join(("%g"%x if isinstance(x,float) else str(x)) for x in v[:12])
        return "[%s%s]"%(s,", ..." if len(v)>12 else "")
    if vt==U32 and isinstance(v,int) and v>0xFFFF:
        r=NAMES.get(v)
        if r: return "%d (=%s)"%(v,sorted(r)[0])
    return str(v)

def dump(r,c,depth,maxdepth,out,path=""):
    pad='  '*depth
    nm=rn(c['hash'])
    out.append("%s<%s>  %d props, %d children"%(pad,nm,c['nprop'],c['ncont']))
    for nh,vt,v in r.props(c):
        out.append("%s  %-28s %-8s %s"%(pad,rn(nh),VNAME.get(vt,vt),fmt(v,vt)))
    if depth>=maxdepth: 
        if c['ncont']: out.append("%s  ... %d children"%(pad,c['ncont']))
        return
    for ch in r.children(c): dump(r,ch,depth+1,maxdepth,out)

if __name__=='__main__':
    a=sys.argv[1:]
    if len(a)<2: sys.exit(__doc__)
    maxdepth=99; grep=None
    if '--names' in a:
        i=a.index('--names')
        for line in open(a[i+1]):
            h,_,n_=line.rstrip('\n').partition('\t')
            NAMES.setdefault(int(h,16),set()).add(n_)
        a=a[:i]+a[i+2:]
    if '--depth' in a:
        i=a.index('--depth'); maxdepth=int(a[i+1]); a=a[:i]+a[i+2:]
    if '--grep' in a:
        i=a.index('--grep'); grep=a[i+1]; a=a[:i]+a[i+2:]
    r=Rtpc(a[1]); out=[]
    dump(r,r.root,0,maxdepth,out)
    for line in out:
        if grep is None or grep.lower() in line.lower(): print(line)
