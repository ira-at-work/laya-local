"""Known-answer check: 16 hand-labelled support messages, department + refund."""
import sys

import laya

REV = "7b928d828b7b0e022f929d9bd2e44165aa270148"
DEPTS = ["billing", "technical support", "sales", "account management"]
QUESTIONS = {
    "refund": {"type": "noul", "instructions": "Does the customer request a refund?"},
    "dept": {"type": "choice", "instructions": "Which team should handle this?", "criteria": DEPTS},
}
# (text, department, requests_refund)
CASES = [
    ("We were billed twice this month. Please refund the duplicate charge.", "billing", True),
    ("My invoice shows a charge for a plan I never signed up for. I want my money back.", "billing", True),
    ("Can you send me a copy of last quarter's invoices for our accountant?", "billing", False),
    ("Why did the price on my renewal go up by 20%?", "billing", False),
    ("The app crashes every time I open the export screen on Android 14.", "technical support", False),
    ("I keep getting a 502 error when calling your API since this morning.", "technical support", False),
    ("The software never worked on my machine. Refund me, I'm done.", "technical support", True),
    ("Login with SSO fails with 'invalid SAML assertion'.", "technical support", False),
    ("We're a 200-seat company. What would an enterprise plan cost?", "sales", False),
    ("Do you offer volume discounts if we upgrade 50 licences?", "sales", False),
    ("I'd like a demo of the analytics add-on before we buy.", "sales", False),
    ("Please change the owner of our account to jane@example.com.", "account management", False),
    ("I need to add three new users and change our billing contact.", "account management", False),
    ("Close my account and delete my data. No refund needed.", "account management", False),
    ("Cancel my subscription and refund this year's payment, I never used it.", "account management", True),
    ("Thanks, the issue is resolved now. No further action needed.", "technical support", False),
]

device = sys.argv[1] if len(sys.argv) > 1 else "mps"
agent = laya.load("convaiinnovations/laya", subfolder="typed-decisions", device=device, revision=REV)
dept_ok = refund_ok = 0
for text, dept, refund in CASES:
    a = agent.predict(text, QUESTIONS)["answers"]
    got_dept, p = a["dept"]["choice"], a["refund"]["noul"]
    d, r = got_dept == dept, (p >= 0.5) == refund
    dept_ok += d
    refund_ok += r
    print(f"{'ok ' if d else 'BAD'} dept={got_dept!r:22} (want {dept!r:22}) conf={a['dept']['confidence']:.2f} | "
          f"{'ok ' if r else 'BAD'} P(refund)={p:.2f} (want {refund}) | {text[:50]}")
n = len(CASES)
print(f"\ndept {dept_ok}/{n}  refund {refund_ok}/{n}  (refund majority-class baseline: {sum(not c[2] for c in CASES)}/{n})")
