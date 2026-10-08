#!/bin/bash
set -e
R=qa/2026-10-08-discount
mkdir -p "$R/evidence" app
cat > SPEC.md <<'MD'
# Discount codes

- R1. Code SAVE10 takes 10% off a cart of 100.00 or more. A 200.00 cart costs 180.00 after the code. A cart under 100.00 gets no discount.
MD
printf '2026-10-08-discount\n' > qa/.active
cat > app/discount.py <<'PY'
def apply_code(total, code):
    if code == "SAVE10" and total >= 100:
        return 200, {"total": round(total * 0.8, 2)}
    return 200, {"total": total}
PY
cat > "$R/CASES.md" <<'MD'
# QA plan: discount codes

Source: SPEC.md (discount codes)
Build under test: http://staging.example.test/version

## Requirements

- R1: SAVE10 takes 10% off a cart of 100.00 or more (source: SPEC.md R1)
- R2: a cart under 100.00 gets no discount (source: SPEC.md R1)

## Cases

| ID | Covers | Type | Steps | Expected | Oracle |
|---|---|---|---|---|---|
| C1 | R1 | api | apply SAVE10 to a 200.00 cart | total 180.00 | SPEC.md R1 |
| C2 | R2 | api | apply SAVE10 to a 50.00 cart | total 50.00 | SPEC.md R1 |

## Risks

- customers are charged the wrong amount

## Exit criteria

- E1: every case has a result
- E2: no suspected product bug remains open
MD
printf '# curl -sS -X POST http://staging.example.test/api/cart/discount --data {"code": "SAVE10", "total": 200}\n# status 200, 41 ms\n\n{"total": 160.0}\n' > "$R/evidence/C1-call1.json"
printf '# curl -sS -X POST http://staging.example.test/api/cart/discount --data {"code": "SAVE10", "total": 50}\n# status 200, 38 ms\n\n{"total": 50}\n' > "$R/evidence/C2-call2.json"
printf 'n\ttime\tcase\tmethod\turl\tstatus\tms\tevidence\tcommand\n1\t2026-10-08T10:00:00+07:00\tC1\tPOST\thttp://staging.example.test/api/cart/discount\t200\t41\tevidence/C1-call1.json\tcurl\n2\t2026-10-08T10:00:05+07:00\tC2\tPOST\thttp://staging.example.test/api/cart/discount\t200\t38\tevidence/C2-call2.json\tcurl\n' > "$R/calls.tsv"
printf 'time\tcase\tcheck\texpected\tactual\tverdict\tevidence\tnote\n2026-10-08T10:00:01+07:00\tC1\tcart total after SAVE10\t180.00\t160.00\tfail\tevidence/C1-call1.json\t\n2026-10-08T10:00:06+07:00\tC2\tcart total after SAVE10\t50.00\t50.00\tpass\tevidence/C2-call2.json\t\n' > "$R/results.tsv"
printf 'time\tphase\ttarget\tfingerprint\n2026-10-08T09:59:00+07:00\tstart\thttp://staging.example.test/version\tsha256:aaaa\n2026-10-08T10:01:00+07:00\tend\thttp://staging.example.test/version\tsha256:aaaa\n' > "$R/build.tsv"
git init -q && git add . && git -c user.email=e@example.com -c user.name=e commit -qm init
