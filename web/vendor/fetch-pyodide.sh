#!/bin/sh
# Fetch the Pyodide core runtime into web/vendor/pyodide for local development.
# CI does the same thing in .github/workflows/pages.yml, so the runtime is never
# committed - the repo stays small and the deployed site still serves it from
# its own origin.
set -eu
VER="${PYODIDE_VERSION:-0.26.4}"
DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$DIR/pyodide/pyodide.js" ]; then
  echo "already present: $DIR/pyodide"
  exit 0
fi

URL="https://github.com/pyodide/pyodide/releases/download/${VER}/pyodide-core-${VER}.tar.bz2"
if ! curl -sfIL "$URL" >/dev/null; then
  echo "pyodide-core ${VER} not found; using the latest release instead" >&2
  VER=$(curl -s https://api.github.com/repos/pyodide/pyodide/releases/latest \
        | grep -o '"tag_name": *"[^"]*"' | head -1 | cut -d'"' -f4)
  URL="https://github.com/pyodide/pyodide/releases/download/${VER}/pyodide-core-${VER}.tar.bz2"
fi

echo "fetching pyodide ${VER}"
curl -fL "$URL" -o /tmp/pyodide-core.tar.bz2
tar -xjf /tmp/pyodide-core.tar.bz2 -C "$DIR"
rm -f /tmp/pyodide-core.tar.bz2
test -f "$DIR/pyodide/pyodide.js" || { echo "unexpected tarball layout" >&2; exit 1; }
du -sh "$DIR/pyodide"
