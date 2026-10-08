import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import py

BUGGY = "def discount(total):\n    return total * 0.8\n"
FIXED = "def discount(total):\n    return total * 0.9\n"
TEST = "from pricing import discount\n\ndef test_ten_percent():\n    assert discount(200) == 180\n"
WEAK_TEST = "from pricing import discount\n\ndef test_returns_number():\n    assert discount(200) > 0\n"


def git(d, *a):
    subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)


class RedFirst(unittest.TestCase):
    def repo(self, test_body: str, fixed: str = FIXED) -> Path:
        d = Path(tempfile.mkdtemp(prefix="red-first-test-"))
        git(d, "init", "-q", "-b", "main")
        git(d, "config", "user.email", "t@example.com")
        git(d, "config", "user.name", "t")
        (d / "pricing.py").write_text(BUGGY)
        git(d, "add", ".")
        git(d, "commit", "-qm", "buggy")
        (d / "pricing.py").write_text(fixed)
        (d / "tests").mkdir()
        (d / "tests" / "test_pricing.py").write_text(test_body)
        return d

    def run_it(self, d: Path):
        cmd = f'{sys.executable} -m pytest -q tests' if self.has_pytest else \
            f'{sys.executable} -c "import sys; sys.path.insert(0, \'.\'); sys.path.insert(0, \'tests\'); ' \
            f'import test_pricing as t; [getattr(t, n)() for n in dir(t) if n.startswith(\'test_\')]"'
        return py("skills/red-first/red_first.py", "--repo", str(d), "--base", "main", "--test", cmd)

    @classmethod
    def setUpClass(cls):
        cls.has_pytest = subprocess.run([sys.executable, "-c", "import pytest"], capture_output=True).returncode == 0

    def test_real_regression_test_is_red_then_green(self):
        r = self.run_it(self.repo(TEST))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("RED-THEN-GREEN", r.stdout)

    def test_weak_test_is_not_red(self):
        r = self.run_it(self.repo(WEAK_TEST))
        self.assertEqual(r.returncode, 1)
        self.assertIn("NOT-RED", r.stdout)

    def test_failing_on_import_is_wrong_red(self):
        t = "from pricing import discount, new_helper\n\ndef test_x():\n    assert new_helper(200) == 180\n"
        fixed = FIXED + "\ndef new_helper(t):\n    return discount(t)\n"
        r = self.run_it(self.repo(t, fixed))
        self.assertEqual(r.returncode, 1)
        self.assertIn("WRONG-RED", r.stdout)

    def test_worktree_is_cleaned_up(self):
        d = self.repo(TEST)
        self.run_it(d)
        out = subprocess.run(["git", "-C", str(d), "worktree", "list"], capture_output=True, text=True).stdout
        self.assertEqual(len(out.strip().splitlines()), 1, out)


if __name__ == "__main__":
    unittest.main()
