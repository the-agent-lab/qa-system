import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prepublish_scan import scan_text  # noqa: E402

PHONE = "09" + "12345678"
ID12 = "07" + "9172034747"


class Scan(unittest.TestCase):
    def codes(self, text, deny=()):
        return sorted({c for c, _, _ in scan_text("f", text, list(deny))})

    def test_the_v1_leak_shape_is_caught(self):
        config = '{"credentials": {"username": "%s", "password": "%s"}, "base_url": "https://api.corp-test.internal"}' % (
            PHONE, "test" + "@123!")
        self.assertEqual(self.codes(config, ["corp-test.internal"]), ["S1", "S2", "S4"])

    def test_placeholders_are_not_findings(self):
        for line in ['"password": "***"', 'password: "<your password>"', 'TOKEN="${API_TOKEN}"', '"api_key": "changeme"']:
            self.assertEqual(self.codes(line), [], line)

    def test_national_id_shape(self):
        self.assertEqual(self.codes("user " + ID12), ["S3"])

    def test_marked_fake_line_is_skipped(self):
        self.assertEqual(self.codes('"password": "hunter2"  # leakscan: fake'), [])

    def test_version_numbers_and_hashes_are_not_phones(self):
        self.assertEqual(self.codes("version 1.0912345678 sha 0912345678abcdef"), [])


if __name__ == "__main__":
    unittest.main()
