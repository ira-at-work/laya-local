import resource, statistics, sys, time

import laya

REV = "7b928d828b7b0e022f929d9bd2e44165aa270148"
STATE = {"subject": "Charged twice for order 8841", "body": "We were billed twice. Please refund the duplicate, and cancel my subscription."}
QUESTIONS = {
    "department": {"type": "choice", "instructions": "Which team should handle this?",
                   "criteria": ["billing", "technical support", "sales", "account management"]},
    "refund": {"type": "noul", "instructions": "Does the customer request a refund?"},
    "cancel": {"type": "noul", "instructions": "Does the customer want to cancel?"},
    "urgency": {"type": "score", "instructions": "How urgent is this request?",
                "criteria": ["No time pressure", "Mild, can wait days", "Moderate, should be handled today", "High, blocking the customer", "Critical, outage or financial loss"]},
}

device = sys.argv[1]
agent = laya.load("convaiinnovations/laya", subfolder="typed-decisions", device=device, revision=REV)
for _ in range(3):
    agent.predict(STATE, QUESTIONS)
ts = []
for _ in range(20):
    t = time.perf_counter(); r = agent.predict(STATE, QUESTIONS); ts.append((time.perf_counter() - t) * 1000)
print(f"{device}: 4 questions median {statistics.median(ts):.0f} ms (p90 {sorted(ts)[17]:.0f}), {statistics.median(ts)/4:.0f} ms/question; peak RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**30:.2f} GB")
print(r["answers"])
