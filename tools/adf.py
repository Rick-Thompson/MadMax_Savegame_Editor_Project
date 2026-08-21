#!/usr/bin/env python3
"""Reader for Avalanche ADF files (Mad Max .gsrc, .adf, and friends).

Ported from Gibbed.MadMax.FileFormats/AdfFile.cs and Gibbed.MadMax.ConvertAdf,
with the primitive type table derived rather than hard-coded.

An ADF file is a small relocatable heap plus metadata describing how to read it:

    header        magic 'ADF ' (bytes 20 46 44 41), version 4, then counts and
                  offsets for instances, type definitions and the name table,
                  then a NUL-terminated comment
    name table    u8 length per name, then the names, each NUL-terminated
    type defs     Structure and Array definitions, keyed by a name hash
    instances     { nameHash, typeHash, offset, size, nameIndex }

**Type definitions are often in a different file.** A .gsrc typically declares
zero types and refers to a shared library by hash, which is why `dump` takes
`--lib`. Feed it any ADF that defines the types you need; `types` lists what a
file provides.

Primitive types are never defined in-file - they are implicit, keyed by
`lookup3(name + type + size + alignment)`:

    uint8011 -> 0CA2821D    int8011  -> 580D0A62    float044  -> 7515A207
    uint16022-> 86D152BD    int16022 -> D13FCF93    double088 -> C609F663
    uint32044-> 075E4E4F    int32044 -> 192FE633    String588 -> 8955583E
    uint64088-> A139E01F    int64088 -> AF41354F

The first four are the ones Gibbed hard-codes; reproducing them from the naming
rule confirms the rule, and the rest follow from it.

  adf.py typelib MADMAX.EXE OUTDIR    pull the embedded type library out of the exe
  adf.py info FILE [...]              header, counts, comment
  adf.py types FILE [...]             type definitions a file provides
  adf.py dump FILE [--names D.tsv] [--lib L ...]

**Where the type library lives:** not in the archives - it is compiled into
`MadMax.exe` as 40 embedded ADF blobs, 302 type definitions between them,
including `GSGraph` (63B4A6F9), the root type of every .gsrc. `adf.py typelib`
extracts them.

Everything inside a graph is a `lookup3` hash - node classes, pin names, value
types. Pass `--names` a `hash<TAB>name` file from `names.py build` and they are
resolved inline.
"""
import os, struct, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _l(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
N=_l('names.py')

MAGIC=0x41444620
PRIM={}
for _n,_t,_s,_a in [('uint8',0,1,1),('uint16',0,2,2),('uint32',0,4,4),('uint64',0,8,8),
                    ('int8',0,1,1),('int16',0,2,2),('int32',0,4,4),('int64',0,8,8),
                    ('float',0,4,4),('double',0,8,8)]:
    PRIM[N.jenkins(("%s%d%d%d"%(_n,_t,_s,_a)).encode())]=(_n,_s)
STRING_HASH=N.jenkins(b'String588')

NAMES={}

def resolve(h):
    v=NAMES.get(h)
    return sorted(v)[0] if v else None

STRUCTURE,POINTER,ARRAY,INLINE_ARRAY,STRING,BITFIELD,ENUM,STRINGHASH=1,2,3,4,5,7,8,9
TYPENAME={0:'primitive',1:'struct',2:'pointer',3:'array',4:'inline-array',
          5:'string',7:'bitfield',8:'enum',9:'string-hash'}

class Adf:
    def __init__(self,path):
        d=open(path,'rb').read(); self.data=d; self.path=path
        if struct.unpack_from('<I',d,0)[0]!=MAGIC:
            raise ValueError("%s: not an ADF file"%path)
        f=struct.unpack_from('<15I',d,4)
        (self.version,self.ninst,self.oinst,self.ntype,self.otype,
         self.nunk,self.ounk,self.nname,self.oname,self.total)=f[:10]
        if self.version!=4: raise ValueError("ADF version %d not supported"%self.version)
        end=d.index(b'\0',0x40)
        self.comment=d[0x40:end].decode('latin1')
        self.names=self._names()
        self.types=self._types()
        self.instances=self._instances()

    def _names(self):
        if not self.nname: return []
        d=self.data; o=self.oname
        lens=list(d[o:o+self.nname]); o+=self.nname; out=[]
        for L in lens:
            out.append(d[o:o+L].decode('latin1')); o+=L+1
        return out

    def _nm(self,i):
        return self.names[i] if 0<=i<len(self.names) else "<%d>"%i

    def _types(self):
        out={}; o=self.otype
        for _ in range(self.ntype):
            typ,size,align,nh=struct.unpack_from('<IIII',self.data,o)
            ni,=struct.unpack_from('<q',self.data,o+16)
            flags,eth,elen=struct.unpack_from('<III',self.data,o+24); o+=36
            t=dict(type=typ,size=size,align=align,hash=nh,name=self._nm(ni),
                   flags=flags,elem=eth,elen=elen,members=[])
            cnt,=struct.unpack_from('<I',self.data,o); o+=4
            if typ==STRUCTURE:
                for _m in range(cnt):
                    mi,=struct.unpack_from('<q',self.data,o)
                    th,msz=struct.unpack_from('<II',self.data,o+8)
                    moff,=struct.unpack_from('<q',self.data,o+16)
                    u14,u18=struct.unpack_from('<II',self.data,o+24); o+=32
                    t['members'].append(dict(name=self._nm(mi),type=th,size=msz,
                                             offset=moff,u14=u14,u18=u18))
            elif typ==ARRAY:
                if cnt: raise ValueError("array type with %d members"%cnt)
            elif typ==ENUM:
                # 12 bytes per entry: s64 nameIndex, s32 value
                for _m in range(cnt):
                    ei,=struct.unpack_from('<q',self.data,o)
                    ev,=struct.unpack_from('<i',self.data,o+8); o+=12
                    t['members'].append(dict(name=self._nm(ei),value=ev))
            else:
                t['unparsed_members']=cnt
                if cnt: raise ValueError("type %s (%s) carries %d members - layout unknown, "
                                         "cannot continue"%(TYPENAME.get(typ,typ),t['name'],cnt))
            out[nh]=t
        return out

    def _instances(self):
        out=[]; o=self.oinst
        for _ in range(self.ninst):
            nh,th,off,size=struct.unpack_from('<IIII',self.data,o)
            ni,=struct.unpack_from('<q',self.data,o+16); o+=24
            out.append(dict(hash=nh,type=th,offset=off,size=size,name=self._nm(ni)))
        return out

def render(adf,lib,inst,maxdepth=64):
    """-> list of output lines for one instance.

    Instance data is addressed as its own buffer: every offset inside it,
    including array offsets, is relative to the instance start, not the file."""
    d=adf.data[inst['offset']:inst['offset']+inst['size']]; out=[]
    def prim(th,o):
        if th in PRIM:
            n,sz=PRIM[th]
            fmt={('uint8',1):'<B',('int8',1):'<b',('uint16',2):'<H',('int16',2):'<h',
                 ('uint32',4):'<I',('int32',4):'<i',('uint64',8):'<Q',('int64',8):'<q',
                 ('float',4):'<f',('double',8):'<d'}[(n,sz)]
            v=struct.unpack_from(fmt,d,o)[0]
            return ("%g"%v) if n in ('float','double') else str(v)
        return None
    def gsdata(t,base,label):
        f={m['name']:m for m in t['members']}
        def u32(n):
            m=f.get(n)
            return struct.unpack_from('<I',d,base+m['offset'])[0] if m else None
        nm=u32('Name'); ty=u32('Type'); ref=u32('Reference')
        av=f.get('Value')
        val='?'
        if av is not None:
            aoff,acnt=struct.unpack_from('<qq',d,base+av['offset'])
            raw=d[aoff:aoff+acnt]
            tn=resolve(ty) or ''
            if   tn=='uint32' and acnt>=4: val=str(struct.unpack_from('<I',raw,0)[0])
            elif tn=='int'    and acnt>=4: val=str(struct.unpack_from('<i',raw,0)[0])
            elif tn=='float'  and acnt>=4:
                u=struct.unpack_from('<I',raw,0)[0]
                # graphs declare pin metadata as float but store small ints in it;
                # anything below the smallest normal float is an integer, not a value
                val=str(u) if u<0x00800000 else "%g"%struct.unpack_from('<f',raw,0)[0]
            elif tn=='bool'   and acnt>=1: val=str(bool(raw[0])).lower()
            elif tn in ('string','String'): val=repr(raw.split(b'\0')[0].decode('latin1'))
            elif acnt==4:
                u=struct.unpack_from('<I',raw,0)[0]
                val="%d"%u if u<1<<24 else "%08X%s"%(u," (=%s)"%resolve(u) if resolve(u) else "")
            else: val=raw[:24].hex(' ')+("..." if acnt>24 else "")
        return "%s: %s = %s%s"%(label, resolve(nm) or "%08X"%nm, val,
                                "" if not ref else "  ref=%08X"%ref)

    def walk(th,o,indent,label):
        pad='  '*indent
        p=prim(th,o)
        if p is not None:
            n=None
            if PRIM.get(th,('',0))[0]=='uint32':
                n=resolve(struct.unpack_from('<I',d,o)[0])
            out.append("%s%s = %s%s"%(pad,label,p," (=%s)"%n if n else "")); return
        t=lib.get(th)
        if t is None:
            out.append("%s%s : <unknown type %08X>"%(pad,label,th)); return
        k=t['type']
        if k==STRUCTURE and t['name']=='GSData':
            out.append("%s%s"%(pad,gsdata(t,o,label))); return
        if k==STRUCTURE:
            out.append("%s%s : %s"%(pad,label,t['name'] or "struct"))
            if indent>maxdepth: out.append("%s  ..."%pad); return
            for m in t['members']:
                walk(m['type'],o+m['offset'],indent+1,m['name'])
        elif k==ARRAY:
            aoff,acnt=struct.unpack_from('<qq',d,o)
            et=lib.get(t['elem']); esz=(PRIM[t['elem']][1] if t['elem'] in PRIM
                                        else (et['size'] if et else 0))
            out.append("%s%s : %s[%d]"%(pad,label,t['name'] or "array",acnt))
            if not esz or indent>maxdepth: return
            for i in range(min(acnt,512)):
                walk(t['elem'],aoff+i*esz,indent+1,"[%d]"%i)
            if acnt>512: out.append("%s  ... %d more"%(pad,acnt-512))
        elif k==STRING:
            soff,=struct.unpack_from('<q',d,o)
            e=d.index(b'\0',soff)
            out.append("%s%s = %r"%(pad,label,d[soff:e].decode('latin1')))
        elif k==STRINGHASH:
            out.append("%s%s = hash %08X"%(pad,label,struct.unpack_from('<I',d,o)[0]))
        elif k==INLINE_ARRAY:
            out.append("%s%s : inline[%d]"%(pad,label,t['elen']))
            esz=PRIM[t['elem']][1] if t['elem'] in PRIM else (lib[t['elem']]['size'] if t['elem'] in lib else 0)
            if esz:
                for i in range(t['elen']): walk(t['elem'],o+i*esz,indent+1,"[%d]"%i)
        elif k==ENUM:
            sz=t['size'] or 4
            v=int.from_bytes(d[o:o+sz],'little')
            nm=next((m['name'] for m in t['members'] if m['value']==v),None)
            out.append("%s%s = %s"%(pad,label,nm if nm else "%d (%s)"%(v,t['name'])))
        elif k==BITFIELD:
            sz=t['size'] or 4
            v=int.from_bytes(d[o:o+sz],'little')
            out.append("%s%s = 0x%X (bitfield)"%(pad,label,v))
        else:
            out.append("%s%s : <%s, not rendered>"%(pad,label,TYPENAME.get(k,k)))
    walk(inst['type'],0,0,inst['name'] or "instance")
    return out

def load_lib(paths):
    lib={}
    for p in paths:
        try: a=Adf(p)
        except Exception as e: print("  skip %s: %s"%(os.path.basename(p),e)); continue
        lib.update(a.types)
    return lib

def typelib(exe,outdir):
    d=open(exe,'rb').read(); os.makedirs(outdir,exist_ok=True); n=0
    pat=struct.pack('<I',MAGIC); o=d.find(pat)
    while o!=-1:
        if o+0x40<=len(d):
            ver,ninst,oinst,ntype,otype,nunk,ounk,nname,oname,total=struct.unpack_from('<10I',d,o+4)
            if ver==4 and 0<total<8_000_000 and o+total<=len(d) and ntype<10000:
                p=os.path.join(outdir,'lib_%06X.adf'%o)
                open(p,'wb').write(d[o:o+total])
                try: n+=len(Adf(p).types)
                except Exception: pass
        o=d.find(pat,o+1)
    print("extracted %d type definitions into %s"%(n,outdir))

def main():
    a=sys.argv[1:]
    if not a: sys.exit(__doc__)
    cmd=a[0]; libs=[]
    if '--names' in a:
        i=a.index('--names')
        for line in open(a[i+1]):
            h,_,nm=line.rstrip('\n').partition('\t')
            NAMES.setdefault(int(h,16),set()).add(nm)
        a=a[:i]+a[i+2:]
    if '--lib' in a:
        i=a.index('--lib'); libs=a[i+1:]; a=a[:i]
    files=a[1:]
    if cmd=='typelib': typelib(files[0],files[1]); return
    if cmd=='info':
        for p in files:
            f=Adf(p)
            print("%s\n  version %d  instances %d  types %d  names %d  total %d"%(
                os.path.basename(p),f.version,f.ninst,f.ntype,f.nname,f.total))
            if f.comment: print("  comment: %s"%f.comment)
            for i in f.instances:
                print("  instance %-28s type %08X  off %d  size %d"%(i['name'],i['type'],i['offset'],i['size']))
            if f.names: print("  names: %s"%", ".join(f.names[:20]))
    elif cmd=='types':
        for p in files:
            f=Adf(p); print("%s  %d types"%(os.path.basename(p),f.ntype))
            for h,t in sorted(f.types.items(),key=lambda kv:kv[1]['name']):
                print("  %08X %-10s %-38s size %-6d %s"%(h,TYPENAME.get(t['type'],t['type']),
                      t['name'],t['size'],"%d members"%len(t['members']) if t['members'] else ""))
    elif cmd=='dump':
        lib=load_lib(libs)
        for p in files:
            f=Adf(p); lib2=dict(lib); lib2.update(f.types)
            print("===== %s  (library: %d types)"%(os.path.basename(p),len(lib2)))
            for inst in f.instances:
                for line in render(f,lib2,inst): print(line)
    else: sys.exit(__doc__)

if __name__=='__main__': main()
