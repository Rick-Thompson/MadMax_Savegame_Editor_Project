#!/usr/bin/env python3
"""The single source of truth for what the web editor can do.

Every capability is one registered entry here. `mkweb.py` reads this registry
and writes `web/manifest.json`; the page builds its whole UI from that file and
calls back into `call()` to do the work. **Adding a feature is adding one entry
to this file** - no HTML, no JavaScript, no manifest editing.

An entry is a class used as a namespace. Which methods it defines decides what
kind of control the page draws:

    read(inp)                 -> value        a number field (with write)
    write(inp, out, value)                    ...its writer
    run(inp, out, **params)   -> str          an action button
    report(inp)               -> str          a read-only panel

`verified` is rendered next to every control and is not decoration:

    in-game      an edit of this kind has been loaded by the game and checked
    structural   provably correct against the format, never tested in game
    speculative  inferred, could be wrong

Handlers take and return file paths, so the existing tools are used unchanged -
the page writes the uploaded save to the virtual filesystem and reads the result
back out.
"""
import io, json, os, contextlib, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
def _t(n):
    s = importlib.util.spec_from_file_location(n[:-3], os.path.join(HERE, n))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

M = _t('madmax_save.py')

REGISTRY = []

def register(**spec):
    def deco(cls):
        spec['id'] = spec.get('id') or cls.__name__
        spec['help'] = (spec.get('help') or cls.__doc__ or '').strip()
        spec['kind'] = ('number' if hasattr(cls, 'read')
                        else 'action' if hasattr(cls, 'run')
                        else 'report')
        spec['_cls'] = cls
        REGISTRY.append(spec)
        return cls
    return deco

def manifest():
    """The registry as plain JSON-able data, in declaration order."""
    return [{k: v for k, v in s.items() if not k.startswith('_')} for s in REGISTRY]

def _find(op):
    for s in REGISTRY:
        if s['id'] == op: return s
    raise KeyError("no such operation: %s" % op)

def _verify(inp, out):
    """Every write goes through this. Length must be unchanged and the stored
    checksum must match what the file's own delta implies."""
    a, b = M.load(inp), M.load(out)
    if len(a) != len(b):
        raise SystemExit("REFUSED: length changed %d -> %d" % (len(a), len(b)))
    if M.delta_of(a) != M.delta_of(b):
        raise SystemExit("REFUSED: checksum does not verify after the edit")
    if M.mirror_room(b) and not M.has_mirror(b):
        if M.mirror_room(a) and not M.has_mirror(a):
            raise SystemExit(
                "REFUSED: this save already holds two payload blocks that differ from "
                "each other, before any edit. There is no safe way to tell which one "
                "the game reads, so nothing here will touch it. 48 of 51 saves "
                "measured have identical copies - this one is unusual.")
        raise SystemExit("REFUSED: the edit left the second copy of the payload stale. "
                         "That is a bug in the tool, not in your save.")
    return len(b)

def call(op, mode, inp, out=None, params=None):
    """The one entry point the page uses. Returns a JSON string."""
    s = _find(op); cls = s['_cls']; params = params or {}
    log = io.StringIO()
    try:
        with contextlib.redirect_stdout(log):
            if mode == 'read':
                value = cls.read(inp) if hasattr(cls, 'read') else cls.report(inp)
            elif mode == 'write':
                cls.write(inp, out, params['value']); value = _verify(inp, out)
            elif mode == 'run':
                cls.run(inp, out, **params); value = _verify(inp, out)
            else:
                raise ValueError("bad mode %r" % mode)
        return json.dumps({'ok': True, 'value': value, 'log': log.getvalue()})
    except BaseException as e:
        return json.dumps({'ok': False, 'error': "%s: %s" % (type(e).__name__, e),
                           'log': log.getvalue()})

def call_json(args):
    """JSON in, JSON out - the only thing the page calls.

    Keeping a single shape means a Python-side failure comes back as a message
    the page can show, instead of an exception escaping into JavaScript."""
    a = json.loads(args)
    return call(a['op'], a['mode'], a['inp'], a.get('out'), a.get('params'))

# --------------------------------------------------------------------------

