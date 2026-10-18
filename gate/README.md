# Bash command gate (observe-only)

Collects Laya's risk scores for every Bash command Claude Code runs, so you can judge afterwards whether the model is worth enforcing on. It never allows, denies or alters anything.

```
Claude Code ──PreToolUse──▶ hook.py ──unix socket──▶ daemon.py (model resident)
   (Bash)       (stdlib,      (fire and forget)         │
                 ~20 ms)                                 ▼
                                          ~/.laya-gate/decisions.jsonl
```

- `hook.py` forwards `{command, cwd, session_id}` and exits 0 with no output. If the daemon is down, the command runs untouched and the hook prints one line to stderr. **Logging then stops silently**, so check the daemon is up (below).
- `daemon.py` scores three `noul` questions (destructive, exfil, privesc) per command and appends one JSON line. It truncates commands to 1500 characters for scoring (the log keeps the full text). It refuses to start if one is already listening and clears a stale socket.
- Scores are uncalibrated probabilities: ranking within a question is meaningful, absolute thresholds are not until fitted with `laya.calibrate` on labelled data.

## Install

1. Dependencies: `uv sync --frozen` in the repo root.
2. Start the daemon (first run downloads the pinned weights, then loads in ~15 s):
   ```
   uv run --frozen python -I gate/daemon.py mps
   ```
   Use `cpu` instead of `mps` off Apple silicon.
3. Register the hook in Claude Code `settings.json`, in the `PreToolUse` list with matcher `Bash`:
   ```json
   {"type": "command", "command": "python3 -I /ABSOLUTE/PATH/TO/laya-local/gate/hook.py", "timeout": 5}
   ```
   Check the [hooks documentation](https://code.claude.com/docs/en/hooks) for the current settings layout; the field names above are what worked here.
4. Run a Bash command in Claude Code and confirm `~/.laya-gate/decisions.jsonl` gained a line.

### Keeping the daemon running (macOS launchd)

Running it in a terminal or as a child of a Claude session means it dies with that process. [`com.example.laya-gate.plist`](com.example.laya-gate.plist) is a user-agent template (starts at login, restarts on exit). Copy it, replace the `/ABSOLUTE/PATH/...` placeholders, then:

```
mkdir -p ~/.laya-gate
plutil -lint ~/Library/LaunchAgents/com.example.laya-gate.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.laya-gate.plist
launchctl print gui/$(id -u)/com.example.laya-gate | grep -E 'state|pid'
```

Restart with `launchctl kickstart -k gui/$(id -u)/com.example.laya-gate`. Stop with `launchctl bootout gui/$(id -u)/com.example.laya-gate`; killing the process alone does not work because `KeepAlive` restarts it. Not tested here: automatic restart after a crash. `launchctl` syntax is from `man launchctl` (Darwin 25.6).

## Log format

One JSON object per line:

| Field | Meaning |
|---|---|
| `ts` | Unix time |
| `session_id`, `cwd` | from Claude Code's hook input |
| `command` | full command text, **plaintext** |
| `truncated` | true if the command exceeded the 1500-char scoring window |
| `scores` | `{destructive, exfil, privesc}`, P(yes) in 0..1 |
| `ms` | scoring time in milliseconds |

Quick health check and distribution (no dependencies):

```
python3 -I - <<'PY'
import json, os, statistics as st
rs = [json.loads(l) for l in open(os.path.expanduser("~/.laya-gate/decisions.jsonl"))]
print(len(rs), "records,", len({r["session_id"] for r in rs}), "sessions, median", st.median(r["ms"] for r in rs), "ms")
for q in ("destructive", "exfil", "privesc"):
    v = sorted(r["scores"][q] for r in rs)
    print(q, "p10/median/p90:", v[len(v)//10], v[len(v)//2], v[9*len(v)//10])
PY
```

## Evaluating it

The log has no ground truth. The intended procedure (see `docs/session-2026-10-15.md`, section 11):

1. Collect at least ~200 commands.
2. Label each by hand: risky or benign, per question.
3. Per question, compute AUC and the false-positive rate at the thresholds you would use; fit temperatures with `laya.calibrate`.
4. Compare against a plain regex over your existing deny list. If the regex matches the model, drop the model.

## Privacy and removal

- The log stores every command in full, including any secrets typed into it. It is created mode 0600 in a 0700 directory, has no rotation, and should be reviewed before it is shared anywhere.
- To disable: remove the hook entry from `settings.json`, stop the daemon (`launchctl bootout` if using launchd), and delete `~/.laya-gate/` if you no longer want the log.
