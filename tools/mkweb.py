#!/usr/bin/env python3
"""Build the data files the web editor needs. Run from anywhere; writes into web/.

    mkweb.py [--game GAMEDIR]

Produces, all generated - never hand-edit them:

  web/manifest.json   the capability list, straight out of webapi.py's registry
  web/pytools.json    {filename: source} for every tool the page loads into
                      Pyodide's virtual filesystem
  web/relics.json     the 116 relic ids from the game's own relics.relicsetc,
                      so the page can say which collectibles you are missing.
                      Only written if --game points at a Mad Max install; the
                      page degrades gracefully without it.

The point of generating rather than hand-writing: the page cannot drift from the
tools. Fix a tool, rebuild, and the editor is fixed too.
"""
import json, os, re, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEB  = os.path.join(ROOT, 'web')

# Which tools to bundle is DERIVED, never listed by hand. The tools import each
# other lazily by filename at call time - convoy.py only reaches for tailedit.py
# once you actually reset a convoy - so a hand-kept list looks complete right up
# until a user clicks the one button that needs the missing file. That is exactly
# what happened on the first live run.
REF = re.compile(r"""['"]([a-z0-9_]+\.py)['"]""")

def closure(start='webapi.py'):
    """Every .py the page could reach from `start`, following filename literals
    transitively. Over-inclusion costs a few KB; under-inclusion is a crash in
    front of a user."""
    seen, queue, prose = set(), [start], set()
    while queue:
        n = queue.pop()
        if n in seen or n in prose: continue
        if not os.path.exists(os.path.join(HERE, n)):
            prose.add(n)           # a filename mentioned in a docstring, not an import
            continue
        seen.add(n)
        for m in REF.findall(open(os.path.join(HERE, n), encoding='utf-8').read()):
            if m not in seen: queue.append(m)
    if prose:
        print("  (mentioned but not a file, ignored: %s)" % ", ".join(sorted(prose)))
    return sorted(seen)

def _load(name):
    p = os.path.join(HERE, name)
    s = importlib.util.spec_from_file_location(name[:-3], p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def main():
    game = None
    if '--game' in sys.argv: game = sys.argv[sys.argv.index('--game') + 1]
    os.makedirs(WEB, exist_ok=True)

    W = _load('webapi.py')
    man = W.manifest()
    json.dump(man, open(os.path.join(WEB, 'manifest.json'), 'w'), indent=1)
    print("manifest.json  %d capabilities" % len(man))

    src = {}
    for t in closure():
        src[t] = open(os.path.join(HERE, t), encoding='utf-8').read()
    json.dump(src, open(os.path.join(WEB, 'pytools.json'), 'w'))
    print("pytools.json   %d files, %d KB" % (len(src), sum(map(len, src.values())) // 1024))

    out = os.path.join(WEB, 'relics.json')
    if game:
        R = _load('relics.py')
        hist, hood = R.table(game)
        json.dump({'history': hist, 'hood': hood}, open(out, 'w'))
        print("relics.json    %d history + %d hood ornament ids" % (len(hist), len(hood)))
    elif os.path.exists(out):
        print("relics.json    kept (pass --game to regenerate)")
    else:
        print("relics.json    skipped - pass --game GAMEDIR to build it")

if __name__ == '__main__':
    main()
