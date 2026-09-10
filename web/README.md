# The browser editor

A save editor that runs entirely in the page. No upload, no server, no
third-party requests — the Python runtime is served from this site's own origin.

Live at
<https://rick-thompson.github.io/MadMax_Savegame_Editor_Project/>

## How it is put together

```
tools/webapi.py     the registry: one entry per capability   <- the only file
tools/mkweb.py      generates the three files below              you edit to
web/manifest.json   generated - the capability list              add a feature
web/pytools.json    generated - the tools, as source
web/relics.json     generated - 116 relic ids from the game
web/index.html      the shell: no scripts but app.js, no styles but its own
web/app.js          draws controls from the manifest, calls back into Python
web/vendor/pyodide  fetched at deploy time, never committed
```

The page knows nothing about the save format. It reads `manifest.json`, draws a
control for each entry, and calls `webapi.call_json()`. **The tools that do the
work are the same ones in `tools/`, unchanged** — the build copies their source
into `pytools.json` and Pyodide loads them into a virtual filesystem. There is
no second implementation of the format to keep in sync, which matters most for
the checksum and re-seal path, where a bug corrupts saves.

## Adding a capability

Add one entry to `tools/webapi.py`:

```python
@register(label='Water', group='Resources', verified='structural',
          min=0, max=1000, order=15)
class water:
    """One sentence the page shows under 'What this does'."""
    @staticmethod
    def read(inp): ...
    @staticmethod
    def write(inp, out, value): ...
```

Which methods you define decides the control: `read`/`write` gives a number
field, `run` gives a button (with `params` for dropdowns), `report` gives a
read-only panel. Then `python3 tools/mkweb.py` and push. No HTML, no JavaScript,
no manifest editing.

`verified` is rendered next to every control and is not decoration:

| value | meaning |
|---|---|
| `in-game` | an edit of this kind has been loaded by the game and checked |
| `structural` | provably correct against the format, never tested in game |
| `speculative` | inferred, could be wrong |

## Safety rails

Every write goes through `webapi._verify()`, which refuses the result if the
file length changed or the checksum no longer verifies. That is not belt and
braces — the integrity value is not solved in closed form, only carried across
length-preserving edits, so a length change silently produces a file the game
rejects. See [../docs/FORMAT.md](../docs/FORMAT.md).

The page never overwrites anything: it hands you a new `*-edited.sav` to
download, and keeps the file you opened so you can start over.

## Building locally

```sh
python3 tools/mkweb.py --game "/path/to/steamapps/common/Mad Max"
cd web && ./vendor/fetch-pyodide.sh && python3 -m http.server 8000
```

`--game` is optional and only needed to regenerate `relics.json`. It must be
served over HTTP — Pyodide will not start from a `file://` page.
