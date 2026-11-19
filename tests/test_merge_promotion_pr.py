"""Exercise the merge helper with the errors from a protected environment repo."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/merge-promotion-pr.sh"
REPOSITORY = "example/preview-envs"
NUMBER = "42"
HEAD = "a" * 40
STATUS = ["api", f"repos/{REPOSITORY}/pulls/{NUMBER}", "--jq", "[.head.sha, .state, .merged] | @tsv"]
MERGE = ["pr", "merge", NUMBER, "--repo", REPOSITORY, "--squash", "--delete-branch", "--match-head-commit", HEAD]

GH = """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

fixture = Path(os.environ["FIXTURE"])
responses = json.loads(fixture.read_text())
args, output, code = responses.pop(0)
assert sys.argv[1:] == args, (sys.argv[1:], args)
fixture.write_text(json.dumps(responses))
print(output, file=sys.stderr if code else sys.stdout)
sys.exit(code)
"""

OPEN = (STATUS, f"{HEAD}\topen\tfalse", 0)
BLOCKED = (MERGE, "the base branch policy prohibits the merge", 1)
REQUIRED = (MERGE, 'Required status check "gate / CI gate" is expected.', 1)
SUCCESS = (MERGE, "Merged", 0)
MERGED = (STATUS, f"{HEAD}\tclosed\ttrue", 0)
CHANGED = (STATUS, f"{'b' * 40}\topen\tfalse", 0)
CLOSED = (STATUS, f"{HEAD}\tclosed\tfalse", 0)
DENIED = (MERGE, "Resource not accessible by integration", 1)

for name, expected_code, responses in (
    ("immediate success", 0, [OPEN, SUCCESS]),
    ("both merge errors while waiting for CI", 0, [OPEN, BLOCKED, OPEN, REQUIRED, OPEN, SUCCESS]),
    ("another run merges the expected head", 0, [OPEN, BLOCKED, MERGED]),
    ("the head changes during the wait", 1, [OPEN, BLOCKED, CHANGED]),
    ("the PR closes without merging", 1, [CLOSED]),
    ("the credential cannot merge", 1, [OPEN, DENIED]),
):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for command, body in (("gh", GH), ("sleep", "#!/bin/sh\nexit 0\n")):
            stub = root / command
            stub.write_text(body)
            stub.chmod(0o755)
        fixture = root / "responses.json"
        fixture.write_text(json.dumps(responses))
        env = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}", FIXTURE=str(fixture))
        result = subprocess.run(["bash", SCRIPT, REPOSITORY, NUMBER, HEAD], env=env,
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == expected_code, (name, result.stdout, result.stderr)
        assert not json.loads(fixture.read_text()), (name, result.stdout, result.stderr)
        assert "Traceback" not in result.stderr, (name, result.stderr)
        print("PASS:", name)
