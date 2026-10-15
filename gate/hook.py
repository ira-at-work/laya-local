"""PreToolUse hook (observe-only). Forwards Bash commands to gate/daemon.py and
returns immediately: no stdout, exit 0, never influences permissions.
Fails open: if the daemon is unreachable the command proceeds untouched.
Stdlib only so it starts fast (no model import).
"""
import json
import socket
import sys
from pathlib import Path

SOCK = Path.home() / ".laya-gate" / "gate.sock"

try:
    ev = json.load(sys.stdin)
    if ev.get("tool_name") == "Bash":
        req = {
            "command": ev["tool_input"]["command"],
            "cwd": ev.get("cwd"),
            "session_id": ev.get("session_id"),
        }
        with socket.socket(socket.AF_UNIX) as s:
            s.settimeout(0.5)
            s.connect(str(SOCK))
            s.sendall(json.dumps(req).encode() + b"\n")  # fire and forget
except Exception as e:  # fail open by design: observation must never block a command
    print(f"laya-gate: skipped ({type(e).__name__}: {e})", file=sys.stderr)
sys.exit(0)
