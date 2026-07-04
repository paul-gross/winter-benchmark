"""Fake host — a scripted, zero-token agent for harness self-tests.

Not an experimental condition: `--host fake` exists so the full runner loop
(reset → launch → capture → grade → judge → emit) can be exercised without
spending model quota, and so runner changes are testable deterministically.
The script receives the agent workdir as cwd and the prompt on stdin, does
whatever a scripted 'agent' should (e.g. apply a reference patch and commit),
and prints its final message to stdout.

Select the script with BENCH_FAKE_SCRIPT=/path/to/script.sh; without it, the
fake host completes having done nothing (a guaranteed not_achieved run).
"""

from __future__ import annotations

import json
import os
import subprocess
import time

from hosts.base import HostAdapter, HostRequest, HostResult


class FakeHost(HostAdapter):
    name = "fake"

    def version(self) -> str:
        return "fake-1"

    def run(self, request: HostRequest) -> HostResult:
        transcript = request.out_dir / "transcript.jsonl"
        script = os.environ.get("BENCH_FAKE_SCRIPT")
        started = time.monotonic()
        final_message = "I did nothing."
        stall = "completed"
        exit_code = 0
        events = [{"type": "system", "note": f"fake host; script={script or 'none'}"}]
        if script:
            result = subprocess.run(
                ["bash", script], cwd=request.workdir, input=request.prompt,
                capture_output=True, text=True, timeout=request.max_seconds,
            )
            exit_code = result.returncode
            final_message = result.stdout.strip() or final_message
            events.append({"type": "tool_use", "command": f"bash {script}"})
            events.append({"type": "result", "result": final_message})
            if exit_code != 0:
                stall = "crashed"
        transcript.write_text("\n".join(json.dumps(e) for e in events) + "\n")
        (request.out_dir / "final-message.md").write_text(final_message)
        return HostResult(
            stall_signal=stall,
            final_message=final_message,
            transcript_path=transcript,
            host_version=self.version(),
            exit_code=exit_code,
            efficiency={
                "recorded_not_scored": True,
                "wall_clock_seconds": round(time.monotonic() - started, 1),
                "tokens_input": 0, "tokens_output": 0, "cost_usd": 0.0,
                "commands_executed": 1 if script else 0,
                "failed_commands": 1 if exit_code else 0,
                "retries": 0,
            },
        )
