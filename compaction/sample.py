"""Compaction replay, step 2: draw a seeded sample of tool results WITH text for scoring.
The output contains private transcript content: keep it outside the repo.
    python3 -I compaction/sample.py OUT.jsonl [N=400]
"""
import glob
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # -I drops the script dir
from replay import ROOT, session_items  # noqa: E402

MIN_CHARS = 300  # smaller results are not worth compacting
random.seed(0)
n = int(sys.argv[2]) if len(sys.argv) > 2 else 400
pool = []
for p in sorted(glob.glob(str(ROOT / "*/*.jsonl"))):
    for i, it in enumerate(session_items(p, with_text=True)):
        if it["chars"] >= MIN_CHARS:
            it["session"], it["idx"] = Path(p).stem, i
            pool.append(it)
sample = random.sample(pool, min(n, len(pool)))
with open(sys.argv[1], "w") as f:
    for it in sample:
        f.write(json.dumps(it) + "\n")
print(f"pool={len(pool)} sampled={len(sample)} needed10={sum(i['needed10'] for i in sample)} needed={sum(i['needed'] for i in sample)}")
