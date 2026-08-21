#!/usr/bin/env python3
"""Disassemble Mad Max XVM bytecode (.xvmc) - the game's own gameplay scripts.

A .xvmc is an ADF file holding up to three instances: `module` (an
`XvmFormatModule`), `debug_info` and `debug_strings`. The module carries the
functions, their bytecode, a constant pool, a string buffer and an import list.

Instruction encoding, from Gibbed.MadMax.XvmDisassemble:

    u16 instruction;  opcode = instruction & 0x1F;  oparg = instruction >> 5

Constants are a u64 flags word plus a u64 value:

    length = flags & 0xFF        type 0 = none    type 3 = float (raw u32)
    alloc  = (flags >> 8) & 0xFF type 4 = string / byte blob at StringBuffer[value]

Names referenced by ldglob / ldattr / stattr are resolved two ways. With
`debug_strings` present, StringBuffer[value-2..value-1] is a big-endian offset
into the debug string blob and gives the literal name. Without it, the name is
only a hash: StringBuffer[value-3] indexes StringHashes.

  xvm.py dis FILE.xvmc --lib TYPELIB/*.adf [--names D.tsv]
  xvm.py strings FILE.xvmc --lib ...        just the readable names
"""
import os, struct, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _l(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
A=_l('adf.py'); N=_l('names.py')

OPS={1:'and',2:'or',3:'add',4:'div',5:'mod',6:'mul',7:'sub',8:'mklist',9:'call',
     10:'cmpeq',11:'cmpge',12:'cmpg',13:'cmpne',14:'jmp',15:'jz',18:'ldattr',
     19:'ldconst',20:'ldbool',21:'ldglob',22:'ldloc',23:'lditem',24:'pop',
     25:'dbgout',26:'ret',27:'stattr',28:'stloc',29:'stitem',30:'not',31:'neg'}
SIMPLE={1,2,3,4,5,6,7,10,11,12,13,23,24,29,30,31}
JUMPS={14,15}
NAMED={18,21,27}

class Module:
    def __init__(self,path,lib):
        a=A.Adf(path); l=dict(lib); l.update(a.types)
        self.name=os.path.basename(path); self.mod=None; self.dbg=None
        for i in a.instances:
            v=A.to_py(a,l,i)
            if i['name']=='module': self.mod=v
            elif i['name']=='debug_strings': self.dbg=v
        if self.mod is None: raise ValueError("%s: no module instance"%path)
        self.sb=self.mod.get('StringBuffer') or b''
        self.dbgbuf=(self.dbg or {}).get('StringBufferDebug') or b''
        self.consts=self.mod.get('Constants') or []
        self.hashes=self.mod.get('StringHashes') or []

    def const(self,i):
        c=self.consts[i]; f=c['Type']; v=c['Value']
        return dict(length=f&0xFF, alloc=(f>>8)&0xFF, type=(f>>16)&0xF, value=v)

    def name_of(self,i):
        """Name referenced by ldglob/ldattr/stattr."""
        c=self.const(i); v=c['value']
        if self.dbgbuf and v>=2:
            off=(self.sb[v-2]<<8)|self.sb[v-1]
            if off<len(self.dbgbuf):
                e=self.dbgbuf.index(b'\0',off)
                return self.dbgbuf[off:e].decode('utf-8','replace')
        if v>=3 and self.sb:
            hi=self.sb[v-3]
            if hi<len(self.hashes):
                h=self.hashes[hi]
                return N_resolve(h) or "0x%08X"%h
        return "?"

    def const_repr(self,i):
        c=self.const(i)
        if c['type']==0: return "ldnone"
        if c['type']==3:
            return "ldfloat %g"%struct.unpack('<f',struct.pack('<I',c['value']&0xFFFFFFFF))[0]
        if c['type']==4:
            b=bytes(self.sb[c['value']:c['value']+c['length']])
            try:
                t=b.decode('ascii')
                if all(0x20<=ord(x)<=0x7E or x in '\t\n\r' for x in t): return 'ldstr %r'%t
            except Exception: pass
            return "ldbytes %s"%b.hex(' ')
        return "ldconst #%d (type %d)"%(i,c['type'])

NAMES={}
def N_resolve(h):
    v=NAMES.get(h)
    return sorted(v)[0] if v else None

def disassemble(m):
    out=["module %s  srccrc %08X  %d functions  %d constants%s"%(
        m.name,m.mod.get('SrcCRC',0),len(m.mod.get('Functions') or []),
        len(m.consts)," (debug strings present)" if m.dbgbuf else "")]
    imports=m.mod.get('ImportHashes') or []
    if imports:
        out.append("  imports: "+", ".join(N_resolve(h) or "0x%08X"%h for h in imports))
    for fn in (m.mod.get('Functions') or []):
        nm=(fn.get('Name') or b'').split(b'\0')[0].decode('latin1')
        ins=fn.get('Instructions') or []
        out.append("")
        out.append("function %s  args %d  locals %d  stack %d  (%d instructions)"%(
            nm or "0x%08X"%fn.get('NameHash',0),fn.get('ArgCount',0),
            fn.get('LocalsCount',0),fn.get('MaxStackDepth',0),len(ins)))
        labels={}
        for w in ins:
            if (w&0x1F) in JUMPS: labels[w>>5]="label_%d"%(w>>5)
        for i,w in enumerate(ins):
            op=w&0x1F; arg=w>>5
            if i in labels: out.append("  %s:"%labels[i])
            if op in SIMPLE: t=OPS.get(op,"op%d"%op)
            elif op in JUMPS: t="%s %s"%(OPS[op],labels.get(arg,arg))
            elif op in NAMED: t='%s "%s"'%(OPS[op],m.name_of(arg))
            elif op==19: t=m.const_repr(arg)
            elif op==8: t="mklist %d"%arg
            elif op==9: t="call %d"%arg
            elif op==20: t="ldbool %d"%arg
            elif op==22: t="ldloc %d"%arg
            elif op==28: t="stloc %d"%arg
            elif op==25: t="dbgout %d"%arg
            elif op==26: t="ret %d"%arg
            else: t="%s %d"%(OPS.get(op,"op%d"%op),arg)
            out.append("    %-4d %s"%(i,t))
    return out

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
    lib=A.load_lib(libs)
    for p in a[1:]:
        try: m=Module(p,lib)
        except Exception as e: print("%s: %s"%(os.path.basename(p),e)); continue
        if cmd=='dis':
            for line in disassemble(m): print(line)
        elif cmd=='strings':
            print("== %s"%m.name)
            if m.dbgbuf:
                for s in m.dbgbuf.split(b'\0'):
                    if len(s)>2: print("   %s"%s.decode('utf-8','replace'))
        else: sys.exit(__doc__)

if __name__=='__main__': main()
