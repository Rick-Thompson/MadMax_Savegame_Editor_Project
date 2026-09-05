#!/usr/bin/env python3
"""Decode the save's 1520-entry roster against the game's own economy tables.

The roster in payload section 2 is not a bespoke save structure. It is a
verbatim copy of the first 1520 rows of `global/economyresources.economyresourcesc`,
an ADF the game ships:

    EconomyResource  (24 bytes)
        u64 ID              world object id
        u8  ProfileIndex    -> EconomyResourceProfile
        u8  pad[3]
        f32 LastAmount      how much is left in it
        u32 LastVisited     respawn clock
        u32 pad

    EconomyResourceProfile
        u32   Profile           name hash
        enum  Type              Water Food Fuel Scrap Threat
                                Ammo_Shotgun Ammo_Sniper Ammo_Thunderstick Shiv
        f32   RegenerationRate  StartAmountMin  StartAmountMax
        f32   Capacity          CoolDownTime    FillChance
        u8    Infinite

Every ID and ProfileIndex in a save matches the shipped table exactly - 1520 of
1520, no exceptions - so the roster's `type` column is a ProfileIndex and its
`state` column is LastAmount, a float quantity, not a 1.0/0.0 flag. Threat
objects only look boolean because their capacity is 1.

`global/regioninfo.regioninfoc` groups those same row indices by region and by
threat type, which is what identifies the classes:

    threat 0  camps        37    threat 3  convoys     13
    threat 1  scarecrows   97    threat 4  minefields  30
    threat 2  snipers      35

`positions` in the same ADF holds one world XYZ per row, index-aligned, so any
roster row can be placed on the map.

  economy.py tables  GAMEDIR                 profiles and per-class counts
  economy.py dump    GAMEDIR SAVE [--type T] [--class C]   annotate a roster
  economy.py refill  GAMEDIR SAVE OUT [--type T] [--class C]
                                             set LastAmount back to StartAmountMax

`refill` goes through sec2edit.rebuild, so it is length-preserving and the
integrity delta stays valid. Filter it: `--type Threat` re-arms every camp,
sniper, scarecrow, minefield and convoy in the world at once, which is a far
bigger change than it sounds. `--class camp` or `--type Scrap` is the usual
intent.
"""
import os, struct, sys, collections, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def _l(n):
    s=importlib.util.spec_from_file_location(n[:-3],os.path.join(HERE,n))
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
ADF=_l('adf.py'); ARCX=_l('arcx.py'); SE=_l('sec2edit.py'); N=_l('names.py')

FILES=['economyresources.economyresourcesc','regioninfo.regioninfoc']
THREAT=['camp','scarecrow','sniper','convoy','minefield']
ENUM_HASH=0x4D28669F           # EconomyResourceType
# regioninfo has 32 region slots; these three are territory-wide aggregates
# that repeat rows already listed by the individual regions. Counting them
# would double every object.
TERRITORY_ROWS={28,29,30}

def _extract(gamedir,outdir):
    """Pull the two ADFs out of the archives. Both live in patch_win64 - the
    patch supersedes the copies in archives_win64, which is why looking only in
    archives_win64 reports them missing."""
    os.makedirs(outdir,exist_ok=True); got={}
    for sub in ('patch_win64','archives_win64'):
        d=os.path.join(gamedir,sub)
        if not os.path.isdir(d) or len(got)==len(FILES): continue
        idx=ARCX.index(d)
        for name in FILES:
            if name in got: continue
            v=idx.get(N.jenkins(name.encode()))
            if not v: continue
            p=os.path.join(outdir,name)
            open(p,'wb').write(ARCX.extract(v[0],v[1],v[2])); got[name]=p
    for f in FILES:
        if f not in got: raise SystemExit("could not find %s under %s"%(f,gamedir))
    return got

def load(gamedir,cache=None):
    cache=cache or os.path.join(HERE,'.economy-cache')
    have={f:os.path.join(cache,f) for f in FILES}
    if not all(os.path.exists(p) for p in have.values()):
        have=_extract(gamedir,cache)
    er=ADF.Adf(have['economyresources.economyresourcesc'])
    b={i['name']:i for i in er.instances}
    prof=ADF.to_py(er,er.types,b['profiles'])['EconomyProfiles']
    rt=ADF.to_py(er,er.types,b['resource_table'])
    pos=ADF.to_py(er,er.types,b['positions'])['EconomyPositions']
    names={m['value']:m['name'] for m in er.types[ENUM_HASH]['members']}
    ri=ADF.Adf(have['regioninfo.regioninfoc'])
    regs=ADF.to_py(ri,ri.types,ri.instances[0])['ThreatsInRegionByType']
    cls={}
    for r_i,r in enumerate(regs):
        if r_i in TERRITORY_ROWS: continue
        for k,t in enumerate(r['EconomyIndicesByThreatType']):
            for idx in t['Indices']: cls[idx]=(THREAT[k],r_i)
    return dict(profiles=prof,resources=rt['EconomyResources'],
                saved=rt['SpawnedStartIndex'],positions=pos,
                typename=names,classof=cls)

