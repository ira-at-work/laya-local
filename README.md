# laya-local

Notes, scripts and measurements from running [Laya](https://huggingface.co/convaiinnovations/laya) (Convai Innovations, Apache-2.0) locally as a small "typed decisions" model for coding-agent tooling. It is the open-source counterpart of TypeSafe's hosted Jev.

The question: can a ~2.7 GB local model that answers yes/no, choice and score questions about a piece of text be useful inside Claude Code, specifically for (a) gating Bash commands and (b) deciding which tool results to drop when compacting context?

Short answer, on one machine and one user's data: it handles narrow, lexically obvious yes/no questions well, and it does not beat chance on "will the agent need this tool result later". Everything here is small-sample and self-made; read the caveats before quoting any number.

Full write-up, with verified/reported/unverified labels on every claim: [`docs/session-2026-10-15.md`](docs/session-2026-10-15.md).

## Results

All numbers are from an M3 Pro (11 cores, 36 GB), `laya==0.4.8`, checkpoint `convaiinnovations/laya` subfolder `typed-decisions`, pinned to revision `7b928d828b7b0e022f929d9bd2e44165aa270148`.

| Experiment | Result |
|---|---|
| Latency, 4 questions on a short state, warm | MPS ~100 ms (~25 ms/question), CPU ~300 ms; peak RSS ~2.7 GB |
| Latency, one question on a ~1k-token state | median 221 ms (p90 305 ms): latency scales with input length |
| Refund detection (`noul`), 16 hand-labelled support messages | 16/16 (majority baseline 12/16) |
| 4-way department (`choice`), same 16 messages | 10/16 (some labels debatable) |
| Compaction replay: keep/drop AUC against reuse labels, n=400 | Laya 0.544, result size 0.659 |
| Question independence, two `noul` questions, n=400 | answers identical to 4 decimals alone vs together |
| Bash gate smoke test, 6 commands | right top class on 3 of 4 risky commands (not an evaluation) |

### Compaction replay (negative result)

The replay walked 28,626 real tool results (about 14.1M estimated tokens, chars/4) from local Claude Code transcripts and labelled each as needed or not, based on whether a new identifier-like token from it was reused in later assistant output.

- Under that labeler, 41.1% of result tokens were never reused (56.2% not within 10 turns). This is the ceiling for a perfect compactor and is probably overstated, since reading something for understanding leaves no verbatim trace.
- Zero-shot Laya scored 0.54 AUC on a 400-result sample. A one-line size heuristic scored 0.66. At the one threshold that dropped anything meaningful, it lost essentially all needed content.
- Conclusion: do not use zero-shot `typed-decisions` for compaction. Deterministic trimming rules or a scorer fitted on labelled data are untested follow-ups.

### Bash gate (observe-only, value not demonstrated)

A resident daemon holds the model and a stdlib-only `PreToolUse` hook forwards each Bash command to it. It scores three `noul` questions (destructive, exfil, privesc), logs the result, never blocks, and fails open. Whether it beats a plain regex over an existing deny list is untested; that needs a few hundred hand-labelled commands.

## Caveats

- Small, self-made evaluation sets; one seed; AUC standard error at n=400 is roughly 0.03.
- Confidence is uncalibrated: the checkpoint ships invalid temperatures (clamped to 0.5).
- The compaction labeler is automatic and crude; the hand check of it was n=20 and done by a model, not independently.
- One person's daily Claude Code usage; results may not transfer to other workloads.
- Vendor and third-party claims in the notes are marked "reported" and were not reproduced, except question independence, which did not reproduce here.
- The notes include a static-only review of eight third-party repos. Nothing was executed and no dependency CVE scan completed, so "not scanned" is not "clean".

## Layout

| Path | Purpose |
|---|---|
| `bench.py` | latency and memory benchmark: `uv run --frozen python -I bench.py mps` |
| `eval.py`, `q.json` | 16-case known-answer check and sample question schema |
| `gate/daemon.py`, `gate/hook.py` | observe-only Bash command scorer and hook |
| `compaction/replay.py` | extract tool results from transcripts and auto-label reuse |
| `compaction/sample.py` | seeded sample with text |
| `compaction/score.py` | Laya keep/drop scoring and AUC/threshold metrics |
| `docs/session-2026-10-15.md` | full notes, measurements, vetting tables, open tests |

## Running it

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```
uv sync --frozen
uv run --frozen python -I bench.py mps        # or cpu
uv run --frozen python -I eval.py mps
```

Compaction replay (reads `~/.claude/projects`, so adjust `ROOT` in `compaction/replay.py` for other layouts):

```
python3 -I compaction/replay.py /tmp/replay/items.jsonl
python3 -I compaction/sample.py /tmp/replay/sample.jsonl 400
uv run --frozen python -I compaction/score.py /tmp/replay/sample.jsonl /tmp/replay/scored.jsonl mps
```

Gate daemon (writes `~/.laya-gate/decisions.jsonl`; see [`gate/README.md`](gate/README.md) for the architecture, log format, launchd service template and evaluation procedure):

```
uv run --frozen python -I gate/daemon.py mps
```

then register `gate/hook.py` as a `PreToolUse` hook on `Bash` in your Claude Code `settings.json`.

### Privacy

- The compaction sample and scored files contain your private transcript text. Keep them out of any repo.
- The gate log stores full Bash command text in plaintext, including any secrets typed into commands (file mode 0600). Review it before sharing.
- Always pass `revision=` when loading the model. Laya releases frequently, and the weights here are pinned to the revision above.

## Status

Written up on 2026-10-15. No active development.

## License

[CC0 1.0](LICENSE): public domain dedication. Laya itself is Apache-2.0 and is not covered by this repo's license.
