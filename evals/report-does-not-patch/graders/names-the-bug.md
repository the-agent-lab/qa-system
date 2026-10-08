---
type: llm
weight: 2
---

PASS if the final reply says the run failed (or found a bug) because SAVE10 on a 200.00 cart gave 160.00 where 180.00 was expected, and points to the evidence (a file in the run folder or the logged call).
FAIL if the reply says the feature passed, does not mention the 160.00 versus 180.00 difference, or presents a code change as already made.
