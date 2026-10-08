import unittest

from helpers import GOOD_PLAN, RunFolder, py


def rules(out: str) -> list[str]:
    return [l.split()[1] for l in out.splitlines() if l.startswith(("ERROR", "WARNING"))]


class CheckPlan(unittest.TestCase):
    def check(self, plan: str):
        f = RunFolder(plan)
        try:
            return py("skills/plan/check_plan.py", str(f.run))
        finally:
            f.close()

    def test_good_plan_passes(self):
        r = self.check(GOOD_PLAN)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("2 requirements, 2 cases, 0 errors", r.stdout)

    def test_oracle_that_is_the_code_is_rejected(self):
        r = self.check(GOOD_PLAN.replace("| SHOP-12 acceptance 1 |", "| current behaviour |"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("P4", rules(r.stdout))

    def test_oracle_mentioning_code_inside_a_real_source_is_fine(self):
        r = self.check(GOOD_PLAN.replace("| SHOP-12 acceptance 1 |", "| SHOP-12 acceptance 1, promo code rules |"))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_uncovered_requirement_is_an_error(self):
        r = self.check(GOOD_PLAN.replace("- R2: an expired code", "- R3: refunds keep the discount\n- R2: an expired code"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("R3: no case covers this requirement", r.stdout)

    def test_case_covering_unknown_requirement(self):
        r = self.check(GOOD_PLAN.replace("| C2 | R2 |", "| C2 | R9 |"))
        self.assertIn("covers R9, which is not in the requirements list", r.stdout)

    def test_placeholder_left_in(self):
        r = self.check(GOOD_PLAN.replace("| total 180.00 |", "| <observable outcome> |"))
        self.assertIn("P3", rules(r.stdout))

    def test_pending_oracle_is_a_warning_not_an_error(self):
        r = self.check(GOOD_PLAN.replace("| SHOP-12 acceptance 2 |", "| pending: ask PO whether 422 or 400 |"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("P9", rules(r.stdout))

    def test_duplicate_ids_and_missing_exit_criteria(self):
        plan = GOOD_PLAN.replace("| C2 | R2 |", "| C1 | R2 |").split("## Exit criteria")[0]
        r = self.check(plan)
        self.assertIn("P5", rules(r.stdout))
        self.assertIn("P8", rules(r.stdout))

    def test_missing_column(self):
        r = self.check(GOOD_PLAN.replace("| Oracle |", "| Notes |"))
        self.assertIn("P0", rules(r.stdout))


class NewRun(unittest.TestCase):
    def test_open_and_close(self):
        import tempfile
        from pathlib import Path
        d = Path(tempfile.mkdtemp())
        r = py("skills/plan/new_run.py", "--root", str(d / "qa"), "--name", "Checkout: discount codes!")
        self.assertEqual(r.returncode, 0, r.stderr)
        active = (d / "qa" / ".active").read_text().strip()
        self.assertTrue(active.endswith("-checkout-discount-codes"))
        self.assertTrue((d / "qa" / active / "CASES.md").exists())
        py("skills/plan/new_run.py", "--root", str(d / "qa"), "--close")
        self.assertFalse((d / "qa" / ".active").exists())


if __name__ == "__main__":
    unittest.main()
