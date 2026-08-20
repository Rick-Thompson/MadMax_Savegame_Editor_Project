#!/usr/bin/env python3
"""Snapshot every Mad Max autosave as it is written.

  watch_saves.py WATCHDIR SNAPDIR [--poll 0.4]

Polls the save directory and copies any slot file whose contents change into
SNAPDIR as NNN_slotSS_ptNNNN.sav (sequence, slot number, play time in seconds).
Identical writes are skipped, and a partially-written file is detected by its
checksum delta and re-read on the next tick rather than snapshotted.

Autosaves fire on almost every state change, so a task that takes a minute
produces several frames. The frames on either side of a completion show what
the tables do at the moment it happens, and the frames during ordinary driving
give a baseline for what churns anyway.
"""
import os, sys, time, shutil, struct, hashlib, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('m', os.path.join(HERE,'madmax_save.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

watch, snap = sys.argv[1], sys.argv[2]
poll = float(sys.argv[sys.argv.index('--poll')+1]) if '--poll' in sys.argv else 0.4
os.makedirs(snap, exist_ok=True)
log = open(os.path.join(snap,'watch.log'),'a',buffering=1)
seen, seq = {}, len([f for f in os.listdir(snap) if f.endswith('.sav')])
log.write("=== watching %s -> %s (poll %.1fs, starting seq %d) ===\n"%(watch,snap,poll,seq))

while True:
    try:
        for fn in sorted(os.listdir(watch)):
            if not fn.startswith('GameSave') or not fn.endswith('.sav'):
                continue
            p = os.path.join(watch, fn)
            try:
                st = os.stat(p)
                if fn in seen and (st.st_mtime, st.st_size) == seen[fn][:2]:
                    continue
                # read twice: a save caught mid-write will differ between reads
                data = open(p,'rb').read()
                time.sleep(0.15)
                if open(p,'rb').read() != data:
                    continue                               # still being written
            except (OSError, IOError):
                continue
            h = hashlib.sha1(data).hexdigest()
            if seen.get(fn, (0,0,''))[2] == h:
                seen[fn] = (st.st_mtime, st.st_size, h); continue
            if len(data) < 0x100 or len(data) % 512:
                continue
            try:
                d = m.xor(data); hd = m.header(d)
                if hd['magic'] != m.MAGIC: continue
                # payload must fit the file - catches a truncated write
                if hd['payload_end'] > len(d): continue
                pt, slot = hd['playtime_s'], hd['slot']
            except Exception:
                continue
            out = os.path.join(snap, "%03d_slot%02d_pt%d.sav"%(seq, slot, pt))
            shutil.copyfile(p, out)
            log.write("%s  %-28s from %s  %d bytes  playtime %d\n"%(
                time.strftime('%H:%M:%S'), os.path.basename(out), fn, len(data), pt))
            seen[fn] = (st.st_mtime, st.st_size, h); seq += 1
        time.sleep(poll)
    except KeyboardInterrupt:
        break
    except Exception as e:
        log.write("error: %r\n"%e); time.sleep(1)
