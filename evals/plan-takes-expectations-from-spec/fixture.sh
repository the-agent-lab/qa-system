#!/bin/bash
set -e
cat > SPEC.md <<'MD'
# Discount codes

- R1. Code SAVE10 takes 10% off a cart of 100.00 or more. A 200.00 cart costs 180.00 after the code.
- R2. An expired code (for example OLD5) is rejected, and the cart total does not change.
MD
mkdir -p app
cat > app/discount.py <<'PY'
EXPIRED = {"OLD5"}


def apply_code(total, code):
    if code in EXPIRED:
        return 400, {"error": "invalid"}
    if code == "SAVE10" and total >= 100:
        return 200, {"total": round(total * 0.8, 2)}
    return 200, {"total": total}
PY
git init -q && git add . && git -c user.email=e@example.com -c user.name=e commit -qm init
