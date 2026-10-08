import unittest

import qa_core as q
from helpers import RunFolder, py


class Report(unittest.TestCase):
    def setUp(self):
        self.f = RunFolder()

    def tearDown(self):
        self.f.close()

    def result(self, case, verdict, evidence=None, actual="x", expected="x", note=""):
        ev = evidence if evidence is not None else self.f.evidence(f"{case}-{verdict}.txt")
        q.append_row(self.f.run / "results.tsv", q.RESULT_FIELDS, {"time": q.now(), "case": case, "check": "c",
                     "expected": expected, "actual": actual, "verdict": verdict, "evidence": ev, "note": note})

    def build(self, start, end):
        for phase, fp in (("start", start), ("end", end)):
            if fp:
                q.append_row(self.f.run / "build.tsv", q.BUILD_FIELDS,
                             {"time": q.now(), "phase": phase, "target": "http://x/v", "fingerprint": fp})

    def report(self):
        r = py("skills/report/report.py", str(self.f.run))
        return r, (self.f.run / "report.md").read_text()

    def test_all_pass_on_stable_build_is_pass(self):
        self.result("C1", "pass")
        self.result("C2", "pass")
        self.build("a", "a")
        r, text = self.report()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("Verdict: **PASS**", text)

    def test_suspected_bug_is_fail(self):
        self.result("C1", "fail", actual="200.00", expected="180.00")
        self.result("C2", "pass")
        self.build("a", "a")
        _, text = self.report()
        self.assertIn("Verdict: **FAIL**", text)
        self.assertIn("Suspected product bugs (1)", text)

    def test_build_change_makes_it_inconclusive_but_keeps_the_bug(self):
        self.result("C1", "fail", actual="200.00", expected="180.00")
        self.result("C2", "pass")
        self.build("a", "b")
        _, text = self.report()
        self.assertIn("Verdict: **INCONCLUSIVE**", text)
        self.assertIn("build changed", text)
        self.assertIn("1 suspected product bug(s) found anyway", text)

    def test_case_without_result_cannot_pass(self):
        self.result("C1", "pass")
        self.build("a", "a")
        _, text = self.report()
        self.assertIn("Verdict: **INCONCLUSIVE**", text)
        self.assertIn("| C2 | no result recorded |", text)

    def test_server_error_is_environment_not_bug(self):
        ev = self.f.evidence("C1-call1.json", "{}")
        q.append_row(self.f.run / "calls.tsv", q.CALL_FIELDS, {"n": 1, "time": q.now(), "case": "C1", "method": "GET",
                     "url": "http://x", "status": 502, "ms": 5, "evidence": ev, "command": "curl"})
        self.result("C1", "fail", evidence=ev, actual="502", expected="200")
        self.result("C2", "pass")
        self.build("a", "a")
        _, text = self.report()
        self.assertIn("Environment problems (1)", text)
        self.assertNotIn("Suspected product bugs", text)
        self.assertIn("INCONCLUSIVE", text)

    def test_missing_evidence_is_broken_check(self):
        self.result("C1", "fail", evidence="evidence/gone.txt")
        self.result("C2", "pass")
        self.build("a", "a")
        _, text = self.report()
        self.assertIn("Broken checks (1)", text)

    def test_note_marks_intended_change(self):
        self.result("C1", "fail", actual="200.00", expected="180.00")
        self.result("C2", "pass")
        self.build("a", "a")
        (self.f.run / "notes.tsv").write_text("case\tclass\treason\nC1\tintended-change\tPO said discount moved to 0%\n")
        _, text = self.report()
        self.assertIn("Intended changes (1)", text)

    def test_note_without_reason_is_ignored(self):
        self.result("C1", "fail", actual="200.00", expected="180.00")
        self.result("C2", "pass")
        self.build("a", "a")
        (self.f.run / "notes.tsv").write_text("case\tclass\treason\nC1\tintended-change\t \n")
        _, text = self.report()
        self.assertIn("Suspected product bugs (1)", text)

    def test_check_rejects_fix_lines_and_dead_evidence(self):
        self.result("C1", "pass")
        self.result("C2", "pass")
        self.build("a", "a")
        self.report()
        p = self.f.run / "report.md"
        p.write_text(p.read_text() + "\nSuggested fix: change the multiplier\n\n[proof](evidence/nope.txt)\n")
        r = py("skills/report/report.py", str(self.f.run), "--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("K2", r.stdout)
        self.assertIn("K3", r.stdout)


if __name__ == "__main__":
    unittest.main()
