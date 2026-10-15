# Handover (written 2026-10-15)

Full narrative, measurements, vetting tables and conclusions: `docs/session-2026-10-15.md` (sections 7-11 cover the gate, the compaction replay, conclusions and open tests). This file is only the "how to pick it back up" sheet.

## State at hand-off

| Item | State |
|---|---|
| `laya-local` repo | clean, master, last commit `3df8e7bab3`. `laya==0.4.8`, `uv.lock` committed |
| Pinned model revision | `7b928d828b7b0e022f929d9bd2e44165aa270148` (`typed-decisions`) |
| Gate hook | registered in `settings.json` (PreToolUse, Bash, timeout 5). Observe-only, fail-open, ~20 ms per command |
| Gate daemon | running **as a background task of the Claude session that started it** (pid seen 69510). Unverified, but it will probably die when that session ends; the hook then silently does nothing (fail-open), so **logging stops without any error** |
| Gate log | `~/.laya-gate/decisions.jsonl` (mode 0600, plaintext commands), 33 records at hand-off |
| Compaction replay | finished, negative result, nothing installed in Claude Code |
| TypeSafe plugin | installed (`typesafe@typesafe-ai` 0.5.7), vetted; `~/.claude/skills/laya-local` overlay holds the Laya-specific API notes |
| Dotfiles | `~/.homesick/repos/dotclaude/home/.claude/settings.json` has the hook edit **uncommitted**, together with unrelated pre-existing churn |

## To resume the gate experiment

1. Start the daemon in its own terminal so it outlives Claude sessions:
   `cd /Users/ira/src/laya-local && nice uv run --frozen python -I gate/daemon.py mps`
   (it refuses to start if one is already listening; a stale socket is cleaned up automatically).
2. Check it is logging: `wc -l ~/.laya-gate/decisions.jsonl` should grow after Bash commands in any Claude session.
3. Let it accumulate (target at least 200 commands). The log holds full command text, so review it before sharing anywhere and consider rotating it.
4. Label the log by hand (risky or benign per question), then follow `docs/session-2026-10-15.md` section 11, item 1: per-question AUC, false-positive rate, `laya.calibrate` fit, and comparison against a regex version of the existing deny list. If the regex matches Laya, drop the model.

To turn the gate off: remove the `laya-local/gate/hook.py` entry from `PreToolUse` in `settings.json` (edit the target under `~/.homesick/repos/dotclaude`, since `~/.claude/settings.json` is a symlink), or just stop the daemon.

## To rerun the compaction replay

```
python3 -I compaction/replay.py /tmp/replay/items.jsonl          # oracle labels over all transcripts
python3 -I compaction/sample.py /tmp/replay/sample.jsonl 400      # seeded sample with text (private)
uv run --frozen python -I compaction/score.py /tmp/replay/sample.jsonl /tmp/replay/scored.jsonl mps
```
Results will drift slightly because transcripts keep growing. Sample and score files under `/tmp/replay/` contain private transcript text (the scored file holds scores and labels only).

## Waiting on explicit user authorization (nothing below was done)

- Delete quarantine dirs: `/var/folders/qc/bs_g9d1d6fl2wxwwgl45h17c0000gn/T/tbi-quarantine.*` (eight third-party repos plus `TZgHr8`) and `laya-q.ZNSRxs` in the same directory.
- Delete `/tmp/tbi-reports.5DzTzi`, `/tmp/tbi-lmcp-code.*`, `/tmp/ss_sum.py`, and `/tmp/replay/` (private transcript text).
- Commit the dotfiles `settings.json` change, and sync `~/.claude/skills/laya-local` into dotfiles.
- Any use of `sudo` (standing rule: only with an explicit go-ahead).

## Known gaps

- No linter or diagnostics run on `gate/` or `compaction/` (`mcp__ide__getDiagnostics` was unavailable). Only run-tested.
- Dependency-CVE scanning of third-party packages never completed (trivy needs `docker-credential-osxkeychain`).
- The `serve`, `mcp`, `onnx` and `fast` extras remain uninstalled and unvetted.
- `laya` ships releases very frequently; re-run test-before-install before any version bump and keep `revision=` pinned.
