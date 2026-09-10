/* Mad Max save editor - UI shell.
 *
 * This file deliberately knows nothing about the save format. It reads
 * manifest.json, draws a control per entry, and calls webapi.call_json() in
 * Pyodide to do the work. Adding a capability means adding an entry to
 * tools/webapi.py and rebuilding - never editing this file.
 *
 * ES2020, no modules, no build step, no external requests.
 */
(function () {
  'use strict';

  var REPO = 'https://github.com/Rick-Thompson/MadMax_Savegame_Editor_Project';
  var IN = '/work/in.sav', CUR = '/work/cur.sav', OUT = '/work/out.sav';

  var el = function (id) { return document.getElementById(id); };
  var state = { py: null, api: null, manifest: null, name: 'edited.sav', dirty: false };

  function status(msg) { el('status').textContent = msg || ''; }

  function log(msg, isErr) {
    var d = document.createElement('div');
    if (isErr) d.className = 'err';
    d.textContent = msg;
    el('log').appendChild(d);
    el('log').scrollTop = el('log').scrollHeight;
  }

  function loadScript(src) {
    return new Promise(function (res, rej) {
      var s = document.createElement('script');
      s.src = src; s.onload = res; s.onerror = function () { rej(new Error('cannot load ' + src)); };
      document.head.appendChild(s);
    });
  }

  function getJSON(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + ': HTTP ' + r.status);
      return r.json();
    });
  }

  /* ---------------------------------------------------------------- runtime */

  function boot() {
    if (state.py) return Promise.resolve();
    status('Loading the Python runtime. About 20 MB, once - it is cached after this.');
    return loadScript('vendor/pyodide/pyodide.js')
      .then(function () { return loadPyodide({ indexURL: 'vendor/pyodide/' }); })
      .then(function (py) {
        state.py = py;
        return getJSON('pytools.json');
      })
      .then(function (tools) {
        var py = state.py;
        py.FS.mkdir('/tools'); py.FS.mkdir('/work');
        Object.keys(tools).forEach(function (name) {
          py.FS.writeFile('/tools/' + name, tools[name]);
        });
        py.runPython("import sys; sys.path.insert(0, '/tools')");
        state.api = py.runPython("import webapi; webapi");
        status('');
      });
  }

  /* Every call into Python goes through here. One shape, JSON in and out, so a
     Python-side error surfaces as a message rather than a broken page. */
  function api(op, mode, params, inPath, outPath) {
    var args = { op: op, mode: mode, inp: inPath || CUR, out: outPath || null, params: params || null };
    var raw;
    try {
      raw = state.api.call_json(JSON.stringify(args));
    } catch (e) {
      return { ok: false, error: String(e), log: '' };
    }
    return JSON.parse(raw);
  }

  /* ------------------------------------------------------------------- edit */

  function afterWrite(spec, res) {
    if (!res.ok) { log(spec.label + ': ' + res.error, true); return false; }
    state.py.FS.writeFile(CUR, state.py.FS.readFile(OUT));
    state.dirty = true;
    el('download').disabled = false;
    el('revert').disabled = false;
    return true;
  }

  function refreshReports() {
    (state.manifest || []).forEach(function (spec) {
      if (spec.kind !== 'report') return;
      var pre = el('out-' + spec.id);
      if (!pre) return;
      var res = api(spec.id, 'read');
      pre.textContent = res.ok ? res.value : res.error;
    });
    (state.manifest || []).forEach(function (spec) {
      if (spec.kind !== 'number') return;
      var inp = el('in-' + spec.id);
      if (!inp) return;
      var res = api(spec.id, 'read');
      if (res.ok) inp.value = res.value;
      else { inp.disabled = true; inp.placeholder = 'not in this save'; }
    });
  }

  /* ------------------------------------------------------------------ build */

  function tag(v) {
    var s = document.createElement('span');
    s.className = 'tag t-' + v;
    s.textContent = v;
    s.title = v === 'in-game' ? 'An edit of this kind has been loaded by the game and checked.'
      : v === 'structural' ? 'Provably correct against the format, but never tested in game.'
      : 'Inferred. Could be wrong. Keep a backup.';
    return s;
  }

  function helpBlock(text) {
    if (!text) return null;
    var d = document.createElement('details');
    var s = document.createElement('summary'); s.textContent = 'What this does';
    var p = document.createElement('pre'); p.textContent = text;
    d.appendChild(s); d.appendChild(p);
    return d;
  }

  function paramControls(spec, holder) {
    var got = {};
    (spec.params || []).forEach(function (p) {
      var wrap = document.createElement('span');
      var lab = document.createElement('label');
      lab.textContent = p.label + ' ';
      lab.style.fontWeight = 'normal';
      var sel = document.createElement('select');
      (p.choices || []).forEach(function (c) {
        var o = document.createElement('option');
        o.value = c[0]; o.textContent = c[1];
        if (String(p.default) === String(c[0])) o.selected = true;
        sel.appendChild(o);
      });
      lab.appendChild(sel); wrap.appendChild(lab); holder.appendChild(wrap);
      got[p.id] = function () { return sel.value; };
    });
    return got;
  }

  function card(spec) {
    var c = document.createElement('div'); c.className = 'card';
    var row = document.createElement('div'); row.className = 'row';
    var lab = document.createElement('label'); lab.className = 'grow';
    lab.textContent = spec.label;
    row.appendChild(lab); row.appendChild(tag(spec.verified));
    c.appendChild(row);

    if (spec.kind === 'report') {
      var pre = document.createElement('pre');
      pre.className = 'mono'; pre.id = 'out-' + spec.id; pre.textContent = '…';
      c.appendChild(pre);

    } else if (spec.kind === 'number') {
      var r2 = document.createElement('div'); r2.className = 'row';
      var inp = document.createElement('input');
      inp.type = 'number'; inp.id = 'in-' + spec.id;
      if (spec.min !== undefined) inp.min = spec.min;
      if (spec.max !== undefined) inp.max = spec.max;
      if (spec.step !== undefined) inp.step = spec.step;
      var btn = document.createElement('button');
      btn.textContent = 'Set';
      btn.onclick = function () {
        var v = Number(inp.value);
        if (!isFinite(v)) { log(spec.label + ': not a number', true); return; }
        var res = api(spec.id, 'write', { value: v }, CUR, OUT);
        if (afterWrite(spec, res)) log(spec.label + ' → ' + v);
      };
      r2.appendChild(inp); r2.appendChild(btn);
      c.appendChild(r2);

    } else {
      var r3 = document.createElement('div'); r3.className = 'row';
      var getters = paramControls(spec, r3);
      var run = document.createElement('button');
      run.textContent = 'Apply';
      run.onclick = function () {
        var p = {};
        Object.keys(getters).forEach(function (k) { p[k] = getters[k](); });
        var res = api(spec.id, 'run', p, CUR, OUT);
        if (afterWrite(spec, res)) {
          log(spec.label + (Object.keys(p).length ? ' (' + JSON.stringify(p) + ')' : ''));
          (res.log || '').split('\n').forEach(function (l) { if (l.trim()) log('   ' + l.trim()); });
          refreshReports();
        }
      };
      r3.appendChild(run);
      c.appendChild(r3);
    }

    var h = helpBlock(spec.help);
    if (h) c.appendChild(h);
    return c;
  }

  function buildUI() {
    var host = el('groups'); host.textContent = '';
    var groups = [];
    state.manifest.forEach(function (s) {
      if (groups.indexOf(s.group) < 0) groups.push(s.group);
    });
    groups.forEach(function (g) {
      var h = document.createElement('h2'); h.textContent = g; host.appendChild(h);
      state.manifest.filter(function (s) { return s.group === g; })
        .sort(function (a, b) { return (a.order || 0) - (b.order || 0); })
        .forEach(function (s) { host.appendChild(card(s)); });
    });
  }

  /* ------------------------------------------------------------------- file */

  function openSave(file) {
    state.name = file.name.replace(/\.sav$/i, '') + '-edited.sav';
    status('Reading ' + file.name + '…');
    file.arrayBuffer()
      .then(function (buf) {
        return boot().then(function () {
          var bytes = new Uint8Array(buf);
          state.py.FS.writeFile(IN, bytes);
          state.py.FS.writeFile(CUR, bytes);
          state.dirty = false;
          el('download').disabled = true;
          el('revert').disabled = true;
          el('log').textContent = '';
          if (!state.manifest) return getJSON('manifest.json').then(function (m) {
            state.manifest = m; buildUI();
          });
        });
      })
      .then(function () {
        el('editor').className = '';
        refreshReports();
        log('Opened ' + file.name);
        status('');
      })
      .catch(function (e) { status(''); log(String(e && e.message || e), true); });
  }

  function download() {
    var bytes = state.py.FS.readFile(CUR);
    var blob = new Blob([bytes], { type: 'application/octet-stream' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = state.name;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 5000);
    log('Downloaded ' + state.name);
  }

  /* ------------------------------------------------------------------- wire */

  window.addEventListener('DOMContentLoaded', function () {
    el('src').innerHTML = 'Source, format notes and the research behind it: ' +
      '<a href="' + REPO + '">' + REPO.replace('https://', '') + '</a>';

    el('file').addEventListener('change', function (e) {
      if (e.target.files && e.target.files[0]) openSave(e.target.files[0]);
    });

    var drop = el('drop');
    ['dragenter', 'dragover'].forEach(function (t) {
      drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add('over'); });
    });
    ['dragleave', 'drop'].forEach(function (t) {
      drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.remove('over'); });
    });
    drop.addEventListener('drop', function (e) {
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0])
        openSave(e.dataTransfer.files[0]);
    });

    el('download').addEventListener('click', download);
    el('revert').addEventListener('click', function () {
      state.py.FS.writeFile(CUR, state.py.FS.readFile(IN));
      state.dirty = false;
      el('download').disabled = true; el('revert').disabled = true;
      log('Reverted to the file you opened');
      refreshReports();
    });

    window.addEventListener('beforeunload', function (e) {
      if (state.dirty) { e.preventDefault(); e.returnValue = ''; }
    });
  });
})();
