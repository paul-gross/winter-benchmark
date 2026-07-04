"""Claude Code host adapter — headless `claude -p` with stream-json capture.

Unattended posture: --dangerously-skip-permissions inside the sandbox (the
same consistently automated approval for every cell — a non-engineering
intervention per the protocol). Subscription-billed; cost fields may be null.
"""

from __future__ import annotations

import json
import os
import subprocess
import time

from hosts.base import HostAdapter, HostRequest, HostResult


class ClaudeCodeHost(HostAdapter):
    name = "claude"

    def version(self) -> str:
        result = subprocess.run(["claude", "--version"], capture_output=True, text=True)
        return result.stdout.strip() or "unknown"

    def run(self, request: HostRequest) -> HostResult:
        transcript = request.out_dir / "transcript.jsonl"
        cmd = [
            "claude", "-p", request.prompt,
            "--model", request.model,
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ]
        env = dict(os.environ)
        started = time.monotonic()
        stall = "completed"
        exit_code: int | None = None
        try:
            with open(transcript, "w") as sink:
                proc = subprocess.Popen(
                    cmd, cwd=request.workdir, env=env,
                    stdout=sink, stderr=subprocess.STDOUT, text=True,
                    start_new_session=True,
                )
                exit_code = proc.wait(timeout=request.max_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(30)
            stall = "boundary"
        wall = time.monotonic() - started

        final_message = ""
        efficiency = {
            "recorded_not_scored": True,
            "wall_clock_seconds": round(wall, 1),
            "tokens_input": None, "tokens_output": None, "cost_usd": None,
            "commands_executed": None, "failed_commands": None, "retries": None,
        }
        commands = failed = 0
        if transcript.exists():
            for line in transcript.read_text(errors="replace").splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "result":
                    final_message = event.get("result") or final_message
                    usage = event.get("usage") or {}
                    efficiency["tokens_input"] = usage.get("input_tokens")
                    efficiency["tokens_output"] = usage.get("output_tokens")
                    efficiency["cost_usd"] = event.get("total_cost_usd")
                    if event.get("is_error"):
                        stall = "crashed" if stall == "completed" else stall
                elif event.get("type") == "assistant":
                    for block in (event.get("message") or {}).get("content", []):
                        if block.get("type") == "tool_use":
                            commands += 1
                elif event.get("type") == "user":
                    content = (event.get("message") or {}).get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if block.get("type") == "tool_result" and block.get("is_error"):
                                failed += 1
        efficiency["commands_executed"] = commands
        efficiency["failed_commands"] = failed

        if stall == "completed" and exit_code not in (0, None):
            stall = "crashed"

        (request.out_dir / "final-message.md").write_text(final_message)
        return HostResult(
            stall_signal=stall,
            final_message=final_message,
            transcript_path=transcript,
            host_version=self.version(),
            exit_code=exit_code,
            efficiency=efficiency,
        )
