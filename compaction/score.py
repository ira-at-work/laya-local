"""Compaction replay, step 3: score sampled tool results with Laya keep/drop questions and
compare against the reuse labels and simple baselines.

Two questions run as separate calls and again jointly, to test whether co-asked questions
change each other's answers (vendor claim, unverified).
    uv run --frozen python -I compaction/score.py SAMPLE.jsonl SCORED.jsonl [device]
"""
import json
import statistics
import sys
import time

import laya

REV = "7b928d828b7b0e022f929d9bd2e44165aa270148"
HEAD, TAIL = 1800, 700  # chars of result shown to the model; window is ~4096 tokens
QA = {"type": "noul", "instructions": "Will the assistant need specific details from this tool result (names, values, errors, code) to continue the task?"}
QB = {"type": "noul", "instructions": "Is this tool result routine noise (passed checks, listings, confirmations, banners) with nothing needed later?"}


def clip(s):
    return s if len(s) <= HEAD + TAIL else s[:HEAD] + "\n[...]\n" + s[-TAIL:]


def auc(scores, labels):
    """P(score of a positive > score of a negative), ties 0.5."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def main():
    device = sys.argv[3] if len(sys.argv) > 3 else "mps"
    rows = [json.loads(line) for line in open(sys.argv[1])]
    agent = laya.load("convaiinnovations/laya", subfolder="typed-decisions", device=device, revision=REV)
    ms = []
    for r in rows:
        state = {"task": r["task"][:400], "tool": r["tool"], "call": r["call"][:300], "result": clip(r["result"])}
        t = time.perf_counter()
        a = agent.predict(state, {"a": QA})["answers"]["a"]["noul"]
        ms.append((time.perf_counter() - t) * 1000)
        j = agent.predict(state, {"a": QA, "b": QB})["answers"]
        r.update(pa=a, pa_joint=j["a"]["noul"], pb_joint=j["b"]["noul"])
    with open(sys.argv[2], "w") as f:  # scores + labels only, no transcript text
        for r in rows:
            f.write(json.dumps({k: v for k, v in r.items() if k not in ("result", "call", "task")}) + "\n")

    n = len(rows)
    print(f"n={n} single-question latency median {statistics.median(ms):.0f} ms p90 {sorted(ms)[int(.9 * n)]:.0f} ms ({device})")
    print(f"question independence: mean |pa - pa_joint| = {statistics.mean(abs(r['pa'] - r['pa_joint']) for r in rows):.4f}, max {max(abs(r['pa'] - r['pa_joint']) for r in rows):.4f}")
    sig = {"A keep-prob": [r["pa"] for r in rows], "B noise-prob (inverted)": [-r["pb_joint"] for r in rows],
           "size (chars)": [r["chars"] for r in rows], "new_anchors": [r["new_anchors"] for r in rows]}
    for lab in ("needed", "needed10"):
        ys = [r[lab] for r in rows]
        print(f"\nlabel={lab}  positives {sum(ys)}/{n}")
        for name, s in sig.items():
            print(f"  AUC {name:26} {auc(s, ys):.3f}")
    print("\nthreshold sweep on A keep-prob (drop if P < t); tokens = chars/4")
    tot = sum(r["chars"] for r in rows)
    for lab in ("needed", "needed10"):
        need_tot = sum(r["chars"] for r in rows if r[lab])
        print(f" label={lab}: base rate {sum(r[lab] for r in rows) / n:.2f}")
        for t in (0.3, 0.4, 0.5, 0.6, 0.7):
            d = [r for r in rows if r["pa"] < t]
            if not d:
                continue
            miss = [r for r in d if r[lab]]
            print(f"   t={t}: dropped {len(d):3} results, {sum(r['chars'] for r in d) / tot:5.1%} of tokens saved, "
                  f"missed {len(miss):3} needed results ({sum(r['chars'] for r in miss) / need_tot:5.1%} of needed tokens), "
                  f"precision of drops {1 - len(miss) / len(d):.2f}")
    print("\nscore distribution A:", {q: round(statistics.quantiles([r['pa'] for r in rows], n=10)[i], 3) for q, i in (("p10", 0), ("p50", 4), ("p90", 8))})


if __name__ == "__main__":
    main()
