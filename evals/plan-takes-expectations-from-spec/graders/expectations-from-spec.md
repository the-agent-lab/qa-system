---
type: llm
focus: trace
weight: 2
---

Look at the test plan Claude wrote (the file content in a Write tool call, or the plan in the final message).

PASS if the plan's expected result for SAVE10 on a 200.00 cart is 180.00 (10% off) and its expected result for the expired code is HTTP 422 with "Code expired", both attributed to SPEC.md or the spec. Mentioning that the code currently does something else is fine and even good.

FAIL if any expected result in the plan is 160.00, 20% off, or HTTP 400 for the expired code (that is the code's behaviour, not the spec's), or if the plan has no explicit expected results.
