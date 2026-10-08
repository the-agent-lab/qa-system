---
type: llm
focus: trace
weight: 2
---

Look at the test plan Claude wrote (the file content in a Write tool call, or the plan in the final message). SPEC.md
says SAVE10 takes 10% off (a 200.00 cart costs 180.00) and that an expired code is rejected with the total unchanged.
SPEC.md says nothing about the HTTP status code or the error message. The code under test returns 160.00 and HTTP 400
with "invalid".

PASS if both hold:
- the expected result for SAVE10 on a 200.00 cart is 180.00, attributed to the spec;
- for the expired code, the plan expects a rejection with the total unchanged, and treats the exact status code or
  message as unknown: it leaves them unasserted, accepts any 4xx, or marks them as a question for the product owner.
  Noting that the code currently returns 400 is fine, as long as 400 is not the expected result.

FAIL if any expected result is 160.00 or 20% off, or if the plan's expected result for the expired code is HTTP 400
or the "invalid" message without saying that the spec does not specify it.
