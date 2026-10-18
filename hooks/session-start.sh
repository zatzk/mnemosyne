#!/usr/bin/env bash
# Mnemosyne SessionStart hook: ambient due-count nudge & stale stash recovery prompt.
# Must never break a session: degrades cleanly to exit 0 on any failure.
set -u

command -v python3 >/dev/null 2>&1 || exit 0

emit_json() {
  python3 - "$1" <<'PY' 2>/dev/null || true
import json, sys
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": sys.argv[1]
    }
}))
PY
}

ROOT="${MNEMOSYNE_ROOT:-${ZCODE_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_PLUGIN_ROOT:-}}}}"
if [ -z "$ROOT" ] || [ ! -f "$ROOT/scripts/mnemosyne.py" ]; then
  ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")/.." 2>/dev/null && pwd)"
fi
[ -f "$ROOT/scripts/mnemosyne.py" ] || exit 0

NUDGE="$(python3 "$ROOT/scripts/mnemosyne.py" session-start 2>/dev/null || true)"
if [ -z "$NUDGE" ]; then
  # Fallback to status summary if session-start outputs nothing
  NUDGE="$(python3 "$ROOT/scripts/mnemosyne.py" status --brief 2>/dev/null || true)"
fi
[ -n "$NUDGE" ] || exit 0

case "${MNEMOSYNE_HOOK_FORMAT:-}" in
  json) emit_json "$NUDGE"; exit 0 ;;
esac

if [ -n "${ZCODE_PLUGIN_ROOT:-}" ]; then
  emit_json "$NUDGE"
  exit 0
fi

printf '%s\n' "$NUDGE"
exit 0
