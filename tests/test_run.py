import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import qa_core as q
from helpers import RunFolder, py


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("ETag", '"v1"')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/boom":
            return self._reply(502, {"error": "upstream"})
        self._reply(200, {"total": "180.00", "path": self.path})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self._reply(201, {"echo": json.loads(self.rfile.read(n) or b"{}")})


class HttpWrapper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        self.f = RunFolder()

    def tearDown(self):
        self.f.close()

    def url(self, path="/api"):
        return f"http://127.0.0.1:{self.port}{path}"

    def test_get_is_logged_with_evidence_and_verdict(self):
        r = py("skills/run/qa_http.py", "--run", str(self.f.run), "--case", "C1", "--url", self.url(),
               "--expect-status", "200")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = q.read_rows(self.f.run / "calls.tsv")
        self.assertEqual(calls[0]["status"], "200")
        self.assertTrue((self.f.run / calls[0]["evidence"]).is_file())
        res = q.read_rows(self.f.run / "results.tsv")
        self.assertEqual(res[0]["verdict"], "pass")

    def test_write_to_unlisted_host_is_refused_and_not_sent(self):
        r = py("skills/run/qa_http.py", "--run", str(self.f.run), "--case", "C2", "--method", "POST",
               "--url", self.url(), "--hosts", "staging.example.com", "--data", "{}")
        self.assertEqual(r.returncode, 3)
        self.assertIn("REFUSED", r.stdout)
        self.assertEqual(q.read_rows(self.f.run / "calls.tsv"), [])

    def test_write_to_listed_host_with_port_goes_through(self):
        r = py("skills/run/qa_http.py", "--run", str(self.f.run), "--case", "C2", "--method", "POST",
               "--url", self.url(), "--hosts", f"127.0.0.1:{self.port}", "--data", '{"qty": 2}',
               "--expect-status", "201")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(q.read_rows(self.f.run / "results.tsv")[0]["verdict"], "pass")

    def test_secrets_are_masked_in_log_and_output(self):
        r = py("skills/run/qa_http.py", "--run", str(self.f.run), "--case", "C1", "--method", "POST",
               "--url", self.url("/login?token=abc123"), "--hosts", "127.0.0.1",
               "--header", "Authorization: Bearer s3cr3t", "--data", '{"user": "qa-user", "password": "hunter2"}')  # leakscan: fake
        log = (self.f.run / "calls.tsv").read_text()
        for secret in ("s3cr3t", "hunter2", "abc123"):
            self.assertNotIn(secret, log)
            self.assertNotIn(secret, r.stdout)

    def test_login_token_goes_to_a_private_file_not_the_log(self):
        import os, stat
        r = py("skills/run/qa_http.py", "--run", str(self.f.run), "--case", "C1", "--method", "POST",
               "--url", self.url("/login"), "--hosts", "127.0.0.1", "--data", '{"data": {"access_token": "tok-xyz"}}',  # leakscan: fake
               "--token-key", "access_token")
        self.assertEqual(r.returncode, 0, r.stdout)
        tok = self.f.run / ".token"
        self.assertEqual(tok.read_text(), "tok-xyz")
        self.assertEqual(stat.S_IMODE(os.stat(tok).st_mode), 0o600)
        ev = (self.f.run / q.read_rows(self.f.run / "calls.tsv")[0]["evidence"]).read_text()
        self.assertNotIn("tok-xyz", ev)
        self.assertNotIn("tok-xyz", r.stdout)

    def test_no_response_is_blocked_not_fail(self):
        r = py("skills/run/qa_http.py", "--run", str(self.f.run), "--case", "C1", "--url", "http://127.0.0.1:1/x",
               "--expect-status", "200", "--timeout", "2")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(q.read_rows(self.f.run / "results.tsv")[0]["verdict"], "blocked")


class Record(unittest.TestCase):
    def setUp(self):
        self.f = RunFolder()

    def tearDown(self):
        self.f.close()

    def rec(self, *extra):
        return py("skills/run/record.py", "--run", str(self.f.run), "--case", "C1", "--check", "total",
                  "--expected", "180.00", *extra)

    def test_no_evidence_no_verdict(self):
        r = self.rec("--actual", "180.00", "--evidence", "evidence/missing.txt")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(q.read_rows(self.f.run / "results.tsv"), [])

    def test_equal_values_pass_and_different_values_fail(self):
        ev = self.f.evidence("c1.txt")
        self.rec("--actual", " 180.00 ", "--evidence", ev)
        self.rec("--actual", "200.00", "--evidence", ev)
        self.assertEqual([r["verdict"] for r in q.read_rows(self.f.run / "results.tsv")], ["pass", "fail"])

    def test_overriding_the_comparison_needs_a_reason(self):
        ev = self.f.evidence("c1.txt")
        self.assertEqual(self.rec("--actual", "180.0", "--evidence", ev, "--verdict", "pass").returncode, 2)
        self.assertEqual(self.rec("--actual", "180.0", "--evidence", ev, "--verdict", "pass",
                                  "--note", "numeric comparison").returncode, 0)


class PinBuild(unittest.TestCase):
    def test_command_fingerprint(self):
        f = RunFolder()
        try:
            r = py("skills/run/pin_build.py", "--run", str(f.run), "--phase", "start", "--command", "echo v1")
            self.assertEqual(r.returncode, 0, r.stdout)
            row = q.read_rows(f.run / "build.tsv")[0]
            self.assertTrue(row["fingerprint"].startswith("sha256:"))
        finally:
            f.close()


if __name__ == "__main__":
    unittest.main()