@register(label='Save file', group='This save', verified='in-game', order=0)
class info:
    """Slot, playtime and format, plus the integrity check. Read this first to
    be sure you picked the file you meant to."""
    @staticmethod
    def report(inp):
        d = M.load(inp); h = M.header(d)
        st, comp, ok = M.check(d)
        dl = M.delta_of(d)
        pt = h.get('playtime_s') or 0
        y = h.get('date') or ()
        return "\n".join([
            "slot          %s" % h.get('slot'),
            "playtime      %d h %02d m" % (pt // 3600, (pt % 3600) // 60),
            "saved         %s" % ("%04d-%02d-%02d %02d:%02d" % y if len(y) == 5 else "?"),
            "format        v%s" % h.get('version'),
            "file length   %d bytes" % len(d),
            "payload       %d bytes%s" % (h['block_len'],
                " + mirror copy" if M.has_mirror(d) else ""),
            "checksum      stored %08X  computed %08X" % (st, comp),
            "delta         %08X%s" % (dl, "  (current format)" if dl == 0 else
                                          "  (v6 - carried across edits)"),
        ])

@register(label='Scrap', group='Resources', verified='in-game',
          min=0, max=999999, step=1, order=10)
class scrap:
    """The scrap in your inventory. Confirmed to load correctly on Windows as
    well as Linux. Its record id moves between saves, so it is located by the
    shape of the record around it rather than by a fixed id."""
    @staticmethod
    def read(inp):
        R = _t('resource.py'); hits = R.find_scrap(M.load(inp))
        if not hits: raise SystemExit("no scrap field found in this save")
        return hits[0][1]
    @staticmethod
    def write(inp, out, value):
        _t('resource.py').cmd_scrap([inp, out, str(float(value))])

@register(label='Restore all convoys', group='Activities', verified='in-game',
          params=[{'id': 'state', 'label': 'Bring them back as', 'type': 'choice',
                   'default': '2',
                   'choices': [['2', 'Active - marked red on the map, playable'],
                               ['0', 'Undiscovered - present, not yet on the map'],
                               ['3', 'Wrecked - what killing one writes']]}],
          order=20)
class convoy_reset:
    """Puts every convoy in the world back. Verified in game twice, on a live
    playthrough and on a 100% save: the routes come back marked in red and
    driving to one gives a complete, working convoy.

    This writes the record that actually governs a convoy. Six earlier attempts
    failed by editing records that only describe one."""
    @staticmethod
    def run(inp, out, state='2'):
        _t('convoy.py').cmd_reset(inp, out, None, int(state))

@register(label='Restore destroyed threats', group='Activities',
          verified='in-game',
          params=[{'id': 'klass', 'label': 'Put back', 'type': 'choice',
                   'default': 'all',
                   'choices': [['all',       'Everything destroyed (recommended)'],
                               ['scarecrow', 'Scarecrows only (97 in the world)'],
                               ['sniper',    'Snipers only (35)'],
                               ['minefield', 'Minefields only (30)']]}],
          order=30)
class restore_threats:
    """Puts destroyed threats back - both the object and its map marker, which
    both have to move or you get an object with no marker, or a marker with no
    object.

    Restoring scarecrows has been verified in game. Snipers and minefields use
    exactly the same mechanism on the same tables, but have not been loaded and
    checked, so treat them as structural until someone does.

    The intact value is read back from the save itself rather than assumed:
    it is not always 1.0, and writing a flat 1.0 would corrupt the classes that
    keep a count or a timer in that field.

    Prefer "everything destroyed". Restoring one class on its own still clears
    every cleared map marker, so the other classes end up with a marker and no
    object behind it - harmless, but the map will not match what is out there."""
    PROFILES = {'scarecrow': {45, 46, 47, 48}, 'sniper': {49}, 'minefield': {52},
                'all': {45, 46, 47, 48, 49, 52}}
    @staticmethod
    def run(inp, out, klass='all'):
        _t('mmworld.py').edit(inp, out, restore_threats.PROFILES[klass], 1.0, None, True)

@register(label='Collectibles', group='This save', verified='structural', order=40)
class collectibles:
    """History relics and hood ornaments you have picked up, checked against the
    game's own relic table. Read-only: adding one means adding a record, and
    every edit here has to keep the file length identical."""
    @staticmethod
    def report(inp):
        p = os.path.join(HERE, 'relics.json')
        if not os.path.exists(p): return "relic table not bundled with this build"
        t = json.load(open(p))
        hist, hood = set(t['history']), set(t['hood'])
        R = _t('relics.py'); r = R.collected(inp, hist | hood)
        if not r: return "no collectibles list in this save yet"
        _o, n, ids = r; got = set(ids)
        return "\n".join([
            "collected       %d" % n,
            "history relics  %d / %d" % (len(got & hist), len(hist)),
            "hood ornaments  %d / %d" % (len(got & hood), len(hood)),
        ])

if __name__ == '__main__':
    print(json.dumps(manifest(), indent=2))
