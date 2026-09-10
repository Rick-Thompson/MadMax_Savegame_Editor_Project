#!/usr/bin/env python3
"""Exercise the web editor's capabilities against ONLY the bundled files.

    test_bundle.py [SAVE ...]        defaults to data/ladder/*.sav

Why this exists, specifically: the first live run of the page failed with
`No such file or directory: '/tools/tailedit.py'`. Every Python test passed,
because they ran inside tools/ where every file is present. The page runs in a
filesystem containing only what `mkweb.py` bundled, and `convoy.py` reaches for
`tailedit.py` lazily - at the moment a user clicks Restore convoys, not at
import time.

So this copies exactly the bundle into an empty directory and runs from there.
If a tool is missing from the bundle, this fails the way the browser would.

It also chains operations the way the page does - each edit feeds the next -
which is how the stale-second-payload bug in convoy.py turned up.
"""
import glob, json, os, shutil, sys, tempfile, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def _mod(path, name):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def main(saves):
    mk = _mod(os.path.join(HERE, 'mkweb.py'), 'mkweb')
    bundle = mk.closure()
    sand = tempfile.mkdtemp(prefix='mmbundle-')
    for f in bundle:
        shutil.copy(os.path.join(HERE, f), os.path.join(sand, f))
    for extra in ('relics.json',):                      # data the page ships too
        p = os.path.join(ROOT, 'web', extra)
        if os.path.exists(p): shutil.copy(p, os.path.join(sand, extra))
    print("bundle: %d files -> %s\n" % (len(bundle), sand))

    W = _mod(os.path.join(sand, 'webapi.py'), 'webapi')
    M = W.M
    ops = W.manifest()
    work = os.path.join(sand, 'work'); os.makedirs(work)
    cur, out = os.path.join(work, 'cur.sav'), os.path.join(work, 'out.sav')

    def call(**kw): return json.loads(W.call_json(json.dumps(kw)))

    # Every action, with every choice of every parameter, chained in sequence.
    steps = [('scrap', 'write', {'value': 7777})]
    for o in ops:
        if o['kind'] != 'action': continue
        ps = o.get('params') or []
        if not ps:
            steps.append((o['id'], 'run', {}))
        else:
            p = ps[0]
            for c in p['choices']:
                steps.append((o['id'], 'run', {p['id']: c[0]}))
    steps.append(('scrap', 'write', {'value': 4242}))

    passed = refused = failed = 0
    for src in saves:
        shutil.copy(src, cur)
        name = os.path.basename(src)
        bad = None
        for op, mode, p in steps:
            r = call(op=op, mode=mode, inp=cur, out=out, params=p)
            if not r['ok']:
                bad = (op, p, r['error']); break
            shutil.copy(out, cur)
        if bad:
            kind = 'REFUSED' if 'REFUS' in bad[2].upper() or 'refusing' in bad[2] else 'FAILED'
            if kind == 'REFUSED': refused += 1
            else: failed += 1
            print("%-8s %-26s %s %s\n         %s" % (kind, name, bad[0], bad[1], bad[2][:120]))
            continue
        a, b = M.load(src), M.load(cur)
        st, comp, _ = M.check(b)
        checks = {
            'length':   len(a) == len(b),
            'checksum': (st ^ comp) == M.delta_of(a),
            'copies':   (not M.mirror_room(b)) or M.has_mirror(b),
            'readback': call(op='scrap', mode='read', inp=cur)['value'] == 4242.0,
        }
        # reports must not raise either
        for o in ops:
            if o['kind'] == 'report':
                checks['report:' + o['id']] = call(op=o['id'], mode='read', inp=cur)['ok']
        if all(checks.values()):
            passed += 1; print("ok       %-26s %d steps" % (name, len(steps)))
        else:
            failed += 1
            print("FAILED   %-26s %s" % (name, [k for k, v in checks.items() if not v]))

    print("\n%d passed, %d safely refused, %d failed" % (passed, refused, failed))
    shutil.rmtree(sand, ignore_errors=True)
    return 1 if failed else 0

if __name__ == '__main__':
    a = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, 'data', 'ladder', '*.sav')))
    if not a: sys.exit("no saves to test against")
    sys.exit(main(a))
