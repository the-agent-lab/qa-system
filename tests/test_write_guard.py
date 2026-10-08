import json
import tempfile
import unittest
from pathlib import Path

from helpers import py


class WriteGuard(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="guard-"))
        (self.project / "qa").mkdir()
        (self.project / "qa" / ".active").write_text("2026-01-01-x\n")

    def guard(self, command, hosts="staging.example.com,localhost:3000", active=True):
        if not active:
            (self.project / "qa" / ".active").unlink()
        event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(self.project)}
        return py("hooks/write_guard.py", stdin=json.dumps(event),
                  env={"CLAUDE_PROJECT_DIR": str(self.project), "CLAUDE_PLUGIN_OPTION_TEST_HOSTS": hosts})

    def assertBlocked(self, cmd, **kw):
        r = self.guard(cmd, **kw)
        self.assertEqual(r.returncode, 2, f"should block: {cmd}\n{r.stderr}")

    def assertAllowed(self, cmd, **kw):
        r = self.guard(cmd, **kw)
        self.assertEqual(r.returncode, 0, f"should allow: {cmd}\n{r.stderr}")

    def test_writes_to_other_hosts_are_blocked(self):
        for cmd in ["curl -X POST https://api.example.com/orders -d '{}'",
                    "curl -sS --request=DELETE https://prod.example.com/users/1",
                    "curl https://prod.example.com/login --data 'u=a&p=b'",
                    "curl -XPATCH https://prod.example.com/x",
                    "curl --json '{}' https://prod.example.com/x",
                    "wget --post-data='a=1' https://prod.example.com/x",
                    "http POST https://prod.example.com/x name=a",
                    "TOKEN=1 curl -X PUT https://prod.example.com/x",
                    "cd /tmp && curl -X POST https://prod.example.com/x"]:
            self.assertBlocked(cmd)

    def test_reads_and_test_hosts_are_allowed(self):
        for cmd in ["curl https://prod.example.com/health",
                    "curl -X GET https://prod.example.com/orders",
                    "curl -X POST https://staging.example.com/orders -d '{}'",
                    "curl -X POST http://localhost:3000/api -d '{}'",
                    "python3 skills/run/qa_http.py --method POST --url https://prod.example.com/x",
                    "git commit -m 'curl -X POST https://prod.example.com'",
                    "echo hello"]:
            self.assertAllowed(cmd)

    def test_suffix_is_not_a_match(self):
        self.assertBlocked("curl -X POST https://api.staging.example.com/x -d '{}'")

    def test_port_must_match_when_listed_with_port(self):
        self.assertBlocked("curl -X POST http://localhost:8080/api -d '{}'")

    def test_inactive_run_never_blocks(self):
        self.assertAllowed("curl -X DELETE https://prod.example.com/users/1", active=False)

    def test_no_hosts_configured_blocks_all_writes(self):
        self.assertBlocked("curl -X POST http://localhost:3000/api -d '{}'", hosts="")

    def test_garbage_input_does_not_block(self):
        r = py("hooks/write_guard.py", stdin="not json")
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
