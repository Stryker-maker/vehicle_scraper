import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collector_execution import execute_collector


class CollectorExecutionTests(unittest.TestCase):
    def test_success_preserves_command_timeout_environment_and_output(self):
        command = ["python", "collector.py"]
        with tempfile.TemporaryDirectory() as temp, patch(
            "collector_execution.subprocess.run",
            return_value=subprocess.CompletedProcess(command, 0, "collected\n", "warning\n"),
        ) as run, patch("collector_execution.sys.stdout", new_callable=io.StringIO) as stdout, patch(
            "collector_execution.sys.stderr", new_callable=io.StringIO
        ) as stderr:
            result = execute_collector(command, root=Path(temp), timeout_seconds=91.5)

        self.assertEqual(result, (0, False, "collected\n", "warning\n"))
        kwargs = run.call_args.kwargs
        self.assertEqual(run.call_args.args, (command,))
        self.assertEqual(kwargs["cwd"], Path(temp))
        self.assertIs(kwargs["text"], True)
        self.assertIs(kwargs["capture_output"], True)
        self.assertIs(kwargs["check"], False)
        self.assertEqual(kwargs["timeout"], 91.5)
        self.assertEqual(kwargs["env"], os.environ.copy())
        self.assertEqual(stdout.getvalue(), "collected\n")
        self.assertEqual(stderr.getvalue(), "warning\n")

    def test_timeout_preserves_partial_bytes_and_logs_only_last_4000_characters(self):
        command = ["python", "collector.py"]
        partial_stdout = ("x" * 4001 + "tail\n").encode()
        partial_stderr = b"partial error\n"
        timeout = subprocess.TimeoutExpired(
            command, 7.25, output=partial_stdout, stderr=partial_stderr
        )
        with tempfile.TemporaryDirectory() as temp, patch(
            "collector_execution.subprocess.run", side_effect=timeout
        ) as run, patch("collector_execution.sys.stdout", new_callable=io.StringIO) as stdout, patch(
            "collector_execution.sys.stderr", new_callable=io.StringIO
        ) as stderr:
            result = execute_collector(command, root=Path(temp), timeout_seconds=7.25)

        expected_stdout = partial_stdout.decode("utf-8", errors="replace")
        expected_stderr = partial_stderr.decode("utf-8", errors="replace")
        self.assertEqual(result, (None, True, expected_stdout, expected_stderr))
        self.assertEqual(run.call_args.kwargs["timeout"], 7.25)
        self.assertEqual(stdout.getvalue(), expected_stdout[-4000:])
        self.assertEqual(stderr.getvalue(), expected_stderr)

    def test_timeout_accepts_text_partial_output(self):
        command = ["python", "collector.py"]
        timeout = subprocess.TimeoutExpired(
            command, 3, output="partial stdout", stderr="partial stderr"
        )
        with tempfile.TemporaryDirectory() as temp, patch(
            "collector_execution.subprocess.run", side_effect=timeout
        ), patch("collector_execution.sys.stdout", new_callable=io.StringIO), patch(
            "collector_execution.sys.stderr", new_callable=io.StringIO
        ):
            result = execute_collector(command, root=Path(temp), timeout_seconds=3)
        self.assertEqual(result, (None, True, "partial stdout", "partial stderr"))


if __name__ == "__main__":
    unittest.main()
