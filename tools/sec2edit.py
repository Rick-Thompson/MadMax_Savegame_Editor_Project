#!/usr/bin/env python3
"""Edit the section-2 tables of a Mad Max save and rebuild the file.

  sec2edit.py IN.sav OUT.sav [--slot N] [--add T:HEXENTRY] [--del T:KEYHEX] ...
    T = table index (0..3).  --add takes a full entry in hex.
    --del removes every entry whose first u32 equals KEYHEX.

Table 0 (8B entries)  : live/active world objects - destroying REMOVES a row.
Table 1 (16B entries) : destroyed objects        - destroying ADDS a row.
"""
import os, struct, sys, importlib.util
spec=importlib.util.spec_from_file_location('m', os.path.join(os.path.dirname(os.path.abspath(__file__)),'madmax_save.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def split(path):
    d=m.load(path); h=m.header(d)
    payload=d[m.PAYLOAD_START:m.PAYLOAD_START+h['block_len']]
    r=m.records(d); rend=max(r[i][1]+len(r[i][0]) for i in r)-m.PAYLOAD_START
    return d,h,payload[:rend],payload[rend:]

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
        out.append(dict(off=o,f=list(f),count=cnt,esz=esz,
                        ents=[s[o+28+k*esz:o+28+(k+1)*esz] for k in range(cnt)]))
        end=o+28+nb
    return out

def roles(ts):
    """Map logical role -> table index. Positional indices are NOT stable:
    later-game saves grow an extra 24-byte table, which shifts everything after
    it. Always select by role."""
    r={}
    for i,t in enumerate(ts):
        if t['esz']==8 and 'live' not in r: r['live']=i
        elif t['esz']==16 and 'markers' not in r: r['markers']=i
        elif t['esz']==32 and 'misc' not in r: r['misc']=i
    best=None
    for i,t in enumerate(ts):
        if t['esz']==24 and (best is None or len(t['ents'])>len(ts[best]['ents'])): best=i
    if best is not None: r['roster']=best
    return r


def resolve(ts,name):
    r=roles(ts)
    if isinstance(name,str) and name in r: return r[name]
    i=int(name)
    return i


def rebuild(inp,out,adds,dels,slot=None,sets=()):
    d,h,head,s2=split(inp)
    ts=tables(s2)
    for ti,hexe in adds:
        e=bytes.fromhex(hexe)
        ti=resolve(ts,ti); t=ts[ti]
        if len(e)!=t['esz']: raise SystemExit("table %d wants %dB entries"%(ti,t['esz']))
        if e in t['ents']: print("  note: entry already in table %d"%ti); continue
        t['ents'].append(e)
        t['ents'].sort(key=lambda x: struct.unpack_from('<I',x,4)[0] if t['esz']==8 else 0)
        print("  table %d: added %s"%(ti,e.hex(' ')))
    for ti,key in dels:
        ti=resolve(ts,ti); t=ts[ti]; k=int(key,16)
        keep=[e for e in t['ents'] if struct.unpack_from('<I',e,0)[0]!=k]
        print("  table %d: removed %d entr%s with key %08X"%(ti,len(t['ents'])-len(keep),
              'y' if len(t['ents'])-len(keep)==1 else 'ies',k))
        t['ents']=keep
    for ti,key,hexe in sets:
        ti=resolve(ts,ti); t=ts[ti]; k=int(key,16); e=bytes.fromhex(hexe)
        if len(e)!=t['esz']: raise SystemExit("table %d wants %dB entries"%(ti,t['esz']))
        n=0
        for j,old in enumerate(t['ents']):
            if struct.unpack_from('<I',old,0)[0]==k:
                print("  table %d: %s"%(ti,old.hex(' ')));print("           -> %s"%e.hex(' '))
                t['ents'][j]=e; n+=1
        if not n: raise SystemExit("no entry with key %08X in table %d"%(k,ti))
    # reassemble section 2
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
    print("  payload %d -> %d ; file %d -> %d %s"%(h['block_len'],len(payload),len(d),len(body),
          "(unchanged - delta valid)" if len(body)==len(d) else "*** LENGTH CHANGED ***"))
    if len(body)!=len(d): raise SystemExit("refusing: file length changed, delta would be wrong")
    m.save(out, m.reseal(body, m.delta_of(d)))
    print("  wrote",out)

if __name__=='__main__':
    a=sys.argv; adds=[];dels=[];sets=[];slot=None;i=3
    while i<len(a):
        if a[i]=='--slot': slot=int(a[i+1]); i+=2
        elif a[i]=='--add': t,e=a[i+1].split(':'); adds.append((t,e)); i+=2
        elif a[i]=='--del': t,k=a[i+1].split(':'); dels.append((t,k)); i+=2
        elif a[i]=='--set': t,k,e=a[i+1].split(':'); sets.append((t,k,e)); i+=2
        else: i+=1
    rebuild(a[1],a[2],adds,dels,slot,sets)