def roster(savepath):
    _,_,_,s2=SE.split(savepath); ts=SE.tables(s2)
    i=SE.roles(ts).get('roster')
    if i is None: raise SystemExit("%s: no roster table"%savepath)
    return ts[i]['ents']

def row(e):
    ID,pi=struct.unpack_from('<QB',e,0)
    amt,lv=struct.unpack_from('<fI',e,12)
    return ID,pi,amt,lv

def _keep(E,i,pi,only_t,only_c):
    if only_t:
        tn=E['typename'].get(E['profiles'][pi]['Type'],'')
        if tn.lower()!=only_t.lower(): return False
    if only_c:
        c=E['classof'].get(i)
        if not c or c[0].lower()!=only_c.lower(): return False
    return True

def cmd_tables(gamedir):
    E=load(gamedir); prof=E['profiles']; res=E['resources']; n=E['saved']
    c=collections.Counter(r['ProfileIndex'] for r in res[:n])
    print("%d rows saved (of %d in the shipped table), %d profiles\n"%(n,len(res),len(prof)))
    print("prof  type               start          cap  fill  rows  class")
    for p in sorted(c):
        q=prof[p]
        cl={E['classof'][i][0] for i,r in enumerate(res[:n])
            if r['ProfileIndex']==p and i in E['classof']}
        print("%4d  %-17s %6g-%-7g %5g  %.2f  %4d  %s"%(
            p,E['typename'].get(q['Type'],q['Type']),q['StartAmountMin'],
            q['StartAmountMax'],q['Capacity'],q['FillChance'],c[p],",".join(sorted(cl))))

def cmd_dump(gamedir,save,only_t,only_c):
    E=load(gamedir); prof=E['profiles']; ents=roster(save); pos=E['positions']
    print("%-5s %-12s %-4s %-17s %10s %8s %6s  %-22s %s"%(
        "idx","ID","prof","type","LastAmount","capacity","visit","class","position"))
    shown=0
    for i,e in enumerate(ents):
        ID,pi,amt,lv=row(e)
        if not _keep(E,i,pi,only_t,only_c): continue
        q=prof[pi]; cl=E['classof'].get(i); shown+=1
        xyz=pos[i]['Position'] if i<len(pos) else None
        print("%-5d %-12d %-4d %-17s %10.3f %8g %6d  %-22s %s"%(
            i,ID,pi,E['typename'].get(q['Type'],q['Type']),amt,q['Capacity'],lv,
            "%s region %d"%cl if cl else "",
            "%.0f %.0f %.0f"%tuple(xyz) if xyz else ""))
    print("\n%d of %d rows"%(shown,len(ents)))

def cmd_refill(gamedir,save,out,only_t,only_c):
    E=load(gamedir); prof=E['profiles']; ents=roster(save)
    keys=collections.Counter(struct.unpack_from('<I',e,0)[0] for e in ents)
    sets=[]; plan=[]
    for i,e in enumerate(ents):
        ID,pi,amt,lv=row(e)
        if not _keep(E,i,pi,only_t,only_c): continue
        tgt=prof[pi]['StartAmountMax']
        if abs(amt-tgt)<=1e-6: continue
        k=struct.unpack_from('<I',e,0)[0]
        if keys[k]!=1:
            print("  skip [%d]: low-32 key %08X is not unique, cannot address it"%(i,k))
            continue
        ne=bytearray(e); struct.pack_into('<f',ne,12,tgt)
        sets.append(('roster','%08X'%k,bytes(ne).hex()))
        plan.append((i,amt,tgt))
    if not sets: print("nothing to refill"); return
    print("refilling %d rows (%s)"%(len(plan),
          " ".join(filter(None,["type=%s"%only_t if only_t else "",
                                "class=%s"%only_c if only_c else ""])) or "everything"))
    for i,a,t in plan[:20]: print("  [%d] %.3f -> %g"%(i,a,t))
    if len(plan)>20: print("  ... %d more"%(len(plan)-20))
    SE.rebuild(save,out,[],[],sets=sets)

def main():
    a=sys.argv[1:]
    if not a: sys.exit(__doc__)
    only_t=only_c=None
    for flag in ('--type','--class'):
        if flag in a:
            i=a.index(flag)
            if flag=='--type': only_t=a[i+1]
            else: only_c=a[i+1]
            a=a[:i]+a[i+2:]
    cmd=a[0]
    if   cmd=='tables' and len(a)==2: cmd_tables(a[1])
    elif cmd=='dump'   and len(a)==3: cmd_dump(a[1],a[2],only_t,only_c)
    elif cmd=='refill' and len(a)==4: cmd_refill(a[1],a[2],a[3],only_t,only_c)
    else: sys.exit(__doc__)

if __name__=='__main__': main()
