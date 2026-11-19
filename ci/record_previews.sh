#!/usr/bin/env bash
# Record every plugin's preview.gif with the firmware's tools/preview.py.
# FIRMWARE: a checkout of martinwoodward/gitmatrix (default ./firmware).
# OUT: write <OUT>/<plugin>.gif instead of <plugin>/preview.gif.
# A plugin that fails to record keeps its previous preview (or its thumbnail) and
# only warns, so one plugin can't block publishing the rest.
set -u
cd "$(dirname "$0")/.."
TOOL="${FIRMWARE:-firmware}/gitmatrix/tools/preview.py"
if [ ! -f "$TOOL" ]; then
  echo "::warning::$TOOL not found, previews not recorded"
  exit 0
fi
[ -n "${OUT:-}" ] && mkdir -p "$OUT"
for init in */__init__.py; do
  plugin="${init%/__init__.py}"
  [ "$plugin" = firmware ] && continue
  out="${OUT:+$OUT/$plugin.gif}"
  if ! python3 "$TOOL" "$plugin" ${out:+-o "$out"}; then
    echo "::warning::couldn't record a preview of $plugin"
  fi
done
