#!/usr/bin/env python3
"""Read the collectibles list out of a save, against the game's own relic table.

`legend/relics.relicsetc` is an ADF shipping 103 `HistoryRelic` and 13
`HoodOrnamentRelic` entries, each with a u32 `Id`. The save stores the ones you
have collected as a plain `(u32 index, u32 4, u32 relicId)` record stream in
payload section 2:

    index 0        value = N, the number collected
    index 1..N     value = a relic Id, straight out of relics.relicsetc

Verified on the reference ladder - N equals history + hood exactly in every save
that has the stream:

    PT2   34 = 29 history + 5 hood
    PT3   69 = 59 + 10
    PT4  102 = 89 + 13
    PT5  116 = 103 + 13     (100%)
    PT6  116 = 103 + 13

This is the second structure found to be keyed by an id the game ships rather
than by a name hash - the 1520-entry roster was the first (see ECONOMY.md). It
is worth treating as the default hypothesis for any opaque id list in this save
format: look for a shipped table before reaching for a hash function.

  relics.py list    GAMEDIR SAVE     what is collected
  relics.py missing GAMEDIR SAVE     what is not

**Read-only.** Adding a relic means adding a 12-byte record, and every edit in
this project has to preserve file length (see FORMAT.md). Whether the 512-byte
tail padding can absorb an insert is untested - see OPEN-QUESTIONS.md.
"""
import os, struct, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _l(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
M=_l('madmax_save.py'); ADF=_l('adf.py'); ARCX=_l('arcx.py'); N=_l('names.py')

RELICS='relics.relicsetc'

def table(gamedir,cache=None):
    cache=cache or os.path.join(HERE,'.economy-cache')
    p=os.path.join(cache,RELICS)
    if not os.path.exists(p):
        os.makedirs(cache,exist_ok=True)
        for sub in ('patch_win64','archives_win64'):
            d=os.path.join(gamedir,sub)
            if not os.path.isdir(d): continue
            v=ARCX.index(d).get(N.jenkins(RELICS.encode()))
            if v: open(p,'wb').write(ARCX.extract(v[0],v[1],v[2])); break
        else: raise SystemExit("could not find %s under %s"%(RELICS,gamedir))
    f=ADF.Adf(p); d=ADF.to_py(f,f.types,f.instances[0])
    hist=[r['Id'] for r in d['HistoryRelics']]
    hood=[r['Id'] for r in d['HoodOrnamentRelics']]
    return hist,hood

def collected(savepath,known):
    """-> (offset, count, [ids]) for the collectibles stream, or None."""
    d=M.load(savepath); h=M.header(d)
    p=d[M.PAYLOAD_START:M.PAYLOAD_START+h['block_len']]
    o=0; L=len(p)
    while o+12<=L:
        i0,s0,n=struct.unpack_from('<III',p,o)
        if i0==0 and s0==4 and 0<n<4096:
            q=o+12; ids=[]; k=1
            while q+12<=L and k<=n:
                a,b,v=struct.unpack_from('<III',p,q)
                if a!=k or b!=4: break
                ids.append(v); q+=12; k+=1
            if len(ids)==n and set(ids)&known: return o,n,ids
        o+=1
    return None

def report(gamedir,save,show_missing):
    hist,hood=table(gamedir)
    known=set(hist)|set(hood)
    r=collected(save,known)
    if not r:
        print("no collectibles stream in %s (a save with almost nothing collected "
              "may not have one yet)"%os.path.basename(save)); return
    _o,n,ids=r; got=set(ids)
    stray=got-known
    print("%s: %d collected"%(os.path.basename(save),n))
    print("  history relics  %d/%d"%(len(got&set(hist)),len(hist)))
    print("  hood ornaments  %d/%d"%(len(got&set(hood)),len(hood)))
    if stray: print("  %d ids not in relics.relicsetc: %s"%(len(stray),sorted(stray)[:8]))
    if not show_missing: return
    for label,lst in (("history relic",hist),("hood ornament",hood)):
        miss=[(i,x) for i,x in enumerate(lst) if x not in got]
        if not miss: continue
        print("\n  missing %s (%d):"%(label,len(miss)))
        for i,x in miss: print("    #%-4d id %10d  0x%08X"%(i+1,x,x))

if __name__=='__main__':
    a=sys.argv[1:]
    if len(a)!=3 or a[0] not in ('list','missing'): sys.exit(__doc__)
    report(a[1],a[2],a[0]=='missing')
