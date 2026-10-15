"""Compaction replay, step 1: extract tool results from Claude Code transcripts and
auto-label whether later assistant output reused anything new from them.

A result is "needed" if some token (path/identifier-like, >=8 chars) that is new in
the result (absent from its own call input and from all earlier text) appears later in
assistant text or tool_use inputs. "needed10" restricts the lookup to the next 10
assistant turns. Token counts are chars/4 estimates, not a tokenizer.

Writes JSONL (metadata only, no result text) and prints an oracle summary.
    python3 -I compaction/replay.py OUT.jsonl [GLOB]
"""
import bisect
import collections
import glob
import json
import re
import sys
from pathlib import Path

TOK = re.compile(r"[A-Za-z0-9_./~-]{8,}")
ROOT = Path.home() / ".claude/projects"


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def session_items(path):
    calls, events, assistant_turn = {}, [], 0
    out_tokens = collections.defaultdict(list)  # token -> assistant turn indices (sorted)
    seen = set()
    for line in open(path, errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("isSidechain") or r.get("type") not in ("assistant", "user"):
            continue
        content = r["message"].get("content")
        if not isinstance(content, list):
            continue
        if r["type"] == "assistant":
            assistant_turn += 1
            for b in content:
                if b.get("type") == "tool_use":
                    s = json.dumps(b.get("input", {}))
                    calls[b["id"]] = (b.get("name", "?"), s)
                    toks = set(TOK.findall(s))
                elif b.get("type") == "text":
                    toks = set(TOK.findall(b.get("text", "")))
                else:
                    continue
                for t in toks:
                    out_tokens[t].append(assistant_turn)
                seen |= toks
        else:
            for b in content:
                if b.get("type") == "tool_result":
                    txt = text_of(b.get("content"))
                    name, call = calls.get(b.get("tool_use_id"), ("?", ""))
                    new = set(TOK.findall(txt)) - set(TOK.findall(call)) - seen
                    events.append((name, len(txt), assistant_turn, new))
                    seen |= set(TOK.findall(txt))
                elif b.get("type") == "text":
                    seen |= set(TOK.findall(b.get("text", "")))
    for name, n, turn, new in events:
        first = min((out_tokens[t][i] for t in new if (i := bisect.bisect_right(out_tokens[t], turn)) < len(out_tokens[t])), default=None)
        yield {"tool": name, "chars": n, "turn": turn, "new_anchors": len(new),
               "needed": first is not None, "needed10": first is not None and first - turn <= 10}


def main():
    out = sys.argv[1]
    files = sorted(glob.glob(str(ROOT / (sys.argv[2] if len(sys.argv) > 2 else "*/*.jsonl"))))
    n = 0
    tot = collections.Counter()
    by_tool = collections.defaultdict(collections.Counter)
    with open(out, "w") as f:
        for p in files:
            for it in session_items(p):
                it["session"] = Path(p).stem
                f.write(json.dumps(it) + "\n")
                n += 1
                tk = it["chars"] / 4
                for c in (tot, by_tool[it["tool"]]):
                    c["results"] += 1
                    c["tokens"] += tk
                    c["unneeded_tokens"] += tk * (not it["needed"])
                    c["unneeded10_tokens"] += tk * (not it["needed10"])
    print(f"files={len(files)} results={n}")
    t = tot
    print(f"result tokens (est) {t['tokens']:.0f}; never reused later {t['unneeded_tokens'] / t['tokens']:.1%}; not reused within 10 turns {t['unneeded10_tokens'] / t['tokens']:.1%}")
    print("by tool (results, est tokens, % tokens never reused):")
    for name, c in sorted(by_tool.items(), key=lambda kv: -kv[1]["tokens"])[:12]:
        print(f"  {name:20} {c['results']:6} {c['tokens']:12.0f} {c['unneeded_tokens'] / max(c['tokens'], 1):.1%}")


if __name__ == "__main__":
    main()
